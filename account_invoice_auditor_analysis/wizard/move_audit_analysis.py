# -*- coding: utf-8 -*-
# Coded by German Ponce Dominguez
#     ▬▬▬▬▬.◙.▬▬▬▬▬
#       ▂▄▄▓▄▄▂
#    ◢◤█▀▀████▄▄▄▄▄▄ ◢◤
#    █▄ █ █▄ ███▀▀▀▀▀▀▀ ╬
#    ◥ █████ ◤
#     ══╩══╩═
#       ╬═╬
#       ╬═╬ Dream big and start with something small!!!
#       ╬═╬
#       ╬═╬ You can do it!
#       ╬═╬   Let's go...
#    ☻/ ╬═╬
#   /▌  ╬═╬
#   / \
# Cherman Seingalt - german.ponce@outlook.com
#
# ─────────────────────────────────────────────────────────────────
# MIGRACIÓN A ODOO 18
# Cambios principales respecto a versiones anteriores:
#
#  1. sat_uuid → campo stored related a l10n_mx_edi_cfdi_uuid
#     (el UUID ya lo gestiona l10n_mx_edi nativamente en Odoo 18).
#
#  2. Lectura del adjunto XML: se usa attachment.raw (bytes) en lugar
#     de ir.attachment._full_path() que desapareció en Odoo 17+.
#
#  3. Se eliminó el campo cfdi_id (Many2one 'account.cfdi') porque el
#     modelo account.cfdi ya no existe en l10n_mx_edi de Odoo 18.
#
#  4. Los estados SAT se leen de l10n_mx_edi_cfdi_sat_state
#     (valid/cancelled/not_found/not_defined/error).
#
#  5. __manifest__: se eliminó la clave 'test', versión 18.0.x.x.x.
#
#  6. Vistas XML: t-esc → t-out (deprecado en Odoo 17+).
#     view_type eliminado de ir.actions.act_window.
# ─────────────────────────────────────────────────────────────────

import ast
import base64
import calendar
import logging
import math
import re
import zipfile
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from io import BytesIO
from xml.dom.minidom import parseString

import pytz
import xlsxwriter
import tempfile
from xlsxwriter.utility import xl_rowcol_to_cell

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

""" Limpiando Tablas (utilitario)
delete from cfdi_txt_metadata;
delete from move_audit_analysis_check;
delete from move_audit_analysis_line;
delete from move_audit_analysis;
"""


# ─────────────────────────────────────────────────────────────────
# EXTENSIÓN DE account.move
# ─────────────────────────────────────────────────────────────────
class AccountMove(models.Model):
    _inherit = 'account.move'

    # ------------------------------------------------------------------
    # sat_uuid: alias almacenado del campo nativo l10n_mx_edi_cfdi_uuid.
    # Se mantiene como campo "related stored" para que las consultas SQL
    # del módulo sigan funcionando con la columna `sat_uuid` en la tabla
    # account_move sin necesidad de reescribir todas las queries.
    # ------------------------------------------------------------------
    sat_uuid = fields.Char(
        string="CFDI UUID",
        related='l10n_mx_edi_cfdi_uuid',
        store=True,
        index=True,
        readonly=True,
    )

    # sat_folio y sat_serie se siguen calculando desde el XML adjunto
    # porque l10n_mx_edi de Odoo 18 no almacena esos atributos por separado.
    @api.depends('l10n_mx_edi_invoice_document_ids', 'l10n_mx_edi_payment_document_ids')
    def _compute_sat_serie_folio(self):
        """Extrae Serie y Folio del nodo cfdi:Comprobante del XML timbrado."""
        for rec in self:
            rec.sat_serie = False
            rec.sat_folio = False
            xml_data = rec._get_cfdi_xml_raw()
            if not xml_data:
                continue
            try:
                arch_xml = parseString(xml_data)
                comprobante_nodes = arch_xml.getElementsByTagName('cfdi:Comprobante')
                if not comprobante_nodes:
                    continue
                node = comprobante_nodes[0]
                try:
                    rec.sat_serie = node.attributes['Serie'].value
                except (KeyError, AttributeError):
                    pass
                try:
                    rec.sat_folio = node.attributes['Folio'].value
                except (KeyError, AttributeError):
                    pass
            except Exception as e:
                _logger.warning("Error al parsear XML para folio/serie en move %s: %s", rec.id, e)

    def _get_cfdi_xml_raw(self):
        """
        Devuelve el contenido en bytes del archivo XML CFDI adjunto.
        Usa attachment.raw (disponible desde Odoo 16) en lugar del
        método _full_path() que fue eliminado en versiones recientes.
        """
        self.ensure_one()
        # Busca el adjunto XML generado por l10n_mx_edi
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'account.move'),
            ('res_id', '=', self.id),
            ('name', 'ilike', '.xml'),
        ], limit=1)
        if not attachment:
            return False
        try:
            # attachment.raw devuelve bytes directamente (Odoo 16+)
            return attachment.raw
        except Exception as e:
            _logger.error("No se pudo leer el XML adjunto a la factura %s: %s", self.id, e)
            return False

    sat_folio = fields.Char(
        compute='_compute_sat_serie_folio',
        string="CFDI Folio",
        store=True,
        index=True,
    )
    sat_serie = fields.Char(
        compute='_compute_sat_serie_folio',
        string="CFDI Serie",
        store=True,
        index=True,
    )


# ─────────────────────────────────────────────────────────────────
# MODELO: cfdi.txt.metadata
# ─────────────────────────────────────────────────────────────────
class CFDITxtMetadata(models.Model):
    _name = 'cfdi.txt.metadata'
    _description = 'Metadatos del archivo TXT descargado del SAT'

    uuid = fields.Char('UUID', required=True)
    rfc_emisor = fields.Char('RFC Emisor')
    nombre_emisor = fields.Char('Nombre Emisor')
    rfc_receptor = fields.Char('RFC Receptor')
    nombre_receptor = fields.Char('Nombre Receptor')
    rfc_pac = fields.Char('RFC PAC')
    fecha_emision = fields.Date('Fecha Emisión')
    fecha_certificacion_sat = fields.Date('Fecha Certificación SAT')
    monto = fields.Float('Monto')
    efecto_comprobante = fields.Selection([
        ('I', 'Ingreso'),
        ('E', 'Egreso'),
        ('T', 'Traslado'),
        ('N', 'Nómina'),
        ('P', 'Pago'),
    ], string='Efecto Comprobante')
    estatus = fields.Selection([
        ('0', 'Cancelado'),
        ('1', 'Vigente'),
        ('2', 'Cancelación en proceso'),
    ], string='Estatus')
    fecha_cancelacion = fields.Date('Fecha Cancelación', required=False)

    analysis_id = fields.Many2one('move.audit.analysis', 'Análisis de la Auditoría',
                                  ondelete='cascade')
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        default=lambda self: self.env.company,
    )


