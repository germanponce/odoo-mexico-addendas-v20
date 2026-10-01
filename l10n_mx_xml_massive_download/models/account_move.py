# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
import logging

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
import base64
from lxml import etree
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)

# Codigos SAT validos de FormaDePago/FormaDePagoP (CFDI 4.0 + REP 2.0)
_SAT_FORMA_PAGO_CODES = {
    '01','02','03','04','05','06','08','12','13','14','15','17',
    '23','24','25','26','27','28','29','30','31','99',
}
_NS_TFD = '{http://www.sat.gob.mx/TimbreFiscalDigital}'
_NS_PAGOS20 = '{http://www.sat.gob.mx/Pagos20}'

USO_CFDI  = [
    ("G01", "Adquisición de mercancías"),
    ("G02", "Devoluciones, descuentos o bonificaciones"),
    ("G03", "Gastos en general"),
    ("I01", "Construcciones"),
    ("101", "Construcciones"),
    ("I02", "Mobiliario y equipo de oficina por inversiones"),
    ("I03", "Equipo de transporte"),
    ("I04", "Equipo de cómputo y accesorios"),    
    ("105", "Dados, troqueles, moldes, matrices y herramental"),
    ("106", "Comunicaciones telefónicas"),
    ("107", "Comunicaciones satelitales"),
    ("108", "Otra maquinaria y equipo"),
    ("D01", "Honorarios médicos, dentales y gastos hospitalarios"),
    ("D02", "Gastos médicos por incapacidad o discapacidad"),
    ("D03", "Gastos funerales"),
    ("D04", "Donativos"),
    ("D05", "Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación)"),
    ("D06", "Aportaciones voluntarias al SAR"),
    ("D07", "Primas por seguros de gastos médicos"),
    ("D08", "Gastos de transportación escolar obligatoria"),
    ("D09", "Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones"),
    ("D10", "Pagos por servicios educativos (colegiaturas)"),
    ("CP01", "Pagos"),
    ("CN01", "Nómina"),
    ("S01", "Sin Efectos Fiscales"),
]

