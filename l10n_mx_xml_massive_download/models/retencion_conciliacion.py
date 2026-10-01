# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo | License OPL-1
"""Conciliacion de Impuestos Retenidos: SAT (flujo) vs Odoo (libros).

El SAT prellena las retenciones por pagar de un periodo integrando los CFDIs
RECIBIDOS efectivamente pagados:
  - PUE: se considera pagado en el mes de emision (fecha de documento).
  - PPD: se considera pagado en la FechaPago del complemento de pago (REP),
         NO en la fecha de timbrado del REP (un REP timbrado en mayo puede
         documentar un pago de febrero -> cuenta en febrero); en parcialidades,
         la retencion se reconoce PROPORCIONAL al monto pagado en el periodo.

Este wizard reproduce ese calculo desde los XML descargados (tax_isr_ret /
tax_iva_ret ya parseados) y lo compara contra la retencion registrada en la
poliza de Odoo (tax lines de la factura ligada), a nivel UUID, mostrando la
diferencia y en que poliza esta.
"""
import base64
import io
import logging

from lxml import etree

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PAGO_NS = (
    'http://www.sat.gob.mx/Pagos20',  # CFDI 4.0
    'http://www.sat.gob.mx/Pagos',    # CFDI 3.3
)


class RetencionConciliacionWizard(models.TransientModel):
    _name = 'l10n_mx.retencion.conciliacion.wizard'
    _description = 'Conciliacion de Impuestos Retenidos SAT vs Odoo'

    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda s: s.env.company)
    date_from = fields.Date(
        string='Periodo Desde', required=True,
        default=lambda s: fields.Date.context_today(s).replace(day=1))
    date_to = fields.Date(
        string='Periodo Hasta', required=True,
        default=lambda s: fields.Date.context_today(s))
    line_ids = fields.One2many(
        'l10n_mx.retencion.conciliacion.line', 'wizard_id', string='Detalle')
    generado = fields.Boolean(default=False)

    # Totales
    total_isr_sat = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    total_iva_sat = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    total_isr_odoo = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    total_iva_odoo = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    total_diff_isr = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    total_diff_iva = fields.Monetary(compute='_compute_totals', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_currency')

    xlsx_file = fields.Binary(string='Excel', readonly=True)
    xlsx_name = fields.Char(string='Nombre Excel', readonly=True)

    @api.depends('company_id')
    def _compute_currency(self):
        for w in self:
            w.currency_id = w.company_id.currency_id

    @api.depends('line_ids.isr_ret_sat', 'line_ids.iva_ret_sat',
                 'line_ids.isr_ret_odoo', 'line_ids.iva_ret_odoo')
    def _compute_totals(self):
        for w in self:
            w.total_isr_sat = sum(w.line_ids.mapped('isr_ret_sat'))
            w.total_iva_sat = sum(w.line_ids.mapped('iva_ret_sat'))
            w.total_isr_odoo = sum(w.line_ids.mapped('isr_ret_odoo'))
            w.total_iva_odoo = sum(w.line_ids.mapped('iva_ret_odoo'))
            w.total_diff_isr = w.total_isr_sat - w.total_isr_odoo
            w.total_diff_iva = w.total_iva_sat - w.total_iva_odoo

    @api.onchange('date_from')
    def _onchange_date_from(self):
        """Al fijar la fecha de inicio, sugiere automaticamente el ULTIMO dia de
        ese mes como fin (editable: el usuario puede cambiarlo despues)."""
        if self.date_from:
            import calendar
            last_day = calendar.monthrange(self.date_from.year, self.date_from.month)[1]
            self.date_to = self.date_from.replace(day=last_day)

    # ------------------------------------------------------------------ logica
    def _build_rep_map(self):
        """Parsea los REP (complementos de pago) RECIBIDOS y devuelve
        {uuid_factura_pagada (lower): [{date, imp}, ...]} considerando SOLO los
        pagos cuya FechaPago cae en el periodo.

        IMPORTANTE (fiscal): la fecha de pago es la **FechaPago** del nodo
        <Pago> del complemento, NO la fecha de timbrado/emision del REP. Un REP
        timbrado en mayo puede documentar un pago de febrero -> esa retencion
        cuenta en FEBRERO (cuando se pago), no en mayo. Como la emision del REP
        siempre es >= FechaPago, se buscan REP con document_date >= date_from
        SIN tope superior (para no perder los timbrados tarde) y luego se filtra
        cada Pago por su FechaPago real. Un mismo REP puede traer varios Pago con
        fechas distintas; cada uno se evalua por separado.
        imp = ImpPagado del DoctoRelacionado (monto pagado de esa factura)."""
        self.ensure_one()
        reps = self.env['account.edi.downloaded.xml.sat'].search([
            ('company_id', '=', self.company_id.id),
            ('cfdi_type', '=', 'recibidos'),
            ('document_type', '=', 'P'),
            ('document_date', '>=', self.date_from),
        ])
        rep_map = {}
        for rep in reps:
            att = rep.attachment_id.filtered(
                lambda a: (a.mimetype or '').endswith('xml')
                or (a.name or '').lower().endswith('.xml')) or rep.attachment_id[:1]
            if not att or not att[:1].datas:
                continue
            raw = base64.b64decode(att[:1].datas)
            root = None
            for attempt in (raw, raw.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation')):
                try:
                    root = etree.fromstring(attempt)
                    break
                except etree.XMLSyntaxError:
                    continue
            if root is None:
                continue
            for ns_uri in PAGO_NS:
                for pago in root.iter('{%s}Pago' % ns_uri):
                    fp = (pago.get('FechaPago') or '')[:10]
                    try:
                        fpago = fields.Date.to_date(fp) if fp else None
                    except (ValueError, TypeError):
                        fpago = None
                    # Solo cuenta si la FechaPago REAL cae dentro del periodo.
                    if not (fpago and self.date_from <= fpago <= self.date_to):
                        continue
                    for docto in pago.iter('{%s}DoctoRelacionado' % ns_uri):
                        idd = (docto.get('IdDocumento') or '').strip().lower()
                        if not idd:
                            continue
                        try:
                            imp = float(docto.get('ImpPagado') or 0.0)
                        except (TypeError, ValueError):
                            imp = 0.0
                        rep_map.setdefault(idd, []).append(
                            {'date': fpago, 'imp': imp})
        return rep_map

    @staticmethod
    def _odoo_retention(move):
        """Suma las retenciones (ISR/IVA) registradas en las tax lines de la
        poliza. Devuelve (isr_ret, iva_ret) en positivo."""
        isr = iva = 0.0
        if not move:
            return 0.0, 0.0
        # _classify_tax_line es @staticmethod de account.edi.downloaded.xml.sat
        # (NO de account.move.line): clasifica una tax line en isr_ret/iva_ret/etc.
        XS = move.env['account.edi.downloaded.xml.sat']
        for line in move.line_ids.filtered(lambda l: l.display_type == 'tax'):
            kind = XS._classify_tax_line(line)
            if kind == 'isr_ret':
                isr += abs(line.balance)
            elif kind == 'iva_ret':
                iva += abs(line.balance)
        return isr, iva

    def action_generar(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('El "Desde" no puede ser mayor al "Hasta".'))
        self.line_ids.unlink()
        XML = self.env['account.edi.downloaded.xml.sat']
        base = XML.search([
            ('company_id', '=', self.company_id.id),
            ('cfdi_type', '=', 'recibidos'),
            ('document_type', 'in', ('I', 'E')),
            ('sat_state', 'in', ('Vigente', 'Sin Definir')),
            '|', ('tax_isr_ret', '>', 0.0), ('tax_iva_ret', '>', 0.0),
        ])
        rep_map = self._build_rep_map()
        # Catalogo regimen fiscal (clave -> nombre) para mostrar "626 - Regimen ...".
        regime_sel = dict(XML._fields['tax_regime']._description_selection(self.env))
        vals_list = []
        for x in base:
            isr_total = x.tax_isr_ret or 0.0
            iva_total = x.tax_iva_ret or 0.0
            metodo = x.payment_method or 'PUE'
            if metodo == 'PUE':
                # Pagado en el mes de emision -> entra si la fecha cae en el periodo.
                if not (x.document_date and self.date_from <= x.document_date <= self.date_to):
                    continue
                proporcion = 1.0
                fecha_pago = x.document_date
            else:  # PPD -> entra por los REP del periodo, proporcional a lo pagado.
                reps = rep_map.get((x.name or '').lower(), [])
                if not reps:
                    continue
                pagado = sum(r['imp'] for r in reps)
                total = x.amount_total or 0.0
                proporcion = min(1.0, pagado / total) if total else 1.0
                fecha_pago = max(r['date'] for r in reps)
            isr_sat = isr_total * proporcion
            iva_sat = iva_total * proporcion
            subtotal = (x.sub_total or 0.0) * proporcion  # importe que se fue a gastos
            isr_odoo_full, iva_odoo_full = self._odoo_retention(x.invoice_id)
            isr_odoo = isr_odoo_full * proporcion
            iva_odoo = iva_odoo_full * proporcion
            reg_key = x.tax_regime or ''
            reg_disp = ('%s - %s' % (reg_key, regime_sel.get(reg_key, ''))).strip(' -') if reg_key else ''
            # Tolerancia: diferencias < $1.00 (redondeo) se consideran dentro de tolerancia.
            if not x.invoice_id:
                estado = 'no_odoo'
            elif (abs(isr_sat - isr_odoo) < 1.00 and abs(iva_sat - iva_odoo) < 1.00):
                estado = 'cuadra'
            else:
                estado = 'difiere'
            vals_list.append({
                'wizard_id': self.id,
                'currency_id': self.company_id.currency_id.id,
                'xml_sat_id': x.id,
                'uuid': x.name,
                'partner_id': x.partner_id.id,
                'tax_regime': reg_disp,
                'document_date': x.document_date,
                'payment_method': metodo,
                'payment_date': fecha_pago,
                'proporcion': proporcion,
                'subtotal': subtotal,
                'isr_ret_sat': isr_sat,
                'iva_ret_sat': iva_sat,
                'isr_ret_odoo': isr_odoo,
                'iva_ret_odoo': iva_odoo,
                'move_id': x.invoice_id.id if x.invoice_id else False,
                'estado': estado,
            })
        if vals_list:
            self.env['l10n_mx.retencion.conciliacion.line'].create(vals_list)
        self.generado = True
        if not vals_list:
            raise UserError(_(
                'No se encontraron CFDIs con retencion efectivamente pagados en el '
                'periodo %s a %s.') % (self.date_from, self.date_to))
        # Resultado en ventana COMPLETA, agrupado por regimen (de lo general a lo
        # particular): grupos colapsados con sus grandes totales -> click expande al
        # detalle por UUID. Misma logica que un reporte de impuestos nativo de Odoo.
        return {
            'type': 'ir.actions.act_window',
            'name': _('Impuestos Retenidos %s a %s') % (self.date_from, self.date_to),
            'res_model': 'l10n_mx.retencion.conciliacion.line',
            'domain': [('wizard_id', '=', self.id)],
            'view_mode': 'list',
            'views': [(self.env.ref(
                'l10n_mx_xml_massive_download.view_retencion_conciliacion_line_list').id, 'list')],
            'search_view_id': [self.env.ref(
                'l10n_mx_xml_massive_download.view_retencion_conciliacion_line_search').id],
            'context': {'search_default_group_regimen': 1, 'wizard_id_export': self.id},
            'target': 'current',
        }

    def action_export_excel(self):
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('No esta disponible xlsxwriter en el servidor.'))
        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out, {'in_memory': True})
        ws = wb.add_worksheet('Impuestos Retenidos')
        bold = wb.add_format({'bold': True})
        money = wb.add_format({'num_format': '#,##0.00'})
        head = wb.add_format({'bold': True, 'bg_color': '#05518e', 'font_color': 'white'})
        ws.write(0, 0, 'Conciliacion Impuestos Retenidos SAT vs Odoo', bold)
        ws.write(1, 0, 'Empresa: %s   Periodo: %s a %s' % (
            self.company_id.name, self.date_from, self.date_to))
        money_b = wb.add_format({'bold': True, 'num_format': '#,##0.00'})
        pct = wb.add_format({'num_format': '0.0%'})
        headers = ['UUID', 'Proveedor', 'Regimen', 'Fecha Doc', 'Metodo',
                   'Fecha Pago', '% Pagado', 'Subtotal (gasto)', 'ISR Ret SAT',
                   'IVA Ret SAT', 'ISR Ret Odoo', 'IVA Ret Odoo', 'Dif ISR',
                   'Dif IVA', 'Poliza', 'Estado']
        r0 = 3
        for c, h in enumerate(headers):
            ws.write(r0, c, h, head)
        r = r0 + 1
        money_cols = {7, 8, 9, 10, 11, 12, 13}  # Subtotal..Dif IVA
        estado_lbl = dict(self.line_ids._fields['estado'].selection) if self.line_ids else {}
        for ln in self.line_ids:
            row = [ln.uuid or '', ln.partner_id.name or '', ln.tax_regime or '',
                   str(ln.document_date or ''), ln.payment_method or '',
                   str(ln.payment_date or ''), ln.proporcion, ln.subtotal,
                   ln.isr_ret_sat, ln.iva_ret_sat, ln.isr_ret_odoo, ln.iva_ret_odoo,
                   ln.diff_isr, ln.diff_iva, ln.move_id.name or '',
                   estado_lbl.get(ln.estado, '')]
            for c, val in enumerate(row):
                if c == 6:
                    ws.write_number(r, c, val, pct)
                elif c in money_cols:
                    ws.write_number(r, c, val, money)
                else:
                    ws.write(r, c, val)
            r += 1
        ws.write(r, 6, 'TOTALES', bold)
        for c, val in ((7, sum(self.line_ids.mapped('subtotal'))),
                       (8, self.total_isr_sat), (9, self.total_iva_sat),
                       (10, self.total_isr_odoo), (11, self.total_iva_odoo),
                       (12, self.total_diff_isr), (13, self.total_diff_iva)):
            ws.write_number(r, c, val, money_b)
        ws.set_column(0, 0, 38)
        ws.set_column(1, 1, 28)
        ws.set_column(2, 2, 32)
        ws.set_column(14, 14, 16)
        wb.close()
        out.seek(0)
        self.xlsx_file = base64.b64encode(out.read())
        self.xlsx_name = 'impuestos_retenidos_%s_%s.xlsx' % (self.date_from, self.date_to)
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/xlsx_file/%s?download=true' % (
                self._name, self.id, self.xlsx_name),
            'target': 'self',
        }