# ─────────────────────────────────────────────────────────────────
# MODELO: move.audit.analysis.check
# ─────────────────────────────────────────────────────────────────
class MoveAuditAnalysisCheck(models.Model):
    _name = 'move.audit.analysis.check'
    _description = 'Análisis de Facturas - Discrepancias'

    uuid = fields.Char('UUID')
    rfc_emisor = fields.Char('RFC Emisor')
    nombre_emisor = fields.Char('Nombre Emisor')
    rfc_receptor = fields.Char('RFC Receptor')
    nombre_receptor = fields.Char('Nombre Receptor')
    rfc_pac = fields.Char('RFC PAC')
    monto = fields.Float('Monto')
    fecha_emision = fields.Date('Fecha Emisión')
    fecha_cancelacion = fields.Date('Fecha Cancelación', required=False)

    records_cancel_odoo_no_sat_id = fields.Many2one(
        'move.audit.analysis', 'Ref. Canceladas Odoo no SAT')
    records_cancel_sat_no_odoo_id = fields.Many2one(
        'move.audit.analysis', 'Ref. Canceladas SAT no Odoo')
    records_posted_odoo_no_sat_id = fields.Many2one(
        'move.audit.analysis', 'Ref. Vigentes Odoo no SAT')
    records_posted_sat_no_odoo_id = fields.Many2one(
        'move.audit.analysis', 'Ref. Vigentes SAT no Odoo')


# ─────────────────────────────────────────────────────────────────
# MODELO: move.audit.analysis.line
# ─────────────────────────────────────────────────────────────────
class MoveAuditAnalysisLine(models.Model):
    _name = 'move.audit.analysis.line'
    _description = 'Análisis de Auditoría - Detalle'
    _order = "sequence"

    analysis_id = fields.Many2one('move.audit.analysis', 'Análisis de la Auditoría',
                                  ondelete='cascade')
    sequence = fields.Integer('Secuencia')
    name = fields.Char('Tabla')
    total_facturas = fields.Integer('Total Facturas')
    importe_sin_iva = fields.Float('Importe sin IVA')
    facturas_vigentes = fields.Integer('Facturas Vigentes')
    importe_vigente = fields.Float('Importe Vigente')
    facturas_canceladas = fields.Integer('Facturas Canceladas')
    importe_cancelado = fields.Float('Importe Cancelado')


