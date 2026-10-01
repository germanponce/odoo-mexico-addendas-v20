# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
import xml.etree.ElementTree as ET
import base64
import logging

_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # ───────── "Adjuntar XML" (boton verde) en el pago/REP ─────────
    # Incorporado nativo desde `account_move_advanced` (solo v17). Adjunta el
    # complemento de pago (REP) al pago, subiendolo o eligiendo uno del lote SAT.
    wizard_imported = fields.Boolean("XML Adjuntado por Wizard", copy=False)

    def action_open_upload_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Adjuntar XML'),
            'res_model': 'xml.upload.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payment_id': self.id},
        }

    def fill_xml_values_from_attatchment(self, attachment):
        """Registra el CFDI (REP) adjunto al pago como documento EDI."""
        self.ensure_one()
        if 'l10n_mx_edi.document' in self.env:
            try:
                vals = {
                    'state': 'payment_sent',
                    'datetime': fields.Datetime.now(),
                    'attachment_id': attachment.id,
                }
                if self.move_id:
                    vals['move_id'] = self.move_id.id
                edoc = self.env['l10n_mx_edi.document'].create(vals)
                inv_ids = []
                if self.reconciled_invoice_ids:
                    inv_ids = self.reconciled_invoice_ids.ids
                elif self.reconciled_bill_ids:
                    inv_ids = self.reconciled_bill_ids.ids
                if inv_ids and 'invoice_ids' in edoc._fields:
                    edoc.invoice_ids = [(6, 0, inv_ids)]
            except Exception as e:
                _logger.warning(
                    "Adjuntar XML (pago): no se pudo registrar l10n_mx_edi.document: %s", e)
        self.wizard_imported = True
        return False

    def action_erase_fields(self):
        for pay in self:
            if 'l10n_mx_edi_document_ids' in pay._fields:
                pay.l10n_mx_edi_document_ids.unlink()
            pay.wizard_imported = False


    stored_sat_uuid = fields.Char(
        compute='_get_uuid_from_xml_attachment', 
        string="CFDI UUID", 
        store=True,
        index=True,  # Índice para búsquedas rápidas
    )

    # ════════════════════════════════════════════════════════════════════════
    # ANFEPI v.24: info CFDI para complementos de pago RECIBIDOS (REP proveedor)
    # ════════════════════════════════════════════════════════════════════════
    rep_cfdi_status = fields.Char(
        string="Estado REP",
        compute="_compute_rep_cfdi_status",
        store=True,
        help="Estado del complemento de pago recibido del proveedor.",
    )

    def action_check_sat_received(self):
        """Consulta el estado SAT de un complemento de pago RECIBIDO.
        Usa el servicio ConsultaCFDIService del SAT con el UUID del REP,
        RFC emisor (proveedor) y RFC receptor (nosotros)."""
        self.ensure_one()
        uuid = self.stored_sat_uuid
        if not uuid:
            return
        # Leer RFC emisor y receptor del XML adjunto
        rfc_emisor = ''
        rfc_receptor = ''
        total_str = '0.0'
        xml_attachments = self.attachment_ids.filtered(
            lambda a: a.mimetype in ('application/xml', 'text/xml')
                      or (a.name and a.name.lower().endswith('.xml'))
        )
        for att in xml_attachments:
            try:
                raw = base64.b64decode(att.datas)
                root = ET.fromstring(raw)
                rfc_emisor = root.find('.//{http://www.sat.gob.mx/cfd/4}Emisor')
                if rfc_emisor is None:
                    rfc_emisor = root.find('.//{http://www.sat.gob.mx/cfd/3}Emisor')
                rfc_receptor = root.find('.//{http://www.sat.gob.mx/cfd/4}Receptor')
                if rfc_receptor is None:
                    rfc_receptor = root.find('.//{http://www.sat.gob.mx/cfd/3}Receptor')
                rfc_emisor = rfc_emisor.get('Rfc', '') if rfc_emisor is not None else ''
                rfc_receptor = rfc_receptor.get('Rfc', '') if rfc_receptor is not None else ''
                total_str = root.get('Total', '0.0')
                break
            except Exception:
                continue
        if not rfc_emisor:
            rfc_emisor = self.partner_id.vat or ''
        if not rfc_receptor:
            rfc_receptor = self.company_id.vat or ''
        # Llamar al SAT
        try:
            from zeep import Client
            from zeep.transports import Transport
            url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl'
            params = f'?id={uuid}&re={tools.html_escape(rfc_emisor)}&rr={tools.html_escape(rfc_receptor)}&tt={total_str}'
            transport = Transport(timeout=20)
            client = Client(wsdl=url, transport=transport)
            response = client.service.Consulta(params)
            estado = response.get('Estado', '') if hasattr(response, 'get') else getattr(response, 'Estado', '')
        except Exception as e:
            _logger.warning(f"Error consultando SAT para REP {uuid}: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': 'Error SAT', 'message': str(e), 'type': 'warning', 'sticky': False},
            }
        # Mapear respuesta
        sat_map = {'Vigente': 'valid', 'Cancelado': 'cancelled', 'No Encontrado': 'not_found'}
        sat_state = sat_map.get(estado, 'not_defined')
        # Guardar en el move del pago (campo nativo l10n_mx_edi_cfdi_sat_state)
        if self.move_id:
            self.move_id.l10n_mx_edi_cfdi_sat_state = sat_state
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Estado SAT',
                'message': f'REP {uuid}: {estado}',
                'type': 'success' if estado == 'Vigente' else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    @api.depends("stored_sat_uuid", "partner_type")
    def _compute_rep_cfdi_status(self):
        for rec in self:
            if rec.partner_type == "supplier" and rec.stored_sat_uuid:
                rec.rep_cfdi_status = "Recibido"
            elif rec.partner_type == "supplier":
                rec.rep_cfdi_status = "Pendiente"
            else:
                rec.rep_cfdi_status = False

    # ════════════════════════════════════════════════════════════════════════
    # ANFEPI v.23: control de complementos de pago para facturas PPD
    # ════════════════════════════════════════════════════════════════════════
    is_for_ppd_invoice = fields.Boolean(
        string="Pago de factura PPD",
        compute="_compute_anfepi_payment_complement_flags",
        store=True,
        index=True,
        help="True si el pago esta reconciliado con al menos una factura proveedor "
             "cuya politica de pago es PPD (Pago en Parcialidades o Diferido).",
    )
    has_payment_complement_xml = fields.Boolean(
        string="Tiene XML complemento de pago",
        compute="_compute_anfepi_payment_complement_flags",
        store=True,
        index=True,
        help="True si el pago tiene al menos un attachment XML (complemento de pago "
             "del SAT) adjunto.",
    )
    needs_payment_complement = fields.Boolean(
        string="Falta complemento de pago",
        compute="_compute_anfepi_payment_complement_flags",
        store=True,
        index=True,
        help="True si la factura origen es PPD, esta pagada o en proceso de pago, y "
             "todavia no se adjunto el XML del complemento de pago recibido del "
             "proveedor. Usar el filtro 'Facturas PPD sin Complemento Pago' en la "
             "vista de Pagos a Proveedores.",
    )

    @api.depends(
        "attachment_ids",
        "attachment_ids.mimetype",
        "attachment_ids.name",
        "partner_type",
    )
    def _compute_anfepi_payment_complement_flags(self):
        for rec in self:
            # 1) has_payment_complement_xml: ¿hay attachment XML adjunto?
            has_xml = any(
                (a.mimetype in ("application/xml", "text/xml")) or
                (a.name and a.name.lower().endswith(".xml"))
                for a in rec.attachment_ids
            )
            # 2) is_for_ppd_invoice: ¿alguna factura reconciliada es PPD?
            invoices = rec.reconciled_bill_ids if hasattr(rec, "reconciled_bill_ids") else False
            if not invoices:
                invoices = rec.reconciled_invoice_ids if hasattr(rec, "reconciled_invoice_ids") else False
            is_ppd = False
            paid_or_in_payment = False
            if invoices and rec.partner_type == "supplier":
                for inv in invoices:
                    policy = getattr(inv, "l10n_mx_edi_payment_policy", False)
                    if policy == "PPD":
                        is_ppd = True
                    if getattr(inv, "payment_state", "") in ("paid", "in_payment", "partial"):
                        paid_or_in_payment = True
            rec.has_payment_complement_xml = has_xml
            rec.is_for_ppd_invoice = is_ppd
            # 3) needs_payment_complement: PPD + pagada/in_payment + sin XML
            rec.needs_payment_complement = is_ppd and paid_or_in_payment and not has_xml

    @api.depends('attachment_ids')
    def _get_uuid_from_xml_attachment(self):
        for record in self:
            # OPTIMIZACIÓN: Filtrar XMLs directamente
            xml_attachments = record.attachment_ids.filtered(
                lambda x: (x.mimetype in ('application/xml','text/xml','text/plain') or (x.name and x.name.lower().endswith('.xml'))) and (x.name and x.name.lower().endswith('.xml'))
            )
            
            if not xml_attachments:
                record.stored_sat_uuid = False
                continue
            
            # Intentar extraer UUID del primer XML válido
            uuid_found = False
            for attachment in xml_attachments:
                try:
                    xml_content = base64.b64decode(attachment.datas)
                    root = ET.fromstring(xml_content)
                    uuid = root.find('.//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital').attrib['UUID']
                    record.stored_sat_uuid = uuid
                    uuid_found = True
                    break
                except Exception:
                    continue
            
            if not uuid_found:
                record.stored_sat_uuid = False

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrescritura de create para soportar creación múltiple de adjuntos.
        Procesa XMLs de pagos para extraer el UUID del complemento de pago.
        OPTIMIZADO: Solo procesa si es XML de account.payment
        """
        # Asegurar que siempre trabajamos con lista
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        # OPTIMIZACIÓN: Verificar ANTES de crear si hay XMLs de pagos
        # para evitar procesamiento innecesario
        # Si el contexto trae no_document=True, estos son adjuntos técnicos
        # (ej. XMLs de lote SAT) — saltar procesamiento por completo
        if self.env.context.get('no_document'):
            return super(IrAttachment, self).create(vals_list)

        has_payment_xml = any(
            vals.get('mimetype') == 'application/xml' and 
            vals.get('res_model') == 'account.payment'
            for vals in vals_list
        )
        
        # Crear los adjuntos
        attachments = super(IrAttachment, self).create(vals_list)
        
        # OPTIMIZACIÓN: Solo procesar si hay XMLs de pagos
        if not has_payment_xml:
            return attachments
        
        # Procesar SOLO adjuntos XML de account.payment
        payment_xmls = attachments.filtered(
            lambda a: a.mimetype == 'application/xml' and a.res_model == 'account.payment'
        )
        
        for attachment in payment_xmls:
            try:
                payment = self.env['account.payment'].browse(attachment.res_id)
                if payment.exists():
                    data = base64.b64decode(attachment.datas)
                    root = ET.fromstring(data)
                    uuid = root.find('.//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital').attrib['UUID']
                    payment.stored_sat_uuid = uuid
            except Exception as e:
                # Silenciar errores de parsing XML para no romper otros adjuntos
                pass
        
        return attachments