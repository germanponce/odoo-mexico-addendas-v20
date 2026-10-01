from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
from odoo import api, exceptions, fields, models, _
from xml.dom.minidom import parse, parseString
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    
    def _get_xml_file_content(self):
        attachment = self.env['ir.attachment'].search([('res_model', '=', 'account.move'), 
                                                       ('res_id', '=', self.id), 
                                                       ('name', 'ilike', '.xml')], limit=1)
        if not attachment:
            return False
        try:
            file_path = self.env['ir.attachment']._full_path('checklist').replace('checklist','') + attachment.store_fname
            attach_file = open(file_path, 'rb')
            xml_data = attach_file.read()
            attach_file.close()
            return xml_data
        except:
            _logger.error("No se pudo leer el archivo XML adjunto a esta factura, favor de revisar...")
            return False
    
    
    @api.depends('attachment_ids')
    def _get_uuid_from_attachment(self):
        for rec in self:
            rec.sat_serie = False
            rec.sat_uuid = False
            rec.sat_folio = False
            xml_data = rec._get_xml_file_content()
            if xml_data:
                #try:
                arch_xml = parseString(xml_data)
                is_xml_signed = arch_xml.getElementsByTagName('tfd:TimbreFiscalDigital')
                if is_xml_signed:
                    xvalue = arch_xml.getElementsByTagName('tfd:TimbreFiscalDigital')[0]
                    yvalue = arch_xml.getElementsByTagName('cfdi:Comprobante')[0]                    
                    timbre = xvalue.attributes['UUID'].value
                    serie, folio = False, False
                    try:
                        serie = yvalue.attributes['serie'].value
                    except:
                        pass
                    try:
                        folio = yvalue.attributes['folio'].value
                    except:
                        pass
                    res = self.search([('sat_uuid', '=', timbre),('id','!=',rec.id),('company_id','=',rec.company_id.id)])
                    if res:
                        raise UserError(_("Error ! La factura ya se encuentra registrada en el sistema y no puede tener registro duplicado.\n\nLa factura con Folio Fiscal %s se encuentra registrada en el registro %s - Referencia: %s - ID: %s")%(timbre, res.name, res.ref, res.id))
                    rec.sat_uuid = timbre
                    if serie:
                        rec.sat_serie = serie
                    if folio:
                        rec.sat_folio = folio
                    _logger.info("CFDI (Archivo XML) con UUID %s procesado exitosamente..." % timbre)
                    #except:
                    #    _logger.info("Ocurrió un error al intentar tomar los datos del archivo XML")
                    #    pass
    
    sat_uuid = fields.Char(compute='_get_uuid_from_attachment', string="CFDI UUID", store=True, index=True)
    sat_folio = fields.Char(compute='_get_uuid_from_attachment', string="CFDI Folio", store=True, index=True)
    sat_serie = fields.Char(compute='_get_uuid_from_attachment', string="CFDI Serie", store=True, index=True)
    cfdi_id = fields.Many2one('account.cfdi', string="CFDI de Auditoría", readonly=True, index=True)