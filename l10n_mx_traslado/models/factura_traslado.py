# -*- coding: utf-8 -*-

import base64
import json
import requests
import datetime
import ast
from lxml import etree
import uuid
from odoo import fields, models, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.units import mm
from . import amount_to_text_es_MX
import pytz
from odoo import tools
import math

import logging
_logger = logging.getLogger(__name__)


class CfdiTrasladoLine(models.Model):
    _name = "cfdi.traslado.line"
    _description = "CfdiTrasladoLine"

    cfdi_traslado_id = fields.Many2one(comodel_name='cfdi.traslado', string="CFDI Traslado")
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    name = fields.Text(string='Descripción', required=True)
    quantity = fields.Float(string='Cantidad', digits=dp.get_precision('Unidad de medida del producto'), required=True, default=1)
    price_unit = fields.Float(string='Precio unitario', required=True, digits=dp.get_precision('Product Price'))
    invoice_line_tax_ids = fields.Many2many('account.tax', string='Taxes')
    currency_id = fields.Many2one('res.currency', related='cfdi_traslado_id.currency_id', store=True, related_sudo=False, readonly=False)
    price_subtotal = fields.Monetary(string='Subtotal', store=True, readonly=True, compute='_compute_price')
    price_total = fields.Monetary(string='Cantidad (con Impuestos)', store=True, readonly=True, compute='_compute_price')
    pesoenkg = fields.Float(string='Peso Kg', digits=dp.get_precision('Product Price'))
    guias_line_ids = fields.Many2many('cfdi.guias.line', string='Guías', copy=True)
    aduanera_line_ids = fields.Many2many('cfdi.aduanera.line', string='Inf. Aduanera', copy=True)
    transporta_line_ids = fields.Many2many('cfdi.transporta.line', string='Cant. Trans.', copy=True)
    moneda = fields.Selection(
        selection=[('MXN', 'MXN'), ('USD', 'USD'), ('EUR', 'EUR'), ('CAD', 'CAD')],
        string='Moneda', default='MXN'
    )

    # ── Campos de pedimento por línea (pre-llenados desde costes en destino) ──
    tipo_documento_id = fields.Many2one(
        'ccp.tipo.documento',
        string='Tipo de documento aduanero',
        help="Tipo de documento: 01 Pedimento, 02 Autorización temporal, etc."
    )
    pedimento = fields.Char(
        string='No. Pedimento',
        help="Número de pedimento con formato: AA  BB  CCCC  DDDDDDD"
    )
    fecha_pedimento = fields.Date(string='Fecha pedimento')
    aduana_pedimento = fields.Char(string='Aduana')
    id_doc_aduanero = fields.Text(string='Identificador documento aduanero')
    rfc_import = fields.Text(string='RFC de importador')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        self.name = self.product_id.partner_ref
        company_id = self.env.user.company_id
        taxes = self.product_id.taxes_id.filtered(lambda r: r.company_id == company_id)
        self.invoice_line_tax_ids = fp_taxes = taxes
        fix_price = self.env['account.tax']._fix_tax_included_price
        self.price_unit = fix_price(self.product_id.lst_price, taxes, fp_taxes)
        self.pesoenkg = self.product_id.weight

    @api.depends('price_unit', 'invoice_line_tax_ids', 'quantity',
                 'product_id', 'cfdi_traslado_id.partner_id', 'cfdi_traslado_id.currency_id')
    def _compute_price(self):
        for line in self:
            currency = line.cfdi_traslado_id and line.cfdi_traslado_id.currency_id or None
            price = line.price_unit
            taxes = False
            if line.invoice_line_tax_ids:
                taxes = line.invoice_line_tax_ids.compute_all(
                    price, currency, line.quantity,
                    product=line.product_id,
                    partner=line.cfdi_traslado_id.partner_id
                )
            line.price_subtotal = taxes['total_excluded'] if taxes else line.quantity * price
            line.price_total = taxes['total_included'] if taxes else line.price_subtotal

    @api.onchange('quantity')
    def _onchange_quantity(self):
        self.pesoenkg = self.product_id.weight * self.quantity


class CCPUbicacionesLine(models.Model):
    _name = "ccp.ubicaciones.line"
    _description = "CCPUbicacionesLine"

    cfdi_traslado_id = fields.Many2one(comodel_name='cfdi.traslado', string="CFDI Traslado")
    tipoubicacion = fields.Selection(
        selection=[('Origen', 'Origen'), ('Destino', 'Destino')],
        string='Tipo Ubicación', required=True
    )
    contacto = fields.Many2one('res.partner', string="Remitente / Destinatario", required=True)
    numestacion = fields.Many2one('cve.estaciones', string='Número de estación')
    fecha = fields.Datetime(string='Fecha Salida / Llegada', required=True)
    tipoestacion = fields.Many2one('cve.estacion', string='Tipo estación')
    distanciarecorrida = fields.Float(string='Distancia recorrida')
    tipo_transporte = fields.Selection(
        selection=[('01', 'Autotransporte'), ('03', 'Aereo')],
        string='Tipo de transporte'
    )
    idubicacion = fields.Char(string='ID Ubicacion')


class CCPRemolqueLine(models.Model):
    _name = "ccp.remolques.line"
    _description = "CCPRemolqueLine"

    cfdi_traslado_id = fields.Many2one(comodel_name='cfdi.traslado', string="CFDI Traslado")
    subtipo_id = fields.Many2one('cve.remolque.semiremolque', string="Subtipo")
    placa = fields.Char(string='Placa')


class CCPPropietariosLine(models.Model):
    _name = "ccp.figura.line"
    _description = "CCPPropietariosLine"

    cfdi_traslado_id = fields.Many2one(comodel_name='cfdi.traslado', string="CFDI Traslado")
    figura_id = fields.Many2one('res.partner', string="Contacto")
    tipofigura = fields.Many2one('cve.figura.transporte', string="Tipo figura")
    partetransporte = fields.Many2many('cve.parte.transporte', string="Parte transporte")

    # ── Related para poder mostrarlos en vistas list sin notación de punto ──
    figura_licencia = fields.Char(
        related='figura_id.cce_licencia',
        string='No. Licencia',
        readonly=True,
        store=False,
    )
    figura_rfc = fields.Char(
        related='figura_id.vat',
        string='RFC Figura',
        readonly=True,
        store=False,
    )


class CfdiAduaneraLine(models.Model):
    _name = "cfdi.aduanera.line"
    _description = "CCPaduaneraLine"
    _rec_name = "pedimento"

    cfdi_traslado_id = fields.Many2one(comodel_name='cfdi.traslado', string="CFDI Traslado")
    tipo_documento_id = fields.Many2one('ccp.tipo.documento', string='Tipo de documento', required=True)
    pedimento = fields.Text(string='Pedimento')
    id_doc_aduanero = fields.Text(string='Identificador documento aduanero')
    rfc_import = fields.Text(string='RFC de importador')
    fecha_pedimento = fields.Date(string='Fecha pedimento')
    aduana_pedimento = fields.Char(string='Aduana')

