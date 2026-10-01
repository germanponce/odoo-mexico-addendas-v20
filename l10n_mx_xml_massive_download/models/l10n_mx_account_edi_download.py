# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from odoo import api, fields, models, tools, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
from lxml import etree # type: ignore
from lxml.objectify import fromstring # type: ignore
import base64
import json
import requests # type: ignore
import hashlib
import logging
import time
from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import ( # type: ignore
    CFDI_CODE_TO_TAX_TYPE,
)
from io import BytesIO
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
import qrcode
from urllib.parse import urlencode

_logger = logging.getLogger(__name__) 
from datetime import datetime, timedelta, date, time as dtime
import pytz


def _get_cfdi_ns(root):
    """Devuelve el namespace cfdi correcto según la versión del comprobante (3.3 o 4.0)."""
    version = root.get('Version', '4.0') if root is not None else '4.0'
    ns_url = 'http://www.sat.gob.mx/cfd/3' if version.startswith('3') else 'http://www.sat.gob.mx/cfd/4'
    return {'cfdi': ns_url}


# Mimetypes y patrones que aceptamos como "archivo XML del CFDI" en attachments.
# IMPORTANTE: algunos sistemas (forks viejos de Cosal y otros) guardan los XMLs
# con mimetype 'text/plain' en lugar de 'application/xml'. Si filtramos estricto
# por 'application/xml', perdemos esos attachments. Por eso el helper es laxo.
_XML_MIMETYPES = ('application/xml', 'text/xml', 'text/plain')


def _is_xml_attachment(att):
    """True si el attachment se ve como un XML del CFDI, sin importar el
    mimetype exacto. Acepta:
      - mimetype application/xml o text/xml (caso ideal)
      - mimetype text/plain con nombre .xml (caso Cosal)
      - cualquier mimetype donde el name termine en .xml (fallback)
    """
    if not att:
        return False
    name = (att.name or '').lower()
    mt = (att.mimetype or '').lower()
    if mt in _XML_MIMETYPES and name.endswith('.xml'):
        return True
    # Fallback: si el nombre dice .xml, confiamos en eso (algunos sistemas
    # almacenan mimetype incorrecto pero el binario sí es XML).
    if name.endswith('.xml'):
        return True
    return False


def similar(a, b):
    """Ratio de similitud entre dos descripciones de texto.
    Usado para sugerencia de producto/cuenta contable. A nivel de modulo para
    que este disponible en helpers fuera de _run_download_pipeline."""
    return SequenceMatcher(None, a or '', b or '').ratio()


USO_CFDI  = [
    ("G01", "Adquisición de mercancías"),
    ("G02", "Devoluciones, descuentos o bonificaciones"),
    ("G03", "Gastos en general"),
    ("I01", "Construcciones"),
    ("101", "Construcciones"),
    ("I02", "Mobiliario y equipo de oficina por inversiones"),
    ("I03", "Equipo de transporte"),
    ("I04", "Equipo de cómputo y accesorios"),    
    ("I05", "Dados, troqueles, moldes, matrices y herramental"),
    ("I06", "Comunicaciones telefónicas"),
    ("I07", "Comunicaciones satelitales"),
    ("I08", "Otra maquinaria y equipo"),
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
    ("P01", "Por definir"),
]
 
PAYMENT_METHOD = [
    ("01", "Efectivo"),
    ("02", "Cheque nominativo"),
    ("03", "Transferencia electrónica de fondos"),
    ("04", "Tarjeta de crédito"),
    ("05", "Monedero electrónico"),
    ("06", "Dinero electrónico"),
    ("08", "Vales de despensa"),
    ("12", "Dación en pago"),
    ("13", "Pago por subrogación"),
    ("14", "Pago por consignación"),
    ("15", "Condonación"),
    ("17", "Compensación"),
    ("23", "Novación"),
    ("24", "Confusión"),
    ("25", "Remisión de deuda"),
    ("26", "Prescripción o caducidad"),
    ("27", "A satisfacción del acreedor"),
    ("28", "Tarjeta de débito"),
    ("29", "Tarjeta de servicios"),
    ("30", "Aplicación de anticipos"),
    ("31", "Intermediario pagos"),
    ("99", "Por definir"),
]

TAX_REGIME = [
    ("601", "General de Ley Personas Morales"),
    ("603", "Personas Morales con Fines no Lucrativos"),
    ("605", "Sueldos y Salarios e Ingresos Asimilados a Salarios"),
    ("606", "Arrendamiento"),
    ("607", "Régimen de Enajenación o Adquisición de Bienes"),
    ("609", "Consolidación"),
    ("610", "Residentes en el Extranjero sin Establecimiento Permanente en México"),
    ("611", "Ingresos por Dividendos (socios y accionistas)"),
    ("612", "Personas Físicas con Actividades Empresariales y Profesionales"),
    ("614", "Ingresos por intereses"),
    ("615", "Régimen de los ingresos por obtención de premios"),
    ("616", "Sin obligaciones fiscales"),
    ("620", "Sociedades Cooperativas de Producción que optan por diferir sus ingresos"),
    ("621", "Incorporación Fiscal"),
    ("622", "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras"),
    ("623", "Opcional para Grupos de Sociedades"),
    ("624", "Coordinados"),
    ("625", "Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas"),
    ("626", "Régimen Simplificado de Confianza"),
    ("628", "Hidrocarburos"),
    ("629", "De los Regímenes Fiscales Preferentes y de las Empresas Multinacionales"),
    ("630", "Enajenación de acciones en bolsa de valores")
]

