from odoo import api, fields, models, tools
from odoo.exceptions import UserError
import xml.etree.ElementTree as ET
import base64

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    stored_sat_uuid = fields.Char(
        compute='_get_uuid_from_xml_attachment', 
        string="CFDI UUID", 
        store=True, 
    )

    @api.depends('attachment_ids')
    def _get_uuid_from_xml_attachment(self):
        for record in self:
            if not record.stored_sat_uuid:
                # OPTIMIZACIÓN: Usar attachment_ids en lugar de search
                # Evita query adicional a la base de datos
                attachments = record.attachment_ids.filtered(lambda x: x.mimetype == 'application/xml')
                if attachments:
                    for attatchment in attachments:
                        try:
                            xml_content = base64.b64decode(attatchment.datas)
                            root = ET.fromstring(xml_content)
                            uuid = root.find('.//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital').attrib['UUID']
                            record.stored_sat_uuid = uuid
                            break
                        except: 
                            record.stored_sat_uuid = False
            else: 
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