class CfdiTransportaLine(models.Model):
    _name = "cfdi.transporta.line"
    _description = "CCPTransportaLine"
    _rec_name = "name"

    cfdi_traslado_id = fields.Many2one(comodel_name='cfdi.traslado', string="CFDI Traslado")
    cantidad = fields.Float(string='Cantidad')
    idorigen = fields.Char(string='ID Origen')
    iddestino = fields.Char(string='ID Destino')
    # ── NUEVO: Clave de transporte requerida en XML ──
    cves_transporte = fields.Selection(
        selection=[
            ('01', '01 - Autotransporte'),
            ('02', '02 - Transporte Marítimo'),
            ('03', '03 - Transporte Aéreo'),
            ('04', '04 - Transporte Ferroviario'),
        ],
        string='Clave Transporte',
        help="CvesTransporte: clave del catálogo catCartaPorte:c_CveTransporte"
    )
    name = fields.Char(string='Nombre')


class CfdiGuiasLine(models.Model):
    _name = "cfdi.guias.line"
    _description = "CCPguiasLine"
    _rec_name = "guiaid_numero"

    cfdi_traslado_id = fields.Many2one(comodel_name='cfdi.traslado', string="CFDI Traslado")
    guiaid_numero = fields.Char(string='No. Guia')
    guiaid_descrip = fields.Char(string='Descr. guia')
    guiaid_peso = fields.Float(string='Peso guia')


class CCPAduaneroLine(models.Model):
    _name = "ccp.aduanero.line"
    _description = "CCPAduaneroLine"

    cfdi_traslado_id = fields.Many2one(comodel_name='cfdi.traslado', string="CFDI Traslado")
    regimen_aduanero = fields.Many2one('ccp.regimen.aduanero', string='Regimen aduanero')


