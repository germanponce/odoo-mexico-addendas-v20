
# -*- coding: utf-8 -*-
from odoo import api, exceptions, fields, models, _, tools
from odoo.tools import float_is_zero, float_compare, pycompat
from odoo.tools.misc import formatLang
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError
from odoo.addons import decimal_precision as dp
from xml.dom.minidom import parse, parseString

import base64
from lxml.objectify import fromstring
import json, re, uuid
from functools import partial
from lxml import etree
from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode
import logging
_logger = logging.getLogger(__name__)

CFDI_XSLT_CADENA = 'l10n_mx_edi/data/4.0/cadenaoriginal_4_0.xslt'
CFDI_XSLT_CADENA_TFD = 'l10n_mx_edi/data/xslt/4.0/cadenaoriginal_TFD_1_1.xslt'


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
        """Extrae UUID, Serie y Folio del XML adjunto"""
        for rec in self:
            # Valores por defecto
            rec.sat_uuid = False
            rec.sat_folio = False
            rec.sat_serie = False
            
            # Si viene del contexto (importación), usar esos valores
            context = self.env.context
            if context.get('sat_uuid'):
                rec.sat_uuid = context.get('sat_uuid')
                rec.sat_folio = context.get('sat_folio', '')
                rec.sat_serie = context.get('sat_serie', '')
                continue
            
            # Buscar XML en attachments
            xml_data = rec._get_xml_file_content()
            if not xml_data:
                continue
                
            try:
                # Parsear XML
                arch_xml = parseString(xml_data)
                timbre_nodes = arch_xml.getElementsByTagName('tfd:TimbreFiscalDigital')
                
                if not timbre_nodes:
                    _logger.warning(f"XML sin timbrado para factura {rec.name}")
                    continue
                
                # Extraer UUID
                timbre = timbre_nodes[0].attributes['UUID'].value
                
                # Verificar duplicados
                duplicates = self.search([
                    ('sat_uuid', '=', timbre),
                    ('id', '!=', rec.id),
                    ('company_id', '=', rec.company_id.id),
                    ('state', '!=', 'cancel')
                ])
                
                if duplicates:
                    raise ValidationError(
                        f"⚠️ UUID Duplicado\n\n"
                        f"El UUID {timbre} ya existe en:\n"
                        f"• Factura: {duplicates[0].name}\n"
                        f"• Referencia: {duplicates[0].ref}\n"
                        f"• ID: {duplicates[0].id}\n\n"
                        f"No se permiten facturas con el mismo UUID."
                    )
                
                # Extraer Serie y Folio
                comprobante_nodes = arch_xml.getElementsByTagName('cfdi:Comprobante')
                if comprobante_nodes:
                    attrs = comprobante_nodes[0].attributes
                    try:
                        rec.sat_serie = attrs.get('Serie', attrs.get('serie')).value
                    except:
                        pass
                    try:
                        rec.sat_folio = attrs.get('Folio', attrs.get('folio')).value
                    except:
                        pass
                
                rec.sat_uuid = timbre
                _logger.info(f"✅ UUID {timbre} extraído de XML para factura {rec.name}")
                
            except ValidationError:
                raise
            except Exception as e:
                _logger.error(
                    f"❌ Error al extraer UUID del XML para {rec.name}: {str(e)}",
                    exc_info=True
                )
                
    
    # @api.depends('attachment_ids')
    # def _get_uuid_from_attachment(self):
    #     context = self._context
    #     sat_uuid = context.get('sat_uuid','')
    #     sat_folio = context.get('sat_folio','')
    #     sat_serie = context.get('sat_serie','')
    #     _logger.info("\n############### def _get_uuid_from_attachment() ......................... ")
    #     _logger.info("\n############### context: %s " % context)
    #     _logger.info("\n############### sat_uuid: %s " % sat_uuid)
    #     _logger.info("\n############### sat_folio: %s " % sat_folio)
    #     _logger.info("\n############### sat_serie: %s " % sat_serie)
    #     for rec in self:
    #         if sat_uuid or sat_folio or sat_serie:
    #             rec.sat_uuid = False
    #             rec.sat_folio = False
    #             rec.sat_serie = False
    #         else:
    #             rec.sat_serie = False
    #             rec.sat_uuid = False
    #             rec.sat_folio = False
    #             xml_data = rec._get_xml_file_content()
    #             if xml_data:
    #                 try:
    #                     arch_xml = parseString(xml_data)
    #                     is_xml_signed = arch_xml.getElementsByTagName('tfd:TimbreFiscalDigital')
    #                     if is_xml_signed:
    #                         xvalue = arch_xml.getElementsByTagName('tfd:TimbreFiscalDigital')[0]
    #                         yvalue = arch_xml.getElementsByTagName('cfdi:Comprobante')[0]                    
    #                         timbre = xvalue.attributes['UUID'].value
    #                         serie, folio = False, False
    #                         try:
    #                             serie = yvalue.attributes['serie'].value
    #                         except:
    #                             pass
    #                         try:
    #                             folio = yvalue.attributes['folio'].value
    #                         except:
    #                             pass
    #                         res = self.search([('sat_uuid', '=', timbre),('id','!=',rec.id),('company_id','=',rec.company_id.id)])
    #                         if res:
    #                             _logger.info("\n#### Error: La factura ya se encuentra registrada en el sistema y no puede tener registro duplicado.\n\nLa factura con Folio Fiscal %s se encuentra registrada en el registro %s - Referencia: %s - ID: %s" % (timbre, res.name, res.ref, res.id))
    #                         rec.sat_uuid = timbre
    #                         if serie:
    #                             rec.sat_serie = serie
    #                         if folio:
    #                             rec.sat_folio = folio
    #                         _logger.info("CFDI (Archivo XML) con UUID %s procesado exitosamente..." % timbre)
    #                 except:
    #                    _logger.info("Ocurrió un error al intentar tomar los datos del archivo XML")
    #                    pass
    
    sat_uuid = fields.Char(compute='_get_uuid_from_attachment', string="CFDI UUID", store=True, index=True)
    sat_folio = fields.Char(compute='_get_uuid_from_attachment', string="CFDI Folio", store=True, index=True)
    sat_serie = fields.Char(compute='_get_uuid_from_attachment', string="CFDI Serie", store=True, index=True)

    l10n_mx_edi_cfdi_name2 = fields.Char(copy=False)
    is_start_amount = fields.Boolean('Es saldo inicial', help='Si es True, esta factura es de saldos inciiales')
    is_imported = fields.Boolean('Es Importada',
                                 help="Si está marcado significa que la Factura fue importada")
    

    # ==== Other fields ====
    l10n_mx_edi_payment_method_id = fields.Many2one(
        comodel_name='l10n_mx_edi.payment.method',
        string="Forma de Pago",
        compute='_compute_l10n_mx_edi_payment_method_id',
        store=True,
        readonly=False,
        help="Indicates the way the invoice was/will be paid, where the options could be: "
             "Cash, Nominal Check, Credit Card, etc. Leave empty if unkown and the XML will show 'Unidentified'.")

    l10n_mx_edi_payment_policy = fields.Selection(string='Metodo de Pago',
        selection=[('PPD', 'PPD'), ('PUE', 'PUE')],
        compute='_compute_l10n_mx_edi_payment_policy')

    # ==== Other fields Importador ====

    import_l10n_mx_edi_payment_method_id = fields.Many2one(
        comodel_name='l10n_mx_edi.payment.method',
        string="Forma de Pago",
        copy=False)
    
    import_l10n_mx_edi_payment_policy = fields.Selection(string='Metodo de Pago',
        selection=[('PPD', 'PPD'), ('PUE', 'PUE')])


    @api.depends('journal_id', 'import_l10n_mx_edi_payment_method_id')
    def _compute_l10n_mx_edi_payment_method_id(self):
        for move in self:
            if move.import_l10n_mx_edi_payment_method_id:
                move.l10n_mx_edi_payment_method_id = move.import_l10n_mx_edi_payment_method_id.id
            else:
                if move.l10n_mx_edi_payment_method_id:
                    move.l10n_mx_edi_payment_method_id = move.l10n_mx_edi_payment_method_id
                elif move.journal_id.l10n_mx_edi_payment_method_id:
                    move.l10n_mx_edi_payment_method_id = move.journal_id.l10n_mx_edi_payment_method_id
                else:
                    move.l10n_mx_edi_payment_method_id = self.env.ref('l10n_mx_edi.payment_method_otros', raise_if_not_found=False)


    @api.depends('move_type', 'invoice_date_due', 'invoice_date', 'invoice_payment_term_id', 'invoice_payment_term_id.line_ids', 'import_l10n_mx_edi_payment_policy')
    def _compute_l10n_mx_edi_payment_policy(self):
        res = super(AccountMove, self)._compute_l10n_mx_edi_payment_policy()
        for move in self:
            if move.is_invoice(include_receipts=True) and move.invoice_date_due and move.invoice_date:
                if move.move_type == 'out_invoice':
                    if move.import_l10n_mx_edi_payment_policy:
                        move.l10n_mx_edi_payment_policy = move.import_l10n_mx_edi_payment_policy
                    else:
                        # In CFDI 3.3 - rule 2.7.1.43 which establish that
                        # invoice payment term should be PPD as soon as the due date
                        # is after the last day of  the month (the month of the invoice date).
                        if move.invoice_date_due.month > move.invoice_date.month or \
                           move.invoice_date_due.year > move.invoice_date.year or \
                           len(move.invoice_payment_term_id.line_ids) > 1:  # to be able to force PPD
                            move.l10n_mx_edi_payment_policy = 'PPD'
                        else:
                            move.l10n_mx_edi_payment_policy = 'PUE'
                else:
                    if move.move_type == 'out_refund':
                        move.l10n_mx_edi_payment_policy = 'PUE'
                    else:
                        if move.import_l10n_mx_edi_payment_policy:
                            move.l10n_mx_edi_payment_policy = move.import_l10n_mx_edi_payment_policy
                        else:
                            move.l10n_mx_edi_payment_policy = 'PUE'
            else:
                move.l10n_mx_edi_payment_policy = False

    # def action_post(self):
    #     res = super(AccountMove, self).action_post()
    #     for rec in self:
    #         if not rec.is_imported:
    #             continue
    #         docs = rec.l10n_mx_edi_document_ids
    #         if not docs:
    #             continue
    #         xml_attachment = False
    #         for attachment in rec.attachment_ids:
    #             if attachment.name.endswith('xml'):
    #                 xml_attachment = xml_attachment.id
    #         for doc in docs:
    #             doc.write({
    #                 'attachment_id' : xml_attachment,
    #                 # 'attachment_id' : rec.attachment_ids.filtered(lambda ww: ww.name.endswith('xml'))[0].id,
    #                 'state' : 'sent',                   
    #             })
    #     return res

    def action_post(self):

        #### actualizamos el commercial partner id
        for move in self:
            if move.is_imported:
                move.commercial_partner_id = move.partner_id.commercial_partner_id

        """Override para manejar facturas importadas"""
        res = super(AccountMove, self).action_post()
        
        for rec in self:
            # Solo procesar facturas importadas
            if not rec.is_imported:
                continue
                
            # Buscar attachment XML
            xml_attachment = rec.attachment_ids.filtered(
                lambda att: att.name.lower().endswith('.xml') and att.mimetype == 'application/xml'
            )
            
            if not xml_attachment:
                _logger.warning(f"No se encontró XML para factura importada {rec.name}")
                continue
                
            # Tomar el primer XML encontrado
            xml_attachment = xml_attachment[0]
            
            # Buscar o crear documento CFDI
            cfdi_doc = rec.l10n_mx_edi_document_ids.filtered(
                lambda d: d.state in ('invoice_received', 'invoice_sent')
            )
            
            if cfdi_doc:
                # Actualizar documento existente
                cfdi_doc[0].write({
                    'attachment_id': xml_attachment.id,
                    'state': 'invoice_received',  # Estado para facturas importadas
                    'sat_state': 'not_defined',
                })
            else:
                # Crear nuevo documento CFDI
                self.env['l10n_mx_edi.document'].create({
                    'move_id': rec.id,
                    'invoice_ids': [(6, 0, [rec.id])],
                    'attachment_id': xml_attachment.id,
                    'state': 'invoice_received',  # Para facturas de proveedor importadas
                    'sat_state': 'not_defined',
                    'datetime': fields.Datetime.now(),
                })
                
            _logger.info(f"✅ Documento CFDI creado/actualizado para factura {rec.name} con UUID {rec.sat_uuid}")

            # vendor_display_name = rec.partner_id.display_name
            # if not vendor_display_name:
            #     if rec.invoice_source_email:
            #         vendor_display_name = _('@De: %(email)s', email=rec.invoice_source_email)
            #     else:
            #         vendor_display_name = _('#Creado por: %s', rec.sudo().create_uid.name or self.env.user.name)
            #     rec.invoice_partner_display_name = vendor_display_name

            cr  = self.env.cr
            cr.execute("update account_move set invoice_partner_display_name=res_partner.name from res_partner where res_partner.id = account_move.partner_id and account_move.id=%s;" % (rec.id, ))
        return res
    
    
    def _l10n_mx_edi_decode_cfdi(self, cfdi_data=None):
        ''' Helper to extract relevant data from the CFDI to be used, for example, when printing the invoice.
        :param cfdi_data:   The optional cfdi data.
        :return:            A python dictionary.
        '''
        self.ensure_one()

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

        # Find a signed cfdi.
        if not cfdi_data:
            if self.is_imported:
                try:
                    cfdi_data = base64.decodebytes(self.attachment_ids.filtered(lambda x: x.name.endswith('xml'))[0])
                except:
                    pass
            if not cfdi_data:
                signed_edi = self._get_l10n_mx_edi_signed_edi_document()
                if signed_edi:
                    edi_ids = len(signed_edi.attachment_id)
                    if edi_ids > 1:
                        cfdi_data = base64.decodebytes(signed_edi.attachment_id.with_context(bin_size=False)[0].datas)
                    else:
                        try:
                            cfdi_data = base64.decodebytes(signed_edi.attachment_id.with_context(bin_size=False).datas)
                        except:
                            cfdi_data = base64.decodebytes(signed_edi.attachment_id.with_context(bin_size=False)[0].datas)

        # Nothing to decode.
        if not cfdi_data:
            return {}

        try:
            cfdi_node = fromstring(cfdi_data)
        except:
            cfdi_data = cfdi_data.decode("utf-8").replace("http://www.sat.gob.mx/registrofiscal http://www.sat.gob.mx/sitio_internet/cfd/cfdiregistrofiscal/cfdiregistrofiscal.xsd", "http://www.sat.gob.mx/sitio_internet/cfd/cfdiregistrofiscal/cfdiregistrofiscal.xsd").encode('utf-8')
            parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
            h = fromstring(cfdi_data, parser=parser)
            cfdi_node = fromstring(cfdi_data)
        tfd_node = get_node(
            cfdi_node,
            'tfd:TimbreFiscalDigital[1]',
            {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'},
        )
        _logger.info("\n############ cfdi_node: %s " % cfdi_node)
        cfdi_vals =  {
                            'uuid': ({} if tfd_node is None else tfd_node).get('UUID'),
                            'supplier_rfc': cfdi_node.Emisor.get('Rfc', cfdi_node.Emisor.get('rfc')),
                            'customer_rfc': cfdi_node.Receptor.get('Rfc', cfdi_node.Receptor.get('rfc')),
                            'amount_total': cfdi_node.get('Total', cfdi_node.get('total')),
                            'cfdi_node': cfdi_node,
                            'usage': cfdi_node.Receptor.get('UsoCFDI'),
                            'payment_method': cfdi_node.get('formaDePago', cfdi_node.get('MetodoPago')),
                            'bank_account': cfdi_node.get('NumCtaPago'),
                            'sello': cfdi_node.get('sello', cfdi_node.get('Sello', 'No identificado')),
                            'sello_sat': tfd_node is not None and tfd_node.get('selloSAT', tfd_node.get('SelloSAT', 'No identificado')),
                            'cadena': get_cadena(cfdi_node, CFDI_XSLT_CADENA),
                            'certificate_number': cfdi_node.get('noCertificado', cfdi_node.get('NoCertificado')),
                            'certificate_sat_number': tfd_node is not None and tfd_node.get('NoCertificadoSAT'),
                            'expedition': cfdi_node.get('LugarExpedicion'),
                            'fiscal_regime': cfdi_node.Emisor.get('RegimenFiscal', ''),
                            'emission_date_str': cfdi_node.get('fecha', cfdi_node.get('Fecha', '')).replace('T', ' '),
                            'stamp_date': tfd_node is not None and tfd_node.get('FechaTimbrado', '').replace('T', ' '),
                      }

        external_trade_node = get_node(
            cfdi_node,
            'cce11:ComercioExterior[1]',
            {'cce11': 'http://www.sat.gob.mx/ComercioExterior11'},
        )
        if external_trade_node is None:
            external_trade_node = {}
        else:
            cfdi_vals.update({
                'ext_trade_node': external_trade_node,
                'ext_trade_certificate_key': external_trade_node.get('ClaveDePedimento', ''),
                'ext_trade_certificate_source': external_trade_node.get('CertificadoOrigen', '').replace('0', 'No').replace('1', 'Si'),
                'ext_trade_nb_certificate_origin': external_trade_node.get('CertificadoOrigen', ''),
                'ext_trade_certificate_origin': external_trade_node.get('NumCertificadoOrigen', ''),
                'ext_trade_operation_type': external_trade_node.get('TipoOperacion', '').replace('2', 'Exportación'),
                'ext_trade_subdivision': external_trade_node.get('Subdivision', ''),
                'ext_trade_nb_reliable_exporter': external_trade_node.get('NumeroExportadorConfiable', ''),
                'ext_trade_incoterm': external_trade_node.get('Incoterm', ''),
                'ext_trade_rate_usd': external_trade_node.get('TipoCambioUSD', ''),
                'ext_trade_total_usd': external_trade_node.get('TotalUSD', ''),
            })


        return cfdi_vals
    
    def action_invoice_open(self):
        res = super(AccountMove, self).action_invoice_open()
        for rec in self:
            if rec.l10n_mx_edi_cfdi_name2:
                rec.l10n_mx_edi_cfdi_name = rec.l10n_mx_edi_cfdi_name2

        return res

    
    def action_move_create(self):
        res = super(AccountMove, self).action_move_create()
        for inv in self:
            if inv.l10n_mx_edi_cfdi_name2:
                if inv.move_type == 'out_invoice' or inv.move_type == 'out_refund':
                    inv.move_id.name = inv.name
                elif (inv.move_type == 'in_invoice' or inv.move_type == 'in_refund') and inv.is_start_amount:
                    inv.move_id.name = inv.reference
        return res


class AccountTax(models.Model):
    _inherit = 'account.tax'
    tax_code_mx = fields.Char(string='Codigo cuenta')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    codes_unspsc_multi_ids = fields.One2many('product.template.unspsc.multi', 'product_template_id', 'Codigos UNSPSC Asociados')

# class ProductTemplate(models.Model):
#     _inherit = 'product.product'

#     codes_unspsc_multi_ids = fields.One2many('product.template.unspsc.multi', 'product_template_id', 'Codigos UNSPSC Asociados')


class ProductTemplateUnspscMulti(models.Model):
    _name = 'product.template.unspsc.multi'
    _description = 'Relacion Multiple Codigos UNSPSC'
    _rec_name = 'unspsc_code_id' 

    unspsc_code_id = fields.Many2one('product.unspsc.code', 'Categoría de producto UNSPSC', domain=[('applies_to', '=', 'product')],
        help='The UNSPSC code related to this product.  Used for edi in Colombia, Peru and Mexico')

    product_template_id = fields.Many2one('product.template', 'ID Ref. UNSPSC MUlti')
