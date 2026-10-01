# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.

from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class SatConciliationReport(models.Model):
    _name = 'sat.conciliation.report'
    _description = 'Reporte de Conciliación SAT vs Odoo'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Secuencia', default=10)
    concepto = fields.Char(string='Concepto')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    sat_xml_ids = fields.Many2many('account.edi.downloaded.xml.sat', string='XMLs del SAT', copy=False)
    odoo_invoice_ids = fields.Many2many('account.move', string='Facturas Odoo', copy=False)
    odoo_payment_ids = fields.Many2many('account.payment', string='Pagos Odoo', copy=False)
    odoo_payslip_ids = fields.Many2many(
        'hr.payslip',
        string='Recibos de Nomina Odoo',
        copy=False,
    )
    odoo_picking_ids = fields.Many2many(
        'stock.picking',
        string='Transferencias Odoo',
        copy=False,
    )
    # UUIDs timbrados encontrados en otras fuentes (e.g. l10n_mx_payroll.uuid.history).
    # Se guarda como CSV para no atar dependencia a modelo que puede no estar instalado.
    odoo_extra_uuids = fields.Char(
        string="UUIDs adicionales encontrados en Odoo",
        copy=False,
    )
    # Formato de visualizacion (afecta los campos amount_*_display).
    # Se guarda en cada registro para que toda la corrida del reporte respete el formato
    # elegido por el usuario, sin recomputar.
    display_unit = fields.Selection(
        [
            ('units', 'Unidades'),
            ('units_no_dec', 'Sin decimales'),
            ('thousands', 'Miles'),
            ('millions', 'Millones'),
        ],
        string="Formato",
        default='units',
    )
    amount_sat_display = fields.Char(string="$ SAT (texto)", compute='_compute_amount_displays')
    amount_odoo_display = fields.Char(string="$ Odoo (texto)", compute='_compute_amount_displays')
    amount_ignored_display = fields.Char(string="$ Ignorados (texto)", compute='_compute_amount_displays')
    diff_amount_display = fields.Char(string="Dif. Importe (texto)", compute='_compute_amount_displays')

    @api.depends('amount_sat', 'amount_odoo', 'amount_ignored', 'diff_amount', 'display_unit')
    def _compute_amount_displays(self):
        for r in self:
            r.amount_sat_display = r._fmt_amount(r.amount_sat)
            r.amount_odoo_display = r._fmt_amount(r.amount_odoo)
            r.amount_ignored_display = r._fmt_amount(r.amount_ignored)
            r.diff_amount_display = r._fmt_amount(r.diff_amount)

    def _fmt_amount(self, value):
        """Formatea un monto segun display_unit del registro."""
        if value is None:
            return ''
        unit = self.display_unit or 'units'
        sign = '-' if value < 0 else ''
        v = abs(value)
        if unit == 'millions':
            return f"{sign}${v/1_000_000:,.2f} M"
        if unit == 'thousands':
            return f"{sign}${v/1_000:,.1f} K"
        if unit == 'units_no_dec':
            return f"{sign}${v:,.0f}"
        # units
        return f"{sign}${v:,.2f}"
    sat_xml_count = fields.Integer(string='# XMLs SAT', compute='_compute_xml_counts')
    odoo_invoice_count = fields.Integer(string='# Facturas Odoo', compute='_compute_xml_counts')
    odoo_payment_count = fields.Integer(string='# Pagos Odoo', compute='_compute_xml_counts')
    display_name_custom = fields.Char(string='Descripción Personalizada')
    start_date = fields.Date(string='Fecha Inicial')
    end_date = fields.Date(string='Fecha Final')
    document_type = fields.Char(string='Tipo de Documento')
    section_type = fields.Selection([
        ('header_emitidos', 'Encabezado Emitidos'),
        ('emitidos_factura', 'Facturas Emitidas'),
        ('emitidos_nc', 'Notas de Crédito Emitidas'),
        ('emitidos_pago', 'Pagos Emitidos'),
        ('emitidos_nomina', 'Recibos de Nómina Emitidos'),
        ('emitidos_traslado', 'Traslados Emitidos'),
        ('ignored_detail', 'Ignorados'),
        ('separator', 'Separador'),
        ('recibidos_factura', 'Facturas Recibidas'),
        ('recibidos_nc', 'Notas de Crédito Recibidas'),
        ('recibidos_pago', 'Pagos Recibidos'),
        ('recibidos_traslado', 'Traslados Recibidos'),
        ('header_recibidos', 'Encabezado Recibidos'),
        ('total_emitidos', 'Total Emitidos'),
        ('total_recibidos', 'Total Recibidos'),
        ('resumen', 'Resumen Ejecutivo'),
    ], string='Tipo de Sección')
    qty_sat = fields.Integer(string='# XML SAT', default=0)
    amount_sat = fields.Monetary(string='$ SAT', currency_field='currency_id', default=0.0)
    qty_odoo = fields.Integer(string='# XML Odoo', default=0)
    amount_odoo = fields.Monetary(string='$ Odoo', currency_field='currency_id', default=0.0)
    qty_ignored = fields.Integer(string='# Ignorados', default=0)
    amount_ignored = fields.Monetary(string='$ Ignorados', currency_field='currency_id', default=0.0)
    diff_qty = fields.Integer(string='Dif. XML', compute='_compute_differences', store=True)
    diff_amount = fields.Monetary(string='Dif. Importe', currency_field='currency_id',
                                  compute='_compute_differences', store=True)
    diff_percentage = fields.Float(string='Dif. %', compute='_compute_differences', store=True, digits='Percentage')
    missing_sat_count = fields.Integer(string='# SAT sin Odoo', compute='_compute_differences', store=True)
    missing_sat_amount = fields.Monetary(string='$ SAT sin Odoo', currency_field='currency_id',
                                         compute='_compute_differences', store=True)
    extra_odoo_count = fields.Integer(string='# Odoo sin SAT', compute='_compute_differences', store=True)
    extra_odoo_amount = fields.Monetary(string='$ Odoo sin SAT', currency_field='currency_id',
                                        compute='_compute_differences', store=True)
    is_header = fields.Boolean(string='Es Encabezado', default=False)
    is_total = fields.Boolean(string='Es Total', default=False)
    is_separator = fields.Boolean(string='Es Separador', default=False)
    is_subtotal = fields.Boolean(string='Es Subtotal', default=False)

    @api.depends('sat_xml_ids', 'odoo_invoice_ids', 'odoo_payment_ids')
    def _compute_xml_counts(self):
        for record in self:
            record.sat_xml_count = len(record.sat_xml_ids)
            record.odoo_invoice_count = len(record.odoo_invoice_ids)
            record.odoo_payment_count = len(record.odoo_payment_ids)

    INVOICE_SECTIONS = ('emitidos_factura', 'emitidos_nc', 'recibidos_factura', 'recibidos_nc')
    PAYMENT_SECTIONS = ('emitidos_pago', 'recibidos_pago')
    PAYSLIP_SECTIONS = ('emitidos_nomina',)
    PICKING_SECTIONS = ('emitidos_traslado', 'recibidos_traslado')

    @api.depends('qty_sat', 'qty_odoo', 'amount_sat', 'amount_odoo',
                 'sat_xml_ids', 'odoo_invoice_ids', 'odoo_payment_ids',
                 'odoo_payslip_ids', 'odoo_picking_ids')
    def _compute_differences(self):
        for record in self:
            diff_qty = (record.qty_sat or 0) - (record.qty_odoo or 0)
            diff_amount = (record.amount_sat or 0.0) - (record.amount_odoo or 0.0)
            missing = self.env['account.edi.downloaded.xml.sat']
            extra = self.env['account.move']
            missing_amount = 0.0
            extra_amount = 0.0

            if record.section_type in self.INVOICE_SECTIONS:
                missing, extra = record._get_invoice_mismatch()
                missing_amount = sum(x.amount_total for x in missing)
                extra_amount = sum(extra.mapped('amount_total'))
            elif record.section_type in self.PAYMENT_SECTIONS:
                missing, extra = record._get_payment_mismatch()
                missing_amount = sum(x.amount_total for x in missing)
                extra_amount = sum(extra.mapped('amount'))
            elif record.section_type in self.PAYSLIP_SECTIONS:
                missing, extra = record._get_payslip_mismatch()
                missing_amount = sum(x.amount_total for x in missing)
                # Nominas: el monto Odoo es net_pay (no comparable 1:1 con CFDI),
                # por eso no se suma como "extra_amount" — solo cuenta UUIDs huerfanos.
                extra_amount = 0.0
            elif record.section_type in self.PICKING_SECTIONS:
                missing, extra = record._get_picking_mismatch()
                # Traslados no tienen monto monetario (mercancia).
                missing_amount = 0.0
                extra_amount = 0.0

            if missing or extra:
                diff_qty = len(missing) - len(extra)
                diff_amount = missing_amount - extra_amount

            record.diff_qty = diff_qty
            record.diff_amount = diff_amount
            base_amount = record.amount_sat or record.amount_odoo or abs(diff_amount)
            record.diff_percentage = diff_amount / base_amount if base_amount else 0.0
            record.missing_sat_count = len(missing)
            record.missing_sat_amount = missing_amount
            record.extra_odoo_count = len(extra)
            record.extra_odoo_amount = extra_amount

    def action_view_differences(self):
        """Acción para ver detalles de las diferencias."""
        self.ensure_one()
        if self.diff_qty == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin Diferencias',
                    'message': f'No hay diferencias entre SAT y Odoo para {self.concepto}',
                    'type': 'success',
                    'sticky': False,
                }
            }

        if self.section_type in self.INVOICE_SECTIONS + self.PAYMENT_SECTIONS:
            if self.diff_qty > 0:
                return self.action_view_missing_sat()
            return self.action_view_extra_odoo()

        return self.action_view_sat_xmls()

    def action_view_missing_sat(self):
        """Mostrar los XML del SAT que aún no existen en Odoo."""
        self.ensure_one()
        if self.section_type in self.INVOICE_SECTIONS:
            missing, _extra = self._get_invoice_mismatch()
        elif self.section_type in self.PAYMENT_SECTIONS:
            missing, _extra = self._get_payment_mismatch()
        else:
            missing = self.env['account.edi.downloaded.xml.sat']

        if not hasattr(missing, 'ids'):
            missing_model = self.env['account.edi.downloaded.xml.sat']
            missing_ids = []
            for item in missing:
                if hasattr(item, 'id'):
                    missing_ids.append(item.id)
                else:
                    missing_ids.append(item)
            missing = missing_model.browse(missing_ids)

        if not missing:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin pendientes',
                    'message': 'Todos los XML del SAT ya están vinculados en Odoo.',
                    'type': 'info',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': f'SAT sin Odoo - {self.concepto}',
            'res_model': 'account.edi.downloaded.xml.sat',
            'view_mode': 'list,form',
            'domain': [('id', 'in', missing.ids)],
            'context': {'create': False},
        }

    def action_view_extra_odoo(self):
        """Mostrar documentos que existen en Odoo pero no en SAT."""
        self.ensure_one()
        res_model = 'account.move'
        if self.section_type in self.INVOICE_SECTIONS:
            _missing, extra = self._get_invoice_mismatch()
        elif self.section_type in self.PAYMENT_SECTIONS:
            _missing, extra = self._get_payment_mismatch()
            res_model = 'account.payment'
        else:
            extra = self.env['account.move']

        if not hasattr(extra, 'ids'):
            model = self.env[res_model]
            extra_ids = []
            for item in extra:
                if hasattr(item, 'id'):
                    extra_ids.append(item.id)
                else:
                    extra_ids.append(item)
            extra = model.browse(extra_ids)

        if not extra:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin pendientes',
                    'message': 'No hay documentos en Odoo sin XML correspondiente.',
                    'type': 'info',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': f'Odoo sin SAT - {self.concepto}',
            'res_model': res_model,
            'view_mode': 'list,form',
            'domain': [('id', 'in', extra.ids)],
            'context': {'create': False},
        }

    def generate_report(self, start_date, end_date, company_id=None,
                        exclude_externally_stamped=False, exclude_all_emitidos=False,
                        display_unit='units'):
        """Genera el reporte completo.

        :param exclude_externally_stamped: si True, omite Nomina y Traslados emitidos.
        :param exclude_all_emitidos: si True, omite TODAS las secciones de emitidos.
        :param display_unit: formato de cifras ('units', 'units_no_dec', 'thousands', 'millions').
        """
        if not company_id:
            company_id = self.env.company.id
        # exclude_all_emitidos implica exclude_externally_stamped
        if exclude_all_emitidos:
            exclude_externally_stamped = True
        # Defaults aplicables a todos los create() de este reporte.
        # Asi cada fila respeta el display_unit elegido por el usuario.
        self = self.with_context(default_display_unit=display_unit)

        self.search([('company_id', '=', company_id)]).sudo().unlink()

        sequence = 10
        # Estructura por defecto para acumuladores de ignorados (cuando se omiten emitidos)
        _empty = {'qty_ignored': 0, 'amount_ignored': 0.0}
        data_facturas_cliente = _empty
        data_nc_cliente = _empty
        data_pago_emitidos = _empty

        if exclude_all_emitidos:
            _logger.info("Reporte conciliacion: TODAS las secciones de EMITIDOS omitidas (exclude_all_emitidos=True)")
        else:
            # Pre-calculo todas las secciones para tener subtotales antes del header
            data_facturas_cliente = self._get_emitidos_data(start_date, end_date, 'I', 'out_invoice', company_id)
            data_nc_cliente = self._get_emitidos_data(start_date, end_date, 'E', 'out_refund', company_id)
            data_pago_emitidos = self._get_emitidos_pago_data(start_date, end_date, company_id)
            data_nomina_emitidos = self._get_emitidos_nomina_data(start_date, end_date, company_id) if not exclude_externally_stamped else None
            data_traslado_emitidos = self._get_traslado_data('emitidos', start_date, end_date, company_id) if not exclude_externally_stamped else None

            secciones_emitidos = [data_facturas_cliente, data_nc_cliente, data_pago_emitidos]
            if data_nomina_emitidos:
                secciones_emitidos.append(data_nomina_emitidos)
            if data_traslado_emitidos:
                secciones_emitidos.append(data_traslado_emitidos)

            # Header con subtotales acumulados de la seccion
            self.create({
                'sequence': sequence,
                'section_type': 'header_emitidos',
                'concepto': '═════════  📤  XML EMITIDOS  ═════════',
                'is_header': True,
                'qty_sat': sum(s.get('qty_sat', 0) for s in secciones_emitidos),
                'amount_sat': sum(s.get('amount_sat', 0.0) for s in secciones_emitidos),
                'qty_odoo': sum(s.get('qty_odoo', 0) for s in secciones_emitidos),
                'amount_odoo': sum(s.get('amount_odoo', 0.0) for s in secciones_emitidos),
                'start_date': start_date,
                'end_date': end_date,
                'company_id': company_id,
            })
            sequence += 10

            self.create({
                'sequence': sequence,
                'section_type': 'emitidos_factura',
                'concepto': 'Facturas de Cliente (Ingreso)',
                'document_type': 'Factura',
                'qty_sat': data_facturas_cliente['qty_sat'],
                'amount_sat': data_facturas_cliente['amount_sat'],
                'qty_odoo': data_facturas_cliente['qty_odoo'],
                'amount_odoo': data_facturas_cliente['amount_odoo'],
                'qty_ignored': data_facturas_cliente['qty_ignored'],
                'amount_ignored': data_facturas_cliente['amount_ignored'],
                'sat_xml_ids': [(6, 0, data_facturas_cliente['sat_xmls'].ids)],
                'odoo_invoice_ids': [(6, 0, data_facturas_cliente['odoo_invoices'].ids)],
                'company_id': company_id,
                'start_date': start_date,
                'end_date': end_date,
            })
            sequence += 10

            self.create({
                'sequence': sequence,
                'section_type': 'emitidos_nc',
                'concepto': 'Notas de Crédito Cliente (Egreso)',
                'document_type': 'Nota de Crédito',
                'qty_sat': data_nc_cliente['qty_sat'],
                'amount_sat': data_nc_cliente['amount_sat'],
                'qty_odoo': data_nc_cliente['qty_odoo'],
                'amount_odoo': data_nc_cliente['amount_odoo'],
                'qty_ignored': data_nc_cliente['qty_ignored'],
                'amount_ignored': data_nc_cliente['amount_ignored'],
                'sat_xml_ids': [(6, 0, data_nc_cliente['sat_xmls'].ids)],
                'odoo_invoice_ids': [(6, 0, data_nc_cliente['odoo_invoices'].ids)],
                'company_id': company_id,
                'start_date': start_date,
                'end_date': end_date,
            })
            sequence += 10

            self.create({
                'sequence': sequence,
                'section_type': 'emitidos_pago',
                'concepto': 'Complemento de Pago Emitidos',
                'document_type': 'Pago',
                'qty_sat': data_pago_emitidos['qty_sat'],
                'amount_sat': data_pago_emitidos['amount_sat'],
                'qty_odoo': data_pago_emitidos['qty_odoo'],
                'amount_odoo': data_pago_emitidos['amount_odoo'],
                'qty_ignored': data_pago_emitidos['qty_ignored'],
                'amount_ignored': data_pago_emitidos['amount_ignored'],
                'sat_xml_ids': [(6, 0, data_pago_emitidos['sat_xmls'].ids)],
                'odoo_payment_ids': [(6, 0, data_pago_emitidos['odoo_payments'].ids)],
                'company_id': company_id,
                'start_date': start_date,
                'end_date': end_date,
            })
            sequence += 10

            # Secciones de Nomina y Traslado EMITIDOS - solo si el usuario NO marco
            # "excluir timbrado externo".
            if not exclude_externally_stamped:
                self.create({
                    'sequence': sequence,
                    'section_type': 'emitidos_nomina',
                    'concepto': 'Recibos de Nomina (Emitidos)',
                    'document_type': 'Nomina',
                    'qty_sat': data_nomina_emitidos['qty_sat'],
                    'amount_sat': data_nomina_emitidos['amount_sat'],
                    'qty_odoo': data_nomina_emitidos['qty_odoo'],
                    'amount_odoo': data_nomina_emitidos['amount_odoo'],
                    'qty_ignored': data_nomina_emitidos['qty_ignored'],
                    'amount_ignored': data_nomina_emitidos['amount_ignored'],
                    'sat_xml_ids': [(6, 0, data_nomina_emitidos['sat_xmls'].ids)],
                    'odoo_payslip_ids': [(6, 0, data_nomina_emitidos['odoo_payslips'].ids)],
                    'odoo_extra_uuids': data_nomina_emitidos['odoo_extra_uuids'],
                    'company_id': company_id,
                    'start_date': start_date,
                    'end_date': end_date,
                })
                sequence += 10

                self.create({
                    'sequence': sequence,
                    'section_type': 'emitidos_traslado',
                    'concepto': 'Traslados / Cartas Porte (Emitidos)',
                    'document_type': 'Traslado',
                    'qty_sat': data_traslado_emitidos['qty_sat'],
                    'amount_sat': data_traslado_emitidos['amount_sat'],
                    'qty_odoo': data_traslado_emitidos['qty_odoo'],
                    'amount_odoo': data_traslado_emitidos['amount_odoo'],
                    'qty_ignored': data_traslado_emitidos['qty_ignored'],
                    'amount_ignored': data_traslado_emitidos['amount_ignored'],
                    'sat_xml_ids': [(6, 0, data_traslado_emitidos['sat_xmls'].ids)],
                    'odoo_picking_ids': [(6, 0, data_traslado_emitidos['odoo_pickings'].ids)],
                    'company_id': company_id,
                    'start_date': start_date,
                    'end_date': end_date,
                })
                sequence += 10

            total_ignored_emitidos_qty = data_facturas_cliente['qty_ignored'] + data_nc_cliente['qty_ignored'] + data_pago_emitidos['qty_ignored']
            total_ignored_emitidos_amount = data_facturas_cliente['amount_ignored'] + data_nc_cliente['amount_ignored'] + data_pago_emitidos['amount_ignored']
            self.create({
                'sequence': sequence,
                'section_type': 'ignored_detail',
                'concepto': '⚠️ IGNORADOS EMITIDOS (Excluidos del reporte)',
                'qty_sat': 0,
                'qty_odoo': 0,
                'qty_ignored': total_ignored_emitidos_qty,
                'amount_sat': 0.0,
                'amount_odoo': 0.0,
                'amount_ignored': total_ignored_emitidos_amount,
                'company_id': company_id,
                'start_date': start_date,
                'end_date': end_date,
                'is_separator': True,
            })
            sequence += 10

        # Pre-calculo todas las secciones de RECIBIDOS para acumular subtotales
        data_facturas_proveedor = self._get_recibidos_data(start_date, end_date, 'I', 'in_invoice', company_id)
        data_nc_proveedor = self._get_recibidos_data(start_date, end_date, 'E', 'in_refund', company_id)
        data_pago_recibidos = self._get_recibidos_pago_data(start_date, end_date, company_id)
        data_traslado_recibidos = self._get_traslado_data('recibidos', start_date, end_date, company_id)
        secciones_recibidos = [data_facturas_proveedor, data_nc_proveedor, data_pago_recibidos, data_traslado_recibidos]

        # Header con subtotales acumulados
        self.create({
            'sequence': sequence,
            'section_type': 'header_recibidos',
            'concepto': '═════════  📥  XML RECIBIDOS  ═════════',
            'is_header': True,
            'qty_sat': sum(s.get('qty_sat', 0) for s in secciones_recibidos),
            'amount_sat': sum(s.get('amount_sat', 0.0) for s in secciones_recibidos),
            'qty_odoo': sum(s.get('qty_odoo', 0) for s in secciones_recibidos),
            'amount_odoo': sum(s.get('amount_odoo', 0.0) for s in secciones_recibidos),
            'start_date': start_date,
            'end_date': end_date,
            'company_id': company_id,
        })
        sequence += 10

        self.create({
            'sequence': sequence,
            'section_type': 'recibidos_factura',
            'concepto': 'Facturas de Proveedor (Ingreso)',
            'document_type': 'Factura',
            'qty_sat': data_facturas_proveedor['qty_sat'],
            'amount_sat': data_facturas_proveedor['amount_sat'],
            'qty_odoo': data_facturas_proveedor['qty_odoo'],
            'amount_odoo': data_facturas_proveedor['amount_odoo'],
            'qty_ignored': data_facturas_proveedor['qty_ignored'],
            'amount_ignored': data_facturas_proveedor['amount_ignored'],
            'sat_xml_ids': [(6, 0, data_facturas_proveedor['sat_xmls'].ids)],
            'odoo_invoice_ids': [(6, 0, data_facturas_proveedor['odoo_invoices'].ids)],
            'company_id': company_id,
            'start_date': start_date,
            'end_date': end_date,
        })
        sequence += 10

        self.create({
            'sequence': sequence,
            'section_type': 'recibidos_nc',
            'concepto': 'Notas de Crédito Proveedor (Egreso)',
            'document_type': 'Nota de Crédito',
            'qty_sat': data_nc_proveedor['qty_sat'],
            'amount_sat': data_nc_proveedor['amount_sat'],
            'qty_odoo': data_nc_proveedor['qty_odoo'],
            'amount_odoo': data_nc_proveedor['amount_odoo'],
            'qty_ignored': data_nc_proveedor['qty_ignored'],
            'amount_ignored': data_nc_proveedor['amount_ignored'],
            'sat_xml_ids': [(6, 0, data_nc_proveedor['sat_xmls'].ids)],
            'odoo_invoice_ids': [(6, 0, data_nc_proveedor['odoo_invoices'].ids)],
            'company_id': company_id,
            'start_date': start_date,
            'end_date': end_date,
        })
        sequence += 10

        self.create({
            'sequence': sequence,
            'section_type': 'recibidos_pago',
            'concepto': 'Complemento de Pago Recibidos',
            'document_type': 'Pago',
            'qty_sat': data_pago_recibidos['qty_sat'],
            'amount_sat': data_pago_recibidos['amount_sat'],
            'qty_odoo': data_pago_recibidos['qty_odoo'],
            'amount_odoo': data_pago_recibidos['amount_odoo'],
            'qty_ignored': data_pago_recibidos['qty_ignored'],
            'amount_ignored': data_pago_recibidos['amount_ignored'],
            'sat_xml_ids': [(6, 0, data_pago_recibidos['sat_xmls'].ids)],
            'odoo_payment_ids': [(6, 0, data_pago_recibidos['odoo_payments'].ids)],
            'company_id': company_id,
            'start_date': start_date,
            'end_date': end_date,
        })
        sequence += 10

        # Traslados RECIBIDOS (Cartas Porte de proveedores de transporte). Esta seccion
        # NO se omite con el flag exclude_externally_stamped — los XMLs vienen de
        # terceros y el match Odoo (stock.picking) lo controla el cliente.
        self.create({
            'sequence': sequence,
            'section_type': 'recibidos_traslado',
            'concepto': 'Traslados / Cartas Porte (Recibidos)',
            'document_type': 'Traslado',
            'qty_sat': data_traslado_recibidos['qty_sat'],
            'amount_sat': data_traslado_recibidos['amount_sat'],
            'qty_odoo': data_traslado_recibidos['qty_odoo'],
            'amount_odoo': data_traslado_recibidos['amount_odoo'],
            'qty_ignored': data_traslado_recibidos['qty_ignored'],
            'amount_ignored': data_traslado_recibidos['amount_ignored'],
            'sat_xml_ids': [(6, 0, data_traslado_recibidos['sat_xmls'].ids)],
            'odoo_picking_ids': [(6, 0, data_traslado_recibidos['odoo_pickings'].ids)],
            'company_id': company_id,
            'start_date': start_date,
            'end_date': end_date,
        })
        sequence += 10

        total_ignored_recibidos_qty = data_facturas_proveedor['qty_ignored'] + data_nc_proveedor['qty_ignored'] + data_pago_recibidos['qty_ignored']
        total_ignored_recibidos_amount = data_facturas_proveedor['amount_ignored'] + data_nc_proveedor['amount_ignored'] + data_pago_recibidos['amount_ignored']
        self.create({
            'sequence': sequence,
            'section_type': 'ignored_detail',
            'concepto': '⚠️ IGNORADOS RECIBIDOS (Excluidos del reporte)',
            'qty_sat': 0,
            'qty_odoo': 0,
            'qty_ignored': total_ignored_recibidos_qty,
            'amount_sat': 0.0,
            'amount_odoo': 0.0,
            'amount_ignored': total_ignored_recibidos_amount,
            'company_id': company_id,
            'start_date': start_date,
            'end_date': end_date,
            'is_separator': True,
        })

        start_date_str = start_date.strftime("%d/%m/%Y") if isinstance(start_date, datetime) else fields.Date.to_date(start_date).strftime("%d/%m/%Y")
        end_date_str = end_date.strftime("%d/%m/%Y") if isinstance(end_date, datetime) else fields.Date.to_date(end_date).strftime("%d/%m/%Y")

        return {
            'type': 'ir.actions.act_window',
            'name': f'Conciliación SAT vs Odoo ({start_date_str} - {end_date_str})',
            'res_model': 'sat.conciliation.report',
            'view_mode': 'list,form,pivot',
            'target': 'current',
            'domain': [('company_id', '=', company_id)],
            'context': {'create': False, 'edit': False, 'delete': False, 'default_company_id': company_id},
        }

    def _get_invoice_mismatch(self):
        """Devuelve (XML SAT sin factura, facturas sin XML)."""
        self.ensure_one()
        xml_env = self.env['account.edi.downloaded.xml.sat']
        sat_valid = self.sat_xml_ids.filtered(lambda x: x.state not in ['ignored', 'cancel'] and x.name)
        unique_ids = []
        seen = set()
        for xml in sat_valid:
            if xml.name and xml.name not in seen:
                seen.add(xml.name)
                unique_ids.append(xml.id)
        sat_unique = xml_env.browse(unique_ids)
        sat_uuids = set(sat_unique.mapped('name'))

        odoo_invoices = self.odoo_invoice_ids.filtered(lambda x: x.l10n_mx_edi_cfdi_uuid)
        odoo_uuids = set(odoo_invoices.mapped('l10n_mx_edi_cfdi_uuid'))

        missing_uuids = sat_uuids - odoo_uuids
        extra_uuids = odoo_uuids - sat_uuids

        missing = sat_unique.filtered(lambda x: x.name in missing_uuids)
        extra = odoo_invoices.filtered(lambda x: x.l10n_mx_edi_cfdi_uuid in extra_uuids)
        return missing, extra

    def _get_payment_mismatch(self):
        """Devuelve (pagos SAT sin complemento en Odoo, pagos en Odoo sin XML)."""
        self.ensure_one()
        xml_env = self.env['account.edi.downloaded.xml.sat']
        sat_valid = self.sat_xml_ids.filtered(lambda x: x.state not in ['ignored', 'cancel'] and x.name)
        unique_ids = []
        seen = set()
        for xml in sat_valid:
            if xml.name and xml.name not in seen:
                seen.add(xml.name)
                unique_ids.append(xml.id)
        sat_unique = xml_env.browse(unique_ids)
        sat_uuids = set(sat_unique.mapped('name'))

        self.odoo_payment_ids.mapped('attachment_ids.datas')
        payment_map = {}
        extra_ids = []
        for payment in self.odoo_payment_ids:
            uuid = self._extract_payment_uuid(payment)
            if uuid:
                if uuid not in payment_map:
                    payment_map[uuid] = payment
                if uuid not in sat_uuids:
                    extra_ids.append(payment.id)
            else:
                extra_ids.append(payment.id)
        odoo_uuids = set(payment_map.keys())
        missing_uuids = sat_uuids - odoo_uuids

        missing = sat_unique.filtered(lambda x: x.name in missing_uuids)
        extra = self.env['account.payment'].browse(extra_ids)
        return missing, extra

    def _sum_amount_converted(self, model_name, domain, amount_field, currency_field='divisa', date_field='document_date'):
        """Suma amounts agrupando por moneda y convirtiendo cada grupo a la
        moneda de la compania al tipo de cambio del dia mediano del lote.

        Para el campo divisa de XML SAT: el valor es un codigo ISO (MXN, USD, EUR).
        Para account.move: usa currency_id (Many2one) en lugar de campo Char.

        Devuelve el total convertido a company_currency.
        """
        company = self.env['res.company'].browse(self.env.context.get('force_company_id') or self.env.company.id)
        company_currency = company.currency_id

        Model = self.env[model_name]
        is_relational_currency = currency_field in Model._fields and Model._fields[currency_field].type == 'many2one'

        # read_group agrupando por moneda
        grouped = Model.read_group(
            domain,
            [f'{amount_field}:sum', date_field + ':min', date_field + ':max'],
            [currency_field],
        )

        total = 0.0
        for g in grouped:
            amount = g.get(amount_field) or 0.0
            if not amount:
                continue
            # Resolver currency record
            cur = False
            cur_raw = g.get(currency_field)
            if is_relational_currency:
                # tuple (id, name)
                if cur_raw:
                    cur = self.env['res.currency'].browse(cur_raw[0] if isinstance(cur_raw, (list, tuple)) else cur_raw)
            else:
                if cur_raw and cur_raw not in ('XXX',):
                    cur = self.env['res.currency'].search([('name', '=', cur_raw)], limit=1)

            if not cur or cur == company_currency or not cur.active:
                # Sin moneda valida o ya es moneda compania -> sumar tal cual
                total += amount
                continue

            # Convertir usando fecha mediana del grupo (mejor aproximacion sin recorrer registros)
            ref_date = g.get(date_field + '_min') or g.get(date_field + '_max') or fields.Date.context_today(self)
            try:
                converted = cur._convert(amount, company_currency, company, ref_date)
            except Exception:
                converted = amount  # fallback: no convertir si falla
            total += converted
        return total

    def _get_emitidos_data(self, start_date, end_date, document_type, move_type, company_id):
        """OPTIMIZADO + conversion de moneda: agrupa por divisa/currency_id y convierte
        a la moneda de la compania al tipo de cambio del dia."""
        XmlSat = self.env['account.edi.downloaded.xml.sat']
        sat_domain = [
            ('cfdi_type', '=', 'emitidos'),
            ('document_type', '=', document_type),
            ('document_date', '>=', start_date),
            ('document_date', '<=', end_date),
            ('state', 'not in', ['cancel', 'ignored']),
            ('company_id', '=', company_id),
        ]
        sat_xmls = XmlSat.with_context(prefetch_fields=False).search(sat_domain)
        qty_sat = len(sat_xmls)
        amount_sat = self.with_context(force_company_id=company_id)._sum_amount_converted(
            'account.edi.downloaded.xml.sat', sat_domain, 'amount_total',
            currency_field='divisa', date_field='document_date',
        )

        Move = self.env['account.move']
        move_domain = [
            ('move_type', '=', move_type),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('state', '=', 'posted'),
            ('l10n_mx_edi_cfdi_uuid', '!=', False),
            ('company_id', '=', company_id),
        ]
        odoo_moves = Move.with_context(prefetch_fields=False).search(move_domain)
        unique_uuids = set(odoo_moves.mapped('l10n_mx_edi_cfdi_uuid'))
        qty_odoo = len(unique_uuids)
        amount_odoo = self.with_context(force_company_id=company_id)._sum_amount_converted(
            'account.move', move_domain, 'amount_total',
            currency_field='currency_id', date_field='invoice_date',
        )

        return {
            'qty_sat': qty_sat,
            'amount_sat': amount_sat,
            'qty_odoo': qty_odoo,
            'amount_odoo': amount_odoo,
            'qty_ignored': 0,
            'amount_ignored': 0.0,
            'sat_xmls': sat_xmls,
            'odoo_invoices': odoo_moves,
        }

    def _get_emitidos_pago_data(self, start_date, end_date, company_id):
        """Pagos emitidos: con conversion de moneda y filtro stored_sat_uuid."""
        XmlSat = self.env['account.edi.downloaded.xml.sat']
        sat_domain = [
            ('cfdi_type', '=', 'emitidos'),
            ('document_type', '=', 'P'),
            ('document_date', '>=', start_date),
            ('document_date', '<=', end_date),
            ('state', 'not in', ['cancel', 'ignored']),
            ('company_id', '=', company_id),
        ]
        sat_xmls = XmlSat.with_context(prefetch_fields=False).search(sat_domain)
        qty_sat = len(sat_xmls)
        amount_sat = self.with_context(force_company_id=company_id)._sum_amount_converted(
            'account.edi.downloaded.xml.sat', sat_domain, 'amount_total',
            currency_field='divisa', date_field='document_date',
        )

        Payment = self.env['account.payment']
        pay_domain = [
            ('payment_type', '=', 'inbound'),
            ('partner_type', '=', 'customer'),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('state', 'not in', ['cancel', 'draft']),
            ('company_id', '=', company_id),
            ('stored_sat_uuid', '!=', False),
        ]
        odoo_payments = Payment.with_context(prefetch_fields=False).search(pay_domain)
        qty_odoo = len(odoo_payments)
        amount_odoo = self.with_context(force_company_id=company_id)._sum_amount_converted(
            'account.payment', pay_domain, 'amount',
            currency_field='currency_id', date_field='date',
        )

        return {
            'qty_sat': qty_sat,
            'amount_sat': amount_sat,
            'qty_odoo': qty_odoo,
            'amount_odoo': amount_odoo,
            'qty_ignored': 0,
            'amount_ignored': 0.0,
            'sat_xmls': sat_xmls,
            'odoo_payments': odoo_payments,
        }

    def _get_recibidos_data(self, start_date, end_date, document_type, move_type, company_id):
        """Recibidos: con conversion USD/EUR -> MXN."""
        XmlSat = self.env['account.edi.downloaded.xml.sat']
        sat_domain = [
            ('cfdi_type', '=', 'recibidos'),
            ('document_type', '=', document_type),
            ('document_date', '>=', start_date),
            ('document_date', '<=', end_date),
            ('state', 'not in', ['cancel', 'ignored']),
            ('company_id', '=', company_id),
        ]
        sat_xmls = XmlSat.with_context(prefetch_fields=False).search(sat_domain)
        qty_sat = len(sat_xmls)
        amount_sat = self.with_context(force_company_id=company_id)._sum_amount_converted(
            'account.edi.downloaded.xml.sat', sat_domain, 'amount_total',
            currency_field='divisa', date_field='document_date',
        )

        Move = self.env['account.move']
        move_domain = [
            ('move_type', '=', move_type),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('state', '=', 'posted'),
            ('company_id', '=', company_id),
        ]
        odoo_moves = Move.with_context(prefetch_fields=False).search(move_domain)
        unique_uuids = set(odoo_moves.mapped('l10n_mx_edi_cfdi_uuid'))
        qty_odoo = len(unique_uuids)
        amount_odoo = self.with_context(force_company_id=company_id)._sum_amount_converted(
            'account.move', move_domain, 'amount_total',
            currency_field='currency_id', date_field='invoice_date',
        )

        return {
            'qty_sat': qty_sat,
            'amount_sat': amount_sat,
            'qty_odoo': qty_odoo,
            'amount_odoo': amount_odoo,
            'qty_ignored': 0,
            'amount_ignored': 0.0,
            'sat_xmls': sat_xmls,
            'odoo_invoices': odoo_moves,
        }

    def _get_recibidos_pago_data(self, start_date, end_date, company_id):
        """Pagos recibidos: con conversion de moneda."""
        XmlSat = self.env['account.edi.downloaded.xml.sat']
        sat_domain = [
            ('cfdi_type', '=', 'recibidos'),
            ('document_type', '=', 'P'),
            ('document_date', '>=', start_date),
            ('document_date', '<=', end_date),
            ('state', 'not in', ['cancel', 'ignored']),
            ('company_id', '=', company_id),
        ]
        sat_xmls = XmlSat.with_context(prefetch_fields=False).search(sat_domain)
        qty_sat = len(sat_xmls)
        amount_sat = self.with_context(force_company_id=company_id)._sum_amount_converted(
            'account.edi.downloaded.xml.sat', sat_domain, 'amount_total',
            currency_field='divisa', date_field='document_date',
        )

        Payment = self.env['account.payment']
        pay_domain = [
            ('payment_type', '=', 'outbound'),
            ('partner_type', '=', 'supplier'),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('state', 'not in', ['cancel', 'draft']),
            ('company_id', '=', company_id),
            ('stored_sat_uuid', '!=', False),
        ]
        odoo_payments = Payment.with_context(prefetch_fields=False).search(pay_domain)
        qty_odoo = len(odoo_payments)
        amount_odoo = self.with_context(force_company_id=company_id)._sum_amount_converted(
            'account.payment', pay_domain, 'amount',
            currency_field='currency_id', date_field='date',
        )

        return {
            'qty_sat': qty_sat,
            'amount_sat': amount_sat,
            'qty_odoo': qty_odoo,
            'amount_odoo': amount_odoo,
            'qty_ignored': 0,
            'amount_ignored': 0.0,
            'sat_xmls': sat_xmls,
            'odoo_payments': odoo_payments,
        }

    def _get_emitidos_nomina_data(self, start_date, end_date, company_id):
        """Recibos de nomina TIMBRADOS (document_type='N', cfdi_type='emitidos').
        Contraparte Odoo: hr.payslip + l10n_mx_payroll.uuid.history (si esta instalado).
        OPTIMIZADO: read_group + prefetch_fields=False.
        """
        XmlSat = self.env['account.edi.downloaded.xml.sat']
        sat_domain = [
            ('cfdi_type', '=', 'emitidos'),
            ('document_type', '=', 'N'),
            ('document_date', '>=', start_date),
            ('document_date', '<=', end_date),
            ('state', 'not in', ['cancel', 'ignored']),
            ('company_id', '=', company_id),
        ]
        sat_xmls = XmlSat.with_context(prefetch_fields=False).search(sat_domain)
        qty_sat = len(sat_xmls)
        amount_sat = self.with_context(force_company_id=company_id)._sum_amount_converted(
            'account.edi.downloaded.xml.sat', sat_domain, 'amount_total',
            currency_field='divisa', date_field='document_date',
        )

        # Payslips estandar Odoo
        payslip_domain = [
            ('l10n_mx_edi_cfdi_uuid', '!=', False),
            ('company_id', '=', company_id),
        ]
        # Algunos despliegues tienen el campo 'date_to' (rango de nomina); otros 'date'.
        # Usamos lo que exista.
        payslip_model = self.env['hr.payslip']
        date_field = 'date_to' if 'date_to' in payslip_model._fields else 'date_from'
        payslip_domain += [(date_field, '>=', start_date), (date_field, '<=', end_date)]
        odoo_payslips = payslip_model.search(payslip_domain)

        # uuid.history (modelo opcional del modulo l10n_mx_payroll)
        extra_uuids = []
        if 'l10n_mx_payroll.uuid.history' in self.env:
            history = self.env['l10n_mx_payroll.uuid.history'].search([
                ('invoice_date', '>=', start_date),
                ('invoice_date', '<=', end_date),
                ('l10n_mx_edi_cfdi_uuid', '!=', False),
            ])
            payslip_uuids = set(odoo_payslips.mapped('l10n_mx_edi_cfdi_uuid'))
            for h in history:
                if h.l10n_mx_edi_cfdi_uuid and h.l10n_mx_edi_cfdi_uuid not in payslip_uuids:
                    extra_uuids.append(h.l10n_mx_edi_cfdi_uuid)

        qty_odoo = len(odoo_payslips) + len(extra_uuids)
        # Monto Odoo: net_pay si existe el campo, sino 0 (uuid.history NO suma porque
        # su campo de monto es del CFDI, no del payslip).
        amount_odoo = 0.0
        if 'net_pay' in payslip_model._fields:
            amount_odoo = sum(odoo_payslips.mapped('net_pay'))

        return {
            'qty_sat': qty_sat,
            'amount_sat': amount_sat,
            'qty_odoo': qty_odoo,
            'amount_odoo': amount_odoo,
            'qty_ignored': 0,
            'amount_ignored': 0.0,
            'sat_xmls': sat_xmls,
            'odoo_payslips': odoo_payslips,
            'odoo_extra_uuids': ','.join(extra_uuids) if extra_uuids else False,
        }

    def _get_traslado_data(self, cfdi_type, start_date, end_date, company_id):
        """Helper generico para traslados emitidos y recibidos (document_type='T').
        Contraparte Odoo: stock.picking con UUID timbrado. Sin monto monetario
        (los traslados no tienen valor en el CFDI).
        OPTIMIZADO: prefetch_fields=False (los traslados no necesitan SUM).
        """
        XmlSat = self.env['account.edi.downloaded.xml.sat']
        sat_domain = [
            ('cfdi_type', '=', cfdi_type),
            ('document_type', '=', 'T'),
            ('document_date', '>=', start_date),
            ('document_date', '<=', end_date),
            ('state', 'not in', ['cancel', 'ignored']),
            ('company_id', '=', company_id),
        ]
        sat_xmls = XmlSat.with_context(prefetch_fields=False).search(sat_domain)
        qty_sat = len(sat_xmls)

        picking_domain = [
            ('l10n_mx_edi_cfdi_uuid', '!=', False),
            ('company_id', '=', company_id),
            ('scheduled_date', '>=', start_date),
            ('scheduled_date', '<=', end_date),
        ]
        odoo_pickings = self.env['stock.picking'].with_context(prefetch_fields=False).search(picking_domain)
        qty_odoo = len(odoo_pickings)

        return {
            'qty_sat': qty_sat,
            'amount_sat': 0.0,  # Traslados no tienen monto monetario
            'qty_odoo': qty_odoo,
            'amount_odoo': 0.0,
            'qty_ignored': 0,
            'amount_ignored': 0.0,
            'sat_xmls': sat_xmls,
            'odoo_pickings': odoo_pickings,
        }

    def action_view_sat_xmls(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'XMLs del SAT - {self.document_type or self.concepto}',
            'res_model': 'account.edi.downloaded.xml.sat',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.sat_xml_ids.ids)],
            'context': {'create': False},
        }

    def _extract_payment_uuid(self, payment):
        """Devuelve el UUID del CFDI de pago.
        Fast path: campo stored_sat_uuid (indexado, pre-calculado al adjuntar el XML).
        Fallback: parsea el attachment solo si el campo esta vacio (legacy).
        """
        if payment.stored_sat_uuid:
            return payment.stored_sat_uuid
        # Fallback (legacy): parsear attachment. Solo se ejecuta en pagos viejos
        # donde stored_sat_uuid aun no se haya recomputado.
        try:
            from lxml import etree
            import base64

            xml_attachments = payment.attachment_ids.filtered(lambda a: a.mimetype == 'application/xml')
            for attachment in xml_attachments:
                try:
                    xml_content = base64.b64decode(attachment.datas)
                    root = etree.fromstring(xml_content)
                    ns = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
                    tfd = root.find('.//tfd:TimbreFiscalDigital', namespaces=ns)
                    if tfd is not None:
                        uuid = tfd.get('UUID')
                        if uuid:
                            return uuid
                except (etree.XMLSyntaxError, ValueError) as err:
                    _logger.debug("Attachment %s is not valid XML: %s", attachment.name, err)
        except (KeyError, AttributeError) as err:
            _logger.warning("Error extracting payment UUID from %s: %s", payment.name, err)
        return None

    def action_view_odoo_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Facturas Odoo - {self.document_type or self.concepto}',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.odoo_invoice_ids.ids)],
            'context': {'create': False},
        }

    def action_view_odoo_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Pagos Odoo - {self.document_type or self.concepto}',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.odoo_payment_ids.ids)],
            'context': {'create': False},
        }

    def action_view_odoo_documents(self):
        """Abre facturas o pagos según el tipo de sección."""
        self.ensure_one()
        if self.section_type in self.PAYMENT_SECTIONS:
            return self.action_view_odoo_payments()
        return self.action_view_odoo_invoices()

    def generateReport(self, start_date, end_date, company_id=None):
        from datetime import date
        if not start_date:
            start_date = date(date.today().year, 1, 1)
        if not end_date:
            end_date = date.today()
        if not company_id:
            company_id = self.env.company.id
        return self.generate_report(start_date, end_date, company_id)

    def _get_invoice_mismatch(self):
        """Regresa los XML faltantes y las facturas extra."""
        sat_valid = self.sat_xml_ids.filtered(lambda x: x.state not in ['ignored', 'cancel'] and x.name)
        sat_map = {}
        for xml in sat_valid:
            sat_map.setdefault(xml.name, []).append(xml)

        odoo_invoices = self.odoo_invoice_ids.filtered(lambda x: x.l10n_mx_edi_cfdi_uuid)
        odoo_map = {inv.l10n_mx_edi_cfdi_uuid: inv for inv in odoo_invoices}

        missing = [records[0] for uuid, records in sat_map.items() if uuid not in odoo_map]
        extra = odoo_invoices.filtered(lambda inv: inv.l10n_mx_edi_cfdi_uuid not in sat_map)
        return missing, extra

    def _get_payment_mismatch(self):
        """Regresa los pagos XML faltantes y los pagos extra en Odoo.
        OPTIMIZADO: mapea stored_sat_uuid (campo indexado pre-calculado) en una
        sola pasada — evita parsear N attachments XML en runtime.
        """
        sat_valid = self.sat_xml_ids.filtered(lambda x: x.state not in ['ignored', 'cancel'] and x.name)
        sat_map = {}
        for xml in sat_valid:
            sat_map.setdefault(xml.name, []).append(xml)

        # Mapped masivo: 1 SQL pre-fetch del campo stored_sat_uuid de TODOS los
        # payments. Sustituye el parseo XML 1-a-1 que era el hotspot.
        payment_uuids = self.odoo_payment_ids.mapped('stored_sat_uuid')
        payment_map = {}
        extra_ids = []
        for payment, uuid in zip(self.odoo_payment_ids, payment_uuids):
            if uuid:
                payment_map[uuid] = payment
                if uuid not in sat_map:
                    extra_ids.append(payment.id)
            elif payment.attachment_ids:
                # Fallback legacy solo si el payment tiene attachments pero stored_sat_uuid vacio
                uuid = self._extract_payment_uuid(payment)
                if uuid:
                    payment_map[uuid] = payment
                    if uuid not in sat_map:
                        extra_ids.append(payment.id)
        missing = [records[0] for uuid, records in sat_map.items() if uuid not in payment_map]
        extra = self.env['account.payment'].browse(extra_ids)
        return missing, extra

    def _get_payslip_mismatch(self):
        """Regresa nominas XML faltantes en Odoo y payslips extra sin XML del SAT.
        Match por UUID contra hr.payslip Y contra l10n_mx_payroll.uuid.history (si esta instalado).
        Los UUIDs "extra" del uuid.history se reportan en odoo_extra_uuids (sin recordset).
        """
        sat_valid = self.sat_xml_ids.filtered(lambda x: x.state not in ['ignored', 'cancel'] and x.name)
        sat_uuids_upper = {(x.name or '').upper(): x for x in sat_valid}

        odoo_uuids_upper = set()
        # Payslips estandar
        payslip_map = {}
        for slip in self.odoo_payslip_ids:
            u = (slip.l10n_mx_edi_cfdi_uuid or '').upper()
            if u:
                odoo_uuids_upper.add(u)
                payslip_map[u] = slip
        # uuid.history (si el modelo existe en esta BD)
        if self.odoo_extra_uuids:
            for u in self.odoo_extra_uuids.split(','):
                u = u.strip().upper()
                if u:
                    odoo_uuids_upper.add(u)

        missing_uuids = set(sat_uuids_upper) - odoo_uuids_upper
        extra_uuids = odoo_uuids_upper - set(sat_uuids_upper)

        missing = [sat_uuids_upper[u] for u in missing_uuids]
        # Los "extra" como recordset son solo los payslips de Odoo sin XML.
        # Los uuids huerfanos de uuid.history no se devuelven como recordset (modelo opcional).
        extra_ids = [payslip_map[u].id for u in extra_uuids if u in payslip_map]
        extra = self.env['hr.payslip'].browse(extra_ids)
        return missing, extra

    def _get_picking_mismatch(self):
        """Regresa traslados XML faltantes en Odoo y stock.picking extra sin XML del SAT.
        Match por UUID contra stock.picking.l10n_mx_edi_cfdi_uuid.
        """
        sat_valid = self.sat_xml_ids.filtered(lambda x: x.state not in ['ignored', 'cancel'] and x.name)
        sat_uuids_upper = {(x.name or '').upper(): x for x in sat_valid}

        picking_map = {}
        for picking in self.odoo_picking_ids:
            u = (picking.l10n_mx_edi_cfdi_uuid or '').upper()
            if u:
                picking_map[u] = picking

        missing_uuids = set(sat_uuids_upper) - set(picking_map)
        extra_uuids = set(picking_map) - set(sat_uuids_upper)

        missing = [sat_uuids_upper[u] for u in missing_uuids]
        extra = self.env['stock.picking'].browse([picking_map[u].id for u in extra_uuids])
        return missing, extra