class RetencionConciliacionLine(models.TransientModel):
    _name = 'l10n_mx.retencion.conciliacion.line'
    _description = 'Linea de Conciliacion de Retenciones'
    _order = 'document_date, uuid'

    wizard_id = fields.Many2one(
        'l10n_mx.retencion.conciliacion.wizard', ondelete='cascade', index=True)
    company_id = fields.Many2one(related='wizard_id.company_id')
    # Almacenado (no related) para que las sumas Monetarias se agreguen en los
    # encabezados de grupo (read_group necesita la moneda disponible).
    currency_id = fields.Many2one('res.currency')
    xml_sat_id = fields.Many2one('account.edi.downloaded.xml.sat', string='XML SAT')
    uuid = fields.Char(string='UUID')
    partner_id = fields.Many2one('res.partner', string='Proveedor')
    tax_regime = fields.Char(string='Regimen Emisor')
    document_date = fields.Date(string='Fecha Documento')
    payment_method = fields.Char(string='Metodo')
    payment_date = fields.Date(string='Fecha Pago')
    # aggregator=False: NO sumar el % en los encabezados de grupo (sumar
    # porcentajes no tiene sentido; daria 500% para 5 lineas al 100%).
    proporcion = fields.Float(string='% Pagado', aggregator=False)
    subtotal = fields.Monetary(string='Subtotal (gasto)', currency_field='currency_id')
    isr_ret_sat = fields.Monetary(string='ISR Ret SAT', currency_field='currency_id')
    iva_ret_sat = fields.Monetary(string='IVA Ret SAT', currency_field='currency_id')
    isr_ret_odoo = fields.Monetary(string='ISR Ret Odoo', currency_field='currency_id')
    iva_ret_odoo = fields.Monetary(string='IVA Ret Odoo', currency_field='currency_id')
    # store=True para que se agreguen (sum) en los totales de grupo y general:
    # los computed NO almacenados no se pueden sumar en read_group (nivel SQL).
    diff_isr = fields.Monetary(string='Dif ISR', compute='_compute_diff',
                               currency_field='currency_id', store=True)
    diff_iva = fields.Monetary(string='Dif IVA', compute='_compute_diff',
                               currency_field='currency_id', store=True)
    move_id = fields.Many2one('account.move', string='Poliza')
    estado = fields.Selection([
        ('cuadra', 'Cuadra'),
        ('difiere', 'Difiere'),
        ('no_odoo', 'No en Odoo'),
    ], string='Estado')

    @api.depends('isr_ret_sat', 'iva_ret_sat', 'isr_ret_odoo', 'iva_ret_odoo')
    def _compute_diff(self):
        for ln in self:
            ln.diff_isr = ln.isr_ret_sat - ln.isr_ret_odoo
            ln.diff_iva = ln.iva_ret_sat - ln.iva_ret_odoo

    def action_open_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_('Este XML no tiene poliza relacionada en Odoo.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_xml(self):
        """Abre el XML SAT descargado (de xml_massive_download) de este renglon."""
        self.ensure_one()
        if not self.xml_sat_id:
            raise UserError(_('No hay XML SAT relacionado.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.edi.downloaded.xml.sat',
            'res_id': self.xml_sat_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
