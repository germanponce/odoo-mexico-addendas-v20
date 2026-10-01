# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# ── Odoo 18 migration notes ────────────────────────────────────────────────
# 1. Removed `from lxml import elist` — lxml.elist does not exist.
# 2. Replaced `etree.tostring` with `et.tostring` (alias was already imported).
# 3. Removed call to `_l10n_mx_edi_convert_cfdi32_to_cfdi33` — that helper
#    lived in the legacy l10n_mx_einvoice / old l10n_mx_edi and no longer
#    exists in the Odoo 17/18 rewrite of l10n_mx_edi. CFDI 3.2 is obsolete
#    since 2018, so the conversion branch is simply dropped.
# 4. Moved `float_round` import to odoo.tools.float_utils (direct source).
# 5. `from odoo import _` preferred over `from odoo.tools.translate import _`.
# ──────────────────────────────────────────────────────────────────────────

import base64
from codecs import BOM_UTF8

from lxml import objectify
from lxml import etree as et

from odoo import models, api, fields, _
from odoo.tools.float_utils import float_round
from odoo.exceptions import UserError

from . import BeautifyCFDI

from odoo.modules import module

import xmltodict
from xml.dom.minidom import parseString
import requests

import logging
_logger = logging.getLogger(__name__)

BOM_UTF8U = BOM_UTF8.decode('UTF-8')