class CfdiTraslado(models.Model):
    _name = "cfdi.traslado"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _rec_name = "number"
    _description = "CfdiTraslado"

    factura_cfdi = fields.Boolean('Factura CFDI', copy=False)
    number = fields.Char(string="Numero", store=True, readonly=True, copy=False,
                         default=lambda self: _('Factura borrador'))
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('valid', 'Validada'),
        ('cancel', 'Cancelada'),
    ], string='Status', index=True, readonly=True, default='draft')

    forma_pago = fields.Selection(
        selection=[('01', '01 - Efectivo'), ('02', '02 - Cheque nominativo'),
                   ('03', '03 - Transferencia electrónica de fondos'),
                   ('04', '04 - Tarjeta de Crédito'), ('05', '05 - Monedero electrónico'),
                   ('06', '06 - Dinero electrónico'), ('08', '08 - Vales de despensa'),
                   ('12', '12 - Dación en pago'), ('13', '13 - Pago por subrogación'),
                   ('14', '14 - Pago por consignación'), ('15', '15 - Condonación'),
                   ('17', '17 - Compensación'), ('23', '23 - Novación'),
                   ('24', '24 - Confusión'), ('25', '25 - Remisión de deuda'),
                   ('26', '26 - Prescripción o caducidad'),
                   ('27', '27 - A satisfacción del acreedor'),
                   ('28', '28 - Tarjeta de débito'), ('29', '29 - Tarjeta de servicios'),
                   ('30', '30 - Aplicación de anticipos'), ('31', '31 - Intermediario pagos'),
                   ('99', '99 - Por definir')],
        string='Forma de pago'
    )
    methodo_pago = fields.Selection(
        selection=[('PUE', 'Pago en una sola exhibición'), ('PPD', 'Pago en parcialidades o diferido')],
        string='Método de pago',
    )
    uso_cfdi = fields.Selection(
        selection=[('G01', 'Adquisición de mercancías'), ('G02', 'Devoluciones, descuentos o bonificaciones'),
                   ('G03', 'Gastos en general'), ('I01', 'Construcciones'),
                   ('I02', 'Mobiliario y equipo de oficina por inversiones'),
                   ('I03', 'Equipo de transporte'), ('I04', 'Equipo de cómputo y accesorios'),
                   ('I05', 'Dados, troqueles, moldes, matrices y herramental'),
                   ('I06', 'Comunicacion telefónica'), ('I07', 'Comunicación Satelital'),
                   ('I08', 'Otra maquinaria y equipo'),
                   ('D01', 'Honorarios médicos, dentales y gastos hospitalarios'),
                   ('D02', 'Gastos médicos por incapacidad o discapacidad'),
                   ('D03', 'Gastos funerales'), ('D04', 'Donativos'),
                   ('D05', 'Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación).'),
                   ('D06', 'Aportaciones voluntarias al SAR.'),
                   ('D07', 'Primas por seguros de gastos médicos'),
                   ('D08', 'Gastos de transportación escolar obligatoria'),
                   ('D09', 'Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones'),
                   ('D10', 'Pagos por servicios educativos (colegiaturas)'),
                   ('S01', 'Sin efectos fiscales'), ('P01', 'Por definir (obsoleto)')],
        string='Uso CFDI (cliente)', default='S01',
    )
    tipo_comprobante = fields.Selection(
        selection=[('I', 'Ingreso'), ('E', 'Egreso'), ('T', 'Traslado')],
        string='Tipo de comprobante', default='T',
    )
    folio_fiscal = fields.Char('Folio Fiscal', readonly=True, copy=False)
    confirmacion = fields.Char('Confirmación')
    estado_factura = fields.Selection(
        selection=[('factura_no_generada', 'Factura no generada'),
                   ('factura_correcta', 'Factura correcta'),
                   ('solicitud_cancelar', 'Cancelación en proceso'),
                   ('factura_cancelada', 'Factura cancelada'),
                   ('solicitud_rechazada', 'Cancelación rechazada')],
        string='Estado de factura', default='factura_no_generada', readonly=True, copy=False
    )
    fecha_factura = fields.Datetime('Fecha Factura', copy=False)
    tipo_relacion = fields.Selection(
        selection=[('01', 'Nota de crédito de los documentos relacionados'),
                   ('02', 'Nota de débito de los documentos relacionados'),
                   ('03', 'Devolución de mercancía sobre facturas o traslados previos'),
                   ('04', 'Sustitución de los CFDI previos'),
                   ('05', 'Traslados de mercancías facturados previamente'),
                   ('06', 'Factura generada por los traslados previos'),
                   ('07', 'CFDI por aplicación de anticipo')],
        string='Tipo relación'
    )
    regimen_fiscal = fields.Selection(
        selection=[('601', 'General de Ley Personas Morales'),
                   ('603', 'Personas Morales con Fines no Lucrativos'),
                   ('605', 'Sueldos y Salarios e Ingresos Asimilados a Salarios'),
                   ('606', 'Arrendamiento'), ('608', 'Demás ingresos'),
                   ('609', 'Consolidación'),
                   ('610', 'Residentes en el Extranjero sin Establecimiento Permanente en México'),
                   ('611', 'Ingresos por Dividendos (socios y accionistas)'),
                   ('612', 'Personas Físicas con Actividades Empresariales y Profesionales'),
                   ('614', 'Ingresos por intereses'), ('616', 'Sin obligaciones fiscales'),
                   ('620', 'Sociedades Cooperativas de Producción que optan por diferir sus ingresos'),
                   ('621', 'Incorporación Fiscal'),
                   ('622', 'Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras'),
                   ('623', 'Opcional para Grupos de Sociedades'), ('624', 'Coordinados'),
                   ('628', 'Hidrocarburos'),
                   ('607', 'Régimen de Enajenación o Adquisición de Bienes'),
                   ('629', 'De los Regímenes Fiscales Preferentes y de las Empresas Multinacionales'),
                   ('630', 'Enajenación de acciones en bolsa de valores'),
                   ('615', 'Régimen de los ingresos por obtención de premios'),
                   ('625', 'Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas'),
                   ('626', 'Régimen Simplificado de Confianza')],
        string='Régimen Fiscal',
    )
    uuid_relacionado = fields.Char(string='CFDI Relacionado')
    qr_value = fields.Char(string='QR Code Value', copy=False)
    qrcode_image = fields.Binary("QRCode", copy=False)
    comment = fields.Text("Comentario")
    partner_id = fields.Many2one('res.partner', string="Cliente", required=True,
                                 default=lambda self: self.env['res.company']._company_default_get('cfdi.traslado'))
    source_document = fields.Char(string="Documento origen")
    invoice_date = fields.Datetime(string="Fecha de factura")
    factura_line_ids = fields.One2many('cfdi.traslado.line', 'cfdi_traslado_id', string='CFDI Traslado Line', copy=True)
    currency_id = fields.Many2one('res.currency', string='Moneda',
                                  default=lambda self: self.env['res.company']._company_default_get('cfdi.traslado').currency_id,
                                  required=True)
    amount_untaxed = fields.Float(string='Untaxed Amount', store=True, readonly=True, default=0)
    amount_tax = fields.Float(string='Tax', store=True, readonly=True, default=0)
    amount_total = fields.Float(string='Total', store=True, readonly=True, default=0)

    numero_cetificado = fields.Char(string='Numero de cetificado', copy=False)
    cetificaso_sat = fields.Char(string='Cetificado SAT', copy=False)
    fecha_certificacion = fields.Char(string='Fecha y Hora Certificación', copy=False)
    cadena_origenal = fields.Char(string='Cadena Origenal del Complemento digital de SAT', copy=False)
    selo_digital_cdfi = fields.Char(string='Sello Digital del CDFI', copy=False)
    selo_sat = fields.Char(string='Sello del SAT', copy=False)
    moneda = fields.Char(string='Moneda')
    tipocambio = fields.Char(string='TipoCambio')
    number_folio = fields.Char(string='Folio', compute='_get_number_folio')
    invoice_datetime = fields.Char(string='Fecha/Hora CFDI')
    proceso_timbrado = fields.Boolean(string='Proceso de timbrado')
    rfc_emisor = fields.Char(string='RFC')
    name_emisor = fields.Char(string='Name')
    serie_emisor = fields.Char(string='A')

    decimales = fields.Float(string='decimales')
    company_id = fields.Many2one('res.company', 'Compañia',
                                 default=lambda self: self.env['res.company']._company_default_get('cfdi.traslado'))

    tipo_transporte = fields.Selection(
        selection=[('01', 'Autotransporte'), ('03', 'Aereo')],
        string='Tipo de transporte', required=True, default='01'
    )
    carta_porte = fields.Boolean('Agregar carta porte', default=True)

    # ── Atributos CP ──
    transpinternac = fields.Selection(
        selection=[('Sí', 'Si'), ('No', 'No')],
        string='¿Es un transporte internacional?', default='No',
    )
    entradasalidamerc = fields.Selection(
        selection=[('Entrada', 'Entrada'), ('Salida', 'Salida')],
        string='¿Las mercancías ingresan o salen del territorio nacional?',
    )
    viaentradasalida = fields.Many2one('cve.transporte', string='Vía de ingreso / salida')
    totaldistrec = fields.Float(string='Distancia recorrida total', digits=(16, 6))

    # ── Ubicaciones CP ──
    ubicaciones_line_ids = fields.One2many('ccp.ubicaciones.line', 'cfdi_traslado_id', string='Ubicaciones', copy=True)

    # ── Mercancías CP ──
    pesobrutototal = fields.Float(string='Peso bruto total', compute='_compute_pesobruto')
    unidadpeso = fields.Many2one('cve.clave.unidad', string='Unidad peso')
    pesonetototal = fields.Float(string='Peso neto total')
    numerototalmercancias = fields.Float(string='Numero total de mercancías', compute='_compute_mercancia')
    cargoportasacion = fields.Float(string='Cargo por tasación')

    # ── Transporte ──
    permisosct = fields.Many2one('cve.tipo.permiso', string='Permiso SCT')
    numpermisosct = fields.Char(string='Número de permiso SCT')

    # ── Autotransporte ──
    autotrasporte_ids = fields.Many2one('ccp.autotransporte', string='Unidad')
    remolque_line_ids = fields.One2many('ccp.remolques.line', 'cfdi_traslado_id', string='Remolque', copy=True)
    nombreaseg_merc = fields.Char(string='Aseguradora de carga (AseguraCarga)')
    numpoliza_merc = fields.Char(string='Póliza de carga (PolizaCarga)')
    primaseguro_merc = fields.Float(string='Prima del seguro (PrimaSeguro)')
    seguro_ambiente = fields.Char(string='Nombre aseguradora medio ambiente')
    poliza_ambiente = fields.Char(string='Póliza medio ambiente')

    # ── Aéreo CP ──
    numeroguia = fields.Char(string='Número de guía')
    lugarcontrato = fields.Char(string='Lugar de contrato')
    matriculaaeronave = fields.Char(string='Matrícula Aeronave')
    transportista_id = fields.Many2one('res.partner', string="Transportista")
    embarcador_id = fields.Many2one('res.partner', string="Embarcador")

    uuidcomercioext = fields.Char(string='UUID Comercio Exterior')
    paisorigendestino = fields.Many2one('res.country', string='País Origen / Destino')

    # ── Figura transporte ──
    figuratransporte_ids = fields.One2many('ccp.figura.line', 'cfdi_traslado_id', string='Figura transporte', copy=True)
    IdCCP = fields.Char(string='IdCCP', readonly=True, copy=False)

    regimen_aduanero = fields.Many2one('ccp.regimen.aduanero', string='Regimen aduanero')
    aduanero_line_ids = fields.One2many('ccp.aduanero.line', 'cfdi_traslado_id', string='Regimen aduanero', copy=True)
    LogisticaInversa = fields.Selection(selection=[('Sí', 'Si')], string='Logistica Inversa Recoleccion Devolucion')
    qr_ccp_value = fields.Char(string='QR CCP', copy=False)
    qrcode_ccp_image = fields.Binary("QRCode CCP", copy=False)
    aduanera_line_ids = fields.One2many('cfdi.aduanera.line', 'cfdi_traslado_id', string='CFDI Aduanera Line', copy=True)
    guias_line_ids = fields.One2many('cfdi.guias.line', 'cfdi_traslado_id', string='CFDI Guias Line', copy=True)
    manejodeguias = fields.Boolean('Manejo de guías')
    transporta_line_ids = fields.One2many('cfdi.transporta.line', 'cfdi_traslado_id', string='CFDI Transporte Line', copy=True)
    manejodeids = fields.Boolean('Manejo de IDs')

    @api.depends('number')
    def _get_number_folio(self):
        if self.number:
            self.number_folio = self.number.replace('CT', '').replace('/', '')

    @api.model
    def _get_amount_2_text(self, amount_total):
        return amount_to_text_es_MX.get_amount_to_text(self, amount_total, 'es_cheque', self.currency_id.name)

    @api.model
    def _default_journal(self):
        if not self.journal_id:
            company_id = self._context.get('default_company_id', self.env.company.id)
            return self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', company_id)], limit=1)

    journal_id = fields.Many2one('account.journal', 'Diario', default=_default_journal)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('number', _('Draft Invoice')) == _('Draft Invoice'):
                if 'company_id' in vals:
                    vals['number'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('cfdi.traslado') or _('Draft Invoice')
                else:
                    vals['number'] = self.env['ir.sequence'].next_by_code('cfdi.traslado') or _('Draft Invoice')
        result = super(CfdiTraslado, self).create(vals_list)
        return result

    def action_valid(self):
        self.write({'state': 'valid'})
        self.invoice_date = datetime.datetime.now()

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.onchange('factura_line_ids')
    def _compute_pesobruto(self):
        peso = 0
        for rec in self:
            if rec.factura_line_ids:
                for line in rec.factura_line_ids:
                    peso += line.pesoenkg
            rec.pesobrutototal = peso

    @api.onchange('factura_line_ids')
    def _compute_pesoneto(self):
        peso = 0
        for rec in self:
            if rec.factura_line_ids:
                for line in rec.factura_line_ids:
                    peso += line.pesoenkg
            rec.pesonetototal = peso

    @api.onchange('factura_line_ids')
    def _compute_mercancia(self):
        cant = 0
        for rec in self:
            if rec.factura_line_ids:
                for line in rec.factura_line_ids:
                    cant += 1
            rec.numerototalmercancias = cant

    def _get_fecha_expedicion(self):
        timezone = self._context.get('tz')
        if not timezone:
            timezone = self.journal_id.tz or self.env.user.partner_id.tz or 'America/Mexico_City'
        local = pytz.timezone(timezone)
        if not self.fecha_factura:
            naive_from = datetime.datetime.now()
        else:
            naive_from = self.fecha_factura
        local_dt_from = naive_from.replace(tzinfo=pytz.UTC).astimezone(local)
        date_from = local_dt_from.strftime("%Y-%m-%dT%H:%M:%S")
        return str(date_from)

    def _get_serie_xml(self):
        return self.company_id.serie_timbrado or 'CT'

    def _get_folio_xml(self):
        return self.number.replace('CT', '').replace('/', '')

    @api.model
    def to_json(self):
        no_decimales = 2
        no_decimales_prod = 2

        self.check_cfdi_values()

        timezone = self._context.get('tz')
        if not timezone:
            timezone = self.journal_id.tz or self.env.user.partner_id.tz or 'America/Mexico_City'
        local = pytz.timezone(timezone)
        if not self.fecha_factura:
            naive_from = datetime.datetime.now()
        else:
            naive_from = self.fecha_factura
        local_dt_from = naive_from.replace(tzinfo=pytz.UTC).astimezone(local)
        date_from = local_dt_from.strftime("%Y-%m-%dT%H:%M:%S")
        if not self.fecha_factura:
            self.fecha_factura = datetime.datetime.now()

        request_params = {
            'factura': {
                'serie': self.company_id.serie_timbrado,
                'folio': self.number.replace('CT', '').replace('/', ''),
                'fecha_expedicion': date_from,
                'subtotal': self.amount_untaxed,
                'moneda': 'XXX',
                'total': self.amount_total,
                'tipocomprobante': self.tipo_comprobante,
                'metodo_pago': self.methodo_pago,
                'LugarExpedicion': self.company_id.zip,
                'Confirmacion': self.confirmacion,
                'Exportacion': '01',
            },
            'emisor': {
                'rfc': self.company_id.vat.upper(),
                'nombre': self.clean_text(self.company_id.name).upper(),
                'RegimenFiscal': self.company_id.regimen_fiscal,
            },
            'receptor': {
                'nombre': self.clean_text(self.company_id.name).upper(),
                'rfc': self.company_id.vat.upper() if self.company_id.partner_id.country_id.l10n_mx_edi_code == 'MEX' else '',
                'ResidenciaFiscal': self.company_id.partner_id.country_id.l10n_mx_edi_code if self.company_id.partner_id.country_id.l10n_mx_edi_code != 'MEX' else '',
                'NumRegIdTrib': self.company_id.vat.upper() if self.company_id.partner_id.country_id.l10n_mx_edi_code != 'MEX' else '',
                'UsoCFDI': self.uso_cfdi,
                'RegimenFiscalReceptor': self.company_id.regimen_fiscal,
                'DomicilioFiscalReceptor': self.company_id.zip,
            },
            'informacion': {
                'cfdi': '4.0',
                'sistema': 'odoo18 EE',
                'version': '2',
                'api_key': self.company_id.proveedor_timbrado,
                'modo_prueba': self.company_id.modo_prueba,
            },
        }

        invoice_lines = []
        for line in self.factura_line_ids:
            invoice_lines.append({
                'cantidad': self.set_decimals(line.quantity, 6),
                'unidad': line.product_id.uom_id.name,
                'NoIdentificacion': line.product_id.default_code,
                'valorunitario': self.set_decimals(line.price_unit, no_decimales_prod),
                'importe': self.set_decimals(line.price_unit * line.quantity, no_decimales_prod),
                'descripcion': self.clean_text(line.product_id.name),
                'ClaveProdServ': line.product_id.unspsc_code_id.code,
                'ObjetoImp': '01',
                'ClaveUnidad': line.product_id.uom_id.unspsc_code_id.code,
            })

        request_params['factura'].update({'subtotal': '0', 'total': '0'})
        request_params.update({'conceptos': invoice_lines})

        if not self.company_id.archivo_cer:
            raise UserError(_('Archivo .cer path is missing.'))
        if not self.company_id.archivo_key:
            raise UserError(_('Archivo .key path is missing.'))
        archivo_cer = self.company_id.archivo_cer
        archivo_key = self.company_id.archivo_key
        request_params.update({
            'certificados': {
                'archivo_cer': archivo_cer.decode("utf-8"),
                'archivo_key': archivo_key.decode("utf-8"),
                'contrasena': self.company_id.contrasena,
            }
        })
        return request_params

    def set_decimals(self, amount, precision):
        if amount is None or amount is False:
            return None
        return '%.*f' % (precision, amount)

    def clean_text(self, text):
        clean_text = text.replace('\n', ' ').replace('\\', ' ').replace('-', ' ').replace('/', ' ').replace('|', ' ')
        clean_text = clean_text.replace(',', ' ').replace(';', ' ').replace('>', ' ').replace('<', ' ')
        return clean_text[:1000]

    def check_cfdi_values(self):
        if not self.company_id.vat:
            self.write({'proceso_timbrado': False})
            self.env.cr.commit()
            raise UserError(_('El emisor no tiene RFC configurado.'))
        if not self.company_id.name:
            self.write({'proceso_timbrado': False})
            self.env.cr.commit()
            raise UserError(_('El emisor no tiene nombre configurado.'))
        if not self.company_id.regimen_fiscal:
            self.write({'proceso_timbrado': False})
            self.env.cr.commit()
            raise UserError(_('El emisor no tiene régimen fiscal configurado.'))

    def _set_data_from_xml(self, xml_invoice):
        if not xml_invoice:
            return None
        NSMAP = {
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'cfdi': 'http://www.sat.gob.mx/cfd/4',
            'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
        }

        xml_data = etree.fromstring(xml_invoice)
        Complemento = xml_data.find('cfdi:Complemento', NSMAP)
        TimbreFiscalDigital = Complemento.find('tfd:TimbreFiscalDigital', NSMAP)

        self.moneda = xml_data.attrib['Moneda']
        self.numero_cetificado = xml_data.attrib['NoCertificado']
        self.cetificaso_sat = TimbreFiscalDigital.attrib['NoCertificadoSAT']
        self.fecha_certificacion = TimbreFiscalDigital.attrib['FechaTimbrado']
        self.selo_digital_cdfi = TimbreFiscalDigital.attrib['SelloCFD']
        self.selo_sat = TimbreFiscalDigital.attrib['SelloSAT']
        self.folio_fiscal = TimbreFiscalDigital.attrib['UUID']
        self.invoice_datetime = xml_data.attrib['Fecha']
        version = TimbreFiscalDigital.attrib['Version']
        self.cadena_origenal = '||%s|%s|%s|%s|%s||' % (
            version, self.folio_fiscal, self.fecha_certificacion,
            self.selo_digital_cdfi, self.cetificaso_sat
        )

        options = {'width': 275 * mm, 'height': 275 * mm}
        amount_str = str(self.amount_total).split('.')
        qr_value = 'https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?&id=%s&re=%s&rr=%s&tt=%s.%s&fe=%s' % (
            self.folio_fiscal,
            self.company_id.vat,
            self.company_id.vat,
            amount_str[0].zfill(10),
            amount_str[1].ljust(6, '0') if len(amount_str) > 1 else '000000',
            self.selo_digital_cdfi[-8:],
        )
        self.qr_value = qr_value
        ret_val = createBarcodeDrawing('QR', value=qr_value, **options)
        self.qrcode_image = base64.encodebytes(ret_val.asString('jpg'))

        ubicacion = self.ubicaciones_line_ids[0]
        timezone = self._context.get('tz')
        if not timezone:
            timezone = self.journal_id.tz or self.env.user.partner_id.tz or 'America/Mexico_City'
        local = pytz.timezone(timezone)
        local_dt_from = ubicacion.fecha.replace(tzinfo=pytz.UTC).astimezone(local)
        fechaorig = local_dt_from.strftime("%Y-%m-%dT%H:%M:%S")
        qr_ccp_value = 'https://verificacfdi.facturaelectronica.sat.gob.mx/verificaccp/default.aspx?IdCCP=%s&FechaOrig=%s&FechaTimb=%s' % (
            self.IdCCP, fechaorig, self.fecha_certificacion,
        )
        self.qr_ccp_value = qr_ccp_value
        ret_val = createBarcodeDrawing('QR', value=qr_ccp_value, **options)
        self.qrcode_ccp_image = base64.encodebytes(ret_val.asString('jpg'))

    # ──────────────────────────────────────────────────────────────────────────
    # Complemento Carta Porte 3.1 – Generación de JSON
    # ──────────────────────────────────────────────────────────────────────────
    @api.model
    def to_json_carta_porte(self, request_params):
        res = request_params
        self.totaldistrec = 0

        if not self.IdCCP:
            self.IdCCP = str(uuid.uuid4()).upper()
            self.IdCCP = self.IdCCP[:0] + 'CCC' + self.IdCCP[3:]

        # ── Ubicaciones ──
        cp_ubicacion = []
        for ubicacion in self.ubicaciones_line_ids:
            timezone = self._context.get('tz')
            if not timezone:
                timezone = self.journal_id.tz or self.env.user.partner_id.tz or 'America/Mexico_City'
            local = pytz.timezone(timezone)
            local_dt_from = ubicacion.fecha.replace(tzinfo=pytz.UTC).astimezone(local)
            date_fecha = local_dt_from.strftime("%Y-%m-%dT%H:%M:%S")
            self.totaldistrec += float(ubicacion.distanciarecorrida)

            cp_ubicacion.append({
                'TipoUbicacion': ubicacion.tipoubicacion,
                'IDUbicacion': ubicacion.idubicacion,
                'RFCRemitenteDestinatario': ubicacion.contacto.vat if ubicacion.contacto.country_id.l10n_mx_edi_code == 'MEX' else '',
                'NombreRemitenteDestinatario': ubicacion.contacto.name,
                'NumRegIdTrib': ubicacion.contacto.vat if ubicacion.contacto.country_id.l10n_mx_edi_code != 'MEX' else '',
                'ResidenciaFiscal': ubicacion.contacto.country_id.l10n_mx_edi_code if ubicacion.contacto.country_id.l10n_mx_edi_code != 'MEX' else '',
                'NumEstacion': self.tipo_transporte != '01' and ubicacion.numestacion.clave_identificacion or '',
                'NombreEstacion': self.tipo_transporte != '01' and ubicacion.numestacion.descripcion or '',
                'FechaHoraSalidaLlegada': date_fecha,
                'TipoEstacion': self.tipo_transporte != '01' and ubicacion.tipoestacion.c_estacion or '',
                'DistanciaRecorrida': ubicacion.distanciarecorrida > 0 and ubicacion.distanciarecorrida or '',
                'Domicilio': {
                    'Calle': ubicacion.contacto.street_name,
                    'NumeroExterior': ubicacion.contacto.street_number,
                    'NumeroInterior': ubicacion.contacto.street_number2,
                    'Colonia': ubicacion.contacto.l10n_mx_edi_colony_code if ubicacion.contacto.country_id.l10n_mx_edi_code == 'MEX' else (ubicacion.contacto.l10n_mx_edi_colony or ''),
                    'Localidad': ubicacion.contacto.l10n_mx_edi_locality_id.code if ubicacion.contacto.country_id.l10n_mx_edi_code == 'MEX' else ubicacion.contacto.l10n_mx_edi_locality,
                    'Municipio': ubicacion.contacto.city_id.l10n_mx_edi_code if ubicacion.contacto.country_id.l10n_mx_edi_code == 'MEX' else ubicacion.contacto.city,
                    'Estado': ubicacion.contacto.state_id.code if ubicacion.contacto.country_id.l10n_mx_edi_code in ('MEX', 'USA', 'CAN') or ubicacion.contacto.state_id.code else 'NA',
                    'Pais': ubicacion.contacto.country_id.l10n_mx_edi_code,
                    'CodigoPostal': ubicacion.contacto.zip,
                },
            })

        # ── Atributos principales ──
        cartaporte31 = {
            'IdCCP': self.IdCCP,
            'TranspInternac': self.transpinternac,
            'EntradaSalidaMerc': self.entradasalidamerc,
            'ViaEntradaSalida': self.viaentradasalida.c_transporte,
            'TotalDistRec': self.tipo_transporte == '01' and self.totaldistrec or '',
            'PaisOrigenDestino': self.paisorigendestino.l10n_mx_edi_code,
        }

        if self.aduanero_line_ids:
            cp_aduanero = []
            for aduanero in self.aduanero_line_ids:
                cp_aduanero.append({'RegimenAduanero': aduanero.regimen_aduanero.clave})
            cartaporte31.update({'Aduaneros': cp_aduanero})

        cartaporte31.update({'Ubicaciones': cp_ubicacion})

        # ── Mercancías ──
        mercancias = {
            'PesoBrutoTotal': self.pesobrutototal,
            'UnidadPeso': self.unidadpeso.clave,
            'PesoNetoTotal': self.pesonetototal if self.pesonetototal > 0 else '',
            'NumTotalMercancias': self.numerototalmercancias,
            'CargoPorTasacion': self.cargoportasacion if self.cargoportasacion > 0 else '',
            'LogisticaInversa': self.LogisticaInversa,
        }

        mercancia_atributos = []
        for line in self.factura_line_ids:
            if line.quantity <= 0:
                continue

            # ── Guías ──
            guias = []
            for guia_line in line.guias_line_ids:
                guias.append({
                    'NumeroGuiaIdentificacion': guia_line.guiaid_numero,
                    'DescripGuiaIdentificacion': guia_line.guiaid_descrip,
                    'PesoGuiaIdentificacion': guia_line.guiaid_peso,
                })

            # ── Pedimentos / Documentación aduanera ──
            # Primero: usar las sub-líneas de la pestaña Inf. Aduanera (compatibilidad)
            # Si hay pedimento directo en la línea, usarlo como adicional o único
            pedimentos = []
            for aduanera_line in line.aduanera_line_ids:
                num = aduanera_line.pedimento or ''
                if len(num) >= 15:
                    num_fmt = num[:2] + '  ' + num[2:4] + '  ' + num[4:8] + '  ' + num[8:]
                else:
                    num_fmt = num
                pedimentos.append({
                    'TipoDocumento': aduanera_line.tipo_documento_id.clave,
                    'NumPedimento': num_fmt,
                    'IdentDocAduanero': aduanera_line.id_doc_aduanero,
                    'RFCImpo': aduanera_line.rfc_import,
                })

            # Si hay pedimento directo en la línea y no está ya en la lista
            if line.pedimento and line.tipo_documento_id and not pedimentos:
                num = line.pedimento.replace(' ', '')
                if len(num) >= 15:
                    num_fmt = num[:2] + '  ' + num[2:4] + '  ' + num[4:8] + '  ' + num[8:]
                else:
                    num_fmt = line.pedimento
                pedimentos.append({
                    'TipoDocumento': line.tipo_documento_id.clave,
                    'NumPedimento': num_fmt,
                    'IdentDocAduanero': '',
                    'RFCImpo': '',
                })

            # ── CantidadTransporta ──
            transporta = []
            for transporta_line in line.transporta_line_ids:
                transporta.append({
                    'Cantidad': transporta_line.cantidad,
                    'IDOrigen': transporta_line.idorigen,
                    'IDDestino': transporta_line.iddestino,
                    'CvesTransporte': transporta_line.cves_transporte or self.tipo_transporte,
                })

            mercancia_atributos.append({
                'BienesTransp': line.product_id.unspsc_code_id.code,
                'ClaveSTCC': line.product_id.clave_stcc,
                'Descripcion': self.clean_text(line.product_id.name),
                'Cantidad': line.quantity,
                'ClaveUnidad': line.product_id.uom_id.unspsc_code_id.code,
                'Unidad': line.product_id.uom_id.name,
                'Dimensiones': line.product_id.dimensiones,
                'MaterialPeligroso': line.product_id.materialpeligroso,
                'CveMaterialPeligroso': line.product_id.clavematpeligroso.clave,
                'Embalaje': line.product_id.embalaje and line.product_id.embalaje.clave or '',
                'DescripEmbalaje': line.product_id.desc_embalaje and line.product_id.desc_embalaje or '',
                'PesoEnKg': line.pesoenkg,
                'ValorMercancia': line.price_subtotal,
                'Moneda': line.moneda,
                'FraccionArancelaria': line.product_id.l10n_mx_edi_tariff_fraction_id.code if self.transpinternac == 'Sí' else '',
                'UUIDComercioExt': self.uuidcomercioext,
                'SectorCofepris': line.product_id.SectorCofepris.clave,
                'IngredienteActivo': line.product_id.IngredienteActivo,
                'NomQuimico': line.product_id.NomQuimico,
                'DenominacionGenerica': line.product_id.DenominacionGenerica,
                'DenominacionDistintiva': line.product_id.DenominacionDistintiva,
                'Fabricante': line.product_id.Fabricante,
                'FechaCaducidad': line.product_id.FechaCaducidad,
                'LoteMedicamento': line.product_id.LoteMedicamento,
                'FormaFarmaceutica': line.product_id.FormaFarmaceutica.clave,
                'CondicionesEsp': line.product_id.CondicionesEsp.clave,
                'RegistroSanitario': line.product_id.RegistroSanitario,
                'PermisoImportacion': line.product_id.PermisoImportacion,
                'FolioImpoVUCEM': line.product_id.FolioImpoVUCEM,
                'NumCAS': line.product_id.NumCAS,
                'RazonSocialEmpImp': line.product_id.RazonSocialEmpImp,
                'NumRegSan': line.product_id.NumRegSan,
                'DatosFabricante': line.product_id.DatosFabricante,
                'DatosFormulador': line.product_id.DatosFormulador,
                'DatosMaquilador': line.product_id.DatosMaquilador,
                'UsoAutorizado': line.product_id.UsoAutorizado,
                'TipoMateria': line.product_id.TipoMateria.clave,
                'DescripcionMateria': line.product_id.DescripcionMateria,
                'GuiasIdentificacion': guias,
                'DocumentacionAduanera': pedimentos,
                'CantidadTransporta': transporta,
            })

        mercancias.update({'mercancia': {'atributos': mercancia_atributos}})

        # ── Tipo de transporte ──
        if self.tipo_transporte == '01':
            transpote_detalle = {
                'PermSCT': self.permisosct.clave,
                'NumPermisoSCT': self.numpermisosct,
                'IdentificacionVehicular': {
                    'ConfigVehicular': self.autotrasporte_ids.confvehicular.clave,
                    'PesoBrutoVehicular': self.autotrasporte_ids.PesoBrutoVehicular,
                    'PlacaVM': self.autotrasporte_ids.placavm,
                    'AnioModeloVM': self.autotrasporte_ids.aniomodelo,
                },
                'Seguros': {
                    'AseguraRespCivil': self.autotrasporte_ids.nombreaseg,
                    'PolizaRespCivil': self.autotrasporte_ids.numpoliza,
                    'AseguraCarga': self.nombreaseg_merc,
                    'PolizaCarga': self.numpoliza_merc,
                    'PrimaSeguro': self.primaseguro_merc,
                    'AseguraMedAmbiente': self.seguro_ambiente,
                    'PolizaMedAmbiente': self.poliza_ambiente,
                },
            }
            remolques = []
            if self.remolque_line_ids:
                for remolque in self.remolque_line_ids:
                    remolques.append({'SubTipoRem': remolque.subtipo_id.clave, 'Placa': remolque.placa})
                transpote_detalle.update({'Remolques': remolques})
            mercancias.update({'Autotransporte': transpote_detalle})

        elif self.tipo_transporte == '03':
            transpote_detalle = {
                'PermSCT': self.permisosct.clave,
                'NumPermisoSCT': self.numpermisosct,
                'MatriculaAeronave': self.matriculaaeronave,
                'NumeroGuia': self.numeroguia,
                'LugarContrato': self.lugarcontrato,
                'CodigoTransportista': self.transportista_id.codigotransportista.clave,
                'RFCEmbarcador': self.embarcador_id.vat if self.embarcador_id.country_id.l10n_mx_edi_code != 'MEX' else '',
                'NumRegIdTribEmbarc': self.embarcador_id.registro_tributario,
                'ResidenciaFiscalEmbarc': self.embarcador_id.country_id.l10n_mx_edi_code if self.embarcador_id.country_id.l10n_mx_edi_code != 'MEX' else '',
                'NombreEmbarcador': self.embarcador_id.name,
            }
            mercancias.update({'TransporteAereo': transpote_detalle})

        cartaporte31.update({'Mercancias': mercancias})

        # ── Figura transporte ──
        figuratransporte = []
        for figura in self.figuratransporte_ids:
            tipos_figura = {
                'TipoFigura': figura.tipofigura.clave,
                'RFCFigura': figura.figura_id.vat if figura.figura_id.country_id.l10n_mx_edi_code == 'MEX' else '',
                'NumLicencia': figura.figura_id.cce_licencia,
                'NombreFigura': figura.figura_id.name,
                'NumRegIdTribFigura': figura.figura_id.vat if figura.figura_id.country_id.l10n_mx_edi_code != 'MEX' else '',
                'ResidenciaFiscalFigura': figura.figura_id.country_id.l10n_mx_edi_code if figura.figura_id.country_id.l10n_mx_edi_code != 'MEX' else '',
                # El domicilio de la figura se omite en CartaPorte 3.1 (ya no es requerido)
            }
            partes = []
            for parte in figura.partetransporte:
                partes.append({'ParteTransporte': parte.clave})
            figuratransporte.append({'TiposFigura': tipos_figura, 'PartesTransporte': partes})

        cartaporte31.update({'FiguraTransporte': figuratransporte})
        res.update({'cartaporte31': cartaporte31})
        return res

    # ──────────────────────────────────────────────────────────────────────────
    # Timbrado y cancelación
    # ──────────────────────────────────────────────────────────────────────────
    def action_cfdi_generate(self):
        for invoice in self:
            if invoice.proceso_timbrado:
                return True
            else:
                invoice.write({'proceso_timbrado': True})
                self.env.cr.commit()
            if invoice.estado_factura == 'factura_correcta':
                if invoice.folio_fiscal:
                    invoice.write({'factura_cfdi': True})
                    return True
                else:
                    invoice.write({'proceso_timbrado': False})
                    self.env.cr.commit()
                    raise UserError(_('Error para timbrar factura, Factura ya generada.'))
            if invoice.estado_factura == 'factura_cancelada':
                invoice.write({'proceso_timbrado': False})
                self.env.cr.commit()
                raise UserError(_('Error para timbrar factura, Factura ya cancelada.'))

            values = invoice.to_json()
            if self.carta_porte:
                values = invoice.to_json_carta_porte(values)
            if invoice.company_id.proveedor_timbrado == 'servidor':
                url = 'https://facturacion.itadmin.com.mx/api/invoice'
            elif invoice.company_id.proveedor_timbrado == 'servidor2':
                url = 'https://facturacion2.itadmin.com.mx/api/invoice'
            else:
                invoice.write({'proceso_timbrado': False})
                self.env.cr.commit()
                raise UserError(_('Error, falta seleccionar el servidor de timbrado en la configuración de la compañía.'))

            try:
                response = requests.post(url, auth=None, data=json.dumps(values),
                                         headers={"Content-type": "application/json"})
            except Exception as e:
                error = str(e)
                invoice.write({'proceso_timbrado': False})
                self.env.cr.commit()
                if "Name or service not known" in error or "Failed to establish a new connection" in error:
                    raise UserError(_("No se pudo conectar con el servidor."))
                else:
                    raise UserError(_(error))

            if "Whoops, looks like something went wrong." in response.text:
                invoice.write({'proceso_timbrado': False})
                self.env.cr.commit()
                raise UserError(_("Error en el proceso de timbrado, espere un minuto y vuelva a intentar."))

            json_response = response.json()
            estado_factura = json_response['estado_factura']
            if estado_factura == 'problemas_factura':
                invoice.write({'proceso_timbrado': False})
                self.env.cr.commit()
                raise UserError(_(json_response['problemas_message']))

            if json_response.get('factura_xml'):
                invoice._set_data_from_xml(base64.b64decode(json_response['factura_xml']))
                file_name = invoice.number.replace('/', '_') + '.xml'
                self.env['ir.attachment'].sudo().create({
                    'name': file_name,
                    'datas': json_response['factura_xml'],
                    'res_model': self._name,
                    'res_id': invoice.id,
                    'type': 'binary',
                })

            invoice.write({'estado_factura': estado_factura, 'factura_cfdi': True, 'proceso_timbrado': False})
            invoice.message_post(body="CFDI emitido")
        return True

    def action_cfdi_cancel(self):
        for invoice in self:
            if invoice.factura_cfdi:
                if invoice.estado_factura == 'factura_cancelada':
                    pass
                if not invoice.company_id.contrasena:
                    raise UserError(_('El campo de contraseña de los certificados está vacío.'))
                domain = [
                    ('res_id', '=', invoice.id),
                    ('res_model', '=', invoice._name),
                    ('name', '=', invoice.number.replace('/', '_') + '.xml')
                ]
                xml_file = self.env['ir.attachment'].search(domain)
                if not xml_file:
                    raise UserError(_('No se encontró el archivo XML para enviar a cancelar.'))
                values = {
                    'rfc': invoice.company_id.vat,
                    'api_key': invoice.company_id.proveedor_timbrado,
                    'uuid': invoice.folio_fiscal,
                    'folio': invoice.number.replace('CT', '').replace('/', ''),
                    'serie_factura': invoice.journal_id.serie_diario or invoice.company_id.serie_factura,
                    'modo_prueba': invoice.company_id.modo_prueba,
                    'certificados': {'contrasena': invoice.company_id.contrasena},
                    'xml': xml_file[0].datas.decode("utf-8"),
                    'motivo': self.env.context.get('motivo_cancelacion', '02'),
                    'foliosustitucion': self.env.context.get('foliosustitucion', ''),
                }
                if invoice.company_id.proveedor_timbrado == 'servidor':
                    url = 'https://facturacion.itadmin.com.mx/api/refund'
                elif invoice.company_id.proveedor_timbrado == 'servidor2':
                    url = 'https://facturacion2.itadmin.com.mx/api/refund'
                else:
                    raise UserError(_('Error, falta seleccionar el servidor de timbrado.'))

                try:
                    response = requests.post(url, auth=None, data=json.dumps(values),
                                             headers={"Content-type": "application/json"})
                except Exception as e:
                    error = str(e)
                    if "Name or service not known" in error or "Failed to establish a new connection" in error:
                        raise UserError(_("No se pudo conectar con el servidor."))
                    else:
                        raise UserError(_(error))

                if "Whoops, looks like something went wrong." in response.text:
                    raise UserError(_("Error en el proceso de cancelación."))

                json_response = response.json()
                if json_response['estado_factura'] == 'problemas_factura':
                    raise UserError(_(json_response['problemas_message']))
                elif json_response.get('factura_xml', False):
                    file_name = 'CANCEL_' + invoice.number.replace('/', '_') + '.xml'
                    self.env['ir.attachment'].sudo().create({
                        'name': file_name,
                        'datas': json_response['factura_xml'],
                        'res_model': self._name,
                        'res_id': invoice.id,
                        'type': 'binary',
                    })
                invoice.write({'estado_factura': json_response['estado_factura']})

    def send_factura_mail(self):
        self.ensure_one()
        template = self.env.ref('l10n_mx_traslado.email_template_factura_traslado', False)
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)
        ctx = dict()
        ctx.update({
            'default_model': 'cfdi.traslado',
            'default_res_ids': self.ids,
            'default_use_template': bool(template),
            'default_template_id': template.id,
            'default_composition_mode': 'comment',
        })
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    def unlink(self):
        raise UserError("Los registros no se pueden borrar, solo cancelar.")

    def liberar_cfdi(self):
        for invoice in self:
            values = {
                'command': 'liberar_cfdi',
                'rfc': invoice.company_id.vat,
                'folio': invoice.number.replace('CT', '').replace('/', ''),
                'serie_factura': invoice.journal_id.serie_diario or invoice.company_id.serie_factura,
                'archivo_cer': invoice.company_id.archivo_cer.decode("utf-8"),
                'archivo_key': invoice.company_id.archivo_key.decode("utf-8"),
                'contrasena': invoice.company_id.contrasena,
            }
            url = ''
            if invoice.company_id.proveedor_timbrado == 'servidor':
                url = 'https://facturacion.itadmin.com.mx/api/command'
            elif invoice.company_id.proveedor_timbrado == 'servidor2':
                url = 'https://facturacion2.itadmin.com.mx/api/command'
            if not url:
                return
            try:
                response = requests.post(url, auth=None, data=json.dumps(values),
                                         headers={"Content-type": "application/json"})
                json_response = response.json()
            except Exception as e:
                _logger.error(e)
                json_response = {}
            if not json_response:
                return
            respuesta = json_response['respuesta']
            message_id = self.env['mymodule.message.wizard'].create({'message': respuesta})
            return {
                'name': 'Respuesta',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mymodule.message.wizard',
                'res_id': message_id.id,
                'target': 'new',
            }

    def llenar_id_ubicacion(self):
        for traslado in self:
            orig = 1
            dest = 1
            for line in traslado.ubicaciones_line_ids:
                if line.tipoubicacion == 'Origen':
                    line.idubicacion = 'OR' + str(orig).rjust(6, '0')
                    orig += 1
                else:
                    line.idubicacion = 'DE' + str(dest).rjust(6, '0')
                    dest += 1

    @api.onchange('ubicaciones_line_ids')
    def _compute_distancia(self):
        for traslado in self:
            contacto_previo = None
            for line in traslado.ubicaciones_line_ids:
                if line.tipoubicacion == 'Origen':
                    contacto_previo = line.contacto
                if line.tipoubicacion == 'Destino':
                    if contacto_previo and line.contacto:
                        if contacto_previo.cce_latitud and contacto_previo.cce_longitud and line.contacto.cce_latitud and line.contacto.cce_longitud:
                            line.distanciarecorrida = self.haversine_distance(
                                contacto_previo.cce_latitud, contacto_previo.cce_longitud,
                                line.contacto.cce_latitud, line.contacto.cce_longitud
                            )

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        R = 6371.0
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c