# ─────────────────────────────────────────────────────────────────
# MODELO PRINCIPAL: move.audit.analysis
# ─────────────────────────────────────────────────────────────────
class MoveAuditAnalysis(models.Model):
    _name = 'move.audit.analysis'
    _description = 'Análisis de Auditoría'
    _rec_name = "start_date"
    _order = "start_date desc"

    def _get_company_defaults(self):
        return [(6, 0, self.env.companies.ids)]

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id)

    zip_datas_fname = fields.Char('Zip Metadatos', size=256)
    zip_file = fields.Binary('UUID Zip (Metadatos)')

    company_ids = fields.Many2many(
        'res.company',
        'analysis_auditor_company_rel', 'wizard_id', 'company_id',
        string='Compañías',
        default=_get_company_defaults,
        required=True,
    )

    start_date = fields.Date("Fecha Inicio", help="Fecha inicial", required=True)
    end_date = fields.Date("Fecha Final", help="Fecha final", required=True)

    report_type = fields.Selection([
        ('customers', 'Clientes'),
        ('suppliers', 'Proveedores'),
    ], string="Tipo de Reporte", default="customers")

    line_ids = fields.One2many('move.audit.analysis.line', 'analysis_id', 'Detalle Análisis')
    metadata_line_ids = fields.One2many('cfdi.txt.metadata', 'analysis_id', 'Detalle Metadatos')
    account_invoice_ids = fields.Many2many(
        'account.move',
        'wizard_audit_analysis_invoice_rel', 'audit_id', 'move_id',
        string='Facturas Relacionadas',
    )

    records_cancel_odoo_no_sat = fields.Integer('Registros Cancelados Odoo no SAT')
    records_cancel_sat_no_odoo = fields.Integer('Registros Cancelados SAT no Odoo')
    amount_cancel_odoo_no_sat = fields.Float('Monto Cancelados Odoo no SAT')
    amount_cancel_sat_no_odoo = fields.Float('Monto Cancelados SAT no Odoo')

    records_posted_odoo_no_sat = fields.Integer('Registros Vigentes Odoo no SAT')
    records_posted_sat_no_odoo = fields.Integer('Registros Vigentes SAT no Odoo')
    amount_posted_odoo_no_sat = fields.Float('Monto Vigentes Odoo no SAT')
    amount_posted_sat_no_odoo = fields.Float('Monto Vigentes SAT no Odoo')

    records_cancel_odoo_no_sat_ids = fields.One2many(
        'move.audit.analysis.check', 'records_cancel_odoo_no_sat_id',
        'Facturas Canceladas en Odoo pero no en SAT')
    records_cancel_sat_no_odoo_ids = fields.One2many(
        'move.audit.analysis.check', 'records_cancel_sat_no_odoo_id',
        'Facturas Canceladas en SAT pero no en Odoo')
    records_posted_odoo_no_sat_ids = fields.One2many(
        'move.audit.analysis.check', 'records_posted_odoo_no_sat_id',
        'Facturas Vigentes en Odoo pero no en SAT')
    records_posted_sat_no_odoo_ids = fields.One2many(
        'move.audit.analysis.check', 'records_posted_sat_no_odoo_id',
        'Facturas Vigentes en SAT pero no en Odoo')

    hide_resumen = fields.Boolean('Ocultar Resumen', default=False)

    # ------------------------------------------------------------------
    # Acciones de botones
    # ------------------------------------------------------------------
    def show_resumen(self):
        for rec in self:
            rec.hide_resumen = not rec.hide_resumen

    def clean_metadatos(self):
        """Elimina los registros de metadatos que no sean de tipo Ingreso."""
        for metadato in self.metadata_line_ids:
            if metadato.efecto_comprobante != 'I':
                metadato.unlink()

    def action_view_metadata_line_ids(self):
        metadata_line_ids = self.metadata_line_ids.ids if self.metadata_line_ids else []
        return {
            'domain': [('id', 'in', metadata_line_ids)],
            'name': _('Análisis de la Auditoría (Metadatos SAT)'),
            'view_mode': 'list,form',
            'context': {'tree_view_ref': 'account_invoice_auditor_analysis.cfdi_txt_metadata_tree_view'},
            'res_model': 'cfdi.txt.metadata',
            'type': 'ir.actions.act_window',
        }

    def action_view_invoices(self):
        account_invoice_ids = self.account_invoice_ids.ids if self.account_invoice_ids else []
        if self.report_type == 'customers':
            ctx_ref = 'account.view_out_invoice_tree'
        else:
            ctx_ref = 'account.view_in_invoice_bill_tree'
        return {
            'domain': [('id', 'in', account_invoice_ids)],
            'name': _('Análisis de la Auditoría (Facturas Odoo)'),
            'view_mode': 'list,form',
            'context': {'tree_view_ref': ctx_ref},
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
        }

    # ------------------------------------------------------------------
    # Métodos de análisis
    # ------------------------------------------------------------------
    def _build_invoice_xvals(self, line_br):
        """Construye el dict de valores para move.audit.analysis.check desde un account.move."""
        uuid = line_br.l10n_mx_edi_cfdi_uuid or ''
        if line_br.move_type == 'in_invoice':
            rfc_emisor = line_br.partner_id.vat or ''
            nombre_emisor = line_br.partner_id.name or ''
            rfc_receptor = line_br.company_id.partner_id.vat or ''
            nombre_receptor = line_br.company_id.partner_id.name or ''
        else:
            rfc_emisor = line_br.company_id.partner_id.vat or ''
            nombre_emisor = line_br.company_id.partner_id.name or ''
            rfc_receptor = line_br.partner_id.vat or ''
            nombre_receptor = line_br.partner_id.name or ''
        res = {
            'uuid': uuid,
            'rfc_emisor': rfc_emisor,
            'nombre_emisor': nombre_emisor,
            'rfc_receptor': rfc_receptor,
            'nombre_receptor': nombre_receptor,
            'fecha_emision': line_br.invoice_date,
            'monto': line_br.amount_total,
            }
        fecha_cancelacion = "" ### AQUI VA LA FECHA DE CANCELACION DE LA FACTURA

        cancel_doc = line_br.l10n_mx_edi_document_ids.filtered(
            lambda d: d.state == 'invoice_cancel'
        )
        if cancel_doc:
            cancel_date = cancel_doc[:1].datetime  # Es un Datetime
            fecha_cancelacion = str(cancel_date)[0:10]
        if fecha_cancelacion:
            res['fecha_cancelacion'] = fecha_cancelacion if fecha_cancelacion else None
        return res

    def _build_metadata_xvals(self, line_br):
        """Construye el dict de valores para move.audit.analysis.check desde cfdi.txt.metadata."""
        res = {
                    'uuid': line_br.uuid,
                    'rfc_emisor': line_br.rfc_emisor,
                    'nombre_emisor': line_br.nombre_emisor,
                    'rfc_receptor': line_br.rfc_receptor,
                    'nombre_receptor': line_br.nombre_receptor,
                    'fecha_emision': line_br.fecha_emision,
                    'monto': line_br.monto,
                }
        fecha_cancelacion = line_br.fecha_cancelacion or None
        if fecha_cancelacion:
            res['fecha_cancelacion'] = fecha_cancelacion
        return res

    def get_info_list_cancel_odoo_no_sat(self):
        """
        Caso 1 – Canceladas en Odoo pero NO en SAT (o no en metadatos).
        Sub-caso A: move en estado 'cancel' cuyo UUID no aparece en los metadatos.
        Sub-caso B: move en estado 'cancel' cuyo UUID aparece en metadatos con estatus VIGENTE (1).
        """
        info_list = []
        cr = self.env.cr
        move_audit_analysis_check_list = []
        cfdi_txt_metadata = self.env['cfdi.txt.metadata']
        account_move = self.env['account.move']
        records_cancel_odoo_no_sat = 0.0
        amount_cancel_odoo_no_sat = 0.0

        # Sub-caso A: UUID cancelado en Odoo que no está en metadatos SAT
        query_sql = """
SELECT am.id, am.l10n_mx_edi_cfdi_uuid
    FROM account_move am
    LEFT JOIN wizard_audit_analysis_invoice_rel war ON war.move_id = am.id
    LEFT JOIN move_audit_analysis maa ON maa.id = war.audit_id
WHERE am.l10n_mx_edi_cfdi_uuid IS NOT NULL
  AND am.l10n_mx_edi_cfdi_uuid NOT IN (
        SELECT ctm.uuid
          FROM cfdi_txt_metadata ctm
         WHERE ctm.analysis_id = %s
    )
  AND maa.id = %s
  AND am.state = 'cancel'
GROUP BY am.id, am.l10n_mx_edi_cfdi_uuid
""" % (self.id, self.id)
        cr.execute(query_sql)
        cr_res = cr.fetchall()
        if cr_res and cr_res[0] and cr_res[0][0]:
            for line_br in account_move.browse([x[0] for x in cr_res]):
                xvals = self._build_invoice_xvals(line_br)
                records_cancel_odoo_no_sat += 1
                amount_cancel_odoo_no_sat += xvals['monto']
                info_list.append(xvals)
                move_audit_analysis_check_list.append((0, 0, xvals))

        # Sub-caso B: UUID cancelado en Odoo pero aparece VIGENTE en SAT
        query_sql = """
SELECT ctm.id, ctm.uuid
  FROM cfdi_txt_metadata ctm
 WHERE ctm.uuid IN (
    SELECT am.l10n_mx_edi_cfdi_uuid
      FROM account_move am
      LEFT JOIN wizard_audit_analysis_invoice_rel war ON war.move_id = am.id
      LEFT JOIN move_audit_analysis maa ON maa.id = war.audit_id
     WHERE maa.id = %s
       AND am.state = 'cancel'
       AND am.l10n_mx_edi_cfdi_uuid IS NOT NULL
 )
   AND ctm.analysis_id = %s
   AND ctm.estatus = '1'
""" % (self.id, self.id)
        cr.execute(query_sql)
        cr_res = cr.fetchall()
        if cr_res and cr_res[0] and cr_res[0][0]:
            for line_br in cfdi_txt_metadata.browse([x[0] for x in cr_res]):
                xvals = self._build_metadata_xvals(line_br)
                records_cancel_odoo_no_sat += 1
                amount_cancel_odoo_no_sat += xvals['monto']
                info_list.append(xvals)
                move_audit_analysis_check_list.append((0, 0, xvals))

        self.write({
            'records_cancel_odoo_no_sat': records_cancel_odoo_no_sat,
            'amount_cancel_odoo_no_sat': amount_cancel_odoo_no_sat,
        })
        if self._context.get('compute_resumen'):
            self.write({'records_cancel_odoo_no_sat_ids': move_audit_analysis_check_list})
        return info_list

    def get_info_list_cancel_sat_no_odoo(self):
        """
        Caso 2 – Canceladas en SAT pero NO en Odoo.
        Sub-caso A: UUID cancelado en SAT (estatus=0) que no aparece en ningún move de Odoo.
        Sub-caso B: UUID cancelado en SAT (estatus=0) pero el move en Odoo está 'posted'.
        """
        info_list = []
        cr = self.env.cr
        move_audit_analysis_check_list = []
        cfdi_txt_metadata = self.env['cfdi.txt.metadata']
        account_move = self.env['account.move']
        records_cancel_sat_no_odoo = 0.0
        amount_cancel_sat_no_odoo = 0.0

        # Sub-caso A: UUID cancelado en SAT sin registro en Odoo
        query_sql = """
SELECT ctm.id, ctm.uuid
  FROM cfdi_txt_metadata ctm
 WHERE ctm.uuid NOT IN (
    SELECT am.l10n_mx_edi_cfdi_uuid
      FROM account_move am
      LEFT JOIN wizard_audit_analysis_invoice_rel war ON war.move_id = am.id
      LEFT JOIN move_audit_analysis maa ON maa.id = war.audit_id
     WHERE maa.id = %s
       AND am.l10n_mx_edi_cfdi_uuid IS NOT NULL
 )
   AND ctm.analysis_id = %s
   AND ctm.estatus = '0'
GROUP BY ctm.id, ctm.uuid
""" % (self.id, self.id)
        cr.execute(query_sql)
        cr_res = cr.fetchall()
        if cr_res and cr_res[0] and cr_res[0][0]:
            for line_br in cfdi_txt_metadata.browse([x[0] for x in cr_res]):
                xvals = self._build_metadata_xvals(line_br)
                records_cancel_sat_no_odoo += 1
                amount_cancel_sat_no_odoo += xvals['monto']
                info_list.append(xvals)
                move_audit_analysis_check_list.append((0, 0, xvals))

        # Sub-caso B: UUID cancelado en SAT pero el move en Odoo está vigente (posted)
        query_sql = """
SELECT am.id, am.l10n_mx_edi_cfdi_uuid
    FROM account_move am
    LEFT JOIN wizard_audit_analysis_invoice_rel war ON war.move_id = am.id
    LEFT JOIN move_audit_analysis maa ON maa.id = war.audit_id
WHERE am.l10n_mx_edi_cfdi_uuid IN (
        SELECT ctm.uuid
          FROM cfdi_txt_metadata ctm
         WHERE ctm.analysis_id = %s
           AND ctm.estatus = '0'
    )
  AND maa.id = %s
  AND am.state = 'posted'
GROUP BY am.id, am.l10n_mx_edi_cfdi_uuid
""" % (self.id, self.id)
        cr.execute(query_sql)
        cr_res = cr.fetchall()
        if cr_res and cr_res[0] and cr_res[0][0]:
            for line_br in account_move.browse([x[0] for x in cr_res]):
                xvals = self._build_invoice_xvals(line_br)
                records_cancel_sat_no_odoo += 1
                amount_cancel_sat_no_odoo += xvals['monto']
                info_list.append(xvals)
                move_audit_analysis_check_list.append((0, 0, xvals))

        self.write({
            'records_cancel_sat_no_odoo': records_cancel_sat_no_odoo,
            'amount_cancel_sat_no_odoo': amount_cancel_sat_no_odoo,
        })
        if self._context.get('compute_resumen'):
            self.write({'records_cancel_sat_no_odoo_ids': move_audit_analysis_check_list})
        return info_list

    def get_info_list_posted_odoo_no_sat(self):
        """
        Caso 3 – Vigentes en Odoo pero NO en SAT.
        Sub-caso A: UUID vigente en Odoo que no aparece en metadatos.
        Sub-caso B: UUID vigente en Odoo que en SAT está cancelado (estatus=0).
        """
        info_list = []
        cr = self.env.cr
        move_audit_analysis_check_list = []
        cfdi_txt_metadata = self.env['cfdi.txt.metadata']
        account_move = self.env['account.move']
        records_posted_odoo_no_sat = 0.0
        amount_posted_odoo_no_sat = 0.0

        # Sub-caso A: UUID vigente en Odoo sin registro en metadatos
        query_sql = """
SELECT am.id, am.l10n_mx_edi_cfdi_uuid
    FROM account_move am
    LEFT JOIN wizard_audit_analysis_invoice_rel war ON war.move_id = am.id
    LEFT JOIN move_audit_analysis maa ON maa.id = war.audit_id
WHERE am.l10n_mx_edi_cfdi_uuid IS NOT NULL
  AND am.l10n_mx_edi_cfdi_uuid NOT IN (
        SELECT ctm.uuid
          FROM cfdi_txt_metadata ctm
         WHERE ctm.analysis_id = %s
    )
  AND maa.id = %s
  AND am.state = 'posted'
GROUP BY am.id, am.l10n_mx_edi_cfdi_uuid
""" % (self.id, self.id)
        cr.execute(query_sql)
        cr_res = cr.fetchall()
        if cr_res and cr_res[0] and cr_res[0][0]:
            for line_br in account_move.browse([x[0] for x in cr_res]):
                xvals = self._build_invoice_xvals(line_br)
                records_posted_odoo_no_sat += 1
                amount_posted_odoo_no_sat += xvals['monto']
                info_list.append(xvals)
                move_audit_analysis_check_list.append((0, 0, xvals))

        # Sub-caso B: UUID vigente en Odoo pero cancelado en SAT
        query_sql = """
SELECT ctm.id, ctm.uuid
  FROM cfdi_txt_metadata ctm
 WHERE ctm.uuid IN (
    SELECT am.l10n_mx_edi_cfdi_uuid
      FROM account_move am
      LEFT JOIN wizard_audit_analysis_invoice_rel war ON war.move_id = am.id
      LEFT JOIN move_audit_analysis maa ON maa.id = war.audit_id
     WHERE maa.id = %s
       AND am.state = 'posted'
       AND am.l10n_mx_edi_cfdi_uuid IS NOT NULL
 )
   AND ctm.analysis_id = %s
   AND ctm.estatus = '0'
""" % (self.id, self.id)
        cr.execute(query_sql)
        cr_res = cr.fetchall()
        if cr_res and cr_res[0] and cr_res[0][0]:
            for line_br in cfdi_txt_metadata.browse([x[0] for x in cr_res]):
                xvals = self._build_metadata_xvals(line_br)
                records_posted_odoo_no_sat += 1
                amount_posted_odoo_no_sat += xvals['monto']
                info_list.append(xvals)
                move_audit_analysis_check_list.append((0, 0, xvals))

        self.write({
            'records_posted_odoo_no_sat': records_posted_odoo_no_sat,
            'amount_posted_odoo_no_sat': amount_posted_odoo_no_sat,
        })
        if self._context.get('compute_resumen'):
            self.write({'records_posted_odoo_no_sat_ids': move_audit_analysis_check_list})
        return info_list

    def get_info_list_posted_sat_no_odoo(self):
        """
        Caso 4 – Vigentes en SAT pero NO en Odoo.
        Sub-caso A: UUID vigente en SAT (estatus=1) sin ningún move en Odoo.
        Sub-caso B: UUID vigente en SAT pero el move en Odoo está cancelado.
        """
        info_list = []
        cr = self.env.cr
        move_audit_analysis_check_list = []
        cfdi_txt_metadata = self.env['cfdi.txt.metadata']
        account_move = self.env['account.move']
        records_posted_sat_no_odoo = 0.0
        amount_posted_sat_no_odoo = 0.0

        # Sub-caso A: UUID vigente en SAT sin registro en Odoo
        query_sql = """
SELECT ctm.id, ctm.uuid
  FROM cfdi_txt_metadata ctm
 WHERE ctm.uuid NOT IN (
    SELECT am.l10n_mx_edi_cfdi_uuid
      FROM account_move am
      LEFT JOIN wizard_audit_analysis_invoice_rel war ON war.move_id = am.id
      LEFT JOIN move_audit_analysis maa ON maa.id = war.audit_id
     WHERE maa.id = %s
       AND am.l10n_mx_edi_cfdi_uuid IS NOT NULL
 )
   AND ctm.analysis_id = %s
   AND ctm.estatus = '1'
GROUP BY ctm.id, ctm.uuid
""" % (self.id, self.id)
        cr.execute(query_sql)
        cr_res = cr.fetchall()
        if cr_res and cr_res[0] and cr_res[0][0]:
            for line_br in cfdi_txt_metadata.browse([x[0] for x in cr_res]):
                xvals = self._build_metadata_xvals(line_br)
                records_posted_sat_no_odoo += 1
                amount_posted_sat_no_odoo += xvals['monto']
                info_list.append(xvals)
                move_audit_analysis_check_list.append((0, 0, xvals))

        # Sub-caso B: UUID vigente en SAT pero el move en Odoo está cancelado
        query_sql = """
SELECT am.id, am.l10n_mx_edi_cfdi_uuid
    FROM account_move am
    LEFT JOIN wizard_audit_analysis_invoice_rel war ON war.move_id = am.id
    LEFT JOIN move_audit_analysis maa ON maa.id = war.audit_id
WHERE am.l10n_mx_edi_cfdi_uuid IN (
        SELECT ctm.uuid
          FROM cfdi_txt_metadata ctm
         WHERE ctm.analysis_id = %s
           AND ctm.estatus = '1'
    )
  AND maa.id = %s
  AND am.state = 'cancel'
GROUP BY am.id, am.l10n_mx_edi_cfdi_uuid
""" % (self.id, self.id)
        cr.execute(query_sql)
        cr_res = cr.fetchall()
        if cr_res and cr_res[0] and cr_res[0][0]:
            for line_br in account_move.browse([x[0] for x in cr_res]):
                xvals = self._build_invoice_xvals(line_br)
                records_posted_sat_no_odoo += 1
                amount_posted_sat_no_odoo += xvals['monto']
                info_list.append(xvals)
                move_audit_analysis_check_list.append((0, 0, xvals))

        self.write({
            'records_posted_sat_no_odoo': records_posted_sat_no_odoo,
            'amount_posted_sat_no_odoo': amount_posted_sat_no_odoo,
        })
        if self._context.get('compute_resumen'):
            self.write({'records_posted_sat_no_odoo_ids': move_audit_analysis_check_list})
        return info_list

    # ------------------------------------------------------------------
    # Queries SQL de resumen
    # ------------------------------------------------------------------
    def get_query_for_customers(self, analysis_id):
        start_date = str(self.start_date)
        end_date = str(self.end_date)
        company_id = self.company_ids[0].id
        query_sql = """
WITH sat_results AS (
    SELECT
        COUNT(*) AS total_facturas,
        COALESCE(SUM(monto), 0) AS importe_sin_iva,
        COALESCE(COUNT(CASE WHEN estatus IN ('1') THEN 1 ELSE NULL END), 0)       AS facturas_vigentes_auditor,
        COALESCE(SUM(CASE WHEN estatus IN ('1') THEN monto ELSE 0 END), 0)        AS importe_vigente_auditor,
        COALESCE(COUNT(CASE WHEN estatus IN ('0','2') THEN 1 ELSE NULL END), 0)   AS facturas_canceladas_auditor,
        COALESCE(SUM(CASE WHEN estatus IN ('0','2') THEN monto ELSE 0 END), 0)    AS importe_cancelado_auditor
    FROM cfdi_txt_metadata mtdttxt
    JOIN res_company     rc       ON rc.id           = mtdttxt.company_id
    JOIN res_partner     rp_mtdt ON rc.partner_id    = rp_mtdt.id
    WHERE mtdttxt.efecto_comprobante IN ('INGRESO', 'I')
      AND mtdttxt.rfc_emisor = rp_mtdt.vat
      AND mtdttxt.analysis_id = %s
),
odoo_results AS (
    SELECT
        COUNT(*) AS total_facturas,
        COALESCE(SUM(amount_total), 0) AS importe_sin_iva,
        COALESCE(COUNT(CASE WHEN state = 'posted' THEN 1 ELSE NULL END), 0)       AS facturas_vigentes_odoo,
        COALESCE(SUM(CASE WHEN state = 'posted' THEN amount_total ELSE 0 END), 0) AS importe_vigente_odoo,
        COALESCE(COUNT(CASE WHEN state = 'cancel' THEN 1 ELSE NULL END), 0)       AS facturas_canceladas_odoo,
        COALESCE(SUM(CASE WHEN state = 'cancel' THEN amount_total ELSE 0 END), 0) AS importe_cancelado_odoo
    FROM account_move
    WHERE move_type = 'out_invoice'
      AND invoice_date BETWEEN '%s'::date AND '%s'::date
      AND company_id = %s
      AND l10n_mx_edi_cfdi_uuid IS NOT NULL
)
SELECT 'SAT (Auditor)' AS descripcion,
       sat_results.total_facturas, sat_results.importe_sin_iva,
       sat_results.facturas_vigentes_auditor AS facturas_vigentes,
       sat_results.importe_vigente_auditor   AS importe_vigente,
       sat_results.facturas_canceladas_auditor AS facturas_canceladas,
       sat_results.importe_cancelado_auditor   AS importe_cancelado
FROM sat_results
UNION ALL
SELECT 'Odoo (Facturas)' AS descripcion,
       odoo_results.total_facturas, odoo_results.importe_sin_iva,
       odoo_results.facturas_vigentes_odoo   AS facturas_vigentes,
       odoo_results.importe_vigente_odoo     AS importe_vigente,
       odoo_results.facturas_canceladas_odoo AS facturas_canceladas,
       odoo_results.importe_cancelado_odoo   AS importe_cancelado
FROM odoo_results
UNION ALL
SELECT 'Diferencia' AS descripcion,
       sat_results.total_facturas           - odoo_results.total_facturas,
       sat_results.importe_sin_iva          - odoo_results.importe_sin_iva,
       sat_results.facturas_vigentes_auditor  - odoo_results.facturas_vigentes_odoo,
       sat_results.importe_vigente_auditor    - odoo_results.importe_vigente_odoo,
       sat_results.facturas_canceladas_auditor - odoo_results.facturas_canceladas_odoo,
       sat_results.importe_cancelado_auditor   - odoo_results.importe_cancelado_odoo
FROM sat_results, odoo_results;
""" % (analysis_id, start_date, end_date, company_id)
        return query_sql

    def get_query_for_suppliers(self, analysis_id):
        start_date = str(self.start_date)
        end_date = str(self.end_date)
        company_id = self.company_ids[0].id
        query_sql = """
WITH sat_results AS (
    SELECT
        COUNT(*) AS total_facturas,
        COALESCE(SUM(monto), 0) AS importe_sin_iva,
        COALESCE(COUNT(CASE WHEN estatus IN ('1') THEN 1 ELSE NULL END), 0)       AS facturas_vigentes_auditor,
        COALESCE(SUM(CASE WHEN estatus IN ('1') THEN monto ELSE 0 END), 0)        AS importe_vigente_auditor,
        COALESCE(COUNT(CASE WHEN estatus IN ('0','2') THEN 1 ELSE NULL END), 0)   AS facturas_canceladas_auditor,
        COALESCE(SUM(CASE WHEN estatus IN ('0','2') THEN monto ELSE 0 END), 0)    AS importe_cancelado_auditor
    FROM cfdi_txt_metadata mtdttxt
    JOIN res_company     rc       ON rc.id           = mtdttxt.company_id
    JOIN res_partner     rp_mtdt ON rc.partner_id    = rp_mtdt.id
    WHERE mtdttxt.efecto_comprobante IN ('INGRESO', 'I')
      AND mtdttxt.rfc_receptor = rp_mtdt.vat
      AND mtdttxt.analysis_id = %s
),
odoo_results AS (
    SELECT
        COUNT(*) AS total_facturas,
        COALESCE(SUM(amount_total), 0) AS importe_sin_iva,
        COALESCE(COUNT(CASE WHEN state = 'posted' THEN 1 ELSE NULL END), 0)       AS facturas_vigentes_odoo,
        COALESCE(SUM(CASE WHEN state = 'posted' THEN amount_total ELSE 0 END), 0) AS importe_vigente_odoo,
        COALESCE(COUNT(CASE WHEN state = 'cancel' THEN 1 ELSE NULL END), 0)       AS facturas_canceladas_odoo,
        COALESCE(SUM(CASE WHEN state = 'cancel' THEN amount_total ELSE 0 END), 0) AS importe_cancelado_odoo
    FROM account_move
    WHERE move_type = 'in_invoice'
      AND invoice_date BETWEEN '%s'::date AND '%s'::date
      AND company_id = %s
      AND l10n_mx_edi_cfdi_uuid IS NOT NULL
)
SELECT 'SAT (Auditor)' AS descripcion,
       sat_results.total_facturas, sat_results.importe_sin_iva,
       sat_results.facturas_vigentes_auditor AS facturas_vigentes,
       sat_results.importe_vigente_auditor   AS importe_vigente,
       sat_results.facturas_canceladas_auditor AS facturas_canceladas,
       sat_results.importe_cancelado_auditor   AS importe_cancelado
FROM sat_results
UNION ALL
SELECT 'Odoo (Facturas)' AS descripcion,
       odoo_results.total_facturas, odoo_results.importe_sin_iva,
       odoo_results.facturas_vigentes_odoo   AS facturas_vigentes,
       odoo_results.importe_vigente_odoo     AS importe_vigente,
       odoo_results.facturas_canceladas_odoo AS facturas_canceladas,
       odoo_results.importe_cancelado_odoo   AS importe_cancelado
FROM odoo_results
UNION ALL
SELECT 'Diferencia' AS descripcion,
       sat_results.total_facturas            - odoo_results.total_facturas,
       sat_results.importe_sin_iva           - odoo_results.importe_sin_iva,
       sat_results.facturas_vigentes_auditor   - odoo_results.facturas_vigentes_odoo,
       sat_results.importe_vigente_auditor     - odoo_results.importe_vigente_odoo,
       sat_results.facturas_canceladas_auditor - odoo_results.facturas_canceladas_odoo,
       sat_results.importe_cancelado_auditor   - odoo_results.importe_cancelado_odoo
FROM sat_results, odoo_results;
""" % (analysis_id, start_date, end_date, company_id)
        return query_sql

    def get_invoice_ids(self):
        start_date = str(self.start_date)
        end_date = str(self.end_date)
        company_id = self.company_ids[0].id
        move_type = 'out_invoice' if self.report_type == 'customers' else 'in_invoice'
        query_sql = """
SELECT account_move.id
  FROM account_move
 WHERE move_type = '%s'
   AND invoice_date BETWEEN '%s'::date AND '%s'::date
   AND company_id = %s
   AND l10n_mx_edi_cfdi_uuid IS NOT NULL
""" % (move_type, start_date, end_date, company_id)
        cr = self.env.cr
        cr.execute(query_sql)
        cr_res = cr.fetchall()
        if cr_res and cr_res[0] and cr_res[0][0]:
            return [x[0] for x in cr_res]
        return []