def create_list_html(data):
    if not data:
        return ''
    msg = ''
    for x in data.keys():
        if 'xmlns' not in x:
            msg += "<li>%s : %s</li>" % (x.replace('a:', ''), data[x])
    return '<ul>' + msg + '</ul>'


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    # ── CFDI string helpers ────────────────────────────────────────────────

    @api.model
    def get_cfdi_strings_4_xml(self, xml_file, purchase_order):
        xml_string = xml_file.read()
        attachment_cfdi_file_bytes_string = xml_string
        attachment_cfdi_file_string = xml_string.decode("utf-8")
        if 'cfdi:Comprobante' not in attachment_cfdi_file_string:
            return False, False
        return attachment_cfdi_file_string, attachment_cfdi_file_bytes_string

    def get_cfdi_vals_from_xml_strong(self, xml_string, purchase_order):
        module_path = module.get_module_path('l10n_mx_portal_vendor_bills')
        json_config = module_path + '/models/config.json'
        try:
            beauty_res = BeautifyCFDI.BeautifyCFDI(xml_string, 'pdf', json_config)
        except Exception:
            return {}

        beauty_emisor = beauty_res['emisor']
        vals_emisor = {
            'nombre_emisor': beauty_emisor['NombreEmisor'],
            'rfc_emisor': beauty_emisor['RfcEmisor'],
            'regimen_emisor': beauty_emisor['RegimenEmisor'],
        }

        beauty_receptor = beauty_res['receptor']
        vals_receptor = {
            'nombre_receptor': beauty_receptor['NombreReceptor'],
            'rfc_receptor': beauty_receptor['RfcReceptor'],
            'uso_cfdi_receptor': beauty_receptor['UsoReceptor'],
            'regimen_receptor': beauty_receptor['RegimenReceptor'],
            'domicilio_fiscal_receptor': beauty_receptor['DomicilioFiscalReceptor'],
        }

        conceptos_vals = beauty_res['conceptos']
        cfdi_conceptos = []
        for concepto in conceptos_vals or []:
            impuestos_list = []
            for impuesto_key, impuesto_vals in (concepto.get('Impuestos') or {}).items():
                impuestos_list.append((0, 0, {
                    'name': impuesto_vals['Impuesto'],
                    'tipo_impuesto': impuesto_vals['TipoImpuesto'],
                    'factor': impuesto_vals['TipoFactor'],
                    'tasa_cuota': impuesto_vals['TasaOCuota'],
                    'base': impuesto_vals['Base'],
                    'importe': impuesto_vals['Importe'],
                }))
            cfdi_conceptos.append({
                'name': concepto['Descripcion'],
                'clave': concepto['ClaveProdServ'],
                'unidad': concepto['Unidad'],
                'claveunidad': concepto['ClaveUnidad'],
                'cantidad': concepto['Cantidad'],
                'precio': concepto['ValorUnitario'],
                'total': concepto['Importe'],
                'impuesto_ids': impuestos_list,
            })

        beauty_comprobante = beauty_res['comprobante']
        fecha_emision = beauty_comprobante['Fecha']
        fecha_timbrado = beauty_comprobante['FechaTimbrado']
        return {
            'cfdi_emisor': vals_emisor,
            'cfdi_receptor': vals_receptor,
            'cfdi_conceptos': cfdi_conceptos,
            'comprobante_fecha': fecha_emision,
            'metodo_pago': beauty_comprobante['MetodoPago'],
            'version': beauty_comprobante['Version'],
            'tipo_comprobante': beauty_comprobante['TipoDeComprobante'],
            'certificado_documento': beauty_comprobante['Certificado'],
            'no_certificado_documento': beauty_comprobante['NoCertificado'],
            'forma_pago': beauty_comprobante['FormaPago'],
            'sello_emisor': beauty_comprobante['SelloCFD'],
            'sello_sat': beauty_comprobante['SelloSAT'],
            'lugar_expedicion': beauty_comprobante['LugarExpedicion'],
            'moneda': beauty_comprobante['Moneda'],
            'documento_uuid': beauty_comprobante['UUID'],
            'fechatimbrado_doc': fecha_timbrado,
            'rfc_pac': beauty_comprobante['RfcProvCertif'],
            'no_certificado_sat': beauty_comprobante['NoCertificadoSAT'],
            'total': beauty_comprobante['Total'],
            'subtotal': beauty_comprobante['Subtotal'],
            'serie_documento': beauty_comprobante['Serie'],
            'folio_documento': beauty_comprobante['Folio'],
            'tipo_cambio': beauty_comprobante['TipoCambio'],
        }

    # ── Validaciones opcionales (configurables por empresa) ────────────────

    def validate_sat_status(self, xml_dict_vals, purchase_order):
        body = (
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
            ' xmlns:tem="http://tempuri.org/"><soapenv:Header/><soapenv:Body>'
            '<tem:Consulta><tem:expresionImpresa><![CDATA[?re={0}&rr={1}&tt={2}&id={3}]]>'
            '</tem:expresionImpresa></tem:Consulta></soapenv:Body></soapenv:Envelope>'
        )
        url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl'
        headers = {
            'Content-type': 'text/xml;charset="utf-8"',
            'Accept': 'text/xml',
            'SOAPAction': 'http://tempuri.org/IConsultaCFDIService/Consulta',
        }

        uuid = xml_dict_vals['documento_uuid']
        rfc_emisor = (xml_dict_vals['cfdi_emisor']['rfc_emisor']
                      .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
        rfc_receptor = (xml_dict_vals['cfdi_receptor']['rfc_receptor']
                        .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
        monto_total = float(xml_dict_vals['total'])

        result = requests.post(url=url, headers=headers, data=body.format(
            rfc_emisor, rfc_receptor, monto_total, uuid))
        if result.status_code == 200:
            res = xmltodict.parse(result.text)
            estado_cfdi = res['s:Envelope']['s:Body']['ConsultaResponse']['ConsultaResult']['a:Estado']
        else:
            estado_cfdi = "Hubo un error al consultar el estado en el SAT, intentalo mas tarde."

        if estado_cfdi != 'Vigente':
            estado_cfdi = ("La factura no se encuentra vigente en el SAT, "
                           "consulte mas tarde o valida directamente en el portal del SAT.")
        return estado_cfdi

    def validate_rfc_partner(self, xml_dict_vals, purchase_order):
        rfc_emisor = xml_dict_vals['cfdi_emisor']['rfc_emisor']
        partner_rfc = purchase_order.partner_id.vat or ''
        if rfc_emisor != partner_rfc:
            return "El RFC del Proveedor (Emisor) no coincide con el registrado en el sistema."
        return "OK"

    def validate_rfc_company(self, xml_dict_vals, purchase_order):
        rfc_receptor = xml_dict_vals['cfdi_receptor']['rfc_receptor']
        company_rfc = purchase_order.company_id.partner_id.vat or ''
        if rfc_receptor != company_rfc:
            return "El RFC de la Empresa (Receptor) no coincide con el registrado en el sistema."
        return "OK"

    def validate_unique_uuid(self, xml_dict_vals, purchase_order):
        uuid = xml_dict_vals['documento_uuid']
        account_invoice_ids = self.env['account.move'].sudo().search(
            [('vendor_uuid', '=', uuid), ('state', '!=', 'cancel')])
        if account_invoice_ids:
            return "El UUID (folio fiscal) del archivo adjunto ya se encuentra registrado en una factura anterior."
        return "OK"

    def validate_amount_total(self, xml_dict_vals, purchase_order):
        cfdi_total = float(xml_dict_vals['total'])
        parameter = 1.5
        low = purchase_order.amount_total - parameter
        upp = purchase_order.amount_total + parameter
        if cfdi_total > upp or cfdi_total < low:
            return "El Total del CFDI no corresponde al monto de la Orden de Compra."
        return "OK"

    def validate_fiscal_year(self, xml_dict_vals, purchase_order):
        comprobante_fecha = xml_dict_vals['comprobante_fecha']
        comprobante_year = comprobante_fecha.split('-')[0]
        current_year = str(fields.Date.context_today(self)).split('-')[0]
        if current_year != comprobante_year:
            return "El año fiscal del CFDI no corresponde con el año en curso."
        return "OK"

    # ── Validaciones obligatorias ──────────────────────────────────────────

    def validate_cfdi_signed(self, xml_dict_vals, purchase_order):
        tipo_comprobante = xml_dict_vals.get('tipo_comprobante', '')
        total = float(xml_dict_vals.get('total', '0'))
        if tipo_comprobante != 'I':
            return "El tipo de comprobante del archivo adjunto es invalido, solo se admiten facturas de tipo Ingreso."
        if not total:
            return "El tipo de comprobante del archivo adjunto es invalido, no contiene monto."
        return "OK"

    def validate_xml_type(self, xml_dict_vals, purchase_order):
        uuid = xml_dict_vals.get('documento_uuid', '')
        if not uuid:
            return "El archivo adjunto no cuenta con Folio Fiscal (UUID)."
        return "OK"

    # ── Dispatcher de validaciones ─────────────────────────────────────────

    def check_invoice_bill_xml_check_validations(self, xml_dict_vals, purchase_order):
        if purchase_order.partner_id.danone_supplier_type == 'dairy_supplier':
            return self._run_validations(xml_dict_vals, purchase_order, dairy=True)
        return self._run_validations(xml_dict_vals, purchase_order, dairy=False)

    def _run_validations(self, xml_dict_vals, purchase_order, dairy=False):
        """Ejecuta todas las validaciones y devuelve un dict con el resultado."""
        _logger.info("\n\n *** Validaciones %s ...", "Lechero" if dairy else "General")
        empty = {'error': False, 'message_error': '', 'validation_error': ''}
        company = purchase_order.company_id

        def _fail(msg, field):
            return {'error': True, 'message_error': msg, 'validation_field_error': field}

        res = self.validate_cfdi_signed(xml_dict_vals, purchase_order)
        if res != 'OK':
            return _fail(res, 'validate_cfdi_signed')

        res = self.validate_xml_type(xml_dict_vals, purchase_order)
        if res != 'OK':
            return _fail(res, 'validate_xml_type')

        if company.validate_sat_status:
            res = self.validate_sat_status(xml_dict_vals, purchase_order)
            if res != 'Vigente':
                return _fail(res, 'validate_sat_status')

        if company.validate_rfc_partner:
            res = self.validate_rfc_partner(xml_dict_vals, purchase_order)
            if res != 'OK':
                return _fail(res, 'validate_rfc_partner')

        if company.validate_rfc_company:
            res = self.validate_rfc_company(xml_dict_vals, purchase_order)
            if res != 'OK':
                return _fail(res, 'validate_rfc_company')

        if company.validate_unique_uuid:
            res = self.validate_unique_uuid(xml_dict_vals, purchase_order)
            if res != 'OK':
                return _fail(res, 'validate_unique_uuid')

        if company.validate_amount_total:
            if dairy:
                res = self.validate_amount_total_quantities_pending(xml_dict_vals, purchase_order)
            else:
                res = self.validate_amount_total(xml_dict_vals, purchase_order)
            if res != 'OK':
                return _fail(res, 'validate_amount_total')

        if company.validate_fiscal_year:
            res = self.validate_fiscal_year(xml_dict_vals, purchase_order)
            if res != 'OK':
                return _fail(res, 'validate_fiscal_year')

        return empty

    def validate_amount_total_quantities_pending(self, xml_dict_vals, purchase_order):
        """Validación específica para proveedores lecheros (por entrega)."""
        check_total = "OK"
        cfdi_conceptos = xml_dict_vals.get('cfdi_conceptos', [])
        odoo_conceptos_dict = {}
        for line in purchase_order.order_line:
            if not line.qty_to_invoice:
                continue
            codigo_sat = line.product_id.sat_product_id.code
            price_unit_with_taxes = line.price_total / line.product_uom_qty
            odoo_conceptos_dict[codigo_sat] = {
                'qty_to_invoice': line.qty_to_invoice,
                'price_unit': line.price_unit,
                'price_total': line.price_total,
                'product_uom_qty': line.product_uom_qty,
                'product_uom_sat': line.product_uom.sat_uom_id.code,
                'price_unit_with_taxes': price_unit_with_taxes,
            }

        cfdi_total = float(xml_dict_vals['total'])
        xml_check_computed_amount = 0.0
        for concepto in cfdi_conceptos:
            concepto_qty = concepto.get('cantidad')
            concepto_description = concepto.get('name')
            concepto_clave_sat = concepto.get('clave')
            concepto_unidad = concepto.get('claveunidad')
            if concepto_clave_sat not in odoo_conceptos_dict:
                return ("<br/><strong>Producto: </strong>%s<br/>"
                        "<strong>Clave SAT: </strong>%s<br/>"
                        "<strong>Mensaje: </strong>No se encontraron coincidencias en la Orden de Compra."
                        % (concepto_description, concepto_clave_sat))
            odoo_line_info = odoo_conceptos_dict[concepto_clave_sat]
            qty_to_invoice = odoo_line_info['qty_to_invoice']
            product_uom_sat = odoo_line_info['product_uom_sat']
            if product_uom_sat != concepto_unidad:
                return ("<br/><strong>Producto:</strong> %s<br/>"
                        "<strong>Unidad de Medida SAT: </strong>%s<br/>"
                        "<strong>Mensaje: </strong>La clave de la unidad no coincide con la información de la Orden de Compra."
                        % (concepto_description, concepto_unidad))
            if float(concepto_qty) > qty_to_invoice:
                return ("<br/><strong>Producto: </strong>%s<br/>"
                        "<strong>Clave SAT: </strong>%s<br/>"
                        "<strong>Mensaje: </strong>Esta intentando facturar una cantidad superior a la entregada."
                        % (concepto_description, concepto_clave_sat))
            price_unit_with_taxes = odoo_line_info['price_unit_with_taxes']
            xml_check_computed_amount += price_unit_with_taxes * float(concepto_qty)

        parameter = 1.5
        low = xml_check_computed_amount - parameter
        upp = xml_check_computed_amount + parameter
        if cfdi_total > upp or cfdi_total < low:
            check_total = ("<br/>El Total del CFDI no corresponde al monto total disponible para facturar."
                           "<br/><strong>Mensaje: </strong>El monto disponible para facturar es %s."
                           % ('$ {:0,.2f}'.format(round(xml_check_computed_amount, 2)),))
        return check_total

    def check_invoice_bill_xml_get_uuid(self, xml_dict_vals, purchase_order):
        return xml_dict_vals.get('documento_uuid', '') or ''

    # ── Parseo de XML ──────────────────────────────────────────────────────

    @api.model
    def parse_xml(self, xml_file, xml_file_bytes_string, purchase):
        data = base64.b64encode(xml_file_bytes_string)
        res = self.sudo().check_xml({xml_file.filename: data}, purchase)

        xml = objectify.fromstring(xml_file_bytes_string)

        if not res.get(xml_file.filename, True):
            return res, xml_file.filename

        doc_number = xml.get('Folio', False)
        serial = xml.get('Serie', False)
        date = xml.get('Fecha', False)
        try:
            supplier_vat = xml.Emisor.get('Rfc', False)
        except Exception:
            raise UserError(_("El archivo XML es invalido."))

        filename = '%s_%s_%s_%s' % (supplier_vat, doc_number, serial, date[:10])
        return res, filename

    @api.model
    def check_xml(self, files, purchase):
        """Valida los CFDIs antes de crear la factura.

        Odoo 18: se eliminó el bloque de conversión CFDI 3.2→3.3 ya que
        ``_l10n_mx_edi_convert_cfdi32_to_cfdi33`` no existe en l10n_mx_edi v17/18+
        y el formato 3.2 está obsoleto desde 2018.
        """
        if not isinstance(files, dict):
            raise UserError(_("Something went wrong. The parameter for XML files must be a dictionary."))

        wrongfiles = {}
        invoices = {}
        account_id = self._context.get('account_id', False)

        for key, xml64 in files.items():
            try:
                if isinstance(xml64, bytes):
                    xml64 = xml64.decode()
                xml_str = base64.b64decode(xml64.replace('data:text/xml;base64,', ''))
                xml_str = xml_str.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation')
                xml = objectify.fromstring(xml_str)
            except (AttributeError, SyntaxError) as exc:
                wrongfiles[key] = {
                    'xml64': xml64, 'where': 'CheckXML',
                    'error': [exc.__class__.__name__, str(exc)],
                }
                continue

            tipo = xml.get('TipoDeComprobante', False)
            if tipo not in ('I', 'E'):
                wrongfiles[key] = {'cfdi_type': True, 'xml64': xml64}
                continue

            validated = self.validate_documents(key, xml, account_id, purchase)
            wrongfiles.update(validated.get('wrongfiles'))
            if wrongfiles.get(key) and wrongfiles[key].get('xml64'):
                wrongfiles[key]['xml64'] = xml64
            invoices.update(validated.get('invoices'))

        return {'wrongfiles': wrongfiles, 'invoices': invoices}

    def validate_documents(self, key, xml, account_idi, purchase):
        wrongfiles = {}
        invoices = {}

        # xml_str utilizado para logs / futuros adjuntos
        xml_str = et.tostring(xml, pretty_print=True, encoding='UTF-8')  # noqa: F841

        xml_vat_emitter, xml_vat_receiver, xml_amount, xml_currency, version, \
            xml_name_supplier, xml_type_of_document, xml_uuid, xml_serie_folio, xml_taxes = \
            self._get_xml_data(xml)

        xml_folio = xml.get('Folio', '')  # noqa: F841
        xml_date = xml.get('Fecha', '')   # noqa: F841

        invoice_action = purchase.action_create_invoice()
        invoice = self.env['account.move'].browse(invoice_action.get('res_id', []))
        invoice.payment_reference = xml_serie_folio

        invoices[key] = {'invoice_id': invoice.id}
        invoices['invoice_inst'] = invoice

        return {'wrongfiles': wrongfiles, 'invoices': invoices}

    # ── Helpers internos de XML ────────────────────────────────────────────

    def _l10n_mx_edi_get_tfd_etree(self, cfdi_node):
        if hasattr(cfdi_node, 'Complemento'):
            node = cfdi_node.Complemento.xpath(
                'tfd:TimbreFiscalDigital[1]',
                namespaces={'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'})
            return node[0] if node else None
        return None

    @api.model
    def _get_xml_data(self, xml):
        vat_emitter = xml.Emisor.get('Rfc', '').upper()
        vat_receiver = xml.Receptor.get('Rfc', '').upper()
        amount = float(xml.get('Total', 0.0))
        currency = xml.get('Moneda', 'MXN')
        version = xml.get('Version', xml.get('version'))
        name_supplier = xml.Emisor.get('Nombre', '')
        document_type = xml.get('TipoDeComprobante', False)
        tfd = self._l10n_mx_edi_get_tfd_etree(xml)
        uuid = False if tfd is None else tfd.get('UUID', '')
        folio = self.get_xml_folio(xml)
        taxes = self.get_impuestos(xml)
        local_taxes = self.get_local_taxes(xml)
        taxes['wrong_taxes'] = taxes.get('wrong_taxes', []) + local_taxes.get('wrong_taxes', [])
        taxes['withno_account'] = taxes.get('withno_account', []) + local_taxes.get('withno_account', [])
        return vat_emitter, vat_receiver, amount, currency, version, name_supplier, document_type, uuid, folio, taxes

    def get_xml_folio(self, xml):
        return '%s%s' % (xml.get('Serie', ''), xml.get('Folio', ''))

    @staticmethod
    def collect_taxes(taxes_xml):
        taxes = []
        tax_codes = {'001': 'ISR', '002': 'IVA', '003': 'IEPS'}
        for rec in taxes_xml:
            tax_xml = tax_codes.get(rec.get('Impuesto', ''), rec.get('Impuesto', ''))
            amount_xml = float(rec.get('Importe', '0.0'))
            rate_xml = float_round(float(rec.get('TasaOCuota', '0.0')) * 100, 4)
            if 'Retenciones' in rec.getparent().tag:
                amount_xml *= -1
                rate_xml *= -1
            base = float(rec.get('Base', '0.0'))
            taxes.append({'rate': rate_xml, 'tax': tax_xml, 'amount': amount_xml, 'base': base})
        return taxes

    def get_local_taxes(self, xml):
        if not hasattr(xml, 'Complemento'):
            return {}
        type_tax_use = 'purchase' if self._context.get('l10n_mx_edi_invoice_type') == 'in' else 'sale'
        local_taxes = xml.Complemento.xpath(
            'implocal:ImpuestosLocales',
            namespaces={'implocal': 'http://www.sat.gob.mx/implocal'})
        taxes_list = {'wrong_taxes': [], 'withno_account': [], 'taxes': []}
        if not local_taxes:
            return taxes_list
        local_taxes = local_taxes[0]
        tax_obj = self.env['account.tax']
        taxes_to_omit = self.get_taxes_to_omit()

        def _process_tax(name, tasa, importe):
            tax = tax_obj.search([
                '&', ('type_tax_use', '=', type_tax_use),
                '|', ('name', '=', name), ('amount', '=', tasa)], limit=1)
            if not tax and name not in taxes_to_omit:
                taxes_list['wrong_taxes'].append(name)
                return
            # Odoo 17/18: repartition lines still accessible via invoice_repartition_line_ids
            tax_account = tax.invoice_repartition_line_ids.filtered(
                lambda r: r.repartition_type == 'tax')
            if not tax_account and name not in taxes_to_omit:
                taxes_list['withno_account'].append(name)
                return
            taxes_list['taxes'].append((0, 0, {
                'tax_id': tax.id,
                'account_id': tax_account[:1].id,
                'name': name,
                'amount': importe,
                'for_expenses': not bool(tax),
            }))

        if hasattr(local_taxes, 'RetencionesLocales'):
            for local_ret in local_taxes.RetencionesLocales:
                _process_tax(
                    local_ret.get('ImpLocRetenido'),
                    float(local_ret.get('TasadeRetencion')) * -1,
                    float(local_ret.get('Importe')) * -1,
                )
        if hasattr(local_taxes, 'TrasladosLocales'):
            for local_tras in local_taxes.TrasladosLocales:
                _process_tax(
                    local_tras.get('ImpLocTrasladado'),
                    float(local_tras.get('TasadeTraslado')),
                    float(local_tras.get('Importe')),
                )
        return taxes_list

    def get_impuestos(self, xml):
        if not hasattr(xml, 'Impuestos'):
            return {}
        taxes_list = {'wrong_taxes': [], 'taxes_ids': {}, 'withno_account': []}
        for index, rec in enumerate(xml.Conceptos.Concepto):
            if not hasattr(rec, 'Impuestos'):
                continue
            taxes_list['taxes_ids'][index] = []
            taxes_xml = rec.Impuestos
            taxes = []
            if hasattr(taxes_xml, 'Traslados'):
                taxes = self.collect_taxes(taxes_xml.Traslados.Traslado)
            if hasattr(taxes_xml, 'Retenciones'):
                taxes += self.collect_taxes(taxes_xml.Retenciones.Retencion)

            for tax in taxes:
                tax_group_id = self.env['account.tax.group'].search([('name', 'ilike', tax['tax'])])
                domain = [('tax_group_id', 'in', tax_group_id.ids), ('type_tax_use', '=', 'purchase')]
                if -10.67 <= tax['rate'] <= -10.66:
                    domain += [('amount', '<=', -10.66), ('amount', '>=', -10.67)]
                else:
                    domain.append(('amount', '=', tax['rate']))

                name = '%s(%s%%)' % (tax['tax'], tax['rate'])
                tax_get = self.env['account.tax'].search(domain, limit=1)
                taxes_to_omit = self.get_taxes_to_omit()

                if (not tax_group_id or not tax_get) and tax.get('tax') not in taxes_to_omit:
                    taxes_list['wrong_taxes'].append(name)
                    continue
                tax_account = tax_get.invoice_repartition_line_ids.filtered(
                    lambda r: r.repartition_type == 'tax')
                if not tax_account and tax.get('tax', '') not in taxes_to_omit:
                    taxes_list['withno_account'].append(name or tax['tax'])
                else:
                    tax['id'] = tax_get.id
                    tax['account'] = tax_account[:1].id
                    tax['name'] = name or tax['tax']
                    tax['for_expenses'] = not bool(tax_get)
                    taxes_list['taxes_ids'][index].append(tax)
        return taxes_list

    def get_taxes_to_omit(self):
        taxes = self.env['ir.config_parameter'].sudo().get_param('l10n_mx_taxes_for_expense', '')
        return taxes.split(',')

    @api.model
    def _get_fuel_codes(self):
        return [str(r) for r in range(15101500, 15101516)]