class CfdiTrasladoMail(models.Model):
    _name = "cfdi.traslado.mail"
    _inherit = ['mail.thread']
    _description = "CFDI Traslado Mail"

    factura_id = fields.Many2one('cfdi.traslado', string='CFDI Traslado')
    name = fields.Char(related='factura_id.number')
    partner_id = fields.Many2one(related='factura_id.partner_id')
    company_id = fields.Many2one(related='factura_id.company_id')


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _compute_attachment_ids(self):
        res = super(MailComposeMessage, self)._compute_attachment_ids()
        for rec in self:
            if self.model == 'cfdi.traslado':
                attachment_ids = []
                template_id = self.env.ref('l10n_mx_traslado.email_template_factura_traslado')
                if self.template_id.id == template_id.id:
                    res_ids = ast.literal_eval(self.res_ids)
                    for res_id in res_ids:
                        invoice = self.env[self.model].browse(res_id)
                        domain = [
                            ('res_id', '=', invoice.id),
                            ('res_model', '=', invoice._name),
                            ('name', '=', invoice.number.replace('/', '_') + '.xml')
                        ]
                        xml_file = self.env['ir.attachment'].search(domain, limit=1)
                        if xml_file:
                            attachment_ids.extend(rec.attachment_ids.ids)
                            attachment_ids.append(xml_file.id)
                    if attachment_ids:
                        rec.attachment_ids = [(6, 0, attachment_ids)]
        return res