# ─────────────────────────────────────────────────────────────────
# ASISTENTE (WIZARD): wizard.audit.analysis
# ─────────────────────────────────────────────────────────────────
class WizardAuditAnalysis(models.TransientModel):
    """
    Asistente para generar el análisis de auditoría.
    Cambiado de models.Model a models.TransientModel para seguir
    las buenas prácticas de Odoo 18 con wizards.
    """
    _name = 'wizard.audit.analysis'
    _description = "Asistente - Análisis de Auditoría (Metadatos SAT)"

    def _get_company_defaults(self):
        return [(6, 0, self.env.companies.ids)]

    # Campos para exportar archivo (compatibilidad con versiones anteriores)
    datas_fname = fields.Char('File Name', size=256)
    file = fields.Binary('Layout')
    download_file = fields.Boolean('Descargar Archivo')

    company_ids = fields.Many2many(
        'res.company',
        'wizard_analysis_auditor_company_rel', 'wizard_id', 'company_id',
        string='Compañías',
        default=_get_company_defaults,
        required=True,
    )

    start_date = fields.Date("Fecha Inicio", help="Fecha inicial", required=True)
    end_date = fields.Date("Fecha Final", help="Fecha final", required=True)

    report_type = fields.Selection([
        ('customers', 'Clientes'),
        ('suppliers', 'Proveedores'),
    ], string="Tipo de Reporte", required=True, default='customers')

    zip_datas_fname = fields.Char('Zip Metadatos', size=256)
    zip_file = fields.Binary('UUID Zip (Metadatos)', required=True)

    # ------------------------------------------------------------------
    # Validaciones
    # ------------------------------------------------------------------
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.end_date < rec.start_date:
                raise UserError(_("La fecha final no puede ser anterior a la fecha inicial."))

    # ------------------------------------------------------------------
    # Métodos auxiliares
    # ------------------------------------------------------------------
    def fix_date(self, date_val, hours, hour, minute, second):
        """Normaliza la hora de una fecha dada y aplica un offset de horas."""
        fixed_date = datetime.strptime(str(date_val), "%Y-%m-%d %H:%M:%S")
        fixed_date = fixed_date.replace(hour=hour, minute=minute, second=second)
        return fixed_date + timedelta(hours=hours)

    def get_name_from_translation(self, term_dict_str):
        """Extrae el nombre localizado desde un dict de traducciones."""
        if not term_dict_str:
            return ""
        if isinstance(term_dict_str, str):
            term_dict = ast.literal_eval(term_dict_str)
        else:
            term_dict = term_dict_str
        return term_dict.get('es_MX') or term_dict.get('es') or term_dict.get('en_US', "")

    def get_invoice_ids(self):
        """Devuelve los IDs de facturas en el rango de fechas con UUID."""
        start_date = str(self.start_date)
        end_date = str(self.end_date)
        company_id = self.company_ids[0].id
        move_type = 'out_invoice' if self.report_type == 'customers' else 'in_invoice'
        query_sql = """
SELECT account_move.id
  FROM account_move
 WHERE move_type = '%s'
   AND invoice_date BETWEEN '%s'::date AND '%s'::date
   AND company_id = %s
   AND l10n_mx_edi_cfdi_uuid IS NOT NULL
""" % (move_type, start_date, end_date, company_id)
        cr = self.env.cr
        cr.execute(query_sql)
        cr_res = cr.fetchall()
        if cr_res and cr_res[0] and cr_res[0][0]:
            return [x[0] for x in cr_res]
        return []

    def get_query_for_customers(self, analysis_id):
        start_date = str(self.start_date)
        end_date = str(self.end_date)
        company_id = self.company_ids[0].id
        query_sql = """
WITH sat_results AS (
    SELECT
        COUNT(*) AS total_facturas,
        COALESCE(SUM(monto), 0) AS importe_sin_iva,
        COALESCE(COUNT(CASE WHEN estatus IN ('1') THEN 1 ELSE NULL END), 0)       AS facturas_vigentes_auditor,
        COALESCE(SUM(CASE WHEN estatus IN ('1') THEN monto ELSE 0 END), 0)        AS importe_vigente_auditor,
        COALESCE(COUNT(CASE WHEN estatus IN ('0','2') THEN 1 ELSE NULL END), 0)   AS facturas_canceladas_auditor,
        COALESCE(SUM(CASE WHEN estatus IN ('0','2') THEN monto ELSE 0 END), 0)    AS importe_cancelado_auditor
    FROM cfdi_txt_metadata mtdttxt
    JOIN res_company     rc       ON rc.id           = mtdttxt.company_id
    JOIN res_partner     rp_mtdt ON rc.partner_id    = rp_mtdt.id
    WHERE mtdttxt.efecto_comprobante IN ('INGRESO', 'I')
      AND mtdttxt.rfc_emisor = rp_mtdt.vat
      AND mtdttxt.analysis_id = %s
),
odoo_results AS (
    SELECT
        COUNT(*) AS total_facturas,
        COALESCE(SUM(amount_total), 0) AS importe_sin_iva,
        COALESCE(COUNT(CASE WHEN state = 'posted' THEN 1 ELSE NULL END), 0)       AS facturas_vigentes_odoo,
        COALESCE(SUM(CASE WHEN state = 'posted' THEN amount_total ELSE 0 END), 0) AS importe_vigente_odoo,
        COALESCE(COUNT(CASE WHEN state = 'cancel' THEN 1 ELSE NULL END), 0)       AS facturas_canceladas_odoo,
        COALESCE(SUM(CASE WHEN state = 'cancel' THEN amount_total ELSE 0 END), 0) AS importe_cancelado_odoo
    FROM account_move
    WHERE move_type = 'out_invoice'
      AND invoice_date BETWEEN '%s'::date AND '%s'::date
      AND company_id = %s
      AND l10n_mx_edi_cfdi_uuid IS NOT NULL
)
SELECT 'SAT (Auditor)' AS descripcion,
       sat_results.total_facturas, sat_results.importe_sin_iva,
       sat_results.facturas_vigentes_auditor AS facturas_vigentes,
       sat_results.importe_vigente_auditor   AS importe_vigente,
       sat_results.facturas_canceladas_auditor AS facturas_canceladas,
       sat_results.importe_cancelado_auditor   AS importe_cancelado
FROM sat_results
UNION ALL
SELECT 'Odoo (Facturas)' AS descripcion,
       odoo_results.total_facturas, odoo_results.importe_sin_iva,
       odoo_results.facturas_vigentes_odoo   AS facturas_vigentes,
       odoo_results.importe_vigente_odoo     AS importe_vigente,
       odoo_results.facturas_canceladas_odoo AS facturas_canceladas,
       odoo_results.importe_cancelado_odoo   AS importe_cancelado
FROM odoo_results
UNION ALL
SELECT 'Diferencia' AS descripcion,
       sat_results.total_facturas            - odoo_results.total_facturas,
       sat_results.importe_sin_iva           - odoo_results.importe_sin_iva,
       sat_results.facturas_vigentes_auditor   - odoo_results.facturas_vigentes_odoo,
       sat_results.importe_vigente_auditor     - odoo_results.importe_vigente_odoo,
       sat_results.facturas_canceladas_auditor - odoo_results.facturas_canceladas_odoo,
       sat_results.importe_cancelado_auditor   - odoo_results.importe_cancelado_odoo
FROM sat_results, odoo_results;
""" % (analysis_id, start_date, end_date, company_id)
        return query_sql

    def get_query_for_suppliers(self, analysis_id):
        start_date = str(self.start_date)
        end_date = str(self.end_date)
        company_id = self.company_ids[0].id
        query_sql = """
WITH sat_results AS (
    SELECT
        COUNT(*) AS total_facturas,
        COALESCE(SUM(monto), 0) AS importe_sin_iva,
        COALESCE(COUNT(CASE WHEN estatus IN ('1') THEN 1 ELSE NULL END), 0)       AS facturas_vigentes_auditor,
        COALESCE(SUM(CASE WHEN estatus IN ('1') THEN monto ELSE 0 END), 0)        AS importe_vigente_auditor,
        COALESCE(COUNT(CASE WHEN estatus IN ('0','2') THEN 1 ELSE NULL END), 0)   AS facturas_canceladas_auditor,
        COALESCE(SUM(CASE WHEN estatus IN ('0','2') THEN monto ELSE 0 END), 0)    AS importe_cancelado_auditor
    FROM cfdi_txt_metadata mtdttxt
    JOIN res_company     rc       ON rc.id           = mtdttxt.company_id
    JOIN res_partner     rp_mtdt ON rc.partner_id    = rp_mtdt.id
    WHERE mtdttxt.efecto_comprobante IN ('INGRESO', 'I')
      AND mtdttxt.rfc_receptor = rp_mtdt.vat
      AND mtdttxt.analysis_id = %s
),
odoo_results AS (
    SELECT
        COUNT(*) AS total_facturas,
        COALESCE(SUM(amount_total), 0) AS importe_sin_iva,
        COALESCE(COUNT(CASE WHEN state = 'posted' THEN 1 ELSE NULL END), 0)       AS facturas_vigentes_odoo,
        COALESCE(SUM(CASE WHEN state = 'posted' THEN amount_total ELSE 0 END), 0) AS importe_vigente_odoo,
        COALESCE(COUNT(CASE WHEN state = 'cancel' THEN 1 ELSE NULL END), 0)       AS facturas_canceladas_odoo,
        COALESCE(SUM(CASE WHEN state = 'cancel' THEN amount_total ELSE 0 END), 0) AS importe_cancelado_odoo
    FROM account_move
    WHERE move_type = 'in_invoice'
      AND invoice_date BETWEEN '%s'::date AND '%s'::date
      AND company_id = %s
      AND l10n_mx_edi_cfdi_uuid IS NOT NULL
)
SELECT 'SAT (Auditor)' AS descripcion,
       sat_results.total_facturas, sat_results.importe_sin_iva,
       sat_results.facturas_vigentes_auditor AS facturas_vigentes,
       sat_results.importe_vigente_auditor   AS importe_vigente,
       sat_results.facturas_canceladas_auditor AS facturas_canceladas,
       sat_results.importe_cancelado_auditor   AS importe_cancelado
FROM sat_results
UNION ALL
SELECT 'Odoo (Facturas)' AS descripcion,
       odoo_results.total_facturas, odoo_results.importe_sin_iva,
       odoo_results.facturas_vigentes_odoo   AS facturas_vigentes,
       odoo_results.importe_vigente_odoo     AS importe_vigente,
       odoo_results.facturas_canceladas_odoo AS facturas_canceladas,
       odoo_results.importe_cancelado_odoo   AS importe_cancelado
FROM odoo_results
UNION ALL
SELECT 'Diferencia' AS descripcion,
       sat_results.total_facturas            - odoo_results.total_facturas,
       sat_results.importe_sin_iva           - odoo_results.importe_sin_iva,
       sat_results.facturas_vigentes_auditor   - odoo_results.facturas_vigentes_odoo,
       sat_results.importe_vigente_auditor     - odoo_results.importe_vigente_odoo,
       sat_results.facturas_canceladas_auditor - odoo_results.facturas_canceladas_odoo,
       sat_results.importe_cancelado_auditor   - odoo_results.importe_cancelado_odoo
FROM sat_results, odoo_results;
""" % (analysis_id, start_date, end_date, company_id)
        return query_sql

    # ------------------------------------------------------------------
    # Carga del ZIP con metadatos TXT del SAT
    # ------------------------------------------------------------------
    def _load_zip_metadata(self, move_audit_analysis_id):
        """
        Lee el ZIP de metadatos descargado del portal del SAT,
        parsea cada archivo .txt y crea registros en cfdi.txt.metadata.
        """
        if not self.zip_datas_fname or not self.zip_datas_fname.lower().endswith('.zip'):
            raise UserError(_('Solo se permiten archivos con extensión .zip'))

        file_content = base64.b64decode(self.zip_file)
        zip_file = BytesIO(file_content)

        company_obj = self.env['res.company'].sudo()
        company_rfcs = [c.vat for c in self.company_ids]

        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                txt_files = [n for n in zip_ref.namelist() if n.lower().endswith('.txt')]
                if not txt_files:
                    raise UserError(_('El archivo ZIP no contiene archivos .txt'))

                all_data = []
                for txt_file in txt_files:
                    with zip_ref.open(txt_file) as fh:
                        content = fh.read().decode('utf-8')
                        lines = content.strip().split('\n')
                        headers = lines[0].split('~')
                        for line in lines[1:]:
                            values = line.split('~')
                            raw_dict = dict(zip(headers, values))
                            # Limpiar caracteres de retorno de carro
                            clean_dict = {
                                k.replace('\r', ''): v.replace('\r', '')
                                for k, v in raw_dict.items()
                            }
                            clean_dict['Monto'] = float(clean_dict.get('Monto', 0) or 0)
                            # Tomar solo la parte de fecha (YYYY-MM-DD)
                            clean_dict['FechaEmision'] = str(
                                clean_dict.get('FechaEmision', ''))[:10] or None
                            clean_dict['FechaCertificacionSat'] = str(
                                clean_dict.get('FechaCertificacionSat', ''))[:10] or None
                            fecha_cancelacion = clean_dict.get('FechaCancelacion', '')
                            clean_dict['FechaCancelacion'] = str(
                                fecha_cancelacion)[:10] if fecha_cancelacion else None

                            # Determinar empresa según tipo de reporte
                            rfc_emisor = clean_dict.get('RfcEmisor', '')
                            rfc_receptor = clean_dict.get('RfcReceptor', '')
                            company_id = False
                            if self.report_type == 'customers':
                                if rfc_emisor not in company_rfcs:
                                    raise UserError(_(
                                        "El RFC Emisor %s no corresponde a ninguna de las "
                                        "compañías del asistente.") % rfc_emisor)
                                company_rec = company_obj.search(
                                    [('vat', '=', rfc_emisor)], limit=1)
                                company_id = company_rec.id if company_rec else False
                            else:
                                if rfc_receptor not in company_rfcs:
                                    raise UserError(_(
                                        "El RFC Receptor %s no corresponde a ninguna de las "
                                        "compañías del asistente.") % rfc_receptor)
                                company_rec = company_obj.search(
                                    [('vat', '=', rfc_receptor)], limit=1)
                                company_id = company_rec.id if company_rec else False

                            clean_dict['company_id'] = company_id
                            all_data.append(clean_dict)

                # Persistir solo registros de tipo Ingreso
                for data in all_data:
                    if data.get('EfectoComprobante') != 'I':
                        continue
                    rfc_pac = data.get('RfcPac') or data.get('PacCertifico') or ''
                    self.env['cfdi.txt.metadata'].create({
                        'uuid': data.get('Uuid', ''),
                        'rfc_emisor': data.get('RfcEmisor', ''),
                        'nombre_emisor': data.get('NombreEmisor', ''),
                        'rfc_receptor': data.get('RfcReceptor', ''),
                        'nombre_receptor': data.get('NombreReceptor', ''),
                        'rfc_pac': rfc_pac,
                        'fecha_emision': data.get('FechaEmision') or False,
                        'fecha_certificacion_sat': data.get('FechaCertificacionSat') or False,
                        'monto': data.get('Monto', 0.0),
                        'efecto_comprobante': data.get('EfectoComprobante', ''),
                        'estatus': data.get('Estatus', ''),
                        'fecha_cancelacion': data.get('FechaCancelacion') or False,
                        'company_id': data.get('company_id', False),
                        'analysis_id': move_audit_analysis_id.id,
                    })
        except zipfile.BadZipFile:
            raise UserError(_('El archivo proporcionado no es un archivo ZIP válido.'))

    # ------------------------------------------------------------------
    # Acción principal del wizard
    # ------------------------------------------------------------------
    def execute_report(self):
        cr = self.env.cr
        move_audit_analysis = self.env['move.audit.analysis']

        account_invoice_ids = self.get_invoice_ids()

        analysis_vals = {
            'company_ids': [(6, 0, self.company_ids.ids)],
            'start_date': self.start_date,
            'end_date': self.end_date,
            'report_type': self.report_type,
            'zip_datas_fname': self.zip_datas_fname,
            'zip_file': self.zip_file,
            'account_invoice_ids': [(6, 0, account_invoice_ids)] if account_invoice_ids else False,
            'hide_resumen': False,
        }
        move_audit_analysis_id = move_audit_analysis.create(analysis_vals)

        # Cargar metadatos del ZIP
        self._load_zip_metadata(move_audit_analysis_id)

        # Ejecutar query de resumen
        if self.report_type == 'customers':
            query_sql = self.get_query_for_customers(move_audit_analysis_id.id)
        else:
            query_sql = self.get_query_for_suppliers(move_audit_analysis_id.id)

        cr.execute(query_sql)
        cr_res = cr.dictfetchall()

        i = 1
        if cr_res and cr_res[0]:
            analysis_lines_ids = []
            for line in cr_res:
                analysis_lines_ids.append((0, 0, {
                    'sequence': i,
                    'name': line.get('descripcion', ''),
                    'total_facturas': line.get('total_facturas', 0),
                    'importe_sin_iva': line.get('importe_sin_iva', 0.0),
                    'facturas_vigentes': line.get('facturas_vigentes', 0),
                    'importe_vigente': line.get('importe_vigente', 0.0),
                    'facturas_canceladas': line.get('facturas_canceladas', 0),
                    'importe_cancelado': line.get('importe_cancelado', 0.0),
                }))
                i += 1
            move_audit_analysis_id.line_ids = analysis_lines_ids

        # Generar los cuatro análisis de discrepancias
        move_audit_analysis_id.with_context(compute_resumen=True).get_info_list_cancel_odoo_no_sat()
        move_audit_analysis_id.with_context(compute_resumen=True).get_info_list_cancel_sat_no_odoo()
        move_audit_analysis_id.with_context(compute_resumen=True).get_info_list_posted_odoo_no_sat()
        move_audit_analysis_id.with_context(compute_resumen=True).get_info_list_posted_sat_no_odoo()

        return {
            'domain': [('id', 'in', [move_audit_analysis_id.id])],
            'name': _('Análisis de la Auditoría'),
            'view_mode': 'list,form',
            'context': {
                'tree_view_ref': 'account_invoice_auditor_analysis.move_audit_analysis_tree_view'
            },
            'res_model': 'move.audit.analysis',
            'type': 'ir.actions.act_window',
        }