class AccountMove(models.Model):
    _inherit = 'account.move'

    stored_sat_uuid = fields.Char(
        compute='_get_uuid_from_xml_attachment',
        string="UUID CFDI (extraido)",
        store=True,
        index=True,  # Índice para búsquedas rápidas
        )
    # Inverso de account.edi.downloaded.xml.sat.invoice_id. Sirve como fuente
    # de verdad para el computed xml_imported_id: cualquier XML que apunte a
    # esta factura (creacion desde wizard, matching automatico por UUID,
    # vinculacion manual, REPs, etc.) se refleja aqui sin sincronizacion manual.
    xml_sat_ids = fields.One2many(
        'account.edi.downloaded.xml.sat',
        'invoice_id',
        string="XMLs SAT Vinculados",
    )
    xml_imported_id = fields.Many2one(
        'account.edi.downloaded.xml.sat',
        string="Downloaded XML",
        compute='_compute_xml_imported_id',
        store=True,
        index=True,
        help="XML SAT vinculado a esta factura. Computado a partir del reverse "
             "xml.invoice_id para garantizar consistencia en todos los flujos de "
             "vinculacion (wizard de descarga, matching por UUID, vinculacion "
             "manual, REPs). El boton inteligente 'XML SAT' usa este campo.",
    )

    @api.depends('xml_sat_ids')
    def _compute_xml_imported_id(self):
        for move in self:
            move.xml_imported_id = move.xml_sat_ids[:1].id if move.xml_sat_ids else False
    extract_error_message = fields.Text(string="Error Message", readonly=True, copy=False)
    
    # Campos para sellos digitales y certificados
    sello_cfdi = fields.Text(string="Sello Digital CFDI", readonly=True, copy=False)
    sello_sat = fields.Text(string="Sello Digital SAT", readonly=True, copy=False)
    cadena_original = fields.Text(string="Cadena Original", readonly=True, copy=False)
    certificate_number = fields.Char(string="No. Certificado Emisor", readonly=True, copy=False)
    certificate_sat_number = fields.Char(string="No. Certificado SAT", readonly=True, copy=False)

    payment_method = fields.Selection([('PPD','PPD'),('PUE','PUE')], string='Metodo de Pago (CFDI)')
    uso_sat = fields.Selection(USO_CFDI, string="Uso CFDI")

    # ───────── "Adjuntar XML" (boton verde) ─────────
    # Incorporado de forma nativa desde el modulo aparte `account_move_advanced`
    # (solo v17) por peticion del cliente. Permite adjuntar el CFDI a la factura
    # de proveedor subiendo un .xml o eligiendo uno del lote ya descargado del SAT.
    # Cross-version: el decode usa el helper propio de massive y el registro
    # l10n_mx_edi.document solo se hace donde el modelo existe (17/18/19).
    cfdi_payment_form = fields.Many2one(
        'l10n_mx_edi.payment.method', string="Forma de Pago (CFDI)",
        readonly=True, copy=False,
        help="Forma de pago leida del CFDI adjuntado con 'Adjuntar XML'.")
    wizard_imported = fields.Boolean("XML Adjuntado por Wizard", copy=False)

    def action_open_upload_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Adjuntar XML'),
            'res_model': 'xml.upload.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }

    def action_erase_fields(self):
        for move in self:
            move.payment_method = False
            move.cfdi_payment_form = False
            move.uso_sat = False
            if 'l10n_mx_edi_document_ids' in move._fields:
                move.l10n_mx_edi_document_ids.unlink()
            move.wizard_imported = False

    def action_reset_to_draft(self):
        self.ensure_one()
        if self.move_type in ('in_invoice', 'in_refund') and \
                self.payment_state not in ('paid', 'partial', 'in_payment'):
            self.button_draft()
        else:
            raise UserError(_(
                "Esta factura no se puede regresar a borrador; rompa las "
                "conciliaciones de pago primero."))

    def fill_xml_values_from_attatchment(self, attachment):
        """Registra el CFDI adjunto, valida vs la factura y llena campos fiscales.

        Si hay discrepancia de subtotal (no bloqueante) devuelve la accion del
        wizard de confirmacion; RFC y Total si bloquean (UserError).
        """
        self.ensure_one()
        from lxml.objectify import fromstring as _obj_fromstring
        decoded = base64.b64decode(attachment.datas)
        try:
            cfdi_node = _obj_fromstring(decoded)
        except Exception:
            raise UserError(_("El archivo adjunto no es un XML CFDI valido."))
        info = self._l10n_mx_edi_decode_cfdi_etree(cfdi_node)
        if not info:
            raise UserError(_("No se pudo leer el CFDI del XML adjunto."))
        root = ET.fromstring(decoded)
        tipo = root.get('TipoDeComprobante')
        if tipo not in ('I', 'E'):
            raise UserError(_(
                "El XML debe ser de tipo Ingreso (I) o Egreso (E). Se encontro: %s"
            ) % tipo)

        errors = self._validate_invoice_xml_data(root, info)
        if errors and not self.env.context.get('bypass_validation'):
            return {
                'type': 'ir.actions.act_window',
                'name': _('Confirmar Validacion'),
                'res_model': 'custom.validation.confirm',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_move_id': self.id,
                    'default_attachment_id': attachment.id,
                    'default_errors': '\n'.join(errors),
                },
            }
        if errors:
            self.message_post(
                body=_("Advertencias de validacion del XML:\n%s") % '\n'.join(errors))

        # Registrar el CFDI como documento EDI (v17/18/19; en 15/16 no existe).
        # .94: IDEMPOTENTE + aislado en savepoint. Si la factura YA tiene un
        # documento EDI (estaba vinculada a otro XML), NO crear otro: crear un
        # segundo l10n_mx_edi.document en facturas con CFDI previo hacia que Odoo
        # v19 tronara al flush ("Falta el valor requerido para el campo 'Nombre'
        # en ir.attachment", fuera del try). El XML nuevo igual queda adjunto y los
        # campos se llenan; para REEMPLAZAR el XML usar el boton "Volver a subir XML".
        if 'l10n_mx_edi.document' in self.env:
            existing_edi = (self.l10n_mx_edi_document_ids
                            if 'l10n_mx_edi_document_ids' in self._fields else False)
            if existing_edi:
                _logger.info(
                    "Adjuntar XML: la factura %s ya tiene documento EDI; se omite "
                    "registrar otro (use 'Volver a subir XML' para reemplazar).",
                    self.name or self.id)
            else:
                try:
                    with self.env.cr.savepoint():
                        edoc = self.env['l10n_mx_edi.document'].create({
                            'state': 'invoice_sent',
                            'datetime': fields.Datetime.now(),
                            'attachment_id': attachment.id,
                            'move_id': self.id,
                        })
                        if 'invoice_ids' in edoc._fields:
                            edoc.invoice_ids = [(6, 0, [self.id])]
                except Exception as e:
                    _logger.warning(
                        "Adjuntar XML UUID %s: no se pudo registrar "
                        "l10n_mx_edi.document: %s", info.get('uuid'), e)

        # Llenar campos fiscales desde el XML.
        pm = info.get('payment_method')
        if pm in ('PPD', 'PUE'):
            self.payment_method = pm
        forma = root.get('FormaPago')
        if forma and 'l10n_mx_edi.payment.method' in self.env:
            pf = self.env['l10n_mx_edi.payment.method'].search([('code', '=', forma)], limit=1)
            if pf:
                self.cfdi_payment_form = pf.id
        usage = info.get('usage')
        if usage in {k for k, _v in USO_CFDI}:
            self.uso_sat = usage
        fecha = root.get('Fecha')
        if fecha:
            self.invoice_date = fecha[:10]
        serie = root.get('Serie') or ''
        folio = root.get('Folio') or ''
        self.ref = (serie + '/' if serie else '') + folio
        self.wizard_imported = True
        return False

    def _validate_invoice_xml_data(self, root, info):
        errors = []
        xml_rfc = info.get('supplier_rfc')
        xml_total = float(info.get('amount_total') or 0.0)
        xml_subtotal = float(root.get('SubTotal') or 0.0)
        if self.partner_id and self.partner_id.vat and xml_rfc and \
                self.partner_id.vat != xml_rfc:
            raise UserError(_(
                "El RFC del proveedor en la factura (%s) no coincide con el del "
                "XML (%s).") % (self.partner_id.vat, xml_rfc))
        if round(self.amount_untaxed, 2) != round(xml_subtotal, 2):
            errors.append(_(
                "El subtotal de la factura (%.2f) no coincide con el del XML "
                "(%.2f).") % (self.amount_untaxed, xml_subtotal))
        if round(self.amount_total, 2) != round(xml_total, 2):
            raise UserError(_(
                "El total de la factura (%.2f) no coincide con el del XML "
                "(%.2f).") % (self.amount_total, xml_total))
        return errors


    def action_view_xml_sat(self):
        """Abre el registro XML SAT vinculado a esta factura."""
        self.ensure_one()
        if not self.xml_imported_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.edi.downloaded.xml.sat',
            'res_id': self.xml_imported_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_apply_ieps_in_base_from_move(self):
        """Aplica el flag 'IEPS en la base' sobre ESTA factura (boton del form).
        Wrapper que delega a la accion del XML descargado vinculado.
        Solo admin, solo facturas draft con XML vinculado.
        """
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Esta accion solo esta disponible para Administradores.'))
        xmls = self.env['account.edi.downloaded.xml.sat']
        moves_sin_xml = []
        for move in self:
            if move.xml_imported_id:
                xmls |= move.xml_imported_id
            else:
                moves_sin_xml.append(move.name or str(move.id))
        if not xmls:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'IEPS en la base',
                    'message': f'Ninguna factura tiene XML SAT vinculado. ({len(moves_sin_xml)} sin XML)',
                    'type': 'warning',
                    'sticky': False,
                },
            }
        return xmls.action_apply_ieps_in_base_retroactive()

    """
    Method created to have a field that stores the UUID of the CFDI in the account.move model
    To be able to relate the downloaded xml with the invoice
    OPTIMIZADO: Solo recalcula cuando attachment_ids cambia y filtra XMLs
    """
    @api.depends('attachment_ids')
    def _get_uuid_from_xml_attachment(self):
        for record in self:
            # OPTIMIZACIÓN: Solo procesar facturas de cliente/proveedor
            if record.move_type not in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
                record.stored_sat_uuid = False
                continue
            
            # OPTIMIZACIÓN: Filtrar XMLs directamente
            xml_attachments = record.attachment_ids.filtered(
                lambda x: (x.mimetype in ('application/xml','text/xml','text/plain') or (x.name and x.name.lower().endswith('.xml')))
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
                    continue  # Probar siguiente XML
            
            if not uuid_found:
                record.stored_sat_uuid = False


    # def _get_default_uuid_from_xml_attachment(self):
    #     for record in self:
    #         if not record.stored_sat_uuid:
    #             attachments = record.attachment_ids.filtered(lambda x: (x.mimetype in ('application/xml','text/xml','text/plain')) or (x.name and x.name.lower().endswith('.xml')))
    #             if attachments:
    #                 for attachment in attachments:
    #                     try:
    #                         xml_content = base64.b64decode(attachment.datas)
    #                         root = ET.fromstring(xml_content)
    #                         uuid = root.find('.//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital').attrib['UUID']
    #                         print("UUID: "+str(uuid))
    #                         break
    #                         record.stored_sat_uuid = uuid
    #                     except: 
    #                         record.stored_sat_uuid = False

    @api.constrains('state')
    def onchange_update_downloaded_xml_record(self):
        # OPTIMIZACIÓN CRÍTICA: Solo ejecutar si la factura tiene xml_imported_id
        # Evita ejecutarse en TODAS las facturas del sistema
        for record in self:
            if record.xml_imported_id:
                record.xml_imported_id.sudo().with_context(tracking_disable=True).write({'state': record.state})   

    # This method was moved to DownloadedXmlSat --> delete later 
    def relate_download(self):
        domain = [('state', '=', 'draft')]
        to_relate = self.env['account.edi.downloaded.xml.sat'].search(domain)
        
        for download in to_relate: 
            domain = [('state', 'not in', ['cancel', 'draft']), ('l10n_mx_edi_cfdi_uuid', '=', download.name)]
            move = self.env['account.move'].search(domain)
            if len(move) == 1:
                download.write({'invoice_id':move.id, 'state': move.state})
            else:
                download.write({'state': 'error'})

    def create_edi_document_from_attatchment(self, uuid):
        edi = self.env['l10n_mx_edi.document']
        edi_content = self.attachment_ids.filtered(lambda m: (m.mimetype in ('application/xml','text/xml','text/plain')) or (m.name and m.name.lower().endswith('.xml')))
        if edi_content:
            edi_data = {
                'state' : 'invoice_sent',
                'datetime': fields.Datetime.now(),
                'attachment_uuid':uuid,
                'attachment_id':edi_content.id,
                'move_id': self.id,
            }
            new_edi_doc = edi.create(edi_data)

            # Asociar las facturas
            new_edi_doc.invoice_ids = [(6, 0, [self.id])]  # A lo mejor es aqui, en vez de poner ".invoice_ids" poner payment 


    # This methos was taken from odoo 16.0 
    def _l10n_mx_edi_decode_cfdi(self, cfdi_data=None):
        ''' Helper to extract relevant data from the CFDI to be used, for example, when printing the invoice.
        :param cfdi_data:   The optional cfdi data.
        :return:            A python dictionary.
        '''
        self.ensure_one()

        def is_purchase_move(move):
            return move.move_type in move.get_purchase_types() \
                    or move.payment_id.reconciled_bill_ids

        # Find a signed cfdi.
        if not cfdi_data:
            signed_edi = self._get_l10n_mx_edi_signed_edi_document()
            if signed_edi:
                cfdi_data = base64.decodebytes(signed_edi.sudo().attachment_id.with_context(bin_size=False).datas)

            # For vendor bills, the CFDI XML must be posted in the chatter as an attachment.
            elif is_purchase_move(self) and self.country_code == 'MX' and not self.l10n_mx_edi_cfdi_request:
                attachments = self.attachment_ids.filtered(lambda x: (x.mimetype in ('application/xml','text/xml','text/plain')) or (x.name and x.name.lower().endswith('.xml')))
                if attachments:
                    attachment = sorted(attachments, key=lambda x: x.create_date)[-1]
                    cfdi_data = base64.decodebytes(attachment.with_context(bin_size=False).datas)

        # Nothing to decode.
        if not cfdi_data:
            return {}

        try:
            cfdi_node = fromstring(cfdi_data)
        except etree.XMLSyntaxError:
            # Not an xml
            return {}

        return self._l10n_mx_edi_decode_cfdi_etree(cfdi_node)
    
    # This methos was taken from odoo 16.0 
    def _l10n_mx_edi_decode_cfdi_etree(self, cfdi_node):
        ''' Helper to extract relevant data from the CFDI etree object, does not require a move record.
        :param cfdi_node:   The cfdi etree object.
        :return:            A python dictionary.
        '''
        def get_node(cfdi_node, attribute, namespaces):
            if hasattr(cfdi_node, 'Complemento'):
                node = cfdi_node.Complemento.xpath(attribute, namespaces=namespaces)
                return node[0] if node else None
            else:
                return None

        def get_cadena(cfdi_node, template):
            if cfdi_node is None:
                return None
            cadena_root = etree.parse(tools.file_open(template))
            return str(etree.XSLT(cadena_root)(cfdi_node))

        try:
            emisor_node = cfdi_node.Emisor
            receptor_node = cfdi_node.Receptor
        except AttributeError:
            # Not an xml object or not a valid CFDI
            return {}

        tfd_node = get_node(
            cfdi_node,
            'tfd:TimbreFiscalDigital[1]',
            {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'},
        )

        # Generar cadena original del complemento de certificación
        cadena_original = ''
        if tfd_node is not None:
            cadena_parts = []
            cadena_parts.append('||')
            cadena_parts.append(tfd_node.get('Version', '1.1'))
            cadena_parts.append('|')
            cadena_parts.append(tfd_node.get('UUID', ''))
            cadena_parts.append('|')
            cadena_parts.append(tfd_node.get('FechaTimbrado', ''))
            cadena_parts.append('|')
            cadena_parts.append(tfd_node.get('RfcProvCertif', ''))
            cadena_parts.append('|')
            cadena_parts.append(tfd_node.get('SelloCFD', '')[:50] + '...' if len(tfd_node.get('SelloCFD', '')) > 50 else tfd_node.get('SelloCFD', ''))
            cadena_parts.append('|')
            cadena_parts.append(tfd_node.get('NoCertificadoSAT', ''))
            cadena_parts.append('||')
            cadena_original = ''.join(cadena_parts)

        return {
            'uuid': ({} if tfd_node is None else tfd_node).get('UUID'),
            'supplier_rfc': emisor_node.get('Rfc', emisor_node.get('rfc')),
            'customer_rfc': receptor_node.get('Rfc', receptor_node.get('rfc')),
            'amount_total': cfdi_node.get('Total', cfdi_node.get('total')),
            'cfdi_node': cfdi_node,
            'usage': receptor_node.get('UsoCFDI'),
            'payment_method': cfdi_node.get('formaDePago', cfdi_node.get('MetodoPago')),
            'bank_account': cfdi_node.get('NumCtaPago'),
            'sello': cfdi_node.get('sello', cfdi_node.get('Sello', 'No identificado')),
            'sello_sat': tfd_node is not None and tfd_node.get('selloSAT', tfd_node.get('SelloSAT', 'No identificado')),
            'certificate_number': cfdi_node.get('noCertificado', cfdi_node.get('NoCertificado')),
            'certificate_sat_number': tfd_node is not None and tfd_node.get('NoCertificadoSAT'),
            'expedition': cfdi_node.get('LugarExpedicion'),
            'fiscal_regime': emisor_node.get('RegimenFiscal', ''),
            'emission_date_str': cfdi_node.get('fecha', cfdi_node.get('Fecha', '')).replace('T', ' '),
            'stamp_date': tfd_node is not None and tfd_node.get('FechaTimbrado', '').replace('T', ' '),
            'cadena_original': cadena_original,
        }

    # ===================================================================
    # Auto-creacion de xml.sat para REPs timbrados (v.55)
    # ===================================================================
    # Cuando un account.payment se timbra exitosamente y el SAT lo valida,
    # el CFDI XML queda en ir.attachment pero NO entra a
    # account_edi_downloaded_xml_sat hasta que el backend xmlsat.anfepi.com
    # lo descarga via lote SAT (puede tardar dias o no llegar). Eso
    # causaba que el reporte de Complementos de Pago marque rojo
    # "Pago Odoo sin Complemento de Pago en SAT" aunque el REP estuviera
    # timbrado y validado por el SAT.
    #
    # Solucion: cuando el move del payment cambia a sat_state='valid',
    # crear automaticamente la entrada en account.edi.downloaded.xml.sat
    # usando el lote real del mes correspondiente.

    def _get_related_payment(self):
        """Devuelve el account.payment asociado a este move, o False.
        account.move no tiene campo `payment_id` directo: la relacion va
        del payment al move via `account.payment.move_id`.
        """
        self.ensure_one()
        return self.env['account.payment'].sudo().search(
            [('move_id', '=', self.id)], limit=1,
        )

    def write(self, vals):
        # Detectar moves que cambian a sat_state='valid' AHORA. Separamos
        # entre moves de payment (REP) y moves de factura porque la creacion
        # de xml.sat es ligeramente distinta para cada caso.
        pay_triggering = []
        inv_triggering = []
        if vals.get('l10n_mx_edi_cfdi_sat_state') == 'valid':
            transitioning = [
                m.id for m in self if m.l10n_mx_edi_cfdi_sat_state != 'valid'
            ]
            if transitioning:
                pay_move_ids = set(self.env['account.payment'].sudo().search([
                    ('move_id', 'in', transitioning),
                ]).mapped('move_id.id'))
                for m in self.browse(transitioning):
                    if m.id in pay_move_ids:
                        pay_triggering.append(m.id)
                    elif m.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
                        inv_triggering.append(m.id)
        res = super().write(vals)
        for m in self.browse(pay_triggering):
            try:
                m._auto_create_xml_sat_for_payment_move()
            except Exception as e:
                _logger.warning(
                    "Auto-create xml.sat payment fallo para move %s (UUID %s): %s",
                    m.id, m.l10n_mx_edi_cfdi_uuid, e,
                )
        for m in self.browse(inv_triggering):
            try:
                m._auto_create_xml_sat_for_invoice_move()
            except Exception as e:
                _logger.warning(
                    "Auto-create xml.sat invoice fallo para move %s (UUID %s): %s",
                    m.id, m.l10n_mx_edi_cfdi_uuid, e,
                )
        return res

    def _auto_create_xml_sat_for_payment_move(self):
        """Crea entrada en account_edi_downloaded_xml_sat para el move
        de un payment recien timbrado. Idempotente.

        Solo crea si:
          - El move tiene un account.payment asociado (via payment.move_id)
          - Hay UUID l10n_mx_edi_cfdi_uuid
          - No existe ya un xml.sat con ese UUID
          - Hay attachment XML del CFDI
          - Existe lote real del mes (cfdi_type=emitidos, rango cubre el
            payment.date, misma company, state=imported). Sin lote del
            mes, NO crea: el cron de auto-sync ya crea lotes mensuales.
        """
        self.ensure_one()
        payment = self._get_related_payment()
        if not payment:
            return False
        uuid = (self.l10n_mx_edi_cfdi_uuid or '').upper()
        if not uuid:
            return False
        XmlSat = self.env['account.edi.downloaded.xml.sat'].sudo()
        if XmlSat.search_count([('name', '=ilike', uuid)]):
            return False
        att = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'account.move'), ('res_id', '=', self.id),
            '|', ('name', '=ilike', '%.xml'), ('mimetype', 'ilike', '%xml%'),
        ], limit=1)
        if not att or not att.raw:
            return False
        pay_date = payment.date or fields.Date.context_today(self)
        batch = self.env['account.edi.api.download'].sudo().search([
            ('cfdi_type', '=', 'emitidos'),
            ('company_id', '=', self.company_id.id),
            ('date_start', '<=', pay_date),
            ('date_end', '>=', pay_date),
            ('state', '=', 'imported'),
        ], limit=1, order='create_date desc')
        if not batch:
            return False
        try:
            xml_root = ET.fromstring(att.raw)
        except Exception:
            return False
        tipo = xml_root.get('TipoDeComprobante') or 'P'
        moneda = xml_root.get('Moneda') or 'MXN'
        sub_total = float(xml_root.get('SubTotal') or 0.0)
        amount_total = float(xml_root.get('Total') or 0.0)
        pago_node = xml_root.find('.//' + _NS_PAGOS20 + 'Pago')
        forma_pago = None
        if pago_node is not None:
            forma_pago = pago_node.get('FormaDePagoP')
            if pago_node.get('MonedaP'):
                moneda = pago_node.get('MonedaP')
            pm = pago_node.get('Monto')
            if pm:
                amount_total = float(pm)
        if not forma_pago:
            try:
                rs = att.raw.decode('utf-8', errors='replace')
                if 'FormaDePagoP="' in rs:
                    idx = rs.find('FormaDePagoP="') + 14
                    end = rs.find('"', idx)
                    if end > idx and end - idx <= 4:
                        forma_pago = rs[idx:end]
            except Exception:
                pass
        if forma_pago not in _SAT_FORMA_PAGO_CODES:
            forma_pago = None
        tfd = xml_root.find('.//' + _NS_TFD + 'TimbreFiscalDigital')
        ft = tfd.get('FechaTimbrado') if tfd is not None else None
        XmlSat.create({
            'name': uuid,
            'cfdi_type': 'emitidos',
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'payment_id': payment.id,
            'attachment_id': att.id,
            'batch_id': batch.id,
            'document_date': (xml_root.get('Fecha') or '')[:10] or None,
            'fecha_timbrado': (ft.replace('T', ' ')[:19] if ft else None),
            'document_type': tipo,
            'state': 'posted',
            'sub_total': sub_total,
            'amount_total': amount_total,
            'serie': xml_root.get('Serie'),
            'folio': xml_root.get('Folio'),
            'divisa': moneda,
            'sat_state': 'Vigente',
            'payment_method_sat': forma_pago,
            'sello_cfdi': xml_root.get('Sello'),
            'sello_sat': tfd.get('SelloSAT') if tfd is not None else None,
            'certificate_number': xml_root.get('NoCertificado'),
            'certificate_sat_number': tfd.get('NoCertificadoSAT') if tfd is not None else None,
        })
        return True

    def _auto_create_xml_sat_for_invoice_move(self):
        """Crea entrada en account_edi_downloaded_xml_sat para una factura
        recien timbrada y validada por SAT. Idempotente.

        Analogo a _auto_create_xml_sat_for_payment_move pero para facturas
        (out_invoice / in_invoice / out_refund / in_refund). Resuelve el
        caso 'Factura no localizada en XML SAT' cuando el backend xmlsat
        no descargo la factura aunque exista timbrada y validada en Odoo.
        """
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
            return False
        uuid = (self.l10n_mx_edi_cfdi_uuid or '').upper()
        if not uuid:
            return False
        XmlSat = self.env['account.edi.downloaded.xml.sat'].sudo()
        if XmlSat.search_count([('name', '=ilike', uuid)]):
            return False
        att = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'account.move'), ('res_id', '=', self.id),
            '|', ('name', '=ilike', '%.xml'), ('mimetype', 'ilike', '%xml%'),
        ], limit=1)
        if not att or not att.raw:
            return False
        # cfdi_type segun direccion de la factura
        is_emitida = self.move_type in ('out_invoice', 'out_refund')
        cfdi_type = 'emitidos' if is_emitida else 'recibidos'
        inv_date = self.invoice_date or self.date or fields.Date.context_today(self)
        batch = self.env['account.edi.api.download'].sudo().search([
            ('cfdi_type', '=', cfdi_type),
            ('company_id', '=', self.company_id.id),
            ('date_start', '<=', inv_date),
            ('date_end', '>=', inv_date),
            ('state', '=', 'imported'),
        ], limit=1, order='create_date desc')
        if not batch:
            return False
        try:
            xml_root = etree.fromstring(att.raw)
        except Exception:
            return False
        tipo = xml_root.get('TipoDeComprobante') or ('I' if 'invoice' in self.move_type else 'E')
        moneda = xml_root.get('Moneda') or 'MXN'
        sub_total = float(xml_root.get('SubTotal') or 0.0)
        amount_total = float(xml_root.get('Total') or 0.0)
        # FormaPago raiz (validamos contra catalogo)
        forma_pago = xml_root.get('FormaPago')
        if forma_pago not in _SAT_FORMA_PAGO_CODES:
            forma_pago = None
        metodo_pago = xml_root.get('MetodoPago')
        if metodo_pago not in ('PUE', 'PPD'):
            metodo_pago = None
        # tax_regime segun direccion: emitidos lee RegimenFiscalReceptor (CFDI 4.0),
        # recibidos lee RegimenFiscal del Emisor
        tax_regime = None
        ns_cfdi = {'cfdi': 'http://www.sat.gob.mx/cfd/4'}
        if is_emitida:
            _rec = xml_root.find('.//cfdi:Receptor', namespaces=ns_cfdi)
            if _rec is not None:
                tax_regime = _rec.get('RegimenFiscalReceptor')
        else:
            _emi = xml_root.find('.//cfdi:Emisor', namespaces=ns_cfdi)
            if _emi is not None:
                tax_regime = _emi.get('RegimenFiscal')
        # cfdi_usage del Receptor
        cfdi_usage = None
        _rec = xml_root.find('.//cfdi:Receptor', namespaces=ns_cfdi)
        if _rec is not None:
            cfdi_usage = _rec.get('UsoCFDI')
        tfd = xml_root.find('.//' + _NS_TFD + 'TimbreFiscalDigital')
        ft = tfd.get('FechaTimbrado') if tfd is not None else None
        vals = {
            'name': uuid,
            'cfdi_type': cfdi_type,
            'company_id': self.company_id.id,
            'partner_id': self.partner_id.id,
            'invoice_id': self.id,
            'attachment_id': att.id,
            'batch_id': batch.id,
            'document_date': (xml_root.get('Fecha') or '')[:10] or None,
            'fecha_timbrado': (ft.replace('T', ' ')[:19] if ft else None),
            'document_type': tipo,
            'state': 'posted',
            'sub_total': sub_total,
            'amount_total': amount_total,
            'serie': xml_root.get('Serie'),
            'folio': xml_root.get('Folio'),
            'divisa': moneda,
            'sat_state': 'Vigente',
            'payment_method_sat': forma_pago,
            'payment_method': metodo_pago,
            'sello_cfdi': xml_root.get('Sello'),
            'sello_sat': tfd.get('SelloSAT') if tfd is not None else None,
            'certificate_number': xml_root.get('NoCertificado'),
            'certificate_sat_number': tfd.get('NoCertificadoSAT') if tfd is not None else None,
        }
        if tax_regime:
            try:
                _valid_tr = dict(XmlSat._fields['tax_regime'].selection)
                if tax_regime in _valid_tr:
                    vals['tax_regime'] = tax_regime
            except Exception:
                pass
        if cfdi_usage:
            try:
                _valid_uso = dict(XmlSat._fields['cfdi_usage'].selection)
                if cfdi_usage in _valid_uso:
                    vals['cfdi_usage'] = cfdi_usage
            except Exception:
                pass
        XmlSat.create(vals)
        return True

    @api.model
    def action_backfill_xml_sat_from_invoices(self, limit=500):
        """Recorre facturas timbradas y validadas que no tienen entrada
        en account_edi_downloaded_xml_sat y la crea. Idempotente.

        Procesa hasta `limit` por invocacion. Devuelve dict con contadores.
        """
        moves = self.search([
            ('move_type', 'in', ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')),
            ('l10n_mx_edi_cfdi_uuid', '!=', False),
            ('l10n_mx_edi_cfdi_sat_state', '=', 'valid'),
        ], limit=limit)
        created = 0
        skipped = 0
        errors = 0
        for m in moves:
            try:
                if m._auto_create_xml_sat_for_invoice_move():
                    created += 1
                    self.env.cr.commit()
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                _logger.warning(
                    "Backfill xml.sat invoice fallo para move %s: %s", m.id, e,
                )
                self.env.cr.rollback()
        return {'scanned': len(moves), 'created': created, 'skipped': skipped, 'errors': errors}

    @api.model
    def action_backfill_xml_sat_from_payments(self, limit=500):
        """Recorre payments con CFDI timbrado y validado que no tienen
        entrada en account_edi_downloaded_xml_sat y la crea. Idempotente.

        Llamable desde Server Action o cron de mantenimiento.
        Procesa hasta `limit` por invocacion para evitar timeouts.
        Devuelve dict con contadores.
        """
        payments = self.env['account.payment'].sudo().search([
            ('move_id.l10n_mx_edi_cfdi_uuid', '!=', False),
            ('move_id.l10n_mx_edi_cfdi_sat_state', '=', 'valid'),
        ], limit=limit)
        created = 0
        skipped = 0
        errors = 0
        for p in payments:
            try:
                if p.move_id._auto_create_xml_sat_for_payment_move():
                    created += 1
                    self.env.cr.commit()
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                _logger.warning(
                    "Backfill xml.sat fallo para payment %s: %s", p.id, e,
                )
                self.env.cr.rollback()
        return {'scanned': len(payments), 'created': created, 'skipped': skipped, 'errors': errors}