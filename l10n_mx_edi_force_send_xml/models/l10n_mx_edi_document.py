# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from lxml import etree
from xml.dom import minidom
import base64
import logging

_logger = logging.getLogger(__name__)


class L10nMxEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    # Campo para adjuntar XML personalizado
    custom_xml_file = fields.Binary(
        string='Archivo XML Personalizado',
        help="Archivo XML que se enviará directamente al PAC"
    )
    custom_xml_filename = fields.Char(
        string='Nombre del Archivo XML'
    )
    use_custom_xml = fields.Boolean(
        string='Usar XML Personalizado',
        default=False,
        help="Si está activado, se usará el XML adjunto en lugar de generar uno automáticamente"
    )

    def action_validate_custom_xml(self):
        """Valida manualmente el XML personalizado"""
        self.ensure_one()
        if not self.custom_xml_file:
            raise ValidationError(_("No hay archivo XML para validar."))
        
        try:
            xml_content = base64.b64decode(self.custom_xml_file)
            # Validar que sea XML válido
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

    def action_open_xml_attachment_form(self):
        """Abre una vista formulario para editar el XML adjunto"""
        self.ensure_one()
        return {
            'name': _('Adjuntar XML Personalizado'),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_mx_edi.document',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_mx_edi_xml_attachment.view_l10n_mx_edi_document_xml_form').id,
            'target': 'new',
            'context': {'default_use_custom_xml': True}
        }

    @api.model
    def _decode_cfdi_attachment(self, cfdi_data):
        """Override del método _decode_cfdi_attachment para interceptar XML personalizado
        
        Este método es el punto clave donde interceptamos el XML que será procesado
        y enviado al PAC. Si hay un XML personalizado adjuntado, lo usamos en lugar
        del XML generado automáticamente por QWeb.
        """
        _logger.info('=== _decode_cfdi_attachment llamado ===')
        
        # Verificar si algún documento en el contexto tiene XML personalizado
        document_id = self.env.context.get('active_id') or getattr(self, 'id', False)
        if document_id:
            try:
                # Verificar que el documento existe antes de acceder
                if self.env['l10n_mx_edi.document'].sudo().search([('id', '=', document_id)]):
                    document = self.browse(document_id)
                    if document.exists() and document.use_custom_xml and document.custom_xml_file:
                        _logger.info('INTERCEPTADO: Usando XML personalizado desde documento %s', document_id)
                        # Usar el XML personalizado en lugar del cfdi_data original
                        cfdi_data = base64.b64decode(document.custom_xml_file)
                        _logger.info('XML personalizado cargado correctamente, tamaño: %s bytes', len(cfdi_data))
                else:
                    _logger.warning('Documento %s no existe, usando flujo normal', document_id)
            except Exception as e:
                _logger.warning('Error al acceder al documento %s: %s, usando flujo normal', document_id, str(e))
        
        # Si no hay documento específico, verificar por self
        elif hasattr(self, 'use_custom_xml') and hasattr(self, 'custom_xml_file'):
            try:
                if self.exists() and self.use_custom_xml and self.custom_xml_file:
                    _logger.info('INTERCEPTADO: Usando XML personalizado desde self')
                    cfdi_data = base64.b64decode(self.custom_xml_file)
                    _logger.info('XML personalizado cargado correctamente, tamaño: %s bytes', len(cfdi_data))
            except Exception as e:
                _logger.warning('Error al acceder a XML personalizado desde self: %s', str(e))
        
        # Llamar al método original con el cfdi_data (original o personalizado)
        _logger.info('Procesando XML con el método original')
        
        # =================== CÓDIGO ORIGINAL DE COMPLEMENTOS ===================
        # Aquí va toda tu lógica existente de procesamiento de Carta Porte
        
        # Llamamos al método original del padre
        res = super(L10nMxEdiDocument, self)._decode_cfdi_attachment(cfdi_data)
        _logger.info("\n########## res: %s" % res)

        # Obtenemos el nodo principal del CFDI
        cfdi_node_custom = res.get('cfdi_node')
        if not cfdi_node_custom:
            return res
        _logger.info("\n########## cfdi_node_custom: %s" % cfdi_node_custom)

        cfdi_str = etree.tostring(cfdi_node_custom, pretty_print=True, xml_declaration=True, encoding='UTF-8')
        _logger.info("\n#### CFDI_STR original: %s", cfdi_str)

        cfdi_minidom = minidom.parseString(cfdi_str)
        comprobante = cfdi_minidom.getElementsByTagName('cfdi:Comprobante')[0] if cfdi_minidom.getElementsByTagName('cfdi:Comprobante') else None

        cfdi_custom = cfdi_minidom.toxml('UTF-8')
        _logger.info("\n#### CFDI_STR modificado: %s", cfdi_custom)

        res['cfdi_node'] = cfdi_node_custom

        return res

    def action_retry(self):
        """Override del método retry para asegurar contexto correcto"""
        _logger.info('=== action_retry llamado para documentos: %s ===', self.ids)
        
        # Filtrar solo documentos que existen
        existing_docs = self.exists()
        
        for doc in existing_docs:
            try:
                if doc.use_custom_xml and doc.custom_xml_file:
                    _logger.info('Documento %s marcado para usar XML personalizado en retry', doc.id)
                    # Agregar el ID del documento al contexto para que _decode_cfdi_attachment lo detecte
                    self = self.with_context(active_id=doc.id)
            except Exception as e:
                _logger.warning('Error al procesar documento %s en retry: %s', doc.id, str(e))
        
        return super().action_retry()

    def _process_documents_web_services(self, web_service):
        """Override alternativo para asegurar que se use XML personalizado"""
        _logger.info('=== _process_documents_web_services llamado ===')
        
        # Filtrar solo documentos que existen
        existing_docs = self.exists()
        
        # Asegurar que cada documento con XML personalizado tenga el contexto correcto
        for doc in existing_docs:
            try:
                if doc.use_custom_xml and doc.custom_xml_file:
                    _logger.info('Configurando contexto para documento %s con XML personalizado', doc.id)
                    # Asegurar que el contexto incluya el ID del documento
                    doc_with_context = doc.with_context(active_id=doc.id)
                    # Procesar este documento individualmente
                    return super(L10nMxEdiDocument, doc_with_context)._process_documents_web_services(web_service)
            except Exception as e:
                _logger.warning('Error al configurar contexto para documento %s: %s', doc.id, str(e))
        
        # Si no hay documentos con XML personalizado, usar flujo normal
        return super()._process_documents_web_services(web_service)