class DownloadedXmlSat(models.Model):
    _name = "account.edi.downloaded.xml.sat"
    _description = "Account Edi Download From SAT Web Service"
    _inherit = ['mail.thread']
    _check_company_auto = True
  
    name = fields.Char(string="UUID", required=True, index='trigram')
    active_company_id = fields.Integer(string='Empresa activa', compute='_compute_active_company_id')
    company_id = fields.Many2one('res.company', string='Empresa configurada', default=lambda self: self.env.company.id) 
    partner_id = fields.Many2one('res.partner', string="Proveedor") # Cliente/Proveedor
    invoice_id = fields.Many2one('account.move', string="Factura Relacionada") # Factura
    # Relaciones paralelas para tipos de CFDI no-factura (P, T, N).
    # invoice_id se reserva para tipo I/E. Los siguientes se llenan segun corresponda
    # via action_search_related_invoice cuando hay match por UUID exacto.
    payment_id = fields.Many2one(
        'account.payment',
        string="Pago Odoo Relacionado",
        help="Cuando el CFDI es complemento de pago (P), apunta al account.payment "
             "cuyo stored_sat_uuid coincide con el UUID del XML.",
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string="Transferencia Odoo Relacionada",
        help="Cuando el CFDI es traslado (T), apunta al stock.picking cuyo "
             "l10n_mx_edi_cfdi_uuid coincide con el UUID del XML.",
    )
    payslip_id = fields.Many2one(
        'hr.payslip',
        string="Recibo de Nomina Odoo Relacionado",
        help="Cuando el CFDI es nomina (N), apunta al hr.payslip cuyo "
             "l10n_mx_edi_cfdi_uuid coincide con el UUID del XML.",
    )
    cfdi_type = fields.Selection([('recibidos', 'Recibidos'),('emitidos', 'Emitidos'), ], string='Tipo', required=True, default='emitidos')
    batch_id = fields.Many2one(
        comodel_name='account.edi.api.download',
        string='Batch',
        required=True,
        readonly=True,
        index=True,
        ondelete="cascade",
        check_company=True,
    )
    attachment_id = fields.Many2one('ir.attachment', string='XML Attachment')
    document_date =  fields.Date(string="Fecha de Documento")
    # Fecha en que el PAC timbró el CFDI (tfd:TimbreFiscalDigital/@FechaTimbrado).
    # Distinta de document_date: el SAT y Odoo usan document_date para acumulación
    # contable y deducción, pero fecha_timbrado es la oficial del timbrado fiscal.
    fecha_timbrado = fields.Datetime(string="Fecha de Timbrado", index=True)
    serie = fields.Char(string="Serie Factura")
    folio = fields.Char(string="Folio Factura")
    divisa = fields.Char(string="Divisa en Factura")
    currency_id = fields.Many2one('res.currency', string='Moneda', compute='_compute_currency_id', store=True, default=lambda self: self.env.company.currency_id)
    state = fields.Selection(
        selection=[
            ('not_imported', 'No Importado'),
            ('draft', 'Borrador'),
            ('posted', 'Publicado'),
            ('cancel', 'Cancelado'),
            ('ignored', 'Ignorado'),
            ('error_relating', 'Error Relacionando'),
        ],
        string='Status',
        default='draft',
    )
    sat_state = fields.Selection([
        ('Vigente', 'Vigente'),
        ('Cancelado','Cancelado'),
        ('No Encontrado', 'No encontrado'),
        ('Sin Definir', 'Sin Definir')
    ], string="Estatus SAT", default='Sin Definir')
    sat_last_sync = fields.Datetime(
        string="Última sincronización SAT",
        index=True,
        help="Fecha en la que se consultó el estatus por última vez. Evita reprocesar el mismo XML varias veces el mismo día.",
    )
    payment_method = fields.Selection([('PPD','PPD'),('PUE','PUE')], string='Metodo de Pago')
    sub_total = fields.Float(string="Sub Total", required=True)
    amount_total = fields.Float(string="Total", required=True)
    document_type = fields.Selection([
        ('I', 'Ingreso'),
        ('E', 'Egreso'),
        ('T', 'Traslado'),
        ('N', 'Nomina'),
        ('P', 'Pago'),
    ], string='Tipo de Documento')
    cfdi_usage = fields.Selection(USO_CFDI, string="Uso CFDI")
    imported = fields.Boolean(string="Importado", default=False)
    discount = fields.Float(string="Descuento")
    
    downloaded_product_id = fields.One2many(
        'account.edi.downloaded.xml.sat.products',
        'downloaded_invoice_id',
        string='Downloaded product ID',)  
    payment_method_sat = fields.Selection(PAYMENT_METHOD, string="Forma de Pago")
    total_impuestos = fields.Float(string='Total Impuestos')
    total_retenciones = fields.Float(string='Total Retenciones')
    tax_regime = fields.Selection(TAX_REGIME, string="Regimen Fiscal")

    # ---------------- Desglose de impuestos por tipo+tasa ----------------
    # Se parsean del nodo global cfdi:Impuestos (root o concepto-nivel).
    # CFDI 4.0 usa codigos: 001=ISR, 002=IVA, 003=IEPS.
    # Cada campo agrega el Importe correspondiente. Si no hay valor, queda 0.
    # En vistas se usa optional="hide" para esconder los menos comunes por defecto,
    # y invisible="not field" en form para no mostrar lineas con 0.
    tax_iva_16_traslado = fields.Float(string='IVA 16% Trasladado')
    tax_iva_8_traslado = fields.Float(string='IVA 8% Trasladado (frontera)')
    tax_iva_0_traslado = fields.Float(string='IVA Tasa 0% Trasladado')
    tax_iva_exento_traslado = fields.Float(string='IVA Exento Trasladado')
    tax_iva_ret = fields.Float(string='IVA Retenido')
    tax_isr_ret = fields.Float(string='ISR Retenido')
    tax_ieps_traslado = fields.Float(string='IEPS Trasladado')
    tax_ieps_ret = fields.Float(string='IEPS Retenido')
    tax_otros = fields.Float(string='Otros Impuestos', help="Suma de impuestos no estandar (locales, ISH, etc.)")

    # ============================================================================
    # CAMPOS PARA SELLOS DIGITALES Y CERTIFICADOS
    # ============================================================================
    sello_cfdi = fields.Text(string="Sello Digital CFDI", readonly=True, copy=False)
    sello_sat = fields.Text(string="Sello Digital SAT", readonly=True, copy=False)
    cadena_original = fields.Text(string="Cadena Original", readonly=True, copy=False)
    certificate_number = fields.Char(string="No. Certificado Emisor", readonly=True, copy=False)
    certificate_sat_number = fields.Char(string="No. Certificado SAT", readonly=True, copy=False)
    # Ola 1.6: store=False para evitar recompute masivo (13k registros = >30 min y rollback)
    # Se recalcula on-demand cuando el reporte PDF lo lee.
    qr_code_image = fields.Text(string="QR Code Image", compute="_compute_qr_code_image", readonly=True, store=False)

    # =========================================================================
    # FILTRADO POR PERMISOS DE TIPO DE CFDI (por usuario)
    # Se sobreescribe _search para que el ORM filtre dinámicamente los XMLs
    # según los flags can_see_cfdi_* del usuario actual. Esto oculta los
    # registros en CUALQUIER vista (list, kanban, search, dom_force de
    # smart-buttons) sin tener que tocar cada vista individual.
    # Los datos NO se eliminan; solo se ocultan en la UI.
    # =========================================================================
    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        user = self.env.user
        # superusuario (__system__) no debe filtrarse: garantiza migraciones,
        # crons y operaciones internas sin sorpresas.
        if not user or user._is_superuser():
            return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
        extra = []
        if not user.can_see_cfdi_ingreso:
            extra.append(('document_type', '!=', 'I'))
        if not user.can_see_cfdi_egreso:
            extra.append(('document_type', '!=', 'E'))
        if not user.can_see_cfdi_pago:
            extra.append(('document_type', '!=', 'P'))
        if not user.can_see_cfdi_nomina:
            extra.append(('document_type', '!=', 'N'))
        if not user.can_see_cfdi_traslado:
            extra.append(('document_type', '!=', 'T'))
        if extra:
            domain = list(domain) + extra
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    @api.depends('name', 'rfc_emisor', 'rfc_receptor', 'amount_total', 'sello_cfdi')
    def _compute_qr_code_image(self):
        """Genera el QR code como imagen base64 con la URL completa del SAT."""
        for record in self:
            if not record.name:
                record.qr_code_image = False
                continue
                
            try:
                # Construir URL del SAT con todos los parámetros
                params = {
                    'id': record.name,
                    're': record.rfc_emisor or '',
                    'rr': record.rfc_receptor or '',
                    'tt': f"{record.amount_total:.6f}",
                }
                
                # Agregar últimos 8 caracteres del sello si existe
                if record.sello_cfdi and len(record.sello_cfdi) >= 8:
                    params['fe'] = record.sello_cfdi[-8:]
                
                # URL completa
                url = f"https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?{urlencode(params)}"
                
                # Generar QR code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(url)
                qr.make(fit=True)
                
                # Crear imagen
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Convertir a base64
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                record.qr_code_image = img_base64
                
            except Exception as e:
                _logger.error(f"Error generando QR code para {record.name}: {e}")
                record.qr_code_image = False
    
    # ============================================================================
    # CAMPOS RFC Y EMPRESA (MIGRADOS DE V17)
    # ============================================================================
    rfc_emisor = fields.Char(
        string='RFC Emisor',
        compute='_compute_rfc_fields',
        store=True,
        index=True
    )
    rfc_receptor = fields.Char(
        string='RFC Receptor',
        compute='_compute_rfc_fields',
        store=True,
        index=True
    )
    rfc_empresa = fields.Char(
        string='RFC Empresa',
        compute='_compute_rfc_empresa',
        store=True,
        help='RFC de la empresa: Emisor en Emitidos, Receptor en Recibidos'
    )
    rfc_partner = fields.Char(
        string='RFC Contacto',
        compute='_compute_rfc_partner',
        store=True,
        help='RFC del proveedor/cliente: Receptor en Emitidos, Emisor en Recibidos'
    )
    company_mismatch = fields.Boolean(
        string='Empresa Incorrecta',
        compute='_compute_company_mismatch',
        store=True,
        help='Indica si el XML está asignado a una empresa incorrecta según el RFC'
    )
    is_coordinada_authorized = fields.Boolean(
        string='Es Coordinada Autorizada',
        compute='_compute_company_mismatch',
        store=True,
        help='True cuando el RFC del XML pertenece a una coordinada autorizada de la controladora (no es un mismatch real)'
    )
    
    # ============================================================================
    # ART 69-B ALERTA FISCAL (MIGRADO DE V17)
    # ============================================================================
    estatus_69b = fields.Char(
        string='⚠️ Estatus Artículo 69-B',
        index=True,
        help='Estatus del RFC ante el SAT según Artículo 69-B (Presunto, Definitivo, No listado, etc.)'
    )

    # ============================================================================
    # NUEVOS CAMPOS: Documento Origen (NO AFECTA FUNCIONALIDAD EXISTENTE)
    # ============================================================================
    origin_document_id = fields.Many2one(
        'account.move',
        string='Documento Origen',
        help='Documento origen relacionado (SO/PO/Factura)',
        index=True,
        copy=False,
        readonly=True,
    )
    
    origin_document_name = fields.Char(
        string='Referencia Origen',
        compute='_compute_origin_document_name',
        search='_search_origin_document_name',
        help='Nombre del documento origen (SO001, PO042, etc.)'
    )
    
    origin_document_type = fields.Selection([
        ('sale_order', 'Pedido de Venta'),
        ('purchase_order', 'Orden de Compra'),
        ('invoice', 'Factura'),
        ('other', 'Otro')
    ], string='Tipo Documento', compute='_compute_origin_document_name')

    def _compute_active_company_id(self):
        self.active_company_id = self.env.company.id
    
    @api.depends('attachment_id', 'attachment_id.datas')
    def _compute_rfc_fields(self):
        """Extraer RFC emisor y receptor del XML - MIGRADO DE V17"""
        for record in self:
            record.rfc_emisor = False
            record.rfc_receptor = False
            
            if not record.attachment_id or not record.attachment_id.datas:
                continue
            
            try:
                xml_content = base64.b64decode(record.attachment_id.datas)
                root = ET.fromstring(xml_content)
                ns = _get_cfdi_ns(root)
                
                emisor = root.find('.//cfdi:Emisor', namespaces=ns)
                if emisor is not None:
                    record.rfc_emisor = emisor.get('Rfc')
                
                receptor = root.find('.//cfdi:Receptor', namespaces=ns)
                if receptor is not None:
                    record.rfc_receptor = receptor.get('Rfc')
            except (ET.ParseError, ValueError, AttributeError):
                record.rfc_emisor = False
                record.rfc_receptor = False
    
    @api.depends('rfc_emisor', 'rfc_receptor', 'cfdi_type')
    def _compute_rfc_empresa(self):
        """Determinar el RFC de la empresa según el tipo de CFDI - MIGRADO DE V17"""
        for record in self:
            if record.cfdi_type == 'emitidos':
                record.rfc_empresa = record.rfc_emisor
            else:
                record.rfc_empresa = record.rfc_receptor
    
    @api.depends('divisa')
    def _compute_currency_id(self):
        """Calcular el currency_id basado en el campo divisa"""
        for record in self:
            if record.divisa:
                currency = self.env['res.currency'].search([('name', '=', record.divisa)], limit=1)
                record.currency_id = currency.id if currency else self.env.company.currency_id.id
            else:
                record.currency_id = self.env.company.currency_id.id
    
    @api.depends('rfc_emisor', 'rfc_receptor', 'cfdi_type')
    def _compute_rfc_partner(self):
        """Determinar el RFC del contacto según el tipo de CFDI - MIGRADO DE V17"""
        for record in self:
            if record.cfdi_type == 'emitidos':
                record.rfc_partner = record.rfc_receptor
            else:
                record.rfc_partner = record.rfc_emisor
    
    @api.depends('company_id', 'company_id.vat', 'rfc_emisor', 'rfc_receptor', 'cfdi_type')
    def _compute_company_mismatch(self):
        """Detectar si el XML está asignado a la empresa incorrecta - MIGRADO DE V17

        En un esquema single-tenant con coordinadas, un RFC distinto al VAT de la
        controladora NO es un error si pertenece a una coordinada autorizada
        registrada en `l10n_mx.cfdi.coordinado.relation`.
        """
        CoordRel = self.env.get('l10n_mx.cfdi.coordinado.relation')
        # Cache por (company_id, rfc) para evitar query por registro
        coord_cache = {}

        def _is_coord_authorized(company_id, rfc):
            if not (company_id and rfc and CoordRel is not None):
                return False
            key = (company_id, rfc)
            if key in coord_cache:
                return coord_cache[key]
            found = bool(CoordRel.sudo().search_count([
                ('controladora_company_id', '=', company_id),
                ('coordinada_vat', '=', rfc),
                ('active', '=', True),
            ], limit=1))
            coord_cache[key] = found
            return found

        for record in self:
            record.company_mismatch = False
            record.is_coordinada_authorized = False

            if not record.company_id or not record.company_id.vat:
                continue

            company_vat = record.company_id.vat
            xml_rfc = record.rfc_emisor if record.cfdi_type == 'emitidos' else record.rfc_receptor

            if not xml_rfc or xml_rfc == company_vat:
                continue

            # RFC distinto al de la company: ¿es de una coordinada autorizada?
            if _is_coord_authorized(record.company_id.id, xml_rfc):
                record.is_coordinada_authorized = True
            else:
                record.company_mismatch = True

    def view_invoice(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'target': 'current',
        }

    def relate_download(self): 
        for item in self:
            move = self.env['account.move'].search([('stored_sat_uuid', '=', item.name)], limit=1)
            if move:
                item.write({'invoice_id': move.id, 'state': move.state})

    def action_wizard_relate(self):
        action = self.env.ref('l10n_mx_xml_massive_download.action_open_invoice_wizard').read()[0]
        return action
    
    def generate_pdf_attatchment(self, account_id):

        datas = {
            'partner_id':self.partner_id,
            'cfdi_type':self.cfdi_type,
            'company_id':self.company_id,
            'payment_method':self.payment_method,
            'serie':self.serie,
            'folio':self.folio, 
            'divisa':self.divisa,
            'name':self.name,
            'document_date':self.document_date,
            'document_type':self.document_type,
            'downloaded_product_id':self.downloaded_product_id,
            'total_impuestos':self.total_impuestos,
            'total_retenciones':self.total_retenciones,
            'downloaded_product_id':self.downloaded_product_id,
            'total_impuestos':self.total_impuestos,
            'total_retenciones':self.total_retenciones,

        }
        result, format = self.env["ir.actions.report"]._render_qweb_pdf('l10n_mx_xml_massive_download.report_product', [self.id], datas)

        result = base64.b64encode(result)

        ir_values = {
            'name': 'Invoice ' + self.name,
            'type': 'binary',
            'datas': result,
            'store_fname': 'Factura ' + self.name + '.pdf',
            'mimetype': 'application/pdf',
            'res_model': 'account.move',
            'res_id': account_id,
        }
       
        self.env['ir.attachment'].create(ir_values)

    @staticmethod
    def _classify_tax_line(tax_line):
        """Devuelve 'iva_traslado', 'iva_ret', 'ieps_traslado', 'ieps_ret',
        'isr_ret' o None para una account.move.line de tipo 'tax'."""
        if not tax_line.tax_line_id:
            return None
        name = (tax_line.tax_line_id.name or '').upper()
        is_ret = (
            tax_line.tax_line_id.type_tax_use == 'purchase'
            and 'RET' in name
        ) or any(token in name for token in (' RET', 'RET.', 'RETENCION', 'RETENCIÓN'))
        is_ieps = 'IEPS' in name
        is_isr = 'ISR' in name
        is_iva = ('IVA' in name) and not is_ieps and not is_isr
        if is_iva:
            return 'iva_ret' if is_ret else 'iva_traslado'
        if is_ieps:
            return 'ieps_ret' if is_ret else 'ieps_traslado'
        if is_isr:
            return 'isr_ret'
        # Una RETENCION que no es IVA ni IEPS ni dice "ISR" es ISR por eliminacion:
        # cubre nombres como "RETENCION RESICO 1.25%", "1.25% WH", "RET ARRENDAMIENTO",
        # etc. (las retenciones en MX son ISR o IVA; IVA ya se atrapo arriba).
        if is_ret:
            return 'isr_ret'
        return None

    def _force_xml_tax_amounts(self, move, xml_iva_total=0.0, xml_ieps_total=0.0,
                                xml_iva_ret_total=0.0, xml_ieps_ret_total=0.0,
                                xml_isr_ret_total=0.0):
        """Sobrescribe las tax lines del move con los montos EXACTOS del XML.

        Politica fiscal MX: el CFDI timbrado por SAT es la verdad fiscal.
        Si Odoo calculo IVA = base*16% y el XML dice otra cosa (combustibles
        donde IEPS forma parte de la base del IVA), respetamos el XML.
        """
        if not move or move.move_type not in ('in_invoice', 'in_refund', 'out_invoice', 'out_refund'):
            return
        targets = {
            'iva_traslado': xml_iva_total,
            'iva_ret': xml_iva_ret_total,
            'ieps_traslado': xml_ieps_total,
            'ieps_ret': xml_ieps_ret_total,
            'isr_ret': xml_isr_ret_total,
        }
        if not any(v for v in targets.values()):
            return
        tax_lines = move.line_ids.filtered(lambda l: l.display_type == 'tax')
        if not tax_lines:
            return
        total_diff = 0.0
        for tl in tax_lines:
            kind = self._classify_tax_line(tl)
            if not kind:
                continue
            target = targets.get(kind, 0.0)
            if not target:
                continue
            current_abs = abs(tl.balance)
            if abs(current_abs - target) < 0.005:
                continue
            # Safety: si la diferencia es grande (>5% relativa) probablemente
            # es Caso B (combustibles con IEPS implicito en subtotal). Override
            # directo rompe balance porque Odoo recomputa al guardar. Skip.
            # Solucion correcta para Caso B requiere ajustar price_unit y
            # agregar linea IEPS implicito (refactor pendiente).
            diff_pct = abs(current_abs - target) / target if target else 0
            if diff_pct > 0.05:
                _logger.warning(
                    f"_force_xml_tax_amounts: move={move.name} kind={kind} "
                    f"odoo_calc={current_abs:.2f} xml={target:.2f} "
                    f"diff={diff_pct*100:.1f}% — SKIP override "
                    f"(probable Caso B con IEPS implicito en subtotal)"
                )
                continue
            sign = -1 if tl.balance < 0 else 1
            new_balance = sign * target
            new_debit = abs(new_balance) if new_balance > 0 else 0.0
            new_credit = abs(new_balance) if new_balance < 0 else 0.0
            diff = new_balance - tl.balance
            _logger.info(
                f"_force_xml_tax_amounts: move={move.name} tax={tl.tax_line_id.name} "
                f"kind={kind} odoo_calc={tl.balance:.2f} xml={sign*target:.2f} diff={diff:.2f}"
            )
            tl.with_context(check_move_validity=False).write({
                'balance': new_balance,
                'debit': new_debit,
                'credit': new_credit,
                'amount_currency': new_balance,
            })
            total_diff += diff
        # NOTA: NO ajustar payment_term — Odoo lo recomputa automaticamente
        # al cambiar una tax line. Doble ajuste rompe balance.

    def action_import_invoice(self):
        for item in self:
            # Asegurar que currency_id esté calculado antes de generar PDF
            if not item.currency_id:
                item._compute_currency_id()
            
            ref = (self.serie + '/' if self.serie else '') + (self.folio if self.folio else '')
            
            # Buscar moneda, si no se encuentra usar MXN por defecto
            currency = self.env['res.currency'].search([('name', '=', self.divisa or 'MXN')], limit=1)
            if not currency:
                currency = self.env['res.currency'].search([('name', '=', 'MXN')], limit=1)
            if not currency:
                raise UserError("No se pudo encontrar una moneda válida. Asegúrese de tener MXN configurada.")
            
            currency_id = currency.id
            
            account_move_dict = {
                'ref': ref,
                'ref': ref,
                'invoice_date': item.document_date,
                'date': item.document_date,
                'move_type':'out_invoice' if self.cfdi_type == 'recividos' else 'in_invoice',
                'partner_id': item.partner_id.id,
                'company_id': item.company_id.id,
                'invoice_line_ids': [],
                'currency_id': currency_id,
                'l10n_edi_imported_from_sat': True,
                'payment_method':self.payment_method,
                'uso_sat':self.cfdi_usage,
                # NOTA: xml_imported_id ya NO se escribe aqui — es computed
                # store=True basado en xml_sat_ids (reverse de invoice_id).
                # Se autopobla cuando item.write({'invoice_id': move.id}) se
                # ejecuta despues de crear el move.
            }

            # Flag empresarial: si está activo, el IEPS Trasladado se SUMA al precio
            # unitario de la línea (forma parte del gasto deducible) y se REMUEVE
            # del listado de tax_ids. El IVA permanece igual al del XML.
            # Solo aplica al importar facturas de proveedor (CFDIs recibidos).
            ieps_in_base = bool(item.company_id.l10n_mx_xml_download_ieps_in_base) and (self.cfdi_type != 'emitidos')

            # Acumuladores para forzar valores EXACTOS del XML al final.
            # Politica fiscal MX: el XML timbrado es la verdad ante el SAT;
            # NUNCA recalcular IVA/IEPS con base*porcentaje. Critico en combustibles
            # donde IEPS forma parte de la base del IVA.
            xml_iva_total = 0.0
            xml_iva_ret_total = 0.0
            xml_ieps_total = 0.0
            xml_ieps_ret_total = 0.0
            xml_isr_ret_total = 0.0

            for concepto in item.downloaded_product_id:
                    exchange_rate = 1
                    amount_base_currency = concepto.total_amount / exchange_rate

                    # Acumular valores XML para forzar al final.
                    for entry in (concepto.xml_taxes_breakdown or []):
                        amount = entry.get('amount') or 0.0
                        tipo = entry.get('tipo') or ''
                        kind = entry.get('kind') or ''
                        if kind == 'traslado':
                            if tipo == '002':
                                xml_iva_total += amount
                            elif tipo == '003':
                                xml_ieps_total += amount
                        elif kind == 'retencion':
                            if tipo == '001':
                                xml_isr_ret_total += amount
                            elif tipo == '002':
                                xml_iva_ret_total += amount
                            elif tipo == '003':
                                xml_ieps_ret_total += amount
                    if not concepto.xml_taxes_breakdown and concepto.ieps_traslado_amount:
                        xml_ieps_total += concepto.ieps_traslado_amount

                    # Estrategia de precio unitario: "horneamos" el descuento y, si
                    # aplica, el IEPS-en-base en price_unit para que la base del IVA
                    # quede EXACTA al XML. El campo discount del move_line queda en 0
                    # porque el discount % de Odoo es decimal_precision=2 y pierde
                    # precision (ej: 160/2290.69 = 6.984% -> almacena 6.98% -> base
                    # del IVA off por unos pesos -> Compliance falla y total != XML).
                    # Trade-off: la columna 'Discount' en la factura queda 0; el
                    # descuento sigue visible en la vista del XML descargado.
                    # Salvaguarda multi-empresa: si concepto.tax_id quedo apuntando a
                    # impuestos de OTRA compania (por el bug historico del search sin
                    # filtro de empresa), remapear al equivalente de la empresa de la
                    # factura. Sin esto, Odoo rechaza el tax por cruce de empresas y el
                    # IVA se pierde (factura con amount_tax=0). Idempotente.
                    company_tax_ids = concepto.tax_id
                    if any(t.company_id and t.company_id != item.company_id for t in company_tax_ids):
                        remapped = self.env['account.tax']
                        for t in company_tax_ids:
                            if not t.company_id or t.company_id == item.company_id:
                                remapped |= t
                                continue
                            equiv = self.env['account.tax'].search([
                                ('company_id', '=', item.company_id.id),
                                ('amount', '=', t.amount),
                                ('type_tax_use', '=', t.type_tax_use),
                                ('amount_type', '=', t.amount_type),
                                ('l10n_mx_tax_type', '=', t.l10n_mx_tax_type),
                            ], limit=1)
                            remapped |= equiv
                        company_tax_ids = remapped
                    line_tax_ids = company_tax_ids
                    line_price_unit = concepto.unit_value
                    descuento_abs = abs(concepto.discount) if concepto.discount else 0.0

                    if ieps_in_base and concepto.ieps_traslado_amount and concepto.quantity:
                        line_price_unit += concepto.ieps_traslado_amount / concepto.quantity
                        line_tax_ids = company_tax_ids.filtered(lambda t: 'IEPS' not in (t.name or '').upper())

                    if descuento_abs and concepto.quantity:
                        line_price_unit -= descuento_abs / concepto.quantity

                    line_vals = {
                        'product_id': concepto.product_rel.id,
                        'name': concepto.description,
                        'quantity': concepto.quantity,
                        'price_unit': line_price_unit,
                        'amount_currency': concepto.total_amount,
                        'tax_ids': line_tax_ids,
                        'downloaded_product_rel': concepto.id,
                        'discount': 0.0,
                    }
                    # Solo forzar account_id si esta explicitamente definido (override Odoo nativo).
                    # Si esta vacio, Odoo aplica la jerarquia producto -> categoria -> default diario.
                    if concepto.account_id:
                        line_vals['account_id'] = concepto.account_id.id
                    account_move_dict['invoice_line_ids'].append((0, 0, line_vals))
            account_move = self.env['account.move'].create(account_move_dict)

            # POLITICA FISCAL MX: forzar montos EXACTOS del XML.
            try:
                self._force_xml_tax_amounts(
                    account_move,
                    xml_iva_total=xml_iva_total,
                    xml_ieps_total=xml_ieps_total if not ieps_in_base else 0.0,
                    xml_iva_ret_total=xml_iva_ret_total,
                    xml_ieps_ret_total=xml_ieps_ret_total,
                    xml_isr_ret_total=xml_isr_ret_total,
                )
            except Exception as e_force:
                _logger.warning(
                    f"No se pudieron forzar montos XML en move {account_move.name}: {e_force}"
                )

            item.write({'invoice_id': account_move.id, 'state': 'draft'})


            
            self.generate_pdf_attatchment(account_move.id)
            xml_file = self.attachment_id.filtered(_is_xml_attachment)
            attachment_values = {
                'name': self.name,  # Name of the XML file
                'datas': xml_file.datas,  # Read XML file content
                'res_model': 'account.move',
                'res_id': account_move.id,
                'mimetype': 'application/xml',
            }
            self.env['ir.attachment'].create(attachment_values)
            account_move.create_edi_document_from_attatchment(self.name)
            item.write({'imported': True})

    def action_undo_import(self):
        """Desvincula el XML de su factura relacionada y lo devuelve a 'No Importado'
        (sin relacion) para poder re-importarlo o re-vincularlo. Cubre DOS casos:

        1) Factura CREADA por la importacion (l10n_edi_imported_from_sat) y en BORRADOR:
           ademas de desvincular, se BORRA la factura (se importo por equivocacion).
        2) Factura PRE-EXISTENTE (timbrada/manual/auto-vinculada) o PUBLICADA:
           SOLO se rompe el vinculo. La factura real NO se toca ni se borra.

        Asi se protege la contabilidad: nunca se borra una factura publicada ni una
        que el modulo no creo. Evita llamadas de soporte para corregir vinculaciones.
        """
        borradas = 0
        desvinculadas = 0
        for item in self:
            inv = item.invoice_id
            if inv:
                # Solo se borra si la factura la CREO la importacion y sigue en borrador.
                es_creada_por_import = bool(
                    inv.l10n_edi_imported_from_sat) and inv.state == 'draft'
                item.invoice_id = False
                if es_creada_por_import:
                    try:
                        edi_docs = self.env['l10n_mx_edi.document'].sudo().search(
                            [('move_id', '=', inv.id)])
                        if edi_docs:
                            edi_docs.unlink()
                    except Exception as e_edi:
                        _logger.warning(
                            "undo_import: no se pudo limpiar EDI doc de move %s: %s",
                            inv.id, e_edi)
                    try:
                        inv.with_context(force_delete=True).unlink()
                        borradas += 1
                    except Exception as e_del:
                        raise UserError(_(
                            "No se pudo borrar la factura %s: %s"
                        ) % (inv.name or inv.id, e_del))
                else:
                    # Factura real/publicada -> solo desvincular, conservar la factura.
                    desvinculadas += 1
            else:
                desvinculadas += 1
            item.write({
                'invoice_id': False,
                'imported': False,
                'state': 'not_imported',
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Factura desvinculada'),
                'message': _(
                    'Facturas borrador (creadas por la importacion) eliminadas: %s | '
                    'Facturas reales desvinculadas (conservadas): %s. '
                    'Los XML quedaron como "No Importado": ya puedes re-importarlos o '
                    're-vincularlos.'
                ) % (borradas, desvinculadas),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def _attach_xml_and_uuid_to_move(self, move):
        """Adjunta el XML del SAT + setea el UUID en el move AUNQUE este publicado/
        conciliado (solo METADATA: NO toca importes, lineas ni conciliacion). Para el
        caso comun: la factura se registro y pago con solo el PDF, y el XML del SAT
        llega despues; relacionar a mano deja la poliza sin XML/UUID. Idempotente."""
        self.ensure_one()
        if not move:
            return False
        xml_att = self.attachment_id.filtered(_is_xml_attachment)
        if not xml_att or not xml_att[:1].datas:
            return False
        Att = self.env['ir.attachment'].sudo()
        ya = Att.search([
            ('res_model', '=', 'account.move'), ('res_id', '=', move.id),
            ('name', '=', self.name)], limit=1)
        if not ya:
            Att.create({
                'name': self.name,
                'datas': xml_att[:1].datas,
                'res_model': 'account.move',
                'res_id': move.id,
                'mimetype': 'application/xml',
            })
        # UUID: crea el EDI document para que el move tome l10n_mx_edi_cfdi_uuid.
        # sudo() para poder hacerlo sobre facturas publicadas/conciliadas.
        try:
            if not move.l10n_mx_edi_cfdi_uuid:
                move.sudo().create_edi_document_from_attatchment(self.name)
        except Exception as e:
            _logger.warning(
                "attach_xml_to_move: no se pudo crear EDI doc en move %s: %s",
                move.id, e)
        # Respaldo: campo del modulo stored_sat_uuid (si es escribible y esta vacio).
        try:
            if 'stored_sat_uuid' in move._fields and not move.stored_sat_uuid:
                move.sudo().write({'stored_sat_uuid': self.name})
        except Exception:
            pass
        return True

    def action_force_attach_xml(self):
        """Boton: adjunta el XML del SAT + UUID a la poliza YA ligada, aunque este
        publicada/conciliada. Para corregir facturas registradas con solo el PDF."""
        hechas = 0
        sin_factura = 0
        for item in self:
            if not item.invoice_id:
                sin_factura += 1
                continue
            if item._attach_xml_and_uuid_to_move(item.invoice_id):
                hechas += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('XML adjuntado a la poliza'),
                'message': _(
                    'Polizas actualizadas con XML + UUID: %s | XMLs sin factura '
                    'ligada: %s.') % (hechas, sin_factura),
                'type': 'success' if hechas else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_add_payment(self):
        # Buscar factura
        xml_attachment = self.attachment_id.filtered(_is_xml_attachment)
        if not xml_attachment:
            raise UserError('No se encontró el archivo XML adjunto.')
        root = ET.fromstring(base64.b64decode(xml_attachment[0].datas))
        namespace = {**_get_cfdi_ns(root), 'pago20': 'http://www.sat.gob.mx/Pagos20'}
        id_documentos = []

        for docto_relacionado in root.findall('.//pago20:DoctoRelacionado', namespace):
            id_documento = docto_relacionado.get('IdDocumento')
            id_documentos.append(id_documento)

        moves = self.env['account.move'].search([('l10n_mx_edi_cfdi_uuid','in', id_documentos)])

        # Si hay factura, verificar si el estatus es in_payment 

        if moves:
            for move in moves:
                if move.payment_state == 'in_payment' or move.payment_state == 'paid':
                    # Buscar el Id del pago
                    
                    payments = self.env['account.payment'].search([('reconciled_invoice_ids','=',move.id)])
                    xml_file = self.attachment_id.filtered(_is_xml_attachment)
                    for payment in payments:
                        attachment_values = {
                                'name': xml_file.name,  # Name of the XML file
                                'datas': xml_file.datas,  # Read XML file content
                                'res_model': 'account.payment',
                                'res_id': payment.id,
                                'mimetype': 'application/xml',
                            }
                        
                        self.write({'invoice_id':move.id, 'imported':True})
                        res = self.env['ir.attachment'].create(attachment_values)

                        edi = self.env['l10n_mx_edi.document']
    
                        edi_data = {
                                    # 'name' : uuid_name+'.xml',
                                    'state' : 'payment_sent',
                                    'sat_state' : 'not_defined',
                                    'message': '',
                                    'datetime': fields.Datetime.now(),
                                    'attachment_uuid': self.name,
                                    'attachment_id' : res.id,
                                    'move_id'    : payment.move_id.id,
                                    }
                        new_edi_doc = edi.create(edi_data)

                        #### Asociando las Facturas ####
                        invoice_rel_ids = []
                        #### Facturas de Cliente ####
                        if payment.reconciled_invoice_ids:
                            invoice_rel_ids = payment.reconciled_invoice_ids.ids
                        #### Facturas de Proveedor ####
                        if payment.reconciled_bill_ids:
                            invoice_rel_ids = payment.reconciled_bill_ids.ids

                        new_edi_doc.invoice_ids = [(6,0, invoice_rel_ids)]
        else: 
            raise UserError("Error adjuntando pago, verifique que la factura exista y tenga un pago creado")

    def action_ignor(self):
        self.state = 'ignored'

    def _fetch_sat_status(self, supplier_rfc, customer_rfc, total, uuid):
        # CFDI tipo P (Pago/REP): el Total del root del CFDI es 0 por norma SAT
        # (es un acuse — los montos reales viven en pago20:Pago/Monto). Si
        # enviamos amount_total al endpoint ConsultaCFDIService, SAT responde
        # "No Encontrado - 601 expresion impresa no es valida" y el cron 92
        # marca el REP como sat_state='No Encontrado'. Bug historico: todos
        # los REPs (479+) quedaban siempre en No Encontrado por esto.
        if self.document_type == 'P':
            total = 0
        # Fallback de RFCs (v.59): si supplier_rfc o customer_rfc estan vacios,
        # extraerlos directo del XML attachment (cfdi:Emisor/@Rfc y
        # cfdi:Receptor/@Rfc). Sin esto, facturas recibidas cuyo partner no
        # tiene VAT en res.partner, y nominas cuyo trabajador no es
        # res.partner con VAT, quedan en "No Encontrado" porque SAT recibe
        # RFC vacio o el VAT incorrecto. Soporta CFDI 3.3 y 4.0.
        if (not supplier_rfc or not customer_rfc) and self.attachment_id and self.attachment_id.raw:
            try:
                _xroot = etree.fromstring(self.attachment_id.raw)
                for _ns in ('{http://www.sat.gob.mx/cfd/4}', '{http://www.sat.gob.mx/cfd/3}'):
                    if not supplier_rfc:
                        _emi = _xroot.find(_ns + 'Emisor')
                        if _emi is not None:
                            supplier_rfc = _emi.get('Rfc') or _emi.get('rfc') or supplier_rfc
                    if not customer_rfc:
                        _rec = _xroot.find(_ns + 'Receptor')
                        if _rec is not None:
                            customer_rfc = _rec.get('Rfc') or _rec.get('rfc') or customer_rfc
                    if supplier_rfc and customer_rfc:
                        break
            except Exception as _e:
                _logger.debug("XML RFC fallback fallo para UUID %s: %s", uuid, _e)
        url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl'
        headers = {
            'SOAPAction': 'http://tempuri.org/IConsultaCFDIService/Consulta',
            'Content-Type': 'text/xml; charset=utf-8',
        }
        params = f'<![CDATA[?id={uuid or ""}' \
                 f'&re={tools.html_escape(supplier_rfc or "")}' \
                 f'&rr={tools.html_escape(customer_rfc or "")}' \
                 f'&tt={total or 0.0}]]>'
        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
            <SOAP-ENV:Envelope
                xmlns:ns0="http://tempuri.org/"
                xmlns:ns1="http://schemas.xmlsoap.org/soap/envelope/"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
                <SOAP-ENV:Header/>
                <ns1:Body>
                    <ns0:Consulta>
                        <ns0:expresionImpresa>{params}</ns0:expresionImpresa>
                    </ns0:Consulta>
                </ns1:Body>
            </SOAP-ENV:Envelope>
        """
        namespace = {'a': 'http://schemas.datacontract.org/2004/07/Sat.Cfdi.Negocio.ConsultaCfdi.Servicio'}

        try:
            soap_xml = requests.post(url, data=envelope, headers=headers, timeout=35)
            response = etree.fromstring(soap_xml.text)
            fetched_status = response.xpath('//a:Estado', namespaces=namespace)
            fetched_state = fetched_status[0].text if fetched_status else None
        except Exception as e:
            return {
                'error': _("Failure during update of the SAT status: %s", str(e)),
                'value': 'error',
            }
        if fetched_state == 'Vigente':
            self.sat_state = 'Vigente'
        elif fetched_state == 'Cancelado':
            self.sat_state = 'Cancelado'
        elif fetched_state == 'No Encontrado':
            self.sat_state = 'No Encontrado'
        else:
            self.sat_state = 'Sin Definir'
        self.sat_last_sync = fields.Datetime.now()

    def action_fetch_sat_status(self):
        if self.cfdi_type == 'emitidos':
            self._fetch_sat_status(self.company_id.vat, self.partner_id.vat, self.amount_total, self.name)
        else:
            self._fetch_sat_status(self.partner_id.vat, self.company_id.vat, self.amount_total, self.name)

    def action_refetch_sat_status_forced(self):
        """Re-consulta el estatus SAT de los registros seleccionados, ignorando
        cualquier sincronizacion previa. Commit por registro para que un error
        a media corrida no pierda lo ya procesado. Procesa hasta 500 registros
        por invocacion para evitar timeouts HTTP en la UI; el resto debe
        esperar al cron o re-ejecutar la accion.
        """
        MAX_PER_CALL = 500
        if not self:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Re-consultar Estatus SAT',
                    'message': 'No hay registros seleccionados.',
                    'type': 'warning',
                    'sticky': False,
                },
            }
        target = self[:MAX_PER_CALL]
        ok_count = 0
        err_count = 0
        for record in target:
            try:
                if record.cfdi_type == 'emitidos':
                    record._fetch_sat_status(
                        record.company_id.vat, record.partner_id.vat, record.amount_total, record.name,
                    )
                else:
                    record._fetch_sat_status(
                        record.partner_id.vat, record.company_id.vat, record.amount_total, record.name,
                    )
                ok_count += 1
            except Exception as e:
                _logger.warning("Re-consulta SAT fallo para UUID %s: %s", record.name, e)
                err_count += 1
            self.env.cr.commit()
        msg = f'Procesados: {ok_count}'
        if err_count:
            msg += f' | Errores: {err_count}'
        if len(self) > MAX_PER_CALL:
            msg += f' | Restan {len(self) - MAX_PER_CALL} (el cron los procesara, o vuelve a ejecutar la accion)'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Re-consultar Estatus SAT',
                'message': msg,
                'type': 'success' if ok_count and not err_count else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    def cron_fetch_sat_status(self, batch_size=50):
        """Consulta el estatus SAT de los XMLs pendientes en lotes.

        Procesa dos conjuntos en orden:
          1. XMLs huerfanos (sat_last_sync IS NULL): catch-up del historico
             completo, sin filtro de fecha. Esto cubre XMLs descargados antes
             de que existiera sat_last_sync o cuando el cron no estaba activo.
          2. XMLs de los ultimos 31 dias ya sincronizados al menos una vez,
             que merecen actualizacion diaria (Vigente -> Cancelado, etc.).

        Procesa maximo ``batch_size`` registros por ejecucion para evitar que el
        cron supere el ``virtual real time limit`` del worker. Si quedan mas
        pendientes, re-encola este mismo cron para continuar la cola en la
        siguiente ranura libre. Usa ``sat_last_sync`` para no volver a tocar el
        mismo dia un XML ya consultado (previene bucles infinitos al re-disparar).
        """
        now = fields.Datetime.now()
        last_31_days = (now - timedelta(days=31)).strftime('%Y-%m-%d')
        today_str = now.strftime('%Y-%m-%d')
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Dominio unico: cualquier XML con (sat_last_sync IS NULL)  O
        # (es de los ultimos 31 dias y se sincronizo antes de hoy).
        # Ordenado para drenar primero los huerfanos historicos (NULL first).
        domain = [
            ('sat_state', '!=', 'Cancelado'),
            '|',
                # Conjunto 1: huerfanos historicos (sin filtro de fecha)
                ('sat_last_sync', '=', False),
                # Conjunto 2: recientes ya sincronizados que se reverifican
                '&', '&', '&',
                    ('document_date', '>=', last_31_days),
                    ('document_date', '<=', today_str),
                    ('sat_last_sync', '!=', False),
                    ('sat_last_sync', '<', start_of_today),
        ]

        # batch_size + 1 nos permite saber si quedan mas sin pagar otro search.
        records = self.env['account.edi.downloaded.xml.sat'].search(
            domain,
            limit=batch_size + 1,
            order='sat_last_sync asc nulls first, id asc',
        )

        for record in records[:batch_size]:
            if record.cfdi_type == 'emitidos':
                record._fetch_sat_status(record.company_id.vat, record.partner_id.vat, record.amount_total, record.name)
            else:
                record._fetch_sat_status(record.partner_id.vat, record.company_id.vat, record.amount_total, record.name)
            # Commit por registro: si el SAT tira error a media tanda, lo ya
            # consultado queda persistido y no se reprocesa en el siguiente disparo.
            self.env.cr.commit()

        if len(records) > batch_size:
            _logger.info(
                "Lote de %s XMLs SAT completado. Aún hay pendientes; re-encolando cron.",
                batch_size,
            )
            cron = self.env.ref(
                'l10n_mx_xml_massive_download.ir_cron_update_sat_state',
                raise_if_not_found=False,
            )
            if cron:
                cron.sudo()._trigger()
    
    # ============================================================================
    # MÉTODOS PARA DOCUMENTO ORIGEN (NUEVOS - NO MODIFICAN FUNCIONALIDAD ACTUAL)
    # ============================================================================
    
    @api.depends('origin_document_id', 'invoice_id')
    def _compute_origin_document_name(self):
        """Calcula el nombre y tipo del documento origen - OPTIMIZADO."""
        for record in self:
            origin = record.origin_document_id or record.invoice_id
            
            if not origin:
                record.origin_document_name = False
                record.origin_document_type = False
                continue
            
            # Obtener invoice_origin en una sola lectura
            origin_ref = origin.invoice_origin
            if origin_ref:
                if 'SO' in origin_ref or 'S0' in origin_ref:
                    record.origin_document_type = 'sale_order'
                    record.origin_document_name = origin_ref
                elif 'PO' in origin_ref or 'P0' in origin_ref:
                    record.origin_document_type = 'purchase_order'
                    record.origin_document_name = origin_ref
                else:
                    record.origin_document_type = 'invoice'
                    record.origin_document_name = origin.name
            else:
                record.origin_document_type = 'invoice'
                record.origin_document_name = origin.name
    
    def _search_origin_document_name(self, operator, value):
        """Búsqueda customizada para origin_document_name sin store=True."""
        if operator == '!=' and not value:
            # Buscar registros CON documento origen
            return ['|', ('origin_document_id', '!=', False), ('invoice_id', '!=', False)]
        elif operator == '=' and not value:
            # Buscar registros SIN documento origen
            return [('origin_document_id', '=', False), ('invoice_id', '=', False)]
        else:
            # Búsqueda en invoice_origin de ambos campos
            return ['|', 
                    ('origin_document_id.invoice_origin', operator, value),
                    ('invoice_id.invoice_origin', operator, value)]
    
    def _search_origin_document_emitidos(self):
        """Buscar documento origen para XMLs Emitidos (Facturas Cliente)."""
        self.ensure_one()
        
        if self.cfdi_type != 'emitidos':
            return False
        
        # Si ya tiene invoice_id con origen, usarlo
        if self.invoice_id and self.invoice_id.invoice_origin:
            return self.invoice_id
        
        # Buscar SO por criterios de similitud
        if not self.partner_id or not self.amount_total:
            return False
            
        from datetime import timedelta
        
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('state', 'in', ['sale', 'done']),
            ('amount_total', '>=', self.amount_total * 0.95),
            ('amount_total', '<=', self.amount_total * 1.05),
        ]
        
        if self.document_date:
            date_from = self.document_date - timedelta(days=30)
            date_to = self.document_date + timedelta(days=30)
            domain.extend([
                ('date_order', '>=', date_from),
                ('date_order', '<=', date_to)
            ])
        
        # Soft dependency: si el modulo 'sale' no esta instalado (caso
        # tipico de despachos contables sin ventas), simplemente no
        # buscamos sale.order y retornamos False sin error.
        SaleOrder = self.env.get('sale.order')
        if not SaleOrder:
            return False
        sale_order = SaleOrder.search(domain, limit=1, order='date_order desc')

        if sale_order:
            # Buscar factura de esa SO
            invoice = self.env['account.move'].search([
                ('invoice_origin', '=', sale_order.name),
                ('partner_id', '=', self.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '!=', 'cancel')
            ], limit=1)
            return invoice

        return False
    
    def _search_origin_document_recibidos(self):
        """Buscar documento origen para XMLs Recibidos (Facturas Proveedor)."""
        self.ensure_one()
        
        if self.cfdi_type != 'recibidos':
            return False
        
        # Si ya tiene invoice_id con origen, usarlo
        if self.invoice_id and self.invoice_id.invoice_origin:
            return self.invoice_id
        
        # Buscar PO por criterios de similitud
        if not self.partner_id or not self.amount_total:
            return False
            
        from datetime import timedelta
        
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('state', 'in', ['purchase', 'done']),
            ('amount_total', '>=', self.amount_total * 0.95),
            ('amount_total', '<=', self.amount_total * 1.05),
        ]
        
        if self.document_date:
            date_from = self.document_date - timedelta(days=45)
            date_to = self.document_date + timedelta(days=15)
            domain.extend([
                ('date_order', '>=', date_from),
                ('date_order', '<=', date_to)
            ])
        
        # Soft dependency: si 'purchase' no esta instalado (caso despacho
        # contable sin compras propias), no buscamos PO y retornamos False.
        PurchaseOrder = self.env.get('purchase.order')
        if not PurchaseOrder:
            return False
        purchase_order = PurchaseOrder.search(domain, limit=1, order='date_order desc')

        if purchase_order:
            # Buscar factura de esa PO
            invoice = self.env['account.move'].search([
                ('invoice_origin', '=', purchase_order.name),
                ('partner_id', '=', self.partner_id.id),
                ('move_type', 'in', ['in_invoice', 'in_refund']),
                ('state', '!=', 'cancel')
            ], limit=1)
            return invoice
        
        return False
    
    def action_search_origin_document(self):
        """Buscar documento origen (heuristico para facturas; derivado para P/T).

        - I, E (facturas): heuristica partner+monto+fecha contra sale.order/purchase.order
        - P (pagos): si payment_id esta enlazado, el "origen" son las facturas
          reconciliadas con ese payment (toma la primera para origin_document_id).
        - T (traslados): si picking_id esta enlazado, el "origen" es el sale_id o
          purchase_id del picking — la orden que disparo el movimiento.
        - N (nomina): no aplica documento origen.
        """
        found_count = 0
        not_found_count = 0

        for record in self:
            if record.origin_document_id:
                continue

            origin = False
            doc_type = record.document_type or ''

            if doc_type == 'P' and record.payment_id:
                # Buscar facturas reconciliadas con este pago
                payment = record.payment_id
                reconciled = self.env['account.move']
                if hasattr(payment, 'reconciled_invoice_ids') and payment.reconciled_invoice_ids:
                    reconciled = payment.reconciled_invoice_ids
                elif hasattr(payment, 'reconciled_bill_ids') and payment.reconciled_bill_ids:
                    reconciled = payment.reconciled_bill_ids
                if reconciled:
                    origin = reconciled[:1]
            elif doc_type == 'T' and record.picking_id:
                # El picking trae sale_id o purchase_id como origen
                picking = record.picking_id
                so = getattr(picking, 'sale_id', False)
                po = getattr(picking, 'purchase_id', False)
                if so:
                    # Buscar factura derivada de ese SO
                    inv = self.env['account.move'].search([
                        ('invoice_origin', '=', so.name),
                        ('move_type', '=', 'out_invoice'),
                        ('state', '!=', 'cancel'),
                    ], limit=1)
                    origin = inv or False
                elif po:
                    inv = self.env['account.move'].search([
                        ('invoice_origin', '=', po.name),
                        ('move_type', 'in', ('in_invoice', 'in_refund')),
                        ('state', '!=', 'cancel'),
                    ], limit=1)
                    origin = inv or False
            elif doc_type == 'N':
                # Nomina no tiene documento origen en el sentido de SO/PO
                pass
            else:
                # I, E -> heuristica original
                if record.cfdi_type == 'emitidos':
                    origin = record._search_origin_document_emitidos()
                elif record.cfdi_type == 'recibidos':
                    origin = record._search_origin_document_recibidos()

            if origin:
                record.origin_document_id = origin.id
                found_count += 1
            else:
                not_found_count += 1

        # Mensaje de resultados
        message = f'✓ {found_count} documentos encontrados'
        if not_found_count > 0:
            message += f'\n⊘ {not_found_count} sin coincidencias'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Búsqueda de Documentos Origen',
                'message': message,
                'type': 'success' if found_count > 0 else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }
    
    def _update_69b_statuses(self):
        """
        Método interno para actualizar el estatus 69-B de los registros.
        Retorna tupla (actualizados, no encontrados)
        """
        updated = 0
        not_found = 0
        for record in self:
            rfc = record.rfc_partner
            if not rfc:
                not_found += 1
                continue
            blacklist = self.env['l10n_mx.art69b.blacklist'].search([
                ('rfc', '=', rfc),
                ('activo', '=', True)
            ], limit=1)
            if blacklist:
                if blacklist.situacion == 'presuncion':
                    record.estatus_69b = 'Presunto'
                elif blacklist.situacion == 'definitivo':
                    record.estatus_69b = 'Definitivo'
                elif blacklist.situacion == 'desvirtuado':
                    record.estatus_69b = 'Desvirtuado'
                else:
                    record.estatus_69b = 'Listado'
                updated += 1
            else:
                record.estatus_69b = 'No listado'
                not_found += 1
        return updated, not_found
    
    def action_review_69b(self):
        """Acción para revisar Art 69-B en XMLs seleccionados.
        Procesa en lotes con commit + retry ante SerializationFailure."""
        import psycopg2
        BATCH = 200
        total_updated = 0
        total_not_found = 0
        records = self
        for i in range(0, len(records), BATCH):
            batch = records[i:i + BATCH]
            retries = 3
            while retries > 0:
                try:
                    updated, not_found = batch._update_69b_statuses()
                    total_updated += updated
                    total_not_found += not_found
                    self.env.cr.commit()
                    break
                except psycopg2.errors.SerializationFailure:
                    self.env.cr.rollback()
                    retries -= 1
                    if retries == 0:
                        _logger.warning(f"Art 69-B: SerializationFailure persistente en batch {i}, saltando")
                    else:
                        import time
                        time.sleep(2)
                except Exception:
                    self.env.cr.rollback()
                    break
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Revisión Art 69-B',
                'message': f'Actualizados: {total_updated}, No listados: {total_not_found}',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }
    
    def _compute_fiscal_alert(self):
        """Permite recalcular el estatus 69-B sin generar notificaciones"""
        self._update_69b_statuses()
    
    def action_search_related_invoice(self):
        """Busca contraparte Odoo por UUID exacto segun el tipo de documento del CFDI.

        - I, E (Ingreso, Egreso) -> account.move por stored_sat_uuid / l10n_mx_edi_cfdi_uuid
        - P (Pago)               -> account.payment por stored_sat_uuid / l10n_mx_edi_cfdi_uuid
        - T (Traslado)           -> stock.picking por l10n_mx_edi_cfdi_uuid
        - N (Nomina)             -> hr.payslip por l10n_mx_edi_cfdi_uuid

        Procesa en lotes de 200 con commit intermedio para evitar timeout
        en rangos grandes (10K+ XMLs).
        """
        related = 0
        not_found = 0
        BATCH_SIZE = 200
        Move = self.env['account.move']
        Payment = self.env['account.payment']
        Picking = self.env['stock.picking']
        Payslip = self.env['hr.payslip']
        # El campo l10n_mx_edi_cfdi_uuid en hr.payslip / stock.picking lo aportan
        # modulos opcionales (nomina CFDI / l10n_mx_edi_stock). En instalaciones
        # sin ese campo, filtrar por el lanza "Invalid field" y ABORTA el auto-link,
        # cuyo except hace cr.rollback() y borra los XMLs recien creados (sintoma:
        # lote emitidos con CFDI de nomina se queda en 0). Solo buscamos si existe.
        _payslip_has_uuid = 'l10n_mx_edi_cfdi_uuid' in Payslip._fields
        _picking_has_uuid = 'l10n_mx_edi_cfdi_uuid' in Picking._fields

        processed = 0
        total = len(self)
        for record in self:
            uuid = record.name
            if not uuid:
                not_found += 1
                processed += 1
                continue
            company_domain = [('company_id', '=', record.company_id.id)]
            doc_type = record.document_type or ''
            found = False

            # Facturas e ingresos/egresos -> account.move.
            # Busca en stored_sat_uuid (nuestro) Y l10n_mx_edi_cfdi_uuid (nativo Odoo)
            if doc_type in ('I', 'E', '') and not record.invoice_id:
                move = Move.search(
                    ['|',
                     ('stored_sat_uuid', '=', uuid),
                     ('l10n_mx_edi_cfdi_uuid', '=', uuid),
                    ] + company_domain,
                    limit=1,
                )
                if move:
                    record.write({'invoice_id': move.id, 'state': move.state})
                    found = True

            # Pagos -> account.payment
            # Para tipo P: busca por UUID directo en payment, o por DoctoRelacionado
            # en factura proveedor. Llena:
            #   payment_id       = el account.payment
            #   invoice_id       = la factura proveedor que paga (del DoctoRelacionado)
            #   origin_document_id = el asiento contable del pago (payment.move_id)
            if doc_type == 'P' and not record.payment_id:
                payment = Payment.search(
                    ['|',
                     ('stored_sat_uuid', '=', uuid),
                     ('l10n_mx_edi_cfdi_uuid', '=', uuid),
                    ] + company_domain,
                    limit=1,
                )
                if payment:
                    vals_write = {'payment_id': payment.id}
                    if hasattr(payment, 'move_id') and payment.move_id:
                        vals_write['origin_document_id'] = payment.move_id.id
                    record.write(vals_write)
                    self._anfepi_attach_xml_to_payment(record, payment)
                    found = True
                elif record.partner_id and (record.cfdi_type or '') == 'recibidos':
                    target_payment = self._anfepi_find_target_payment_for_complement(
                        record, Move,
                    )
                    if target_payment:
                        self._anfepi_attach_xml_to_payment(record, target_payment)
                        vals_write = {"payment_id": target_payment.id}
                        if hasattr(target_payment, 'move_id') and target_payment.move_id:
                            vals_write['origin_document_id'] = target_payment.move_id.id
                        # invoice_id = la factura que paga (ya resuelta por _find_target)
                        # se llena desde el DoctoRelacionado en _find_target
                        record.write(vals_write)
                        found = True

            # Traslados -> stock.picking
            if doc_type == 'T' and not record.picking_id and _picking_has_uuid:
                picking = Picking.search(
                    [('l10n_mx_edi_cfdi_uuid', '=', uuid)] + company_domain,
                    limit=1,
                )
                if picking:
                    record.write({'picking_id': picking.id})
                    found = True

            # Nomina -> hr.payslip
            if doc_type == 'N' and not record.payslip_id and _payslip_has_uuid:
                payslip = Payslip.search(
                    [('l10n_mx_edi_cfdi_uuid', '=', uuid)] + company_domain,
                    limit=1,
                )
                if payslip:
                    record.write({'payslip_id': payslip.id})
                    found = True

            if found:
                related += 1
            else:
                not_found += 1

            # Commit cada BATCH_SIZE registros para no perder progreso en timeout
            processed += 1
            if processed % BATCH_SIZE == 0:
                self.env.cr.commit()
                _logger.info(
                    f"Buscar Factura Relacionada: {processed}/{total} "
                    f"(+{related} relacionadas, {not_found} sin match)"
                )

        message = f'Relacionadas: {related}, No encontradas: {not_found}'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Búsqueda de Documentos Odoo',
                'message': message,
                'type': 'success' if related > 0 else 'warning',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    # ============================================================================
    # ANFEPI v.23 — Helpers para complementos de pago recibidos
    # ============================================================================

    def _anfepi_find_target_payment_for_complement(self, record, MoveModel):
        """Cuando un complemento de pago recibido (cfdi_type='P') no matchea
        por UUID con ningun account.payment, parseamos el XML del REP para
        encontrar el DoctoRelacionado.IdDocumento (UUID de la factura que paga).
        Luego buscamos esa factura y obtenemos su pago reconciliado.

        Estrategia:
          1. Parsear el XML del REP -> extraer IdDocumento(s) del DoctoRelacionado.
          2. Buscar la factura con ese UUID (stored_sat_uuid o l10n_mx_edi_cfdi_uuid).
          3. Obtener el payment reconciliado de esa factura.
          4. Si no hay match por XML, fallback a buscar por partner (menos preciso).
        """
        if not record.partner_id:
            return False
        company_domain = [("company_id", "=", record.company_id.id)] if record.company_id else []

        # Paso 1: parsear XML del REP para obtener UUIDs de facturas pagadas
        factura_uuids = []
        try:
            if record.attachment_id and record.attachment_id.datas:
                import base64
                raw = base64.b64decode(record.attachment_id.datas)
                rep_root = etree.fromstring(raw)
                ns_pago = {'pago20': 'http://www.sat.gob.mx/Pagos20'}
                for docto in rep_root.findall('.//pago20:DoctoRelacionado', namespaces=ns_pago):
                    id_doc = docto.get('IdDocumento', '').strip()
                    if id_doc:
                        factura_uuids.append(id_doc)
        except Exception as e:
            _logger.warning(f"REP {record.name}: no se pudo parsear DoctoRelacionado: {e}")

        # Paso 2: buscar facturas por UUID del DoctoRelacionado
        if factura_uuids:
            for uuid_factura in factura_uuids:
                bill = MoveModel.search(
                    ['|',
                     ('stored_sat_uuid', '=', uuid_factura),
                     ('l10n_mx_edi_cfdi_uuid', '=', uuid_factura),
                    ] + company_domain,
                    limit=1,
                )
                if bill and bill.payment_state in ('paid', 'in_payment', 'partial'):
                    # Llenar invoice_id con la factura que paga este REP
                    if not record.invoice_id:
                        record.write({'invoice_id': bill.id})
                    payments = self.env["account.payment"]
                    if hasattr(bill, "_get_reconciled_payments"):
                        try:
                            payments = bill._get_reconciled_payments()
                        except Exception:
                            pass
                    if not payments:
                        try:
                            debit_p = bill.line_ids.matched_debit_ids.debit_move_id.payment_id
                            credit_p = bill.line_ids.matched_credit_ids.credit_move_id.payment_id
                            payments = debit_p | credit_p
                        except Exception:
                            pass
                    if payments:
                        return payments.sorted("date", reverse=True)[:1]

        # Sin fallback genérico: si el DoctoRelacionado no matchea con ninguna
        # factura en Odoo, NO adjuntamos a un pago aleatorio del proveedor.
        return False

    def _anfepi_attach_xml_to_payment(self, record, payment):
        """Adjunta el XML del complemento de pago al payment contable via
        message_post para que sea visible en el chatter del pago.
        Idempotente: no duplica si ya existe un attachment con el mismo nombre.
        """
        if not payment or not record:
            return False
        source_attachment = record.attachment_id if hasattr(record, "attachment_id") else False
        if not source_attachment or not source_attachment.datas:
            return False
        attach_name = (record.name or "complemento_pago") + ".xml"
        existing = self.env["ir.attachment"].search([
            ("res_model", "=", "account.payment"),
            ("res_id", "=", payment.id),
            ("name", "=", attach_name),
        ], limit=1)
        if existing:
            return existing
        # Crear attachment y vincularlo al chatter SIN enviar notificación.
        # Se crea un mail.message tipo 'comment' con subtype 'note' (interno)
        # y se vincula el attachment para que sea visible en el chatter del pago.
        attachment = self.env["ir.attachment"].create({
            "name": attach_name,
            "datas": source_attachment.datas,
            "res_model": "account.payment",
            "res_id": payment.id,
            "mimetype": "application/xml",
        })
        # Vincular al chatter sin notificación: nota interna silenciosa
        try:
            note_subtype = self.env.ref("mail.mt_note", raise_if_not_found=False)
            msg = self.env["mail.message"].sudo().create({
                "model": "account.payment",
                "res_id": payment.id,
                "body": "",
                "message_type": "comment",
                "subtype_id": note_subtype.id if note_subtype else False,
                "attachment_ids": [(4, attachment.id)],
            })
        except Exception:
            pass
        return attachment

    # ============================================================================
    # HELPERS DE PARSEO XML — usados tanto en pipeline de descarga como en backfill
    # ============================================================================

    @staticmethod
    def _parse_fecha_timbrado(root):
        """Extrae FechaTimbrado del nodo tfd:TimbreFiscalDigital.
        Devuelve string 'YYYY-MM-DD HH:MM:SS' o False si no hay timbre.
        """
        tfd_node = root.find(
            './/tfd:TimbreFiscalDigital',
            {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'},
        )
        if tfd_node is None:
            return False
        return (tfd_node.get('FechaTimbrado') or '').replace('T', ' ') or False

    @staticmethod
    def _parse_tax_breakdown(root, ns):
        """Recorre cfdi:Impuestos (global o por concepto) y devuelve un dict
        con los 9 campos tax_* poblados. Funciona con CFDI 4.0.

        Reglas (CFDI 4.0):
          - Impuesto = '001' ISR, '002' IVA, '003' IEPS
          - TipoFactor = 'Tasa' (porcentaje), 'Cuota' (fijo), 'Exento'
          - TasaOCuota = ej. '0.160000' = 16%, '0.080000' = 8%, '0.000000' = 0%
          - Importe = monto del impuesto en moneda del CFDI
        Para Exento no hay Importe (es exento, no se paga), se cuenta el
        Subtotal del concepto bajo tax_iva_exento_traslado solo si esta a nivel concepto.
        Como simplificacion, sumamos solo Importes presentes.
        """
        out = {
            'tax_iva_16_traslado': 0.0,
            'tax_iva_8_traslado': 0.0,
            'tax_iva_0_traslado': 0.0,
            'tax_iva_exento_traslado': 0.0,
            'tax_iva_ret': 0.0,
            'tax_isr_ret': 0.0,
            'tax_ieps_traslado': 0.0,
            'tax_ieps_ret': 0.0,
            'tax_otros': 0.0,
        }

        def _classify(tipo, factor, tasa, importe):
            """Devuelve nombre del campo a sumar para un Traslado dado."""
            if tipo == '002':  # IVA
                if factor == 'Exento':
                    return 'tax_iva_exento_traslado'
                if tasa is None:
                    return 'tax_otros'
                if abs(tasa - 0.16) < 0.0005:
                    return 'tax_iva_16_traslado'
                if abs(tasa - 0.08) < 0.0005:
                    return 'tax_iva_8_traslado'
                if abs(tasa - 0.0) < 0.0005:
                    return 'tax_iva_0_traslado'
                return 'tax_otros'
            if tipo == '003':  # IEPS
                return 'tax_ieps_traslado'
            if tipo == '001':  # ISR no se traslada en CFDI normales
                return 'tax_otros'
            return 'tax_otros'

        def _classify_ret(tipo):
            if tipo == '001':
                return 'tax_isr_ret'
            if tipo == '002':
                return 'tax_iva_ret'
            if tipo == '003':
                return 'tax_ieps_ret'
            return 'tax_otros'

        def _to_float(s):
            try:
                return float(s) if s not in (None, '') else None
            except (ValueError, TypeError):
                return None

        # CFDI 4.0: el resumen vive en root/cfdi:Impuestos (Traslados + Retenciones
        # con Importe agregado). Cada concepto tambien lleva su propio cfdi:Impuestos
        # con el desglose por linea. Si sumamos ambos contamos doble.
        # Preferimos el resumen del root; si no existe (caso atipico), fallback
        # a sumar concepto por concepto.
        root_imp = root.find('cfdi:Impuestos', namespaces=ns)
        if root_imp is not None:
            nodes_to_process = [root_imp]
        else:
            nodes_to_process = root.findall('cfdi:Conceptos/cfdi:Concepto/cfdi:Impuestos', namespaces=ns)

        for imp_node in nodes_to_process:
            # Traslados: pueden estar dentro de cfdi:Traslados (root) o directos
            for tr in imp_node.findall('.//cfdi:Traslado', namespaces=ns):
                tipo = tr.get('Impuesto')
                factor = tr.get('TipoFactor')
                tasa = _to_float(tr.get('TasaOCuota'))
                importe = _to_float(tr.get('Importe')) or 0.0
                key = _classify(tipo, factor, tasa, importe)
                out[key] = out.get(key, 0.0) + importe
            # Retenciones
            for re in imp_node.findall('.//cfdi:Retencion', namespaces=ns):
                tipo = re.get('Impuesto')
                importe = _to_float(re.get('Importe')) or 0.0
                key = _classify_ret(tipo)
                out[key] = out.get(key, 0.0) + importe

        # CFDI tipo N (Nomina): el ISR retenido al empleado vive en
        # nomina12:Deducciones/Deduccion[@TipoDeduccion='002']. No es un
        # cfdi:Impuestos al uso (el SAT lo modela distinto en nomina).
        # Sumamos Importe de todas las deducciones tipo 002 al tax_isr_ret.
        if root.get('TipoDeComprobante') == 'N':
            ns_nomina = {'nomina12': 'http://www.sat.gob.mx/nomina12'}
            for ded in root.findall('.//nomina12:Deduccion', namespaces=ns_nomina):
                if ded.get('TipoDeduccion') == '002':  # 002 = ISR
                    importe = _to_float(ded.get('Importe')) or 0.0
                    out['tax_isr_ret'] = out.get('tax_isr_ret', 0.0) + importe

        return out

    # ============================================================================
    # ENRIQUECIMIENTO HISTORICO (acciones de servidor)
    # ============================================================================

    def _backfill_cuenta_predial_from_xml(self):
        """Re-parsea el attachment XML para extraer <cfdi:CuentaPredial> en las
        lineas de conceptos. Solo afecta lineas con cuenta_predial vacia.
        Pensado para usarse vía accion de servidor sobre XMLs ya descargados
        antes de que existiera este campo.
        Devuelve (procesados, actualizados).
        """
        procesados = 0
        actualizados = 0
        for xml in self:
            attachment = xml.attachment_id.filtered(_is_xml_attachment)[:1]
            if not attachment or not attachment.datas:
                continue
            try:
                raw = base64.b64decode(attachment.datas)
                try:
                    root = etree.fromstring(raw)
                except etree.XMLSyntaxError:
                    # CFDIs mal formados (xmlns:schemaLocation invalido de ciertos
                    # PACs): corregir el atributo y reintentar (mismo fix .47.4 del
                    # pipeline). Antes el backfill los saltaba -> fecha_timbrado NULL.
                    root = etree.fromstring(raw.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation'))
            except Exception as exc:
                _logger.warning("Cuenta Predial backfill: XML invalido en %s: %s", xml.name, exc)
                continue
            ns = _get_cfdi_ns(root)
            conceptos_node = root.find('.//cfdi:Conceptos', namespaces=ns)
            if conceptos_node is None:
                continue
            xml_conceptos = conceptos_node.findall('.//cfdi:Concepto', namespaces=ns)
            lineas = xml.downloaded_product_id
            # Match posicional (mismo orden en XML y en BD). Es seguro porque las
            # lineas se crean preservando el orden del XML.
            for line, concepto_node in zip(lineas, xml_conceptos):
                procesados += 1
                if line.cuenta_predial:
                    continue
                cp_node = concepto_node.find('cfdi:CuentaPredial', namespaces=ns)
                if cp_node is not None and cp_node.get('Numero'):
                    line.cuenta_predial = cp_node.get('Numero')
                    actualizados += 1
        return procesados, actualizados

    def action_backfill_cuenta_predial(self):
        """Accion de servidor: backfill de cuenta predial en XMLs historicos."""
        procesados, actualizados = self._backfill_cuenta_predial_from_xml()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Backfill Cuenta Predial',
                'message': f'Lineas revisadas: {procesados} | Actualizadas: {actualizados}',
                'type': 'success' if actualizados else 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    def _backfill_timbrado_y_taxes_from_xml(self):
        """Re-parsea el attachment XML para poblar campos faltantes:
          - fecha_timbrado
          - tax_regime (cuando este vacio; util para emitidos historicos que
            sufrieron el bug 'RegimenFiscal' vs 'RegimenFiscalReceptor' en CFDI 4.0)
          - 9 campos de desglose de impuestos (tax_iva_16_traslado, tax_iva_ret, etc.)
          - ieps_traslado_amount por linea (account.edi.downloaded.xml.sat.products)
            necesario para que el flag IEPS-en-base aplique correctamente.

        Solo escribe los campos que esten vacios o en cero para evitar pisar
        datos correctos en re-runs. Devuelve (revisados, actualizados).
        """
        revisados = 0
        actualizados = 0
        TAX_FIELDS = (
            'tax_iva_16_traslado', 'tax_iva_8_traslado', 'tax_iva_0_traslado',
            'tax_iva_exento_traslado', 'tax_iva_ret', 'tax_isr_ret',
            'tax_ieps_traslado', 'tax_ieps_ret', 'tax_otros',
        )
        for xml in self:
            revisados += 1
            attachment = xml.attachment_id.filtered(_is_xml_attachment)[:1]
            if not attachment or not attachment.datas:
                continue
            try:
                raw = base64.b64decode(attachment.datas)
                try:
                    root = etree.fromstring(raw)
                except etree.XMLSyntaxError:
                    # CFDIs mal formados (xmlns:schemaLocation invalido de ciertos
                    # PACs): corregir el atributo y reintentar (mismo fix .47.4 del
                    # pipeline). Antes el backfill los saltaba -> fecha_timbrado NULL.
                    root = etree.fromstring(raw.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation'))
            except Exception as exc:
                _logger.warning("Backfill timbrado/taxes: XML invalido en %s: %s", xml.name, exc)
                continue

            ns = _get_cfdi_ns(root)
            updates = {}

            # Fecha de timbrado solo si no la tenemos.
            if not xml.fecha_timbrado:
                ft = self._parse_fecha_timbrado(root)
                if ft:
                    updates['fecha_timbrado'] = ft

            # tax_regime solo si esta vacio. Para emitidos lee RegimenFiscalReceptor
            # (atributo correcto de CFDI 4.0); para recibidos lee RegimenFiscal del
            # Emisor. Esto corrige el bug historico que dejaba tax_regime=NULL en
            # 100% de los emitidos.
            if not xml.tax_regime:
                if xml.cfdi_type == 'emitidos':
                    nodo = root.find('.//cfdi:Receptor', namespaces=ns)
                    if nodo is not None:
                        tr = nodo.get('RegimenFiscalReceptor')
                        if tr:
                            updates['tax_regime'] = tr
                else:
                    nodo = root.find('.//cfdi:Emisor', namespaces=ns)
                    if nodo is not None:
                        tr = nodo.get('RegimenFiscal')
                        if tr:
                            updates['tax_regime'] = tr

            # ---- Backfill v.60: campos historicos que tampoco se persistian ----
            # Sellos digitales (raiz + tfd) y certificados.
            if not xml.sello_cfdi:
                _sello_cfdi = root.get('Sello')
                if _sello_cfdi:
                    updates['sello_cfdi'] = _sello_cfdi
            if not xml.certificate_number:
                _cert = root.get('NoCertificado')
                if _cert:
                    updates['certificate_number'] = _cert
            if not xml.sello_sat or not xml.certificate_sat_number or not xml.cadena_original:
                _tfd = root.find(
                    './/tfd:TimbreFiscalDigital',
                    namespaces={'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'},
                )
                if _tfd is not None:
                    if not xml.sello_sat:
                        _ss = _tfd.get('SelloSAT')
                        if _ss:
                            updates['sello_sat'] = _ss
                    if not xml.certificate_sat_number:
                        _csn = _tfd.get('NoCertificadoSAT')
                        if _csn:
                            updates['certificate_sat_number'] = _csn
                    if not xml.cadena_original:
                        # Cadena original tfd (formato canonico documentado por SAT)
                        _parts = ['||', _tfd.get('Version', ''), '|', _tfd.get('UUID', ''),
                                  '|', _tfd.get('FechaTimbrado', ''), '|', _tfd.get('RfcProvCertif', ''),
                                  '|', _tfd.get('SelloCFD', ''), '|', _tfd.get('NoCertificadoSAT', ''), '||']
                        _co = ''.join(p for p in _parts if p is not None)
                        if _co.strip('|'):
                            updates['cadena_original'] = _co

            # Uso CFDI (Receptor/@UsoCFDI).
            if not xml.cfdi_usage:
                _rec = root.find('.//cfdi:Receptor', namespaces=ns)
                if _rec is not None:
                    _uso = _rec.get('UsoCFDI')
                    if _uso:
                        # Validar contra la selection del campo
                        try:
                            _valid = dict(xml._fields['cfdi_usage'].selection)
                            if _uso in _valid:
                                updates['cfdi_usage'] = _uso
                        except Exception:
                            pass

            # Subtotal y total raiz (cuando vacios). Para tipo P, el raiz es 0
            # por norma — no sobreescribimos amount_total si ya tiene valor del Pago.
            if not xml.sub_total or xml.sub_total == 0:
                _st = root.get('SubTotal')
                if _st:
                    try:
                        updates['sub_total'] = float(_st)
                    except (TypeError, ValueError):
                        pass
            if (not xml.amount_total or xml.amount_total == 0) and root.get('TipoDeComprobante') != 'P':
                _tt = root.get('Total')
                if _tt:
                    try:
                        updates['amount_total'] = float(_tt)
                    except (TypeError, ValueError):
                        pass

            # Forma de pago raiz (no aplicar a tipo P — su FormaDePagoP vive
            # en pago20:Pago y ya se llena en otro camino del modulo).
            if not xml.payment_method_sat and root.get('TipoDeComprobante') != 'P':
                _fp = root.get('FormaPago')
                if _fp:
                    try:
                        _valid_fp = dict(xml._fields['payment_method_sat'].selection)
                        if _fp in _valid_fp:
                            updates['payment_method_sat'] = _fp
                    except Exception:
                        pass

            # Metodo de pago (PUE/PPD) raiz.
            if not xml.payment_method and root.get('TipoDeComprobante') not in ('P', 'N'):
                _mp = root.get('MetodoPago')
                if _mp in ('PUE', 'PPD'):
                    updates['payment_method'] = _mp

            # Impuestos: rellenar si TODOS los campos estan en cero.
            # (Si al menos uno tiene valor asumimos que ya se proceso al menos parcialmente.)
            has_any_tax = any(getattr(xml, f, 0.0) for f in TAX_FIELDS)
            if not has_any_tax:
                tax_vals = self._parse_tax_breakdown(root, ns)
                # Solo escribir los que tienen valor distinto de 0 (evita ruido de writes).
                tax_vals = {k: v for k, v in tax_vals.items() if v}
                updates.update(tax_vals)

            if updates:
                xml.write(updates)
                actualizados += 1

            # Backfill POR LINEA (independiente de updates del header):
            #   - ieps_traslado_amount (legacy, sigue siendo util para IEPS-en-base)
            #   - xml_taxes_breakdown (nuevo, full breakdown para render UI)
            # Match posicional entre XML conceptos y downloaded_product_id (mismo orden).
            try:
                conceptos_root = root.find('.//cfdi:Conceptos', namespaces=ns)
                if conceptos_root is not None:
                    xml_conceptos = conceptos_root.findall('cfdi:Concepto', namespaces=ns)
                    lineas = xml.downloaded_product_id

                    def _safe_float(v):
                        try:
                            return float(v) if v not in (None, '') else None
                        except (ValueError, TypeError):
                            return None

                    for line_db, concepto_xml in zip(lineas, xml_conceptos):
                        line_updates = {}
                        ieps_sum = 0.0
                        breakdown = []
                        for trasl in concepto_xml.findall('cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado', namespaces=ns):
                            imp = _safe_float(trasl.get('Importe')) or 0.0
                            if trasl.get('Impuesto') == '003':
                                ieps_sum += imp
                            breakdown.append({
                                'kind': 'traslado',
                                'tipo': trasl.get('Impuesto') or '',
                                'factor': trasl.get('TipoFactor') or '',
                                'rate': _safe_float(trasl.get('TasaOCuota')),
                                'amount': imp,
                            })
                        for ret in concepto_xml.findall('cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion', namespaces=ns):
                            imp_ret = _safe_float(ret.get('Importe')) or 0.0
                            breakdown.append({
                                'kind': 'retencion',
                                'tipo': ret.get('Impuesto') or '',
                                'factor': ret.get('TipoFactor') or '',
                                'rate': _safe_float(ret.get('TasaOCuota')),
                                'amount': imp_ret,
                            })
                        if not line_db.ieps_traslado_amount and ieps_sum:
                            line_updates['ieps_traslado_amount'] = ieps_sum
                        if not line_db.xml_taxes_breakdown and breakdown:
                            line_updates['xml_taxes_breakdown'] = breakdown
                        if line_updates:
                            line_db.write(line_updates)
            except Exception as exc:
                _logger.warning("Backfill por linea fallo en %s: %s", xml.name, exc)

        return revisados, actualizados

    def action_backfill_timbrado_y_taxes(self):
        """Accion de servidor: rellena fecha_timbrado e impuestos desglosados
        en XMLs historicos descargados antes de que existieran esos campos.
        Procesa en chunks de 200 con commits para no agotar memoria/transaccion.
        """
        # Si llaman sin seleccion, procesar todos los XMLs huerfanos.
        if not self:
            # Incluye XMLs sin fecha_timbrado, sin tax_regime, o sin desglose
            # de impuestos. tax_regime se incluye porque emitidos historicos
            # sufrieron el bug RegimenFiscalReceptor.
            domain = ['|', '|',
                ('fecha_timbrado', '=', False),
                ('tax_regime', '=', False),
                ('tax_iva_16_traslado', '=', 0.0),
            ]
            target = self.env['account.edi.downloaded.xml.sat'].search(domain)
        else:
            target = self
        total = len(target)
        if not total:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Backfill Timbrado y Taxes',
                    'message': 'No hay XMLs pendientes de rellenar.',
                    'type': 'info',
                    'sticky': False,
                },
            }
        revisados_total = 0
        actualizados_total = 0
        CHUNK = 200
        for i in range(0, total, CHUNK):
            chunk_ids = target[i:i + CHUNK].ids
            chunk = self.env['account.edi.downloaded.xml.sat'].browse(chunk_ids)
            rev, act = chunk._backfill_timbrado_y_taxes_from_xml()
            revisados_total += rev
            actualizados_total += act
            self.env.cr.commit()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Backfill Timbrado y Taxes',
                'message': f'XMLs revisados: {revisados_total} | Actualizados: {actualizados_total}',
                'type': 'success' if actualizados_total else 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    def _backfill_payment_currency_from_xml(self):
        """Para CFDIs tipo P, re-parsea el attachment y extrae la moneda real del
        pago (pago20:Pago/@MonedaP) en lugar de la del comprobante (que es 'XXX').
        Solo actualiza registros donde divisa actual es 'XXX' o vacia.
        Devuelve (revisados, actualizados).
        """
        revisados = 0
        actualizados = 0
        for xml in self:
            if xml.document_type != 'P':
                continue
            revisados += 1
            if xml.divisa and xml.divisa not in ('XXX', ''):
                continue
            attachment = xml.attachment_id.filtered(_is_xml_attachment)[:1]
            if not attachment or not attachment.datas:
                continue
            try:
                raw = base64.b64decode(attachment.datas)
                try:
                    root = etree.fromstring(raw)
                except etree.XMLSyntaxError:
                    # CFDIs mal formados (xmlns:schemaLocation invalido de ciertos
                    # PACs): corregir el atributo y reintentar (mismo fix .47.4 del
                    # pipeline). Antes el backfill los saltaba -> fecha_timbrado NULL.
                    root = etree.fromstring(raw.replace(b'xmlns:schemaLocation', b'xsi:schemaLocation'))
            except Exception as exc:
                _logger.warning("Backfill MonedaP: XML invalido en %s: %s", xml.name, exc)
                continue
            pago_node = root.find('.//{http://www.sat.gob.mx/Pagos20}Pago')
            moneda_p = pago_node.get('MonedaP') if pago_node is not None else None
            if moneda_p and moneda_p != xml.divisa:
                xml.divisa = moneda_p
                actualizados += 1
        return revisados, actualizados

    def action_backfill_payment_currency(self):
        """Accion de servidor: poblar divisa real (MonedaP) en CFDIs tipo P historicos."""
        revisados, actualizados = self._backfill_payment_currency_from_xml()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Backfill Moneda en CFDIs de Pago',
                'message': f'Pagos revisados: {revisados} | Divisas corregidas: {actualizados}',
                'type': 'success' if actualizados else 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    @api.model
    def cron_backfill_xml_fields(self, limit=3000):
        """CRON (#B auto-poblado): rellena los campos que el parse EN LINEA del create
        deja vacios en algunos casos (fecha_timbrado, desglose de impuestos, cuenta
        predial, moneda de pago) re-parseando el attachment. Corre en su PROPIA
        transaccion, donde los commit-por-chunk de los backfill son seguros (DENTRO
        del pipeline rompen el savepoint -> bug .86). Cubre datos NUEVOS (recien
        bajados) y VIEJOS sin correr acciones de servidor a mano. Acotado por `limit`;
        el cron frecuente termina lo que falte. Idempotente (los backfill solo
        escriben campos vacios)."""
        recs = self.search([('fecha_timbrado', '=', False)], limit=limit)
        if not recs:
            return
        _logger.info("cron_backfill_xml_fields: %d registros con fecha_timbrado vacia", len(recs))
        for _bf in ('_backfill_timbrado_y_taxes_from_xml',
                    '_backfill_cuenta_predial_from_xml',
                    '_backfill_payment_currency_from_xml'):
            if not hasattr(recs, _bf):
                continue
            try:
                getattr(recs, _bf)()
            except Exception as e:
                _logger.warning("cron_backfill_xml_fields %s: %s", _bf, e)

    def _learn_from_imported_invoice(self):
        """Aprende producto/cuenta para los XMLs seleccionados, en dos pases:

        Pase 1 — Match DIRECTO: para XMLs con invoice_id enlazada, copia
        product_id y account_id desde las lineas de la factura (match por
        descripcion mas similar, umbral 0.6).

        Pase 2 — Propagacion entre XMLs del MISMO partner: una vez aprendido
        algo en Pase 1 (o en historial previo), busca otros XMLs del mismo
        partner sin cuenta/producto y propaga el mapeo si la descripcion coincide
        (umbral 0.7). Esto resuelve el caso comun: la primera factura del
        proveedor se registra solo con cuenta contable; las siguientes deben
        heredar esa cuenta automaticamente.

        Solo rellena campos vacios — nunca pisa valores existentes.
        Devuelve (xmls_revisados, productos_aprendidos, cuentas_aprendidas).
        """
        xmls_revisados = 0
        productos_aprendidos = 0
        cuentas_aprendidas = 0

        # PASE 1 — Desde invoice enlazada
        for xml in self:
            invoice = xml.invoice_id
            if not invoice or invoice.state == 'cancel':
                continue
            xmls_revisados += 1
            invoice_lines = invoice.invoice_line_ids.filtered(
                lambda l: l.display_type not in ('line_section', 'line_note', 'line_subtotal')
            )
            if not invoice_lines:
                continue
            for downloaded_line in xml.downloaded_product_id:
                if downloaded_line.product_rel and downloaded_line.account_id:
                    continue
                mejor = None
                mejor_score = 0.0
                for inv_line in invoice_lines:
                    score = similar(downloaded_line.description or '', inv_line.name or '')
                    if score > mejor_score:
                        mejor_score = score
                        mejor = inv_line
                if mejor is None or mejor_score < 0.6:
                    continue
                vals = {}
                if not downloaded_line.product_rel and mejor.product_id:
                    vals['product_rel'] = mejor.product_id.id
                    productos_aprendidos += 1
                if not downloaded_line.account_id and mejor.account_id:
                    vals['account_id'] = mejor.account_id.id
                    cuentas_aprendidas += 1
                if vals:
                    downloaded_line.write(vals)

        # PASE 2 — Propagar entre XMLs del mismo partner.
        # Para cada partner_id de los XMLs seleccionados, juntar TODAS sus lineas
        # historicas que ya tengan product_rel o account_id, y propagarlas a las
        # lineas sin nada del mismo partner.
        partner_ids = set(self.mapped('partner_id').ids)
        XmlLine = self.env['account.edi.downloaded.xml.sat.products']
        for pid in partner_ids:
            # Lineas FUENTE: cualquier linea del partner con cuenta o producto poblado
            fuentes = XmlLine.search([
                ('downloaded_invoice_id.partner_id', '=', pid),
                '|',
                    ('product_rel', '!=', False),
                    ('account_id', '!=', False),
            ], order='id desc')
            if not fuentes:
                continue
            # Lineas DESTINO: solo las que pertenecen a los XMLs seleccionados,
            # sin producto y sin cuenta
            destinos = self.mapped('downloaded_product_id').filtered(
                lambda l: l.downloaded_invoice_id.partner_id.id == pid
                and not l.product_rel
                and not l.account_id
            )
            for d in destinos:
                mejor = None
                mejor_score = 0.0
                d_sat_code = d.sat_id.code if d.sat_id else False
                for f in fuentes:
                    f_sat_code = f.sat_id.code if f.sat_id else False
                    # Boost si comparten codigo SAT exacto
                    score = similar(d.description or '', f.description or '')
                    if f_sat_code and d_sat_code and f_sat_code == d_sat_code:
                        score += 0.2  # boost
                    if score > mejor_score:
                        mejor_score = score
                        mejor = f
                if mejor is None or mejor_score < 0.6:
                    continue
                vals = {}
                if not d.product_rel and mejor.product_rel:
                    vals['product_rel'] = mejor.product_rel.id
                    productos_aprendidos += 1
                if not d.account_id and mejor.account_id:
                    vals['account_id'] = mejor.account_id.id
                    cuentas_aprendidas += 1
                if vals:
                    d.write(vals)
                    xmls_revisados += 1

        return xmls_revisados, productos_aprendidos, cuentas_aprendidas

    def action_learn_from_imported_invoice(self):
        """Accion de servidor: aprende producto+cuenta desde la factura Odoo ya enlazada."""
        revisados, productos, cuentas = self._learn_from_imported_invoice()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Aprendizaje desde facturas enlazadas',
                'message': f'XMLs revisados: {revisados} | Productos aprendidos: {productos} | Cuentas aprendidas: {cuentas}',
                'type': 'success' if (productos or cuentas) else 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    def _learn_from_partner_history(self):
        """Para XMLs SIN factura Odoo enlazada, busca en account.move.line
        historicas del MISMO partner. Heuristica flexible:

        - NO requiere UNSPSC code en el producto Odoo (muchos clientes registran
          solo con cuenta contable, sin producto).
        - Busca match por descripcion similar (umbral 0.6).
        - Boost si comparten codigo SAT cuando ambos tienen producto con UNSPSC.

        Devuelve (xmls_revisados, productos_aprendidos, cuentas_aprendidas).
        """
        xmls_revisados = 0
        productos_aprendidos = 0
        cuentas_aprendidas = 0
        # Cache por partner: todas sus lineas posteadas (independiente de UNSPSC)
        history_cache = {}
        for xml in self:
            if not xml.partner_id:
                continue
            xmls_revisados += 1
            pid = xml.partner_id.id
            if pid not in history_cache:
                history_cache[pid] = self.env['account.move.line'].search(
                    [
                        ('move_id.partner_id', '=', pid),
                        ('move_id.state', '=', 'posted'),
                        ('display_type', 'in', (False, None)),
                        '|',
                            ('product_id', '!=', False),
                            ('account_id', '!=', False),
                    ],
                    order='date desc, id desc',
                    limit=100,
                )
            candidatas = history_cache[pid]
            if not candidatas:
                continue
            for downloaded_line in xml.downloaded_product_id:
                if downloaded_line.product_rel and downloaded_line.account_id:
                    continue
                d_sat_code = downloaded_line.sat_id.code if downloaded_line.sat_id else False
                mejor = None
                mejor_score = 0.0
                for cand in candidatas:
                    score = similar(downloaded_line.description or '', cand.name or '')
                    # Boost si el producto de la candidata tiene el mismo codigo SAT
                    if d_sat_code and cand.product_id and cand.product_id.unspsc_code_id:
                        if cand.product_id.unspsc_code_id.code == d_sat_code:
                            score += 0.2
                    if score > mejor_score:
                        mejor_score = score
                        mejor = cand
                if mejor is None or mejor_score < 0.6:
                    continue
                vals = {}
                if not downloaded_line.product_rel and mejor.product_id:
                    vals['product_rel'] = mejor.product_id.id
                    productos_aprendidos += 1
                if not downloaded_line.account_id and mejor.account_id:
                    vals['account_id'] = mejor.account_id.id
                    cuentas_aprendidas += 1
                if vals:
                    downloaded_line.write(vals)
        return xmls_revisados, productos_aprendidos, cuentas_aprendidas

    def action_learn_from_partner_history(self):
        """Accion de servidor: aprende heuristicamente desde el historial contable del proveedor."""
        revisados, productos, cuentas = self._learn_from_partner_history()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Aprendizaje heuristico desde historial del proveedor',
                'message': f'XMLs revisados: {revisados} | Productos aprendidos: {productos} | Cuentas aprendidas: {cuentas}',
                'type': 'success' if (productos or cuentas) else 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    # ============================================================================
    # EVALUACION CFDI COMPLIANCE PARA XMLs HISTORICOS
    # Los XMLs descargados ANTES de instalar/actualizar compliance no tienen
    # cfdi_document creado (porque el motor solo dispara en ir.attachment.create).
    # Estos metodos crean el doc + corren la pipeline para XMLs huerfanos.
    # ============================================================================

    def _evaluate_compliance(self):
        """Para cada XML en self, asegura que tenga un cfdi_document creado y
        ejecuta la pipeline de compliance. Devuelve (procesados, creados, errores).
        """
        if 'l10n_mx.cfdi.document' not in self.env:
            _logger.info("Modulo l10n_mx_cfdi_compliance no instalado: skip _evaluate_compliance")
            return 0, 0, 0
        # IMPORTANTE: iteramos por IDs y re-browseamos en cada vuelta para evitar
        # 'cursor already closed'. Despues de cr.commit() / cr.rollback() el cursor
        # del environment cambia; si seguimos accediendo a campos de un recordset
        # que viene del scope externo (self), el ORM dispara fetch con cursor stale.
        ids = list(self.ids)
        Model = self.env['account.edi.downloaded.xml.sat']
        Doc = self.env['l10n_mx.cfdi.document'].sudo()
        procesados = 0
        creados = 0
        errores = 0
        for xml_id in ids:
            xml = Model.browse(xml_id)
            att = xml.attachment_id.filtered(_is_xml_attachment)[:1]
            if not att or not att.datas:
                continue
            procesados += 1
            try:
                # Busca doc por UUID; si no existe, lo crea desde el attachment
                doc = Doc.search([('uuid', '=', xml.name)], limit=1) if xml.name else False
                if not doc:
                    doc = Doc._create_from_attachment(att, company=xml.company_id or self.env.company)
                    creados += 1
                doc._run_compliance_pipeline()
                # .86: el campo cfdi_document_id es un compute store=False (compliance
                # v.69+): NO se puede escribir (no tiene inverse) y no hay columna que
                # poblar — el compute lo resuelve on-demand al abrir el registro. Solo
                # lo escribimos si alguna version lo dejara almacenado. Sin este guard,
                # el write tronaba y marcaba "error" en CADA XML de la evaluacion.
                _cfdi_doc_field = xml._fields.get('cfdi_document_id')
                if _cfdi_doc_field and _cfdi_doc_field.store and doc and xml.cfdi_document_id != doc:
                    xml.write({'cfdi_document_id': doc.id})
                # Commit por XML: si la pipeline tira a media tanda, los ya
                # procesados quedan persistidos. El siguiente browse() iniciara con cursor fresco.
                self.env.cr.commit()
            except Exception as exc:
                _logger.warning("Compliance evaluacion fallo en XML %s: %s", xml_id, exc)
                self.env.cr.rollback()
                errores += 1
        return procesados, creados, errores

    def action_evaluate_compliance(self):
        """Accion de servidor: evalua compliance sobre los XMLs seleccionados."""
        procesados, creados, errores = self._evaluate_compliance()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Evaluacion CFDI Compliance',
                'message': f'Procesados: {procesados} | cfdi_documents creados: {creados} | Errores: {errores}',
                'type': 'success' if not errores else 'warning',
                'sticky': errores > 0,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }

    @api.model
    def cron_sync_cfdi_document_links(self):
        """Cron auxiliar: sincroniza el campo cfdi_document_id en xml_sat cuando
        el cfdi_document existe en BD pero el campo no esta poblado. Esto ocurre
        porque el compute _compute_cfdi_document_id solo se dispara cuando cambian
        attachment_id/name del xml_sat, NO cuando se crea un cfdi_document nuevo
        (caso del cron compliance que crea docs en batch).

        Idempotente y barato: solo hace UPDATE de los desincronizados (SQL puro
        sin ORM). Si no hay desincronizados, no toca nada.

        .86: GUARD. En compliance (v.69+) el campo cfdi_document_id del modelo
        xml_sat es un compute con store=False (se resuelve on-demand para no
        bloquear el install en bases con +74K XMLs). Por tanto NO existe columna
        fisica y este UPDATE crudo tronaba con "column x.cfdi_document_id does
        not exist", abortando la transaccion del cron (y con ella el pipeline de
        descarga -> lotes atascados). Si el campo no esta almacenado, no hay nada
        que sincronizar (el compute lo resuelve solo): salimos sin tocar nada.
        """
        XmlModel = self.env['account.edi.downloaded.xml.sat']
        field = XmlModel._fields.get('cfdi_document_id')
        if not field or not field.store:
            return
        self.env.cr.execute(
            """
            UPDATE account_edi_downloaded_xml_sat x
               SET cfdi_document_id = d.id
              FROM l10n_mx_cfdi_document d
             WHERE d.uuid = x.name
               AND x.name IS NOT NULL
               AND x.cfdi_document_id IS NULL
            """
        )
        updated = self.env.cr.rowcount
        if updated:
            self.env.cr.commit()
            _logger.info("Cron compliance sync: %s XMLs sincronizados con su cfdi_document_id", updated)

    @api.model
    def cron_evaluate_compliance_pending(self, batch_size=200):
        """Cron: drena XMLs sin cfdi_document, batch_size por ejecucion.

        Usa SQL directo (LEFT JOIN) para detectar huerfanos — escala a 500K+
        sin cargar listas grandes en memoria. Si el modulo compliance no esta
        instalado, no hace nada.

        Antes de drenar huerfanos, ejecuta sync de links cfdi_document_id que
        pudieron quedar desincronizados (ver cron_sync_cfdi_document_links).
        """
        if 'l10n_mx.cfdi.document' not in self.env:
            return
        # Pase 0: sincronizar links cfdi_document_id desincronizados
        self.cron_sync_cfdi_document_links()
        # LEFT JOIN SQL: XMLs SAT con attachment XML y SIN cfdi_document por UUID.
        # Mucho mas eficiente que cargar el set de UUIDs existentes en Python.
        self.env.cr.execute(
            """
            SELECT x.id
            FROM account_edi_downloaded_xml_sat x
            JOIN ir_attachment a
              ON a.res_id = x.id
             AND a.res_model = 'account.edi.downloaded.xml.sat'
             AND a.mimetype = 'application/xml'
             AND a.store_fname IS NOT NULL
            LEFT JOIN l10n_mx_cfdi_document d
              ON d.uuid = x.name
            WHERE x.name IS NOT NULL
              AND d.id IS NULL
            ORDER BY x.id DESC
            LIMIT %s
            """,
            (batch_size,),
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        if not ids:
            _logger.info("Cron compliance: sin XMLs pendientes de evaluar")
            return
        pendientes = self.browse(ids)
        _logger.info("Cron compliance: evaluando %s XMLs huerfanos (batch_size=%s)", len(ids), batch_size)
        procesados, creados, errores = pendientes._evaluate_compliance()
        _logger.info(
            "Cron compliance: procesados=%s creados=%s errores=%s",
            procesados, creados, errores,
        )

    def action_apply_ieps_in_base_retroactive(self):
        """Aplica el flag 'IEPS en la base' RETROACTIVAMENTE sobre lineas de
        facturas ya creadas a partir de los XMLs seleccionados.

        Solo afecta facturas en estado 'draft' (borrador) por seguridad: facturas
        publicadas, canceladas o conciliadas NO se tocan (cuenta omitidos por estado).
        El admin puede revertir a borrador manualmente si quiere aplicar el cambio.

        Cambios por linea afectada:
          - price_unit += ieps_traslado_amount / quantity
          - tax_ids -= taxes cuyo name empieza con 'IEPS'

        Es SOLO ADMIN porque modifica facturas (riesgo contable).
        """
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Esta accion solo esta disponible para Administradores.'))
        if not self:
            return False
        ajustados = 0
        omitidos_state = 0
        omitidos_sin_ieps = 0
        # Backfill rapido: para los XMLs seleccionados, asegurar que ieps_traslado_amount
        # este poblado antes de iterar. Esto resuelve el caso de XMLs descargados
        # antes de v19.0.46.3 cuyo campo quedo en 0.
        try:
            self._backfill_timbrado_y_taxes_from_xml()
            self.env.cr.commit()
        except Exception as exc:
            _logger.warning("Pre-backfill en accion IEPS retroactivo fallo: %s", exc)
        for xml in self:
            inv = xml.invoice_id
            if not inv:
                continue
            if inv.state != 'draft':
                omitidos_state += 1
                continue
            cambio = False
            for line in inv.invoice_line_ids:
                rel = line.downloaded_product_rel
                if not rel or not rel.quantity:
                    continue
                # Detectar si la linea aun tiene tax IEPS — si no, ya fue ajustada.
                # Detectar taxes IEPS por contenido del name. En MX los names suelen
                # ser "8% IEPS", "26.5% IEPS Trasladado", etc. — no siempre empiezan
                # con 'IEPS'. Usamos 'in' para cubrir todas las variantes.
                ieps_taxes = line.tax_ids.filtered(lambda t: 'IEPS' in (t.name or '').upper())
                if not ieps_taxes:
                    omitidos_sin_ieps += 1
                    continue
                # Si despues del backfill aun no hay ieps_traslado_amount, saltarse esta
                # linea (puede que el XML no tenga IEPS realmente y el tax estaba colgado).
                if not rel.ieps_traslado_amount:
                    continue
                new_price = line.price_unit + (rel.ieps_traslado_amount / rel.quantity)
                line.write({
                    'price_unit': new_price,
                    'tax_ids': [(3, t.id) for t in ieps_taxes],  # remove IEPS taxes
                })
                cambio = True
            if cambio:
                ajustados += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'IEPS en la base (retroactivo)',
                'message': (
                    f'Facturas ajustadas: {ajustados}'
                    f' | Omitidas (no estaban en borrador): {omitidos_state}'
                    f' | Lineas ya ajustadas previamente: {omitidos_sin_ieps}'
                ),
                'type': 'success' if ajustados else 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }


class AccountEdiApiDownload(models.Model):
    _name = 'account.edi.api.download'
    _description = "Account Edi Download From SAT Web Service"

    download_coordinadas = fields.Boolean(
        string="Descargar XMLs de coordinadas",
        default=False,
        help="Si está marcado, se creará un lote por cada coordinada relacionada de la controladora actual."
    )
    # Bandera de visibilidad para el checkbox download_coordinadas en la UI.
    # El checkbox solo tiene sentido si:
    #  1. l10n_mx_cfdi_compliance esta instalado (modelo coordinado.relation existe)
    #  2. La company activa tiene al menos una relacion de coordinada activa
    #     como controladora_company_id (config en menu Compliance > Coordinadas)
    # Sin esto el checkbox se mostraba siempre, confundiendo a clientes
    # single-tenant (Cosal, despachos) que no usan coordinadas.
    has_coordinadas_config = fields.Boolean(
        compute='_compute_has_coordinadas_config',
        help="True si la empresa actual tiene relaciones de coordinadas configuradas. "
             "Controla la visibilidad del checkbox 'Descargar XMLs de coordinadas'.",
    )

    @api.depends_context('company')
    def _compute_has_coordinadas_config(self):
        # Soft dependency: si compliance no esta instalado, env.get retorna None.
        CoordRel = self.env.get('l10n_mx.cfdi.coordinado.relation')
        if CoordRel is None:
            for rec in self:
                rec.has_coordinadas_config = False
            return
        # Conteo unico por company activa (no por record) — todos los lotes de
        # la misma company comparten el mismo valor.
        company_id = self.env.company.id
        count = CoordRel.sudo().search_count([
            ('controladora_company_id', '=', company_id),
            ('active', '=', True),
        ])
        flag = bool(count)
        for rec in self:
            rec.has_coordinadas_config = flag

    @api.model
    def _get_default_vat(self):
        return self.env.company.vat
    
    # Fields
    name = fields.Char(string='Nombre',  index=True) 
    vat = fields.Char(string='RFC',  default=_get_default_vat)
    # company_id se resuelve a partir del VAT del lote:
    # - Si existe una res.company con vat = lote.vat -> esa es la Empresa.
    #   Esto cubre el caso multi-company (despachos como ANFEPI donde cada
    #   cliente es su propia res.company). Antes el default env.company hacia
    #   que lotes de cliente B quedaran pegados a cliente A si el admin
    #   estaba en contexto A al crear/auto-generar el lote.
    # - Si NO existe (caso single-company con varios RFCs internos como Cosal
    #   o Vencedor con coordinadas), se mantiene la company activa.
    # Stored para que las reglas de seguridad por company_id sigan funcionando
    # eficientemente (indexed).
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        compute='_compute_company_id_from_vat',
        store=True,
        readonly=False,
        index=True,
        # NOTA: NO default=env.company. Odoo aplica defaults ANTES del
        # compute, dejando company_id pegado a la company activa aunque
        # el VAT corresponda a otra. El compute maneja el fallback a
        # env.company cuando no hay VAT match.
    )

    @api.depends('vat')
    def _compute_company_id_from_vat(self):
        Company = self.env['res.company'].sudo()
        for rec in self:
            if not rec.vat:
                if not rec.company_id:
                    rec.company_id = self.env.company.id
                continue
            owner = Company.search([('vat', '=', rec.vat)], limit=1)
            if owner:
                rec.company_id = owner.id
            elif not rec.company_id:
                rec.company_id = self.env.company.id

    @api.constrains('vat', 'company_id')
    def _check_vat_company_consistency(self):
        """Impide que un lote tenga company_id distinto a la res.company cuyo
        vat coincide con el del lote. Esto es la barrera defensiva en caso de
        que algun flujo (wizard, importacion masiva, escritura manual ORM)
        intente forzar un mismatch. Permite cualquier company solo cuando el
        VAT del lote no corresponde a ninguna res.company (caso single-tenant
        con RFCs internos: Cosal, Vencedor coordinadas)."""
        Company = self.env['res.company'].sudo()
        for rec in self:
            if not rec.vat or not rec.company_id:
                continue
            owner = Company.search([('vat', '=', rec.vat)], limit=1)
            if owner and owner.id != rec.company_id.id:
                from odoo.exceptions import ValidationError
                raise ValidationError(
                    f"El RFC {rec.vat} pertenece a la empresa '{owner.name}' "
                    f"pero el lote esta asignado a '{rec.company_id.name}'. "
                    f"Esto bloquearia la visibilidad correcta en multi-company. "
                    f"Empresa correcta: {owner.name}."
                )

    @api.constrains('vat', 'cfdi_type', 'date_start', 'date_end', 'company_id')
    def _check_no_duplicate_or_overlap(self):
        """Impide lotes DUPLICADOS o con rango TRASLAPADO para la misma
        (empresa, RFC, tipo). Aplica por igual a lotes principales y a sublotes
        de coordinadas (cada hijo es un registro con su propio vat).

        Es la barrera definitiva contra la fuente de duplicados que inflaba las
        cifras de coordinadas (ej. mayo recibidos x4): antes nada impedia crear
        dos lotes identicos. @api.constrains solo dispara al crear/escribir esos
        campos, por lo que NO rompe el upgrade aunque ya existan duplicados
        historicos (esos se limpian con un dedup aparte)."""
        from odoo.exceptions import ValidationError
        tipo_label = dict(self._fields['cfdi_type'].selection)
        for rec in self:
            if not (rec.vat and rec.cfdi_type and rec.date_start and rec.date_end):
                continue
            otros = self.sudo().search([
                ('id', '!=', rec.id),
                ('vat', '=', rec.vat),
                ('cfdi_type', '=', rec.cfdi_type),
                ('company_id', '=', rec.company_id.id),
            ])
            tlabel = tipo_label.get(rec.cfdi_type, rec.cfdi_type)
            for o in otros:
                if not (o.date_start and o.date_end):
                    continue
                if o.date_start == rec.date_start and o.date_end == rec.date_end:
                    raise ValidationError(
                        "Ya existe un lote para %s (%s) del %s al %s [lote #%s]. "
                        "No se permiten lotes duplicados: usa el lote existente o "
                        "actualizalo en vez de crear otro." % (
                            rec.vat, tlabel, rec.date_start, rec.date_end, o.id))
                if rec.date_start <= o.date_end and rec.date_end >= o.date_start:
                    raise ValidationError(
                        "El rango %s a %s de %s (%s) se traslapa con el lote #%s "
                        "(%s a %s). Ese periodo ya esta considerado en otro lote: "
                        "ajusta el rango, o usa/elimina ese lote." % (
                            rec.date_start, rec.date_end, rec.vat, tlabel,
                            o.id, o.date_start, o.date_end))

    def unlink(self):
        """Permite eliminar lotes (incluidos duplicados y sublotes de
        coordinadas) ahora que el ACL lo habilita, pero protege los que estan
        descargando en este momento para no cortar un pipeline a la mitad."""
        from odoo.exceptions import UserError
        procesando = self.filtered(lambda r: r.state == 'processing')
        if procesando:
            raise UserError(
                "No se puede eliminar un lote en estado 'Procesando': %s. "
                "Espera a que el cron termine o marcalo en 'error' primero." % (
                    ", ".join(procesando.mapped('name') or [str(procesando.ids)])))
        return super().unlink()

    date_start = fields.Date(string='Fecha de Comienzo', required=True, default=fields.Date.today())
    date_end = fields.Date(string='Fecha de Finalizacion', required=True, default=fields.Date.today())

    @api.onchange('date_start')
    def _onchange_date_start_fin_de_mes(self):
        """Al fijar la fecha de comienzo, sugiere automaticamente el ULTIMO dia de
        ese mes como fecha de finalizacion (editable). Asi crear un lote mensual es
        practicamente 1 solo clic. Solo afecta la UI; la creacion programatica
        (onboarding/recover) no dispara onchange."""
        if self.date_start:
            import calendar
            last_day = calendar.monthrange(self.date_start.year, self.date_start.month)[1]
            self.date_end = self.date_start.replace(day=last_day)
    last_update_date = fields.Date(string='Última actualización',  default=fields.Date.today())
    cfdi_type = fields.Selection([('emitidos', 'Emitidos'), ('recibidos', 'Recibidos')], string='Tipo', required=True, default='recibidos')
    state = fields.Selection(
    selection=[
        ('not_imported', 'No importado'),
        ('queued', 'En cola'),
        ('processing', 'Procesando'),
        ('imported', 'Importado'),
        ('error', 'Error'),
    ],
    string='Status', default='not_imported', readonly=True,
    help="Estado del lote. La fecha 'Última actualización' indica cuándo fue la última sincronización con el SAT.",
    )
    queued_at = fields.Datetime(string='Encolado en', readonly=True)
    last_error = fields.Text(string='Último error', readonly=True)
    xml_sat_ids = fields.One2many(
        'account.edi.downloaded.xml.sat',
        'batch_id',
        string='Downloaded XML SAT',
        copy=True,
        readonly=True,
    )
    xml_count = fields.Integer(string='Delivery Orders', compute='_compute_xml_ids')
    child_batch_count = fields.Integer(string='Lotes coordinadas', compute='_compute_child_batch_count')

    # Nombre del contribuyente real, resuelto desde el VAT. En un esquema
    # single-tenant todas las coordinadas viven bajo la company de la
    # controladora (TRANSPORTES VENCEDOR), por lo que mostrar `company_id`
    # en la lista no aporta informacion. Este campo busca el res.partner
    # (activo o archivado) cuyo VAT coincide con el del lote y devuelve su
    # razon social; si no lo encuentra, cae al propio VAT.
    contribuyente_name = fields.Char(
        string='Contribuyente',
        compute='_compute_contribuyente_name',
        store=True,
    )

    @api.depends('vat')
    def _compute_contribuyente_name(self):
        Partner = self.env['res.partner'].with_context(active_test=False)
        for rec in self:
            if not rec.vat:
                rec.contribuyente_name = ''
                continue
            p = Partner.search([
                ('vat', '=', rec.vat),
                ('is_company', '=', True),
            ], limit=1)
            rec.contribuyente_name = p.name if p else rec.vat

    # Relación padre↔hijo: cuando un lote de la controladora se descarga con
    # `download_coordinadas=True`, se encolan lotes "hijos" — uno por cada
    # coordinada— que apuntan al lote padre. Esto permite que el botón
    # inteligente del padre muestre la suma de XMLs (controladora + coordinadas).
    parent_batch_id = fields.Many2one(
        'account.edi.api.download',
        string='Lote padre',
        ondelete='set null',
        readonly=True,
        index=True,
        help="Lote padre de la controladora cuando este lote pertenece a una coordinada."
    )
    child_batch_ids = fields.One2many(
        'account.edi.api.download',
        'parent_batch_id',
        string='Lotes de coordinadas',
        readonly=True,
    )

    # Campos para filtrat por tipo de documento
    ingreso = fields.Boolean(string="Ingreso", default=True)
    egreso = fields.Boolean(string="Egreso", default=True)
    pago = fields.Boolean(string="Pago", default=True)
    nomina = fields.Boolean(string="Nomina", default=True)
    traslado = fields.Boolean(string="Traslado", default=True)
    # Estos estan mas dificiles (pendiente)
    cancelado = fields.Boolean(string="Cancelados", default=True)
    valido = fields.Boolean(string="Vigentes", default=True)
    no_encontrado = fields.Boolean(string="No encontrado", default=True)

    # True cuando el último sync no encontró XMLs nuevos Y han pasado >72h desde date_end.
    # Las 72 horas son la ventana máxima que SAT puede tardar en entregar CFDIs
    # de los últimos días del periodo (ej: facturas del 31 de diciembre pueden
    # llegar hasta el 3 de enero). Antes de ese plazo el lote nunca se marca estable.
    sync_stable = fields.Boolean(
        string="Sincronización completa",
        default=False,
        readonly=True,
        help="Se activa cuando: (1) el último ciclo no trajo XMLs nuevos, (2) no hubieron "
             "chunks fallidos y (3) han transcurrido más de 72 horas desde la Fecha de "
             "Finalización del lote. Las 72h cubren la ventana máxima en que SAT puede "
             "entregar CFDIs de los últimos días del periodo cerrado."
    )

    # ===============================================================
    # End-to-end SAT completeness verification (xmlsat 2026-05)
    # ===============================================================
    sat_verified_complete = fields.Boolean(
        string="Verificado vs SAT",
        readonly=True,
        help="True cuando el conteo de XMLs almacenados coincide con el NumeroCFDIs "
             "declarado por SAT para el rango.",
    )
    sat_expected_count = fields.Integer(
        string="CFDIs declarados SAT",
        readonly=True,
    )
    sat_downloaded_count = fields.Integer(
        string="CFDIs descargados",
        readonly=True,
    )
    sat_verified_windows = fields.Integer(string="Ventanas verificadas", readonly=True)
    sat_total_windows = fields.Integer(string="Ventanas totales", readonly=True)
    sat_last_verified_at = fields.Datetime(string="Ultima verificacion SAT", readonly=True)
    sat_completeness_message = fields.Char(string="Estado verificacion SAT", readonly=True)

    # Totales que incluyen suma de coordinadas hijas. xml_count ya suma hijos
    # por su lado; estos tres campos hacen lo mismo para los conteos SAT y el
    # flag verificado, asi UI muestra cifras coherentes para el lote padre.
    sat_expected_count_total = fields.Integer(
        string="CFDIs declarados SAT (con coordinadas)",
        compute='_compute_sat_totals',
        readonly=True,
    )
    sat_downloaded_count_total = fields.Integer(
        string="CFDIs descargados (con coordinadas)",
        compute='_compute_sat_totals',
        readonly=True,
    )
    sat_verified_complete_total = fields.Boolean(
        string="Verificado vs SAT (con coordinadas)",
        compute='_compute_sat_totals',
        readonly=True,
    )

    @api.depends(
        'sat_expected_count', 'sat_downloaded_count', 'sat_verified_complete',
        'child_batch_ids.sat_expected_count',
        'child_batch_ids.sat_downloaded_count',
        'child_batch_ids.sat_verified_complete',
    )
    def _compute_sat_totals(self):
        for r in self:
            own_exp = r.sat_expected_count or 0
            own_dl = r.sat_downloaded_count or 0
            own_ok = bool(r.sat_verified_complete)
            kids_exp = sum(c.sat_expected_count or 0 for c in r.child_batch_ids)
            kids_dl = sum(c.sat_downloaded_count or 0 for c in r.child_batch_ids)
            kids_ok = all(c.sat_verified_complete for c in r.child_batch_ids) if r.child_batch_ids else True
            r.sat_expected_count_total = own_exp + kids_exp
            r.sat_downloaded_count_total = own_dl + kids_dl
            r.sat_verified_complete_total = own_ok and kids_ok

        
    cfdis_sat_display = fields.Char(
        string="CFDIs en SAT",
        compute='_compute_cfdis_sat_display',
        help="Conteo declarado por el SAT cuando la verificacion esta completa. "
             "Mientras la verificacion contra el SAT sigue en curso muestra "
             "'Verificando...' (con el avance), porque el numero parcial no es "
             "comparable todavia con los XMLs descargados.",
    )

    @api.depends('sat_expected_count_total', 'sat_verified_complete_total',
                 'sat_verified_windows', 'sat_total_windows')
    def _compute_cfdis_sat_display(self):
        for r in self:
            tot = r.sat_total_windows or 0
            done = r.sat_verified_windows or 0
            if r.sat_expected_count_total or r.sat_verified_complete_total or (tot and done >= tot):
                # Hay total real del SAT: metadata autoritativa por UUID
                # (sat_expected_count>0 viene de sat_metadata_ref) o la verificacion
                # de ventanas ya termino -> mostrar el numero. "Verificando..." solo
                # cuando NO hay total comparable aun (expected=0 y ventanas en curso).
                r.cfdis_sat_display = str(r.sat_expected_count_total or 0)
            elif tot:
                r.cfdis_sat_display = "Verificando... %d%%" % int(100 * done / tot)
            else:
                r.cfdis_sat_display = "Verificando..."

    @api.depends('xml_sat_ids', 'child_batch_ids.xml_sat_ids')
    def _compute_xml_ids(self):
        # Conteo via SQL directo: len(xml_sat_ids) falla para lotes con >5500
        # records (ORM no carga toda la relacion, retorna subset).
        if not self:
            return
        all_batch_ids = list(set(self.ids) | set(self.child_batch_ids.ids))
        if not all_batch_ids:
            for xml in self:
                xml.xml_count = 0
            return
        # COUNT(DISTINCT name) en lugar de COUNT(*): si hay duplicados temporales
        # en la tabla (residuos de bug anterior antes de cleanup), el conteo
        # natural del usuario es por UUID unico, no por filas fisicas.
        # Cuando la tabla este limpia, ambos counts coincidiran.
        self.env.cr.execute(
            """
            SELECT batch_id, COUNT(DISTINCT name)
              FROM account_edi_downloaded_xml_sat
             WHERE batch_id = ANY(%s)
               AND name IS NOT NULL AND name != ''
             GROUP BY batch_id
            """,
            (all_batch_ids,),
        )
        counts = dict(self.env.cr.fetchall())
        for xml in self:
            propios = counts.get(xml.id, 0)
            hijos = sum(counts.get(c.id, 0) for c in xml.child_batch_ids)
            xml.xml_count = propios + hijos
        
    def view_xml_sat(self):
         # Incluir XMLs del lote y de sus lotes hijos (coordinadas)
         batch_ids = [self.id] + self.child_batch_ids.ids
         xml_sat_ids = self.env['account.edi.downloaded.xml.sat'].search([
             ('batch_id', 'in', batch_ids)
         ]).ids

         return {
            'type': 'ir.actions.act_window',
            'name': 'XML SAT',
            'res_model': 'account.edi.downloaded.xml.sat',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'target': 'current',
            'domain': [('id', 'in', xml_sat_ids)]
        }

    @api.depends('child_batch_ids')
    def _compute_child_batch_count(self):
        for rec in self:
            rec.child_batch_count = len(rec.child_batch_ids)

    def action_view_child_batches(self):
        """Abre los lotes de las coordinadas vinculados a este lote padre."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lotes de coordinadas',
            'res_model': 'account.edi.api.download',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('id', 'in', self.child_batch_ids.ids)],
            'context': {'create': False},
        }

    def action_manual_upload(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Upload XML',
            'res_model': 'manual.upload.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_mx_xml_massive_download.view_manual_upload_wizard_form').id,
            'target': 'new',
            'context': {
                'default_download_batch_id': self.id,
                'active_id': self.id,
            },
        }

    def _enqueue_coordinadas_children(self, skip_existing=True):
        """Encola lotes hijo (uno por cada coordinada autorizada de la controladora).
        Si skip_existing=True (default), saltea las coordinadas que YA tienen un
        lote hijo asociado a este padre — util para 'agregar coordinadas faltantes'
        despues de la descarga inicial sin duplicar.
        Devuelve cuantos lotes nuevos creo.
        """
        self.ensure_one()
        if not self.company_id:
            return 0
        CoordinadoRelation = self.env['l10n_mx.cfdi.coordinado.relation']
        relaciones = CoordinadoRelation.search([
            ('controladora_company_id', '=', self.company_id.id),
            ('active', '=', True),
        ])
        if not relaciones:
            raise UserError('No existen relaciones de coordinadas activas para esta controladora.')

        created = 0
        for rel in relaciones:
            coordinada_vat = rel.coordinada_vat
            # Idempotente SIEMPRE (no solo con skip_existing): no crear un lote
            # hijo si YA existe uno para la misma (empresa, RFC coordinada, tipo)
            # cuyo rango se TRASLAPE con el solicitado, sin importar de que padre
            # cuelgue. Esto elimina la fuente de los duplicados x2/x4 de
            # coordinadas (se generaban al re-encolar el padre con
            # skip_existing=False) y evita chocar con el constraint de traslape.
            ya_existe = self.sudo().search([
                ('vat', '=', coordinada_vat),
                ('cfdi_type', '=', self.cfdi_type),
                ('company_id', '=', self.company_id.id),
                ('date_start', '<=', self.date_end),
                ('date_end', '>=', self.date_start),
            ], limit=1)
            if ya_existe:
                continue
            vals = {
                'name': f"{self.cfdi_type} ({self.date_start.strftime('%d-%b-%Y')} - {self.date_end.strftime('%d-%b-%Y')}) - {coordinada_vat}",
                'vat': coordinada_vat,
                'company_id': self.company_id.id,
                'date_start': self.date_start,
                'date_end': self.date_end,
                'cfdi_type': self.cfdi_type,
                'ingreso': self.ingreso,
                'egreso': self.egreso,
                'pago': self.pago,
                'nomina': self.nomina,
                'traslado': self.traslado,
                'cancelado': self.cancelado,
                'valido': self.valido,
                'no_encontrado': self.no_encontrado,
                'download_coordinadas': False,  # los hijos no recursan
                'state': 'queued',
                'queued_at': fields.Datetime.now(),
                'parent_batch_id': self.id,
            }
            self.sudo().create(vals)
            created += 1
        return created

    def action_download(self):
        """Encolar lote(s) para procesamiento asíncrono por el cron.

        El procesamiento real (descarga + parseo + escritura BD) consume mucha
        RAM y puede tardar varios minutos por lote. Hacerlo síncrono dentro
        del worker HTTP causaba dos problemas:
          1) Worker mataba por límite de memoria → 502 Bad Gateway.
          2) UI bloqueada → el usuario no podía crear otros lotes.
        Ahora `action_download` solo marca state='queued' y deja que el cron
        `cron_auto_sync_batches` (que corre cada minutos) ejecute el pipeline.
        """
        # Si es controladora con coordinadas, encolar también un lote por cada
        # coordinada relacionada (NO se procesan recursivamente — los toma el cron).
        if self.download_coordinadas:
            self._enqueue_coordinadas_children(skip_existing=True)
        # Marcar el lote actual como encolado y devolver notificación.
        self.write({
            'state': 'queued',
            'queued_at': fields.Datetime.now(),
            'last_error': False,
        })
        self.env.cr.commit()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Lote encolado',
                'message': 'El lote será procesado por el cron en los próximos minutos. Puede continuar creando otros lotes mientras tanto.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_enqueue_missing_coordinadas(self):
        """Agrega descarga de coordinadas a un lote PADRE que ya bajo sin ellas.

        Caso UX: el usuario creo el lote sin marcar 'Descargar XMLs de coordinadas'
        y ya bajo todo. En lugar de borrar y re-descargar, este boton:

        1. Marca download_coordinadas=True (si no lo estaba)
        2. Encola SOLO los hijos faltantes (skip_existing=True evita duplicar)
        3. NO toca el lote padre (no re-descarga lo que ya bajo)

        Solo aplica a lotes padre (no hijos). Idempotente: si todas las coordinadas
        ya tienen lote, no hace nada y notifica.
        """
        self.ensure_one()
        if self.parent_batch_id:
            raise UserError(
                'Esta accion solo aplica a lotes padre (controladora). '
                'Este lote es hijo de una coordinada.'
            )
        # Auto-activar el flag para que el usuario vea el estado consistente
        if not self.download_coordinadas:
            self.write({'download_coordinadas': True})
        created = self._enqueue_coordinadas_children(skip_existing=True)
        self.env.cr.commit()
        if created:
            return {
                'type': 'ir.actions.act_window',
                'name': f'{created} lote(s) coordinada(s) encolados',
                'res_model': 'account.edi.api.download',
                'view_mode': 'list,form',
                'domain': [('parent_batch_id', '=', self.id)],
                'context': {'create': False},
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sin coordinadas pendientes',
                'message': 'Todas las coordinadas autorizadas ya tienen lote para este rango. No se creo ninguno nuevo.',
                'type': 'info',
                'sticky': False,
            }
        }

    def _run_download_pipeline(self):
        """Pipeline real de descarga (lo que antes hacía action_download síncrono).
        Lo invoca el cron desde `cron_auto_sync_batches`. NO debe ser llamado
        desde la UI directamente porque consume mucha RAM y tarda minutos.
        """
        # Lógica original para lote único
        # Cache para impuestos, productos, empresas y partners para optimizar búsquedas repetidas
        tax_cache = {}
        product_cache = {}
        company_cache = {}
        partner_cache = {}  # RFC -> res.partner (evita 1 SELECT por XML)
        sat_code_cache = {}  # clave_prod_serv -> product.unspsc.code (evita repeats por concepto)
        # Mapeos historicos producto SAT -> product.product, agrupados por proveedor.
        # Se precargan en 1 query por proveedor (ver get_products) y se indexan en memoria
        # por codigo SAT para que la sugerencia inteligente sea O(1) por concepto.
        # Estructura: { partner_id: { sat_code: [(description, product_rel), ...] } }
        partner_mappings_cache = {}
        
        _logger.info(f"Iniciando procesamiento del lote {self.name}")

        # similar() ahora vive a nivel de modulo (compartido con los helpers
        # _learn_from_imported_invoice y _learn_from_partner_history).

        def _l10n_mx_edi_import_cfdi_get_tax_from_node(self, tax_node, is_withholding=False):
            try:
                tasa_raw = tax_node.attrib.get('TasaOCuota')
                if tasa_raw is None:
                    # CFDIs exentos o con impuesto sin TasaOCuota → se omite sin error
                    return False
                amount = float(tasa_raw) * (-100 if is_withholding else 100)
                tax_type = CFDI_CODE_TO_TAX_TYPE.get(tax_node.attrib.get('Impuesto'))
                type_use = 'sale' if self.cfdi_type == 'emitidos' else 'purchase'
                
                # Cache key — incluye la empresa del lote: en multi-empresa cada
                # compania tiene su PROPIO "IVA(16%) COMPRAS" (mismo amount/tipo,
                # distinto company_id), por lo que el cache NO puede ser global.
                company = self.company_id
                cache_key = (company.id, amount, type_use, tax_type)
                if cache_key in tax_cache:
                    return tax_cache[cache_key]

                # FIX multi-empresa (SaaS): filtrar por la empresa del lote. Antes el
                # dominio NO filtraba por compania -> en una base con varias empresas el
                # search devolvia el impuesto de OTRO tenant; al asignarlo a la factura
                # Odoo lo rechazaba por cruce de empresas y el IVA quedaba en 0 (sintoma
                # "un dia jala y otro no", segun el contexto de env.company al parsear).
                domain = [
                    ('company_id', '=', company.id),
                    ('amount', '=', amount),
                    ('type_tax_use', '=', type_use),
                    ('amount_type', '=', 'percent'),
                ]
                if tax_type:
                    domain.append(('l10n_mx_tax_type', '=', tax_type))
                taxes = self.env['account.tax'].search(domain, limit=1)
                if not taxes:
                    _logger.warning(f"No se encontró impuesto: {tax_type} {amount}")
                    return False
                
                tax_cache[cache_key] = taxes[:1]
                return taxes[:1]
            except Exception as e:
                _logger.error(f"Error buscando impuesto: {str(e)}")
                return False  

        """  
        Function that extracts the products from the XML
        return: list of dictionaries with the products
        """
        def get_products(xml_file_or_root, partner_id=False):
            # Acepta tanto el árbol lxml ya parseado (cfdi_node) como el string XML original
            # para evitar parsear el mismo XML una tercera vez.
            # partner_id se usa para sugerir el producto Odoo en base al historial del MISMO
            # proveedor (evita contagio entre proveedores que comparten codigo SAT).
            if isinstance(xml_file_or_root, (str, bytes)):
                root = ET.fromstring(xml_file_or_root)
            else:
                root = xml_file_or_root
            # Define the namespace used in the XML (soporta CFDI 3.3 y 4.0)
            ns = _get_cfdi_ns(root)
            # Find the cfdi:Conceptos element
            conceptos_element = root.find('.//cfdi:Conceptos', namespaces=ns)
            # Initialize an empty list to store dictionaries
            conceptos_list = []
            if conceptos_element is not None:

                # Iterate over cfdi:Concepto elements and extract information
                for concepto_element in conceptos_element.findall('.//cfdi:Concepto', namespaces=ns):
                    clave_prod_serv = concepto_element.get('ClaveProdServ')
                    cantidad = concepto_element.get('Cantidad')
                    clave_unidad = concepto_element.get('ClaveUnidad')
                    descripcion = concepto_element.get('Descripcion')
                    valor_unitario = concepto_element.get('ValorUnitario')
                    importe = concepto_element.get('Importe')
                    descuento = concepto_element.get('Descuento')

                    # Cuenta Predial: nodo hijo del Concepto, obligatorio en CFDI
                    # de arrendamiento de inmuebles (clavesSAT 8013xxxx / 8014xxxx).
                    cuenta_predial_node = concepto_element.find('cfdi:CuentaPredial', namespaces=ns)
                    cuenta_predial_num = cuenta_predial_node.get('Numero') if cuenta_predial_node is not None else False

                    taxes = []
                    taxes_ids = []
                    total_impuestos = 0
                    total_retenciones = 0
                    # Acumulador del IEPS TRASLADADO de este concepto. Util cuando el
                    # cliente activa l10n_mx_xml_download_ieps_in_base para que al
                    # importar la factura el IEPS se sume al precio en lugar de
                    # registrarse como impuesto.
                    ieps_traslado_linea = 0.0
                    # Breakdown estructurado de impuestos por concepto — base para render
                    # UI cuando no hay account.tax configurado para algun impuesto.
                    taxes_breakdown_list = []

                    def _safe_float(v):
                        try:
                            return float(v) if v not in (None, '') else None
                        except (ValueError, TypeError):
                            return None

                    # Buscamos los impuestos
                    impuestos = concepto_element.find('.//cfdi:Impuestos', namespaces=ns)
                    if impuestos is not None:

                        traslados = impuestos.find('.//cfdi:Traslados', namespaces=ns)
                        if traslados is not None:
                            for traslado in traslados.findall('.//cfdi:Traslado', namespaces=ns):
                                imp = float(traslado.get('Importe')) if traslado.get('Importe') else 0
                                total_impuestos += imp
                                # Detectar IEPS trasladado (codigo SAT 003) para el flag.
                                if traslado.get('Impuesto') == '003':
                                    ieps_traslado_linea += imp
                                taxes.append(_l10n_mx_edi_import_cfdi_get_tax_from_node(self, tax_node=traslado, is_withholding=False))
                                taxes_breakdown_list.append({
                                    'kind': 'traslado',
                                    'tipo': traslado.get('Impuesto') or '',
                                    'factor': traslado.get('TipoFactor') or '',
                                    'rate': _safe_float(traslado.get('TasaOCuota')),
                                    'amount': imp,
                                })
                        retenciones = impuestos.find('.//cfdi:Retenciones', namespaces=ns)
                        if retenciones is not None:
                            for retencion in retenciones.findall('.//cfdi:Retencion', namespaces=ns):
                                imp_ret = float(retencion.get('Importe')) if retencion.get('Importe') else 0
                                total_retenciones += imp_ret
                                taxes.append(_l10n_mx_edi_import_cfdi_get_tax_from_node(self, tax_node=retencion, is_withholding=True))
                                taxes_breakdown_list.append({
                                    'kind': 'retencion',
                                    'tipo': retencion.get('Impuesto') or '',
                                    'factor': retencion.get('TipoFactor') or '',
                                    'rate': _safe_float(retencion.get('TasaOCuota')),
                                    'amount': imp_ret,
                                })
                    
                    for tax in taxes: 
                        try:
                            if tax.id:
                                taxes_ids.append(tax.id)
                        except AttributeError as e:
                            pass
                    
                    # Sugerencia "inteligente" de producto Odoo + cuenta contable:
                    #   1) Match contra historial del MISMO proveedor (precargado 1 vez por lote)
                    #      con similitud de descripcion > 0.8
                    #   2) Fallback global cross-proveedor solo si la descripcion es casi identica
                    #      (similitud > 0.9) — evita contagio cuando varios proveedores comparten
                    #      codigos SAT genericos (p. ej. 01010101)
                    # El cache devuelve (producto, cuenta) — la cuenta es independiente:
                    # muchas empresas no usan producto Odoo y registran directo en una cuenta.
                    product_cache_key = (partner_id, clave_prod_serv, descripcion)
                    final_product = False
                    final_account = False

                    if product_cache_key in product_cache:
                        final_product, final_account = product_cache[product_cache_key]
                    else:
                        # Precarga del historial del proveedor (1 sola query por proveedor en el lote).
                        # Incluye lineas con product_rel O account_id (cualquiera de los dos sirve
                        # para el aprendizaje contable).
                        if partner_id and partner_id not in partner_mappings_cache:
                            historicos = self.env['account.edi.downloaded.xml.sat.products'].search(
                                [
                                    ('downloaded_invoice_id.partner_id', '=', partner_id),
                                    '|',
                                        ('product_rel', '!=', False),
                                        ('account_id', '!=', False),
                                ],
                                order='id desc',
                            )
                            idx = {}
                            for h in historicos:
                                code = h.sat_id.code if h.sat_id else False
                                if not code:
                                    continue
                                idx.setdefault(code, []).append(
                                    (h.description or '', h.product_rel, h.account_id)
                                )
                            partner_mappings_cache[partner_id] = idx

                        # 1) Match con historial del proveedor (orden id desc => mas reciente gana)
                        if partner_id:
                            candidatos = partner_mappings_cache.get(partner_id, {}).get(clave_prod_serv, [])
                            for hist_desc, hist_prod, hist_acc in candidatos:
                                if similar(descripcion, hist_desc) > 0.8:
                                    final_product = hist_prod
                                    final_account = hist_acc
                                    break

                        # 2) Fallback global con umbral estricto (>0.9)
                        if not final_product and not final_account:
                            cross_candidates = self.env['account.edi.downloaded.xml.sat.products'].search(
                                [
                                    ('sat_id.code', '=', clave_prod_serv),
                                    '|',
                                        ('product_rel', '!=', False),
                                        ('account_id', '!=', False),
                                ],
                                order='id desc',
                                limit=20,
                            )
                            for c in cross_candidates:
                                if similar(descripcion, c.description or '') > 0.9:
                                    final_product = c.product_rel
                                    final_account = c.account_id
                                    break

                        product_cache[product_cache_key] = (final_product, final_account)

                    # Búsqueda de código SAT con cache — evita 1 SELECT por concepto
                    if clave_prod_serv not in sat_code_cache:
                        sat_code_cache[clave_prod_serv] = self.env['product.unspsc.code'].search(
                            [('code', '=', clave_prod_serv)], limit=1
                        )
                    sat_code = sat_code_cache[clave_prod_serv]
                    
                    # Create a dictionary for each concepto and append it to the list
                    concepto_info = {
                        'sat_id': sat_code.id if sat_code else False,
                        'quantity': cantidad,
                        'product_metrics': clave_unidad,
                        'description': descripcion,
                        'unit_value': valor_unitario,
                        'total_amount': importe,
                        'downloaded_invoice_id': False,
                        'product_rel': final_product.id if final_product else False,
                        'account_id': final_account.id if final_account else False,
                        'cuenta_predial': cuenta_predial_num,
                        'tax_id': taxes_ids if taxes_ids else False,
                        'ieps_traslado_amount': ieps_traslado_linea,
                        'xml_taxes_breakdown': taxes_breakdown_list,
                        'discount': -float(descuento) if descuento else 0.0,
                    }
                    conceptos_list.append(concepto_info)
                return (conceptos_list, total_impuestos, total_retenciones)

        def fetch_cfdi_data(RFC, startDate, endDate, xml_type, ingreso, egreso, pago, nomina, valido, cancelado, no_encontrado, traslado, completeness_only=False):
            #base_url ='http://127.0.0.1:5000/get-cfdis'
            base_url = 'https://xmlsat.anfepi.com/get-cfdis'
            # Resolver company por VAT del RFC consultado (no por env.company).
            # Antes se usaba env.company → cuando el lote era de una coordinada
            # con RFC distinto al user, se enviaba la api key incorrecta y xmlsat
            # respondía 402. Ahora SIEMPRE usamos la api key de la company cuyo
            # vat coincide con el RFC pedido.
            company = self.env['res.company'].sudo().search([('vat', '=', RFC)], limit=1)
            if not company:
                company = self.env.company
                _logger.warning(
                    f"No se encontro res.company con vat={RFC}, fallback a env.company={company.vat}"
                )
            api_key = company.l10n_mx_xml_download_api_key
            # Delegación: si esta empresa es una coordinada con una controladora
            # registrada en l10n_mx.cfdi.coordinado.relation, usar la API key
            # de la controladora. xmlsat valida la delegación contra su tabla
            # company_delegation y autoriza la consulta del RFC coordinado.
            #
            # Soft dependency: l10n_mx_cfdi_compliance puede no estar instalado
            # (caso single-tenant tipo Cosal). self.env.get() devuelve None en
            # ese caso y saltamos el check sin warning ruidoso en cada descarga.
            CoordRel = self.env.get('l10n_mx.cfdi.coordinado.relation')
            if CoordRel is not None:
                try:
                    # Resolver la relacion por el RFC consultado (coordinada_vat),
                    # NO solo por coordinada_company_id: las coordinadas suelen ser
                    # RFCs de terceros que NO son res.company (ej. Vencedor: APO/EME
                    # son partners, coordinada_company_id es NULL). Buscar por
                    # company.id (= fallback env.company) nunca matcheaba -> se
                    # enviaba la api key del fallback, incorrecta para coordinadas de
                    # otra controladora. Ahora usamos la api key de la controladora
                    # real segun el RFC pedido.
                    rel = CoordRel.sudo().search([
                        '|',
                        ('coordinada_vat', '=', RFC),
                        ('coordinada_company_id', '=', company.id),
                        ('active', '=', True),
                    ], limit=1)
                    if rel and rel.controladora_company_id and rel.controladora_company_id.l10n_mx_xml_download_api_key:
                        api_key = rel.controladora_company_id.l10n_mx_xml_download_api_key
                        _logger.info(
                            f"🔗 Usando API key delegada de controladora "
                            f"{rel.controladora_company_id.vat} para consultar RFC {RFC}"
                        )
                except Exception as e:
                    _logger.warning(f"Error resolviendo delegación de controladora: {e}")
            # El API key YA viene hasheado desde la base de datos, NO hashear nuevamente
            # La base de datos xml_api_downloader almacena el hash SHA-512 directamente

            url = (
                f"{base_url}?RFC={RFC}&startDate={startDate}&endDate={endDate}&xml_type={xml_type}&api_key={api_key}"
                f"&ingreso={'true' if ingreso else 'false'}"
                f"&egreso={'true' if egreso else 'false'}"
                f"&pago={'true' if pago else 'false'}"
                f"&nomina={'true' if nomina else 'false'}"
                f"&traslado={'true' if traslado else 'false'}"
                f"&valido={'true' if valido else 'false'}"
                f"&cancelado={'true' if cancelado else 'false'}"
                f"&no_encontrado={'true' if no_encontrado else 'false'}"
                + (f"&completeness_only=true" if completeness_only else "")
            )
            try:
                _logger.info(f"\n{'='*80}")
                _logger.info(f"PETICIÓN AL SERVIDOR API")
                _logger.info(f"{'='*80}")
                _logger.info(f"URL: {base_url}")
                _logger.info(f"RFC: {RFC}")
                _logger.info(f"Periodo: {startDate} - {endDate}")
                _logger.info(f"Tipo: {xml_type}")
                _logger.info(f"API Key (hash): {api_key[:40] if api_key else 'NO CONFIGURADO'}...")
                _logger.info(f"Timeout: 120 segundos")
                _logger.info(f"{'='*80}\n")
                
                with requests.get(url, verify=False, timeout=120, stream=True) as response:
                    _logger.info(f"✅ Respuesta recibida: {response.status_code}")

                    if response.status_code == 200:
                        try:
                            data = response.json()
                        except (ValueError, json.JSONDecodeError) as je:
                            # La API xmlsat a veces devuelve JSON truncado cuando el
                            # payload es muy grande (varios MB). El caller debe
                            # subdividir el rango y reintentar.
                            _logger.error(
                                f"❌ JSON truncado/corrupto al parsear respuesta de xmlsat "
                                f"para RFC={RFC} {startDate}..{endDate}: {str(je)[:200]}"
                            )
                            return 'TRUNCATED'
                        xml_count = len(data.get('xmls', []))
                        _logger.info(f"✅ XMLs encontrados: {xml_count}")
                        return data
                    else:
                        # Handle other status codes if needed
                        _logger.error(f"❌ Request failed with status code: {response.status_code}")
                        _logger.error(f"Response: {response.text[:200]}")
                        return None
            except requests.exceptions.Timeout:
                print(f"❌ TIMEOUT: El servidor no respondió en 120 segundos")
                print(f"Verificar conectividad con: curl {base_url}")
                return None
            except requests.exceptions.ConnectionError as e:
                print(f"❌ CONNECTION ERROR: {str(e)[:200]}")
                return None
            except requests.exceptions.RequestException as e:
                print(f"❌ Error during request: {str(e)[:200]}")
                return None     
            
        # Create Batch Name
        start_date_str = self.date_start.strftime('%d-%b-%Y')
        end_date_str = self.date_end.strftime('%d-%b-%Y')
        self.write({'name': f"{self.cfdi_type} ({start_date_str} - {end_date_str})"})

        create_contact = self.env.company.l10n_mx_xml_download_automatic_contact_creation

        def _next_month_start(d):
            """Devuelve el primer día del mes siguiente al de la fecha dada."""
            if d.month == 12:
                return date(d.year + 1, 1, 1)
            return date(d.year, d.month + 1, 1)

        # FIX coordinadas: si el lote tiene `vat` asignado (caso de lotes hijo
        # creados desde una controladora con download_coordinadas=True), usar
        # ese RFC para la consulta a la API SAT. Si el lote no trae vat (caso
        # normal de la controladora), caer al VAT por defecto (env.company.vat).
        rfc = self.vat or self._get_default_vat()
        processed_count = 0
        skipped_count = 0
        total_xmls = 0

        # Pre-cargar todos los UUIDs ya existentes en este lote via SQL directo.
        # NO usar self.xml_sat_ids.mapped('name'): para lotes con mas de ~5500
        # records el ORM falla silenciosamente y carga solo un subset (bug
        # observado en Cosal: lote emitidos mar tenia 7602 UUIDs unicos pero
        # mapped() solo retornaba 5584, causando 2018 duplicados por ciclo).
        # SQL directo carga todos sin importar el volumen.
        self.env.cr.execute("""
            SELECT name FROM account_edi_downloaded_xml_sat
             WHERE batch_id = %s
               AND name IS NOT NULL
               AND name != ''
        """, (self.id,))
        existing_uuids = {row[0] for row in self.env.cr.fetchall()}
        _logger.info(f"UUIDs ya existentes en el lote: {len(existing_uuids)}")

        chunk_start = self.date_start
        failed_chunks = []  # chunks que fallaron todos los reintentos

        def _fetch_chunk_autosplit(c_start, c_end, depth=0):
            """Llama a `fetch_cfdi_data` para el rango [c_start, c_end].
            - Si la respuesta es 'TRUNCATED' (JSON corrupto por payload grande),
              divide el rango en dos mitades y combina los xmls obtenidos.
            - Si el rango ya es de 1 día y sigue truncando, lo da por perdido.
            - Hasta MAX_DEPTH niveles (≈2^7 = 128 sub-chunks; suficiente para
              partir un mes hasta días individuales).
            Devuelve dict {'xmls': [...]}  o None si falló irrecuperablemente.
            """
            MAX_DEPTH = 7
            response = None
            # Reintentos para errores transitorios (timeout / red). Si la
            # respuesta es TRUNCATED no reintentamos el mismo rango: vamos
            # directo a subdividir.
            for intento in range(1, 4):
                response = fetch_cfdi_data(
                    # FIX: el RFC de la consulta al SAT debe ser SIEMPRE el del lote.
                    # El loop de procesamiento reasigna `rfc` = customer/supplier_rfc
                    # del CFDI (p.ej. XAXX010101000 publico general) -> los chunks
                    # siguientes consultaban ese RFC ajeno con la api_key del lote -> 402.
                    (self.vat or self._get_default_vat()), c_start, c_end,
                    self.cfdi_type, self.ingreso, self.egreso, self.pago,
                    self.nomina, self.valido, self.cancelado, self.no_encontrado, self.traslado
                )
                if response is not None and response != 'TRUNCATED':
                    return response
                if response == 'TRUNCATED':
                    break
                if intento < 3:
                    _logger.warning(
                        f"Sub-chunk {c_start} - {c_end} (depth {depth}): intento {intento} "
                        f"fallido, reintentando en 5s..."
                    )
                    time.sleep(5)

            if response == 'TRUNCATED' and (c_end - c_start).days >= 1 and depth < MAX_DEPTH:
                mid = c_start + (c_end - c_start) // 2
                _logger.warning(
                    f"🔪 Auto-split por JSON truncado en [{c_start}..{c_end}]: "
                    f"dividiendo en [{c_start}..{mid}] y [{mid + timedelta(days=1)}..{c_end}]"
                )
                left = _fetch_chunk_autosplit(c_start, mid, depth + 1)
                right = _fetch_chunk_autosplit(mid + timedelta(days=1), c_end, depth + 1)
                if left is None and right is None:
                    return None
                combined = {'xmls': []}
                if left:
                    combined['xmls'].extend(left.get('xmls', []))
                if right:
                    combined['xmls'].extend(right.get('xmls', []))
                return combined

            return None

        while chunk_start <= self.date_end:
            chunk_end = min(_next_month_start(chunk_start) - timedelta(days=1), self.date_end)
            pending_attachments = []  # se llena durante el loop y se crea en batch al final del chunk
            pending_products = []  # OLA 1 perf: productos del chunk acumulados para batch create

            _logger.info(f"Descargando chunk: {chunk_start} - {chunk_end}")
            response = _fetch_chunk_autosplit(chunk_start, chunk_end)
            if response is None:
                _logger.error(
                    f"Chunk {chunk_start} - {chunk_end}: fallido (auto-split agotado o error de red), se omite"
                )
                failed_chunks.append((chunk_start, chunk_end))

            chunk_start = _next_month_start(chunk_end)

            if not response:
                continue

            xmls_list = response.get("xmls", [])
            chunk_xml_count = len(xmls_list)
            total_xmls += chunk_xml_count
            _logger.info(f"Procesando {chunk_xml_count} XMLs del chunk (total acumulado: {total_xmls})")

            for idx, xml in enumerate(xmls_list, 1):
                try:
                    cfdi_node = fromstring(xml["xmlFile"])
                except etree.XMLSyntaxError:
                    # CFDIs MAL FORMADOS (p.ej. `xmlns:schemaLocation` invalido que generan
                    # ciertos PACs) los rechaza el parser estricto -> antes se OMITIAN y el
                    # lote quedaba incompleto (En Odoo < CFDIs en SAT). Reintentar con parser
                    # TOLERANTE (recover) que igual extrae TipoDeComprobante/UUID/impuestos.
                    try:
                        _xf = xml["xmlFile"]
                        _xs = _xf if isinstance(_xf, str) else _xf.decode("utf-8", "replace")
                        # error comun de ciertos PACs: `xmlns:schemaLocation` (declara un
                        # namespace con URI invalida) en vez de `xsi:schemaLocation`.
                        _xs = _xs.replace("xmlns:schemaLocation", "xsi:schemaLocation")
                        cfdi_node = fromstring(_xs.encode("utf-8"))
                    except Exception:
                        skipped_count += 1
                        _logger.warning(f"XML {idx}/{total_xmls} - Error de sintaxis irrecuperable, se omite")
                        continue

                cfdi_infos = self.env['account.move']._l10n_mx_edi_decode_cfdi_etree(cfdi_node)
                # Reusar el mismo árbol lxml en lugar de parsear de nuevo con stdlib ET
                root = cfdi_node

                # Filtrar por tipo de documento según la configuración del lote
                tipo_comprobante = root.get('TipoDeComprobante')
                type_allowed = {
                    'I': self.ingreso,
                    'E': self.egreso,
                    'P': self.pago,
                    'N': self.nomina,
                    'T': self.traslado,
                }
                if tipo_comprobante in type_allowed and not type_allowed[tipo_comprobante]:
                    skipped_count += 1
                    _logger.info(f"XML {idx}/{total_xmls} - Tipo '{tipo_comprobante}' no seleccionado en el lote, se omite")
                    continue

                # Verificar que no se duplique el UUID — usando el set pre-cargado (0 SELECTs)
                uuid_val = cfdi_infos.get('uuid')
                if not uuid_val:
                    skipped_count += 1
                    _logger.warning(f"XML {idx}/{total_xmls} - sin UUID extraible, se omite (no se crea con name nulo)")
                    continue
                if uuid_val in existing_uuids:
                    skipped_count += 1
                    if idx % 10 == 0:
                        _logger.info(f"Progreso: {idx}/{total_xmls} XMLs procesados ({skipped_count} omitidos)")
                    continue
                
                # Log progreso cada 10 XMLs
                if idx % 10 == 0:
                    _logger.info(f"Progreso: {idx}/{total_xmls} XMLs procesados ({processed_count} creados, {skipped_count} omitidos)")
              
                """ 'uuid', 'supplier_rfc', 'customer_rfc', 'amount_total', 'cfdi_node', 'usage', 'payment_method'
                'bank_account', 'sello', 'sello_sat', 'cadena', 'certificate_number', 'certificate_sat_number'
                'expedition', 'fiscal_regime', 'emission_date_str', 'stamp_date' """
                
                tax_regime = ""
                rfc = ""
                name = ""
                zip = ""
                # Buscar el partner — con caché por RFC (evita 1 SELECT repetido por proveedor)
                if self.cfdi_type == 'emitidos':
                    rfc = cfdi_infos.get('customer_rfc')
                    cfdi_ns = _get_cfdi_ns(root)
                    receptor_element = root.find('.//cfdi:Receptor', namespaces=cfdi_ns)
                    # CFDI 4.0: el atributo del Receptor se llama 'RegimenFiscalReceptor'
                    # (no 'RegimenFiscal' como en el Emisor). Bug historico: leiamos
                    # 'RegimenFiscal' que no existe en Receptor y siempre devolvia None.
                    tax_regime = receptor_element.get("RegimenFiscalReceptor") if receptor_element is not None else None
                    name = receptor_element.get("Nombre") if receptor_element is not None else None
                    zip = receptor_element.get("DomicilioFiscalReceptor") if receptor_element is not None else None
                    if rfc not in partner_cache:
                        partner_cache[rfc] = self.env['res.partner'].search([('vat', '=', rfc)], limit=1)
                    partner = partner_cache[rfc]

                else:
                    rfc = cfdi_infos.get('supplier_rfc')
                    cfdi_ns = _get_cfdi_ns(root)
                    emisor_element = root.find('.//cfdi:Emisor', namespaces=cfdi_ns)
                    tax_regime = emisor_element.get("RegimenFiscal") if emisor_element is not None else None
                    name = emisor_element.get("Nombre") if emisor_element is not None else None
                    # LugarExpedicion es el CP fiscal del emisor (proveedor), disponible en CFDI 3.3 y 4.0
                    zip = cfdi_infos.get('expedition') or root.get('LugarExpedicion')
                    if rfc not in partner_cache:
                        partner_cache[rfc] = self.env['res.partner'].search([('vat', '=', rfc)], limit=1)
                    partner = partner_cache[rfc]

                # Si no hay partner y en ajustes esta configurado para crear contacto, lo va a crear
                # OLA 1 perf: deshabilitar mail_thread (followers, mensajes, tracking) en la creacion
                # masiva — eliminamos cascada de INSERTs a mail_followers* que era el cuello identificado
                # en la sesion del lote ene-2026 (PID idle in transaction durante 60s+).
                if not partner and create_contact:
                    contact_name = name or rfc  # usar RFC como nombre de respaldo si el XML no trae Nombre
                    if contact_name:
                        partner = self.env['res.partner'].with_context(
                            tracking_disable=True,
                            mail_create_nolog=True,
                            mail_create_nosubscribe=True,
                            mail_notrack=True,
                        ).create({
                            'vat': rfc,
                            'name': contact_name,
                            'country_id': 156,  # ID de México
                            'l10n_mx_edi_fiscal_regime': tax_regime,
                            'zip': zip
                        })
                        partner_cache[rfc] = partner  # guardar en caché para no recrear

                factura = None
                # TODO: Reactivar cuando stored_sat_uuid tenga store=True
                # factura = self.env['account.move'].search([('stored_sat_uuid','=',cfdi_infos.get('uuid'))], limit=1)
                
                # Determinar la empresa correcta según el RFC del XML (con cache)
                correct_company_id = self.company_id.id
                
                if self.cfdi_type == 'emitidos':
                    # En emitidos, usar el RFC del emisor
                    emisor_rfc = cfdi_infos.get('supplier_rfc')
                    if emisor_rfc:
                        if emisor_rfc not in company_cache:
                            company_cache[emisor_rfc] = self.env['res.company'].search([('vat', '=', emisor_rfc)], limit=1)
                        if company_cache[emisor_rfc]:
                            correct_company_id = company_cache[emisor_rfc].id
                else:
                    # En recibidos, usar el RFC del receptor
                    receptor_rfc = cfdi_infos.get('customer_rfc')
                    if receptor_rfc:
                        if receptor_rfc not in company_cache:
                            company_cache[receptor_rfc] = self.env['res.company'].search([('vat', '=', receptor_rfc)], limit=1)
                        if company_cache[receptor_rfc]:
                            correct_company_id = company_cache[receptor_rfc].id
                
                valid_usage_keys = {k for k, _ in USO_CFDI}
                raw_usage = cfdi_infos.get('usage')

                # Fecha de timbrado (PAC) y desglose de impuestos por tipo+tasa.
                # Se extraen del mismo XML root ya parseado, sin re-leer del attachment.
                try:
                    fecha_timbrado_val = self._parse_fecha_timbrado(root)
                except Exception as e:
                    _logger.warning("UUID %s: no se pudo extraer FechaTimbrado: %s", uuid_val, e)
                    fecha_timbrado_val = False
                try:
                    # root puede ser objectify (fromstring de lxml.objectify) cuyo
                    # find() con namespaces= se comporta distinto. Convertimos a
                    # etree puro para que _parse_tax_breakdown funcione siempre.
                    etree_root = etree.fromstring(etree.tostring(root))
                    tax_breakdown_vals = self._parse_tax_breakdown(etree_root, _get_cfdi_ns(etree_root))
                except Exception as e:
                    _logger.warning("UUID %s: no se pudo desglosar impuestos: %s", uuid_val, e)
                    tax_breakdown_vals = {}

                vals = {
                    'name': uuid_val,
                    'cfdi_type': self.cfdi_type,
                    'company_id': correct_company_id,
                    'invoice_id': factura.id if factura else None,
                    'partner_id': partner.id if partner else False,
                    'document_date': root.attrib.get('Fecha'),
                    'fecha_timbrado': fecha_timbrado_val,
                    'state': factura.state if factura else 'not_imported',
                    'document_type': root.get('TipoDeComprobante'),
                    'payment_method': cfdi_infos.get('payment_method'),
                    # Tipo P: FormaPago raíz está vacía; la real está en pago20:Pago/@FormaDePagoP
                    'payment_method_sat': (
                        (lambda _root: (
                            # Path 1: XPath con namespace Pagos20 explicito.
                            (lambda _n: _n.get('FormaDePagoP') if _n is not None else None)(
                                _root.find('.//{http://www.sat.gob.mx/Pagos20}Pago')
                            )
                            # Path 2: fallback por string search (XMLs con prefijo
                            # de namespace raro o pre-procesados antes del fix de
                            # extraccion). Acepta solo codigos SAT de 2 chars.
                            or (lambda _s: (
                                _s[_s.find('FormaDePagoP="') + 14:_s.find('"', _s.find('FormaDePagoP="') + 14)]
                                if 'FormaDePagoP="' in _s
                                and 0 < (_s.find('"', _s.find('FormaDePagoP="') + 14) - _s.find('FormaDePagoP="') - 14) <= 4
                                else None
                            ))(etree.tostring(_root, encoding='unicode'))
                            # Path 3: atributo raiz (legacy / fallback final).
                            or _root.get('FormaPago')
                        ))(root)
                        if root.get('TipoDeComprobante') == 'P'
                        else root.get('FormaPago')
                    ),
                    'sub_total': root.get('SubTotal') if root.get('SubTotal') else '0.0',
                    'amount_total': cfdi_infos.get('amount_total') if cfdi_infos.get('amount_total') else '0.0',
                    'serie':root.get('Serie'),
                    'folio':root.get('Folio'),
                    # Para CFDI tipo P (Pago) la Moneda raiz suele ser "XXX" (sin moneda)
                    # porque el comprobante es un acuse. La moneda real del pago vive
                    # en pago20:Pago/@MonedaP dentro del complemento.
                    'divisa': (
                        (lambda _root: (
                            (_root.find('.//{http://www.sat.gob.mx/Pagos20}Pago') is not None
                             and _root.find('.//{http://www.sat.gob.mx/Pagos20}Pago').get('MonedaP'))
                            or _root.get('Moneda')
                        ))(root)
                        if root.get('TipoDeComprobante') == 'P'
                        else root.get('Moneda')
                    ),
                    'sat_state':xml['state'],
                    'cfdi_usage': raw_usage if raw_usage in valid_usage_keys else False,
                    'tax_regime': tax_regime,
                    'batch_id':self.id,
                    'discount': -float(root.get("Descuento")) if root.get("Descuento") else None,
                    'sello_cfdi': cfdi_infos.get('sello'),
                    'sello_sat': cfdi_infos.get('sello_sat'),
                    'certificate_number': cfdi_infos.get('certificate_number'),
                    'certificate_sat_number': cfdi_infos.get('certificate_sat_number'),
                    'cadena_original': cfdi_infos.get('cadena_original'),
                }
                # Desglose por tipo+tasa (9 campos): tax_iva_16_traslado, tax_iva_ret, etc.
                vals.update(tax_breakdown_vals)

                if root.get('TipoDeComprobante') == 'P':
                    monto_total_pagos_element = root.find('.//pago20:Totales', {'pago20': 'http://www.sat.gob.mx/Pagos20'})

                    monto_total_pagos = monto_total_pagos_element.get('MontoTotalPagos') if monto_total_pagos_element is not None else ''

                    vals['amount_total'] = monto_total_pagos if monto_total_pagos else ''
                    vals['sub_total'] = monto_total_pagos if monto_total_pagos else ''


                # Creamos los productos del xml
                # recived: boolean to search type of tax
                products = False
                try:
                    products, total_impuestos, total_retenciones = get_products(
                        cfdi_node,
                        partner_id=partner.id if partner else False,
                    )  # reusar el arbol ya parseado
                    vals['total_impuestos'] = total_impuestos
                    vals['total_retenciones'] = total_retenciones
                except:
                    pass
                
                # SIEMPRE crear el registro del XML, tenga o no productos
                # (los XMLs de pago tipo P no tienen productos)
                # OLA 1 perf: tracking_disable evita mail_followers* en cada XML creado
                record = self.env['account.edi.downloaded.xml.sat'].with_context(
                    tracking_disable=True,
                    mail_create_nolog=True,
                    mail_create_nosubscribe=True,
                    mail_notrack=True,
                ).create(vals)
                # Registrar UUID en el set local para evitar duplicados en el mismo lote
                existing_uuids.add(uuid_val)

                if products:
                    if root.get('TipoDeComprobante') == 'P':
                        for product in products:
                            product['total_amount'] = float(monto_total_pagos or 0)

                    # OLA 1 perf: acumular productos del chunk para crear todos en una sola
                    # llamada al final del chunk (downloaded_product_id es One2many y se auto-popula
                    # via downloaded_invoice_id, por lo que NO se requiere el write posterior).
                    for product in products:
                        product['downloaded_invoice_id'] = record.id
                    pending_products.extend(products)

                # Crear el attachment del XML — se acumula en la lista para crear en batch al final del chunk
                pending_attachments.append({
                    'name': xml["uuid"] + ".xml",
                    'datas': base64.b64encode(xml["xmlFile"].encode('utf-8')),
                    'res_model': 'account.edi.downloaded.xml.sat',
                    'res_id': record.id,
                    'type': 'binary',
                    'mimetype': 'application/xml',
                    '_record': record,  # referencia temporal para asignar attachment_id
                })
                processed_count += 1

            # OLA 1 perf: crear TODOS los productos del chunk en una sola llamada
            # (en vez de N llamadas individuales). One2many se auto-popula via FK.
            if pending_products:
                self.env['account.edi.downloaded.xml.sat.products'].with_context(
                    tracking_disable=True,
                    mail_create_nolog=True,
                    mail_create_nosubscribe=True,
                    mail_notrack=True,
                ).create(pending_products)
                pending_products.clear()

            # Crear todos los attachments del chunk — con no_document=True para evitar
            # que el módulo Enterprise Documents procese cada XML como documento,
            # lo que causa 'cursor already closed' bajo carga alta.
            # OLA 1 perf: usar batch create([vals,...]) en vez de N create() individuales.
            if pending_attachments:
                records_for_atts = [a.pop('_record') for a in pending_attachments]
                # OLA 1.5 perf CRITICA: _skip_cfdi_compliance evita que el override
                # de ir.attachment.create en l10n_mx_cfdi_compliance dispare el pipeline
                # de reglas + creacion de l10n_mx.cfdi.document por CADA XML del chunk
                # (no aplica para XMLs descargados masivamente del SAT — no tienen
                # related_move/related_purchase y serian compliance huerfanos).
                att_env = self.env['ir.attachment'].with_context(
                    no_document=True,
                    tracking_disable=True,
                    mail_create_nolog=True,
                    mail_create_nosubscribe=True,
                    mail_notrack=True,
                    _skip_cfdi_compliance=True,
                )
                attachments = att_env.create(pending_attachments)
                # NOTA: en este scope la variable local `zip` fue redefinida como string
                # (codigo postal del receptor), por eso NO podemos usar zip() del builtin.
                for i, rec in enumerate(records_for_atts):
                    rec.attachment_id = attachments[i].id
                pending_attachments.clear()
                    
            # Auto-vincular: buscar factura/pago para los XMLs recién creados
            # (sin esperar click manual de "Buscar Factura Relacionada")
            #
            # .86 FIX CRITICO (lotes atascados / "no avanza"): action_search_related_invoice
            # hace cr.commit() interno cada 200 registros. Un commit DENTRO de un
            # `with cr.savepoint()` DESTRUYE el savepoint -> al salir del `with`,
            # el RELEASE SAVEPOINT falla ("savepoint does not exist") y ese error
            # ABORTA la transaccion (InFailedSqlTransaction). El pipeline entonces
            # truena en la siguiente lectura (`while ... self.date_end`) ANTES de
            # escribir state='imported', dejando el lote pegado en 'processing' por
            # siempre (last_update congelado). Por eso NO debe ir en savepoint.
            # El metodo ya commitea su propio progreso; lo aislamos con try/except
            # + rollback: si falla, los XMLs ya quedaron commiteados y el lote
            # continua y cierra normalmente (solo se pierde el linking parcial).
            # FIX: persistir los XMLs creados ANTES del auto-link. Si el linking
            # falla en el PRIMER registro (antes de su commit interno cada 200), el
            # except de abajo hace cr.rollback() que borraria los XMLs aun no
            # commiteados (causa raiz de "emitidos = 0" cuando el lote trae N/T).
            self.env.cr.commit()
            try:
                new_xmls = self.env['account.edi.downloaded.xml.sat'].search([
                    ('batch_id', '=', self.id),
                    ('invoice_id', '=', False),
                    ('payment_id', '=', False),
                    ('id', '>', 0),
                ], order='id desc', limit=processed_count)
                if new_xmls:
                    new_xmls.action_search_related_invoice()
            except Exception as e:
                _logger.warning("Auto-vinculacion parcial en lote id=%s: %s" % (self.id, e))
                # Recuperar la transaccion para poder cerrar el lote pase lo que pase.
                try:
                    self.env.cr.rollback()
                except Exception:
                    pass

            # Liberar la memoria del chunk antes de pedir el siguiente:
            # ademas de borrar variables Python, invalidar el cache del ORM
            # (que retiene los registros creados/leidos en este chunk) y forzar
            # garbage collect. Sin esto, lotes con >20K XMLs por chunk pueden
            # acumular 2-3GB de cache y matar al worker por memory limit
            # (signal 9 en odoo.sh, ~3GB hard limit).
            del xmls_list
            del response
            self.env.invalidate_all()
            import gc
            gc.collect()

        if failed_chunks:
            _logger.warning(f"Lote {self.name}: {len(failed_chunks)} chunk(s) fallaron tras 3 intentos: {failed_chunks}")
        _logger.info(f"Lote {self.name} completado: {processed_count} XMLs creados, {skipped_count} omitidos de {total_xmls} totales")

        # sync_stable=True requiere tres condiciones simultáneas:
        # 1. No se encontraron XMLs nuevos en este ciclo (processed_count == 0)
        # 2. No hubo chunks que fallaran los 3 reintentos
        # 3. Han pasado más de 72 horas desde date_end del lote:
        #    SAT puede entregar CFDIs de los últimos días del periodo hasta 72h después
        #    de que cierre el mes. Antes de ese plazo siempre podría haber más por llegar.
        # v.73: fix doble bug en calculo. Antes interpretaba date_end
        # como 00:00:00 (inicio) y mezclaba naive con UTC (desfase 6h).
        # Marcaba sync_stable ~30h antes de tiempo.
        _mx_tz = pytz.timezone('America/Mexico_City')
        end_local_naive = datetime.combine(self.date_end, dtime(23, 59, 59))
        end_utc = _mx_tz.localize(end_local_naive).astimezone(pytz.utc).replace(tzinfo=None)
        hours_since_end = (datetime.utcnow() - end_utc).total_seconds() / 3600
        window_clear = hours_since_end > 72
        is_stable = processed_count == 0 and not failed_chunks and window_clear
        if not window_clear:
            _logger.info(
                f"Lote {self.name}: no se marca estable aún — solo han pasado "
                f"{hours_since_end:.1f}h desde date_end (mínimo 72h requeridas)"
            )
        # last_update_date se actualiza en CADA pipeline exitoso (importación inicial o re-sync)
        # para que el usuario vea siempre la fecha de la última sincronización con el SAT.
        write_vals = {
            'state': 'imported',
            'sync_stable': is_stable,
            'last_update_date': fields.Date.today(),
        }
        # SAT completeness end-to-end (xmlsat 2026-05): pedir solo bloque metadata
        # sin XMLs (barato). Si xmlsat es viejo o falla, no rompemos flujo.
        try:
            # .96 FIX: usar el RFC del LOTE (self.vat), NO la variable `rfc` que el
            # loop de parseo sobrescribe con el supplier/customer del ULTIMO XML
            # -> esa llamada de completeness mandaba un RFC ajeno y daba 402.
            comp_response = fetch_cfdi_data(
                self.vat or self._get_default_vat(), self.date_start, self.date_end,
                self.cfdi_type, self.ingreso, self.egreso, self.pago,
                self.nomina, self.valido, self.cancelado, self.no_encontrado, self.traslado,
                completeness_only=True,
            )
            if comp_response and isinstance(comp_response, dict):
                comp = comp_response.get('completeness') or {}
                if comp:
                    # Completitud POR UUID (no por tipo): de los vigentes que el SAT lista para este
                    # periodo (metadata sat_metadata_ref por fecha documento), cuantos tiene Odoo por
                    # UUID sin importar cfdi_type (asi no penaliza traslados $0 clasificados como otro
                    # tipo). Fallback al conteo del lote si no hay metadata local para esta empresa.
                    _expected_sat = 0; _odoo_have = 0; _canc = 0; _no_lib = 0; _metasrc = False
                    try:
                        with self.env.cr.savepoint():
                            # .87: el filtro por RFC SOLO aplica si sat_metadata_ref
                            # tiene esa columna. En single-tenant (p.ej. Cosal) la
                            # tabla NO tiene `rfc` y el filtro `mt.rfc=%s` tronaba ->
                            # caia al fallback (conteo crudo, numeros confusos en la
                            # UI). Detectamos la columna y armamos el WHERE acorde.
                            self.env.cr.execute(
                                "SELECT 1 FROM information_schema.columns "
                                "WHERE table_name='sat_metadata_ref' AND column_name='rfc'")
                            _has_rfc = bool(self.env.cr.fetchone())
                            _rfc_clause = "mt.rfc = %s AND " if _has_rfc else ""
                            _params = []
                            if _has_rfc:
                                _params.append(self.vat)
                            _params += [self.cfdi_type, self.date_start, self.date_end]
                            # .87: el CORTE de periodo lo define la metadata SAT por
                            # FECHA DOCUMENTO (mt.fecha). El match Odoo es POR UUID
                            # GLOBAL (no por lote) -> ambos lados quedan sobre la misma
                            # base (fecha documento), NO fecha-documento vs fecha-timbrado.
                            # Si se restringe por batch_id, el lote (bajado por timbrado)
                            # mete/saca UUIDs de otra fecha y descuadra. Por UUID global
                            # es la metrica que ya probo cuadrar (emitidos 0 faltan).
                            # .88: "CFDIs en SAT" = TODO lo que el SAT lista para el
                            # periodo (todos los estados que el SAT entrega: emitidos
                            # solo vigentes -el SAT NO da cancelados de emitidos-,
                            # recibidos vigentes+cancelados). "En Odoo" = de esos,
                            # cuantos tiene Odoo (match por UUID). Completo = los tiene
                            # TODOS. Corte de periodo por fecha documento (mt.fecha).
                            self.env.cr.execute(
                                "SELECT COUNT(*), "
                                "COUNT(*) FILTER (WHERE mt.estatus IN ('1','Vigente') AND o.uuid IS NULL), "
                                "COUNT(*) FILTER (WHERE mt.estatus NOT IN ('1','Vigente')) "
                                "FROM sat_metadata_ref mt "
                                "LEFT JOIN (SELECT DISTINCT lower(name) AS uuid FROM account_edi_downloaded_xml_sat "
                                "WHERE name IS NOT NULL AND name <> '') o ON o.uuid = mt.uuid "
                                "WHERE " + _rfc_clause + "mt.type = %s AND mt.fecha BETWEEN %s AND %s",
                                tuple(_params))
                            _r = self.env.cr.fetchone()
                        if _r and _r[0]:
                            # _expected = TODO lo que el SAT lista (vig+canc). _missing_vig =
                            # vigentes que el SAT lista y Odoo NO tiene (lo unico recuperable).
                            # Los CANCELADOS no son descargables ("No se permite la descarga de
                            # xml que se encuentren cancelados" -respuesta literal del SAT-) ->
                            # se cuentan como cubiertos. En Odoo = todo - vigentes faltantes.
                            _expected_sat = int(_r[0] or 0); _missing_vig = int(_r[1] or 0); _canc = int(_r[2] or 0)
                            _odoo_have = _expected_sat - _missing_vig; _no_lib = 0; _metasrc = True
                    except Exception:
                        _metasrc = False
                    # .97: senal de verificacion por ventanas (xmlsat). expected_from_sat
                    # SOLO es el TOTAL REAL del SAT cuando TODAS las ventanas estan
                    # verificadas; parcial reporta un acumulado incompleto (a veces
                    # MENOR que lo descargado -> imposible "CFDIs en SAT < En Odoo").
                    # No creer ese numero ni marcar "Completo" hasta verified==total.
                    _vw = int(comp.get('verified_windows') or 0)
                    _tw = int(comp.get('total_windows') or 0)
                    _windows_done = _tw > 0 and _vw >= _tw
                    if not _metasrc:
                        # Sin metadata local (sat_metadata_ref vacia para este RFC/periodo):
                        # el unico "expected" es la agregacion por ventanas de xmlsat.
                        self.env.cr.execute(
                            "SELECT COUNT(DISTINCT name) FROM account_edi_downloaded_xml_sat "
                            "WHERE batch_id = %s AND name IS NOT NULL AND name != ''", (self.id,))
                        _odoo_have = self.env.cr.fetchone()[0] or 0
                        _raw_expected = int(comp['expected_from_sat']) if comp.get('expected_from_sat') is not None else 0
                        # El agregado por ventanas de xmlsat SOLO es el total real del
                        # SAT cuando TODAS las ventanas estan verificadas (y nunca menos
                        # que lo descargado). Parcial -> 0 = "aun no se sabe" (la UI
                        # muestra "Verificando..."), para no fingir un total no comparable.
                        _expected_sat = max(_raw_expected, _odoo_have) if _windows_done else 0
                    # .87: faltan = vigentes SAT - vigentes que Odoo tiene (por UUID).
                    _truly_missing = _expected_sat - _odoo_have
                    _have_all = bool(_expected_sat) and _truly_missing <= 0
                    # .86/.97: "Completo vs SAT" exige periodo cerrado (window_clear).
                    # En la via-ventanas (sin metadata local) exige ADEMAS que TODAS
                    # las ventanas esten verificadas (verified==total): marcarlo con
                    # 2/2486 ventanas era prematuro y hacia que el cron saltara el lote
                    # y nunca terminara. La via-metadata (sat_metadata_ref) es
                    # autoritativa por UUID y NO necesita el cierre de ventanas.
                    _is_complete = _have_all and window_clear and (_metasrc or _windows_done)
                    if not _metasrc and not _windows_done and _tw:
                        # verificacion por ventanas en curso: el total real del SAT aun
                        # no se conoce -> mostrar avance, NO un parcial no comparable.
                        _msg = 'Verificando vs SAT: %d%% (%d/%d ventanas)' % (100 * _vw // _tw, _vw, _tw)
                    elif _expected_sat:
                        if _is_complete:
                            _msg = 'Completo vs SAT: %d/%d' % (_odoo_have, _expected_sat)
                        elif _have_all and not window_clear:
                            _msg = 'Al dia vs SAT: %d/%d (en periodo, puede llegar mas)' % (_odoo_have, _expected_sat)
                        else:
                            _msg = 'Faltan %d vigentes vs SAT (%d/%d)' % (_truly_missing, _odoo_have, _expected_sat)
                        if _canc:
                            _msg += ' (incl %d canc no descargables x SAT)' % _canc
                    else:
                        _msg = comp.get('message') or ''
                    write_vals.update({
                        'sat_verified_complete': _is_complete,
                        'sat_expected_count': _expected_sat,
                        'sat_downloaded_count': _odoo_have,
                        'sat_verified_windows': int(comp.get('verified_windows') or 0),
                        'sat_total_windows': int(comp.get('total_windows') or 0),
                        'sat_completeness_message': _msg[:255],
                        'sat_last_verified_at': fields.Datetime.now(),
                    })
        except Exception as comp_err:
            _logger.warning(
                f"Lote {self.name}: no se pudo obtener completeness SAT: {comp_err}"
            )
        # v.74: REMOVIDO fallback peligroso que auto-marcaba verified_complete
        # con el conteo local cuando xmlsat no respondia. Era un atajo basado
        # en la premisa "si sync_stable=true, el conteo local es la verdad",
        # pero esa premisa fallaba en dos casos reales:
        #
        #   1. sync_stable=true se marcaba prematuramente (bug timezone .73)
        #      - sin haber transcurrido las 72h reales de la ventana SAT
        #      - el conteo local en ese momento estaba incompleto (faltaban
        #        XMLs rezagados que SAT publica durante esa ventana)
        #
        #   2. xmlsat reportaba un expected_count distinto al local pero el
        #      fallback ignoraba a xmlsat y forzaba expected = downloaded,
        #      haciendo que la UI mostrara "Verificado SAT" verde con un
        #      conteo que era inferior a la realidad fiscal del SAT.
        #
        # Sintoma reportado en Cosal 2026-06-02: meses Ene-Abr aparecian
        # con check verde "Verificado SAT" y cifras Total=CFDIs SAT=descargados
        # IDENTICAS (3 veces el mismo numero), pero xmlsat tenia ~400 XMLs mas
        # por mes. El fallback los auto-aprobaba con los datos incompletos.
        #
        # Comportamiento nuevo: si xmlsat no confirma verified_complete=True,
        # el lote queda sat_verified_complete=False hasta que xmlsat responda.
        # Mejor mostrar "no verificado" honesto que un "verificado" falso.
        self.write(write_vals)

    def action_update(self):
        """Encolar lote para re-sincronización por el cron (no bloqueante)."""
        self.write({
            'state': 'queued',
            'queued_at': fields.Datetime.now(),
            'last_error': False,
        })
        self.env.cr.commit()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Lote encolado para actualizar',
                'message': 'El cron volverá a sincronizar este lote en los próximos minutos.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.model
    def _ensure_sat_metadata_ref_table(self):
        """Crea sat_metadata_ref si no existe (idempotente). Es la tabla espejo de
        la metadata del SAT (lo que el SAT LISTA por periodo) que alimenta el
        contador "CFDIs en SAT". Ningun otro punto del modulo la creaba -> en las
        instalaciones donde no se creo a mano, el cron (INSERT) y la verificacion
        (SELECT) fallaban. Se crea multi-RFC (con columna rfc); donde ya existe sin
        rfc (single-tenant) el IF NOT EXISTS la respeta y el resto es rfc-aware."""
        self.env.cr.execute(
            "CREATE TABLE IF NOT EXISTS sat_metadata_ref ("
            " id serial PRIMARY KEY,"
            " rfc varchar,"
            " uuid varchar,"
            " type varchar,"
            " fecha date,"
            " estatus varchar)")
        self.env.cr.execute(
            "CREATE INDEX IF NOT EXISTS sat_metadata_ref_lookup_idx "
            "ON sat_metadata_ref (rfc, type, fecha)")
        self.env.cr.execute(
            "CREATE INDEX IF NOT EXISTS sat_metadata_ref_uuid_idx "
            "ON sat_metadata_ref (uuid)")

    @api.model
    def cron_refresh_sat_metadata(self):
        """Refresca sat_metadata_ref desde xmlsat (/get-metadata) para los lotes
        recientes (date_end ultimos ~100 dias). Asi "CFDIs en SAT" siempre refleja
        el total REAL y ACTUAL del SAT (altas + cancelaciones), sin foto vieja.

        Es la mitad Odoo del refresco de metadata: xmlsat corre su cron diario que
        re-descarga la metadata del SAT (sat_metadata); este cron la jala a Odoo.
        Idempotente: por lote borra su periodo+tipo y reinserta. rfc-aware: la tabla
        es single-tenant en unos clientes (sin columna rfc) y multi-RFC en otros."""
        base = 'https://xmlsat.anfepi.com/get-metadata'
        cutoff = fields.Date.today() - timedelta(days=100)
        # .97: ningun otro punto del modulo crea sat_metadata_ref (en algunos
        # clientes se creo a mano). Si falta, este cron (INSERT) y la verificacion
        # de completeness (SELECT) fallaban en silencio y "CFDIs en SAT" se quedaba
        # en el parcial de ventanas. Crearla aqui (idempotente) la auto-sana.
        self._ensure_sat_metadata_ref_table()
        self.env.cr.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='sat_metadata_ref' AND column_name='rfc'")
        has_rfc = bool(self.env.cr.fetchone())
        lotes = self.search([('date_end', '>=', cutoff), ('parent_batch_id', '=', False)])
        n_ok = 0; n_empty = 0; n_err = 0; n_nokey = 0
        for b in lotes:
            # .95: resolver la api key IGUAL que get-cfdis -> por el RFC del lote
            # (b.vat) + delegacion de controladora. Asi una coordinada usa la api
            # key de su controladora y no manda una invalida (402). El api_key YA
            # viene pre-hasheado (SHA-512) desde la BD: NO se re-hashea.
            company = (self.env['res.company'].sudo().search([('vat', '=', b.vat)], limit=1)
                       or b.company_id or self.env.company)
            api_key = company.l10n_mx_xml_download_api_key
            CoordRel = self.env.get('l10n_mx.cfdi.coordinado.relation')
            if CoordRel is not None:
                try:
                    rel = CoordRel.sudo().search([
                        '|',
                        ('coordinada_vat', '=', b.vat),
                        ('coordinada_company_id', '=', company.id),
                        ('active', '=', True),
                    ], limit=1)
                    if rel and rel.controladora_company_id and                             rel.controladora_company_id.l10n_mx_xml_download_api_key:
                        api_key = rel.controladora_company_id.l10n_mx_xml_download_api_key
                except Exception as e:
                    _logger.warning(
                        "cron_refresh_sat_metadata: delegacion controladora fallo: %s", e)
            if not api_key or not b.vat:
                n_nokey += 1
                continue
            url = ("%s?RFC=%s&startDate=%s&endDate=%s&xml_type=%s&api_key=%s"
                   % (base, b.vat, b.date_start, b.date_end, b.cfdi_type, api_key))
            try:
                resp = requests.get(url, verify=False, timeout=120)
                rows = (resp.json() or {}).get('metadata') or []
            except Exception as e:
                _logger.warning("cron_refresh_sat_metadata: lote %s fetch fallo: %s", b.id, e)
                n_err += 1
                continue
            if not rows:
                n_empty += 1
                continue
            try:
                vals = [r for r in rows if r.get('uuid')]
                if has_rfc:
                    self.env.cr.execute(
                        "DELETE FROM sat_metadata_ref WHERE rfc=%s AND type=%s AND fecha BETWEEN %s AND %s",
                        (b.vat, b.cfdi_type, b.date_start, b.date_end))
                    self.env.cr.executemany(
                        "INSERT INTO sat_metadata_ref (rfc, uuid, type, fecha, estatus) VALUES (%s,%s,%s,%s,%s)",
                        [(b.vat, r['uuid'], b.cfdi_type, r['fecha'], r['estatus']) for r in vals])
                else:
                    self.env.cr.execute(
                        "DELETE FROM sat_metadata_ref WHERE type=%s AND fecha BETWEEN %s AND %s",
                        (b.cfdi_type, b.date_start, b.date_end))
                    self.env.cr.executemany(
                        "INSERT INTO sat_metadata_ref (uuid, type, fecha, estatus) VALUES (%s,%s,%s,%s)",
                        [(r['uuid'], b.cfdi_type, r['fecha'], r['estatus']) for r in vals])
                self.env.cr.commit()
                n_ok += 1
            except Exception as e:
                self.env.cr.rollback()
                n_err += 1
                _logger.warning("cron_refresh_sat_metadata: upsert lote %s fallo: %s", b.id, e)
        _logger.info(
            "cron_refresh_sat_metadata: %d refrescados, %d sin metadata en xmlsat, "
            "%d errores, %d sin api_key/vat (de %d lotes elegibles)",
            n_ok, n_empty, n_err, n_nokey, len(lotes))

    @api.model
    def cron_auto_sync_batches(self):
        """Cron que procesa los lotes encolados y los re-sincroniza.

        Tres pases:
          0) AUTO-RECOVERY: libera lotes 'processing' huerfanos (queued_at > 30 min).
             Cubre el caso de que el worker fuera matado a media descarga (ej. por
             un reinicio del servicio) — sin esto los lotes quedan atascados y ni
             el cron ni el usuario los retoman.
          1) Lotes en 'queued' (encolados desde la UI) — ejecutar la descarga
             inicial. Al terminar pasan a 'imported' (o 'error').
          2) Lotes 'imported' con sync_stable=False — re-sync para
             traer paquetes que el servidor xmlsat aún esté procesando.

        Usa SELECT ... FOR UPDATE SKIP LOCKED para que dos crons concurrentes
        nunca tomen el mismo lote (cuando workers>0 y max_cron_threads>1).
        """
        # ---- Pase 0: AUTO-RECOVERY de lotes 'processing' huerfanos ----
        # Asumimos que ningun pipeline real tarda mas de 30 min. Si lo encontramos
        # en 'processing' con queued_at mas antiguo que eso, fue matado por un
        # reinicio/crash y nadie lo esta procesando.
        self.env.cr.execute(
            """
            UPDATE account_edi_api_download
               SET state = 'queued',
                   queued_at = NOW(),
                   last_error = 'Auto-recuperado: lote estaba en processing > 30 min sin avance (posible reinicio del worker).'
             WHERE state = 'processing'
               AND queued_at < NOW() - INTERVAL '30 minutes'
             RETURNING id, name
            """
        )
        recovered = self.env.cr.fetchall()
        if recovered:
            self.env.cr.commit()
            _logger.warning(
                "Cron SAT [recovery]: liberados %s lotes 'processing' huerfanos: %s",
                len(recovered),
                ", ".join(f"id={r[0]} '{(r[1] or '').strip()}'" for r in recovered),
            )

        def _claim_batch(batch_id):
            """Marca el lote como 'processing' atómicamente. Devuelve True si lo logró,
            False si otro cron ya lo tomó."""
            self.env.cr.execute(
                """
                UPDATE account_edi_api_download
                   SET state = 'processing'
                 WHERE id = %s AND state IN ('queued', 'imported')
                 RETURNING id
                """, (batch_id,)
            )
            row = self.env.cr.fetchone()
            self.env.cr.commit()
            return bool(row)

        # --- Pase 1: lotes encolados desde la UI ---
        queued = self.search([('state', '=', 'queued')], order='queued_at asc, id asc')
        for batch in queued:
            if not _claim_batch(batch.id):
                continue  # otro cron lo tomó
            try:
                _logger.info(f'Cron SAT [queued]: procesando lote "{batch.name}" (id={batch.id})')
                batch._run_download_pipeline()
                # _run_download_pipeline ya escribe state='imported' al final.
                # Si no lo hizo (excepción interna silenciada), forzamos:
                if batch.state == 'processing':
                    batch.write({'state': 'imported', 'last_update_date': fields.Date.today()})
                self.env.cr.commit()
                _logger.info(f'Cron SAT [queued]: lote "{batch.name}" listo (sync_stable={batch.sync_stable})')
            except Exception as e:
                # .86: rollback PRIMERO. Si la transaccion quedo abortada
                # (InFailedSqlTransaction), leer batch.name en el log dispara otro
                # fetch que vuelve a tronar y el estado 'error' nunca se persiste
                # (last_error quedaba vacio y el lote pegado en 'processing').
                self.env.cr.rollback()
                _logger.exception(f'Cron SAT [queued]: error en lote "{batch.name}": {e}')
                batch.write({'state': 'error', 'last_error': str(e)[:4000]})
                self.env.cr.commit()

        # --- Pase 2: re-sync de lotes ya importados pero no estables ---
        unstable = self.search([
            ('state', '=', 'imported'),
            ('sync_stable', '=', False),
        ], order='date_start desc')
        if not unstable:
            _logger.info('Cron SAT [resync]: No hay lotes inestables.')
            return
        _logger.info(f'Cron SAT [resync]: re-sincronizando {len(unstable)} lote(s) no estables.')
        for batch in unstable:
            if not _claim_batch(batch.id):
                continue
            try:
                _logger.info(f'Cron SAT [resync]: lote "{batch.name}" (id={batch.id})')
                batch._run_download_pipeline()
                # state y last_update_date ya los actualiza _run_download_pipeline al terminar.
                self.env.cr.commit()
                _logger.info(f'Cron SAT [resync]: lote "{batch.name}" - sync_stable={batch.sync_stable}')
            except Exception as e:
                # .86: rollback PRIMERO (ver nota en pase 1) para no re-tronar al
                # leer batch.name y poder persistir el estado 'error'.
                self.env.cr.rollback()
                _logger.exception(f'Cron SAT [resync]: error en lote "{batch.name}": {e}')
                batch.write({'state': 'error', 'last_error': str(e)[:4000]})
                self.env.cr.commit()

    def action_admin_delete_batch(self):
        """Elimina lotes seleccionados y todos sus XMLs hijos. SOLO ADMIN.
        El XML SAT model tiene attachment vinculado; al borrar el record el
        attachment queda huerfano y Odoo lo limpia con vacuum_attachments.
        Tambien borra cualquier lote hijo (coordinadas) por la FK.
        Devuelve notificacion con conteo."""
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Esta accion solo esta disponible para Administradores.'))
        if not self:
            return False
        total_lotes = len(self)
        # Contar y borrar XMLs hijos
        xmls = self.env['account.edi.downloaded.xml.sat'].search([
            ('batch_id', 'in', self.ids),
        ])
        total_xmls = len(xmls)
        # Borrado en cascada manual para que las lineas de productos tambien se vayan.
        # (O2M con ondelete=cascade en la FK; si no, el delete falla por integridad.)
        if xmls:
            # Producto lines via O2M downloaded_product_id van con cascada del XML SAT.
            xmls.sudo().unlink()
        # Borrar lotes hijos (coordinadas) si los hay, recursivo via parent_batch_id.
        child_batches = self.env['account.edi.api.download'].search([
            ('parent_batch_id', 'in', self.ids),
        ])
        total_children = len(child_batches)
        if child_batches:
            # Recursivamente borrar XMLs de hijos
            child_xmls = self.env['account.edi.downloaded.xml.sat'].search([
                ('batch_id', 'in', child_batches.ids),
            ])
            child_xmls.sudo().unlink()
            child_batches.sudo().unlink()
        # Finalmente, los lotes seleccionados.
        self.sudo().unlink()
        msg = f'Eliminados: {total_lotes} lote(s) padre, {total_children} lote(s) hijo, {total_xmls} XML(s).'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Lotes eliminados',
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            }
        }


