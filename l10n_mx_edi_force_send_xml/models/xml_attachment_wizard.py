# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from lxml import etree
import base64
import logging

_logger = logging.getLogger(__name__)


class XmlAttachmentWizard(models.TransientModel):
    _name = 'xml.attachment.wizard'
    _description = 'Wizard para adjuntar XML personalizado'

    # Campos del wizard
    document_id = fields.Many2one(
        'l10n_mx_edi.document',
        string='Documento EDI',
        required=True
    )
    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        required=True
    )
    use_custom_xml = fields.Boolean(
        string='Usar XML Personalizado',
        default=True,
        help="Si está activado, se usará el XML adjunto en lugar de generar uno automáticamente"
    )
    custom_xml_file = fields.Binary(
        string='Archivo XML Personalizado',
        help="Archivo XML que se enviará directamente al PAC"
    )
    custom_xml_filename = fields.Char(
        string='Nombre del Archivo XML'
    )

    def action_save_xml_attachment(self):
        """Guarda el XML adjunto en el documento EDI"""
        self.ensure_one()
        
        if self.use_custom_xml and not self.custom_xml_file:
            raise ValidationError(_("Debe adjuntar un archivo XML."))
        
        # Validar XML si está presente
        if self.custom_xml_file:
            try:
                xml_content = base64.b64decode(self.custom_xml_file)
                etree.fromstring(xml_content)
            except Exception as e:
                raise ValidationError(_("El archivo XML no es válido: %s") % str(e))
        
        # Buscar o crear documento EDI
        if not self.document_id:
            document = self.env['l10n_mx_edi.document'].create({
                'move_id': self.move_id.id,
                'state': 'draft',
            })
        else:
            document = self.document_id
        
        # Actualizar campos usando sudo para evitar problemas de permisos
        document.sudo().write({
            'use_custom_xml': self.use_custom_xml,
            'custom_xml_file': self.custom_xml_file,
            'custom_xml_filename': self.custom_xml_filename,
        })
        
        _logger.info('XML personalizado guardado en documento %s', document.id)
        
        return {
            'type': 'ir.actions.act_window_close'
        }

    def action_validate_xml(self):
        """Valida el XML adjunto"""
        self.ensure_one()
        
        if not self.custom_xml_file:
            raise ValidationError(_("No hay archivo XML para validar."))
        
        try:
            xml_content = base64.b64decode(self.custom_xml_file)
            etree.fromstring(xml_content)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Validación Exitosa'),
                    'message': _('El archivo XML es válido.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise ValidationError(_("El archivo XML no es válido: %s") % str(e))