class DownloadedXmlSatProducts(models.Model):
    _name = "account.edi.downloaded.xml.sat.products"
    _description = "Account Edi Download From SAT Web Service Products"

    sat_id = fields.Many2one('product.unspsc.code', string="Codigo SAT")
    quantity = fields.Float(string="Cantidad", required=True)
    product_metrics = fields.Char(string="Clave Unidad")
    description = fields.Char(string="Descripcion", required=True)
    unit_value = fields.Float(string="Valor Unitario", required=True)
    total_amount = fields.Float(string="Importe", required=True)
    product_rel = fields.Many2one('product.product', string="Producto Odoo")
    account_id = fields.Many2one(
        'account.account',
        string="Cuenta Contable",
        help="Cuenta contable sugerida. Si hay producto Odoo, hereda la cuenta del producto/categoria. "
             "Si no hay producto, se sugiere por historial del mismo proveedor + codigo SAT + descripcion similar. "
             "Editable manualmente; al modificarse en la factura tambien actualiza este registro para futuros XMLs.",
    )
    cuenta_predial = fields.Char(
        string="Numero Cuenta Predial",
        help="Numero de cuenta predial del inmueble (obligatorio en CFDI de arrendamiento "
             "de bienes inmuebles segun reglas SAT).",
    )
    tax_id = fields.Many2many('account.tax', string="Impuestos")
    # IEPS TRASLADADO de esta linea/concepto (suma de Importes de cfdi:Traslado
    # con Impuesto='003' bajo este Concepto). Util para el flag "IEPS en la base"
    # de res.company: si esta activo, al importar la factura se SUMA este monto
    # al precio unitario en lugar de registrarlo como impuesto aparte.
    ieps_traslado_amount = fields.Float(string="IEPS Trasladado linea")
    # Breakdown completo de impuestos por linea segun el XML. Lista de dicts:
    # [{'kind': 'traslado'|'retencion', 'tipo': '001'|'002'|'003',
    #   'factor': 'Tasa'|'Cuota'|'Exento', 'rate': float|None, 'amount': float}, ...]
    # Util para render UI: cuando una empresa no tiene account.tax configurado
    # para algun impuesto, el M2M tax_id queda vacio pero este JSON conserva el
    # dato crudo. Render: tax_summary_display preferentemente lee de aqui.
    xml_taxes_breakdown = fields.Json(
        string="Breakdown impuestos XML",
        default=list,
    )
    # Render combinado: badges con label + monto de cada impuesto del XML.
    # Usa xml_taxes_breakdown si esta poblado; sino fallback a tax_id (legacy).
    tax_summary_display = fields.Html(
        string="Impuestos (resumen)",
        compute='_compute_tax_summary_display',
        sanitize=False,
    )

    @api.depends('tax_id', 'tax_id.name', 'ieps_traslado_amount', 'xml_taxes_breakdown')
    def _compute_tax_summary_display(self):
        from markupsafe import escape, Markup

        def _label_from_entry(entry):
            tipo = (entry.get('tipo') or '').strip()
            factor = (entry.get('factor') or '').strip()
            rate = entry.get('rate')
            kind = entry.get('kind')
            if tipo == '002':  # IVA
                if factor == 'Exento':
                    label = 'IVA Exento'
                elif rate is not None:
                    label = f'IVA {rate*100:g}%'
                else:
                    label = 'IVA'
            elif tipo == '003':
                label = 'IEPS'
            elif tipo == '001':
                label = 'ISR'
            else:
                label = f'Imp.{tipo}' if tipo else 'Imp.'
            if kind == 'retencion':
                label += ' Ret.'
            return label

        def _color_for(entry):
            if entry.get('kind') == 'retencion':
                return 'text-bg-danger'
            tipo = entry.get('tipo')
            if tipo == '002':
                return 'text-bg-info'
            if tipo == '003':
                return 'text-bg-warning'
            return 'text-bg-secondary'

        # Estilo del badge (constante). inline-block para que cada uno respete
        # su tamano; el wrapper de abajo permite que se apilen a varias lineas.
        BADGE_STYLE = (
            'display:inline-block; margin:1px 4px 1px 0; '
            'font-size:0.85em; white-space:nowrap;'
        )
        # Wrapper: white-space:normal hace que los badges hagan wrap a la
        # siguiente linea cuando la columna es angosta, en vez de truncarse.
        WRAP_STYLE = 'white-space:normal; line-height:1.6;'

        for rec in self:
            parts = []
            breakdown = rec.xml_taxes_breakdown or []
            if breakdown:
                for entry in breakdown:
                    label = _label_from_entry(entry)
                    amount = entry.get('amount') or 0.0
                    color = _color_for(entry)
                    parts.append(
                        f'<span class="badge rounded-pill {color}" '
                        f'style="{BADGE_STYLE}">'
                        f'{escape(label)} ${amount:,.2f}</span>'
                    )
            else:
                for tax in rec.tax_id:
                    parts.append(
                        f'<span class="badge rounded-pill text-bg-secondary" '
                        f'style="{BADGE_STYLE}">'
                        f'{escape(tax.display_name or "")}</span>'
                    )
                if rec.ieps_traslado_amount:
                    parts.append(
                        f'<span class="badge rounded-pill text-bg-warning" '
                        f'style="{BADGE_STYLE}">'
                        f'IEPS ${rec.ieps_traslado_amount:,.2f}</span>'
                    )
            if parts:
                rec.tax_summary_display = Markup(
                    f'<div style="{WRAP_STYLE}">{"".join(parts)}</div>'
                )
            else:
                rec.tax_summary_display = False

    discount = fields.Float(string="Descuento")

    downloaded_invoice_id = fields.Many2one(
        'account.edi.downloaded.xml.sat',
        string='Downloaded product ID',
        ondelete="cascade")

    @api.onchange('product_rel')
    def _onchange_product_rel_suggest_account(self):
        """Cuando el usuario asigna un producto Odoo, sugiere la cuenta contable
        siguiendo la jerarquia nativa de Odoo (producto -> categoria). Solo
        sobreescribe si la cuenta esta vacia o si el usuario quiere refrescarla.
        """
        for line in self:
            if not line.product_rel:
                continue
            if line.account_id:
                continue
            xml = line.downloaded_invoice_id
            company = xml.company_id or self.env.company
            # cfdi_type emitidos -> ingreso, recibidos -> gasto
            is_income = xml.cfdi_type == 'emitidos'
            try:
                accounts = line.product_rel.with_company(company).product_tmpl_id.get_product_accounts()
            except Exception:
                accounts = {}
            suggested = accounts.get('income' if is_income else 'expense')
            if suggested:
                line.account_id = suggested
