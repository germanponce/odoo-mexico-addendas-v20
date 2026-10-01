# -*- encoding: utf-8 -*-

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning
from odoo import api, exceptions, fields, models, _
#import odoo.addons.decimal_precision as dp
import time
from datetime import datetime, timedelta
import base64
import os
import zipfile
import subprocess
import tempfile
from xml.dom.minidom import parse, parseString
from suds.client import Client
import logging
_logger = logging.getLogger(__name__)


    
class AccountInvoice(models.Model):
    _inherit = "account.move"    
    
    cfdi_id = fields.Many2one('account.cfdi', string="CFDI", required=False)


class AccountPayment(models.Model):
    _inherit = "account.payment"    
    
    cfdi_id = fields.Many2one('account.cfdi', string="CFDI", required=False)
    
    
"""
class EaccountComplements(models.Model):
    _inherit = "eaccount.complements" 
    
    cfdi_id = fields.Many2one('account.cfdi', string="CFDI", required=False)    
"""

    
    
class AccountCFDI(models.Model):
    _name = "account.cfdi"
    _description="CFDIs que se importan del SAT"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    _rec_name = 'folio_fiscal'
    
    state       = fields.Selection([('draft','Por Revisar'),
                                    ('error01','No existe en Odoo'),
                                    ('error02','Error en Factura: Existe mas de una vez en las Facturas'),
                                    ('error03','Error en Factura: El total de la factura no es igual al total del CFDI'),
                                    ('error04','Error en Factura: La moneda de la factura no es igual a la Moneda del CFDI'),
                                    ('error05','Error en Factura: La factura está Cancelada pero el CFDI esta Vigente'),
                                    ('error06','Error en Factura: La factura está Vigente pero el CFDI esta Cancelado'),
                                    ('error10','Error en Pagos: Existe mas de una vez en los Pagos'),
                                    ('error11','Error en Pagos: El monto del Pago no es igual al Monto del Complemento de Pagos del CFDI'),
                                    ('error12','Error en Pagos: La moneda del Pago no es igual a la Moneda del CFDI'),
                                    ('error13','Error en Pagos: El pago está Cancelado pero el CFDI esta Vigente'),
                                    ('error14','Error en Pagos: El pago está Vigente pero el CFDI esta Cancelado'),
                                    ('error20','Error en Complemento de CE: EL UUID existe mas de una vez en una misma póliza'),
                                    ('error21','Error en Complemento de CE: La moneda del Complemento no es igual a la moneda del CFDI'),
                                      ('ok','OK'),
                                      ('error','Error')], 
                                   tracking=True,
                                   string="Estado", required=True, default='draft', readonly=True)
    notes       = fields.Text(string='Observaciones')
    invoice_ids = fields.One2many('account.move', 'cfdi_id', string='Facturas', required=False, readonly=True)
    payment_ids = fields.One2many('account.payment', 'cfdi_id', string='Pagos', required=False, readonly=True)
    #aml_ids     = fields.One2many('account.move.line', 'cfdi_id', string='Partidas Contables', required=False, readonly=True)
    #aml_complement_ids   = fields.One2many('eaccount.complements', 'cfdi_id', string='Complementos de Cont.Elect.',
    #                                                     required=False, readonly=True)
    
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, 
                                 default=lambda self: self.env.user.company_id)
    company_partner_id = fields.Many2one('res.partner', string='Partner', related='company_id.partner_id', readonly=True, store=True)
    company_vat = fields.Char(string='RFC Company', related='company_partner_id.vat', store=True)
    clasificacion_cfdi = fields.Selection([
                                    ('01','Estándar (sin complemento)'),
                                    ('02','Acreditamiento de IEPS'),
                                    ('03','Aerolíneas'),
                                    ('04','Certificado de Destrucción'),
                                    ('05','Comercio Exterior'),
                                    ('06','Comercio Exterior 1.1'),
                                    ('07','Compra Venta de Divisas'),
                                    ('08','Consumo de Combustibles'),
                                    ('09','Donatarias'),
                                    ('10','Estado de Cuenta Bancario'),
                                    ('11','Estado de cuenta de combustibles de monederos electrónicos'),
                                    ('12','INE 1.1'),
                                    ('13','Instituciones Educativas Privadas (Pago de colegiatura)'),
                                    ('14','Leyendas Fiscales'),
                                    ('15','Mis Cuentas'),
                                    ('16','Notarios Públicos'),
                                    ('17','Obras de arte y antigüedades'),
                                    ('18','Otros Derechos e Impuestos'),
                                    ('19','Pago en Especie'),
                                    ('20','Persona Física Integrante de Coordinado'),
                                    ('21','Recepción de Pagos'),
                                    ('22','Recibo de donativo'),
                                    ('23','Recibo de Pago de Salarios'),
                                    ('24','Recibo de Pago de Salarios 1.2'),
                                    ('25','Sector de Ventas al Detalle (Detallista)'),
                                    ('26','Servicios de construcción'),
                                    ('27','SPEI de Tercero a Tercero'),
                                    ('28','Sustitución y renovación vehicular'),
                                    ('29','Terceros'),
                                    ('30','Timbre Fiscal Digital'),
                                    ('31','Turista o Pasajero Extranjero'),
                                    ('32','Vales de Despensa'),
                                    ('33','Vehículo Usado'),
                                    ('34','Venta de Vehículos'),
                                    ('cfdi32','No aplica. Es CFDI 3.2')], string="Clasificación CFDI", default='cfdi32', readonly=True)
    
    
    tipo_cfdi = fields.Selection([('INGRESO','Ingreso (3.2)'),
                                  ('EGRESO','Egreso (3.2)'),
                                  ('TRASLADO','Traslado (3.2)'),
                                  ('I','Ingreso'),
                                  ('E','Egreso'),
                                  ('T','Traslado'),
                                  ('N','Nómina'),
                                  ('P','Pago')], string="Tipo CFDI", readonly=True)
        
    uso_cfdi = fields.Selection([('G01','Adquisición de mercancias'),
                                ('G02','Devoluciones, descuentos o bonificaciones'),
                                ('G03','Gastos en general'),
                                ('I01','Construcciones'),
                                ('I02','Mobilario y equipo de oficina por inversiones'),
                                ('I03','Equipo de transporte'),
                                ('I04','Equipo de computo y accesorios'),
                                ('I05','Dados, troqueles, moldes, matrices y herramental'),
                                ('I06','Comunicaciones telefónicas'),
                                ('I07','Comunicaciones satelitales'),
                                ('I08','Otra maquinaria y equipo'),
                                ('D01','Honorarios médicos, dentales y gastos hospitalarios.'),
                                ('D02','Gastos médicos por incapacidad o discapacidad'),
                                ('D03','Gastos funerales.'),
                                ('D04','Donativos.'),
                                ('D05','Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación).'),
                                ('D06','Aportaciones voluntarias al SAR.'),
                                ('D07','Primas por seguros de gastos médicos.'),
                                ('D08','Gastos de transportación escolar obligatoria.'),
                                ('D09','Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones.'),
                                ('D10','Pagos por servicios educativos (colegiaturas)'),
                                ('CP01','Pagos'),
                                ('CN01','Nómina'),
                                ('S01','Sin efectos fiscales'),
                                ('cfdi32','No aplica. Es CFDI 3.2')], string="Uso CFDI", default='cfdi32', readonly=True)
    
    sat_estado   = fields.Selection([('vigente', 'Vigente'),
                                     ('cancelado', 'Cancelado'),
                                     ('error', 'No se pudo validar'),
                                     ('por_revisar', 'Por Revisar'),
                                     ('no_encontrado', 'No encontrado'),], tracking=True, default='por_revisar',
                                        string='Vigencia CFDI', required=False, index=True, readonly=True)
    date_sat_estado   = fields.Datetime(string='Fecha Revisión Vigencia', required=False, 
                                        help="Fecha en que se revisó si el CFDI estaba Vigente en el portal del SAT", readonly=True, tracking=True)

    
    folio_fiscal  = fields.Char(string="Folio Fiscal (UUID)", required=True, index=True, readonly=True)
    subtotal      = fields.Float(string="SubTotal", default=0.0, required=True, digits=(18,4), readonly=True)
    total         = fields.Float(string="Total", default=0.0, required=True, digits=(18,4), readonly=True)
    monto_pago    = fields.Float(string="Monto Pago", default=0.0, required=True, digits=(18,4), readonly=False)
    pago_currency_id = fields.Many2one('res.currency', string="Moneda Pago", readonly=True,
                                      default=lambda self: self.env.user.company_id.currency_id)  
    fecha_emision = fields.Datetime(string='Fecha Emisión', required=True, readonly=True)
    fecha_certificacion   = fields.Datetime(string='Fecha Certificación', required=True, readonly=True)
    rfc_emisor   = fields.Char(string="RFC Emisor", required=True, index=True, readonly=True)
    rfc_receptor = fields.Char(string="RFC Receptor", required=True, index=True, readonly=True)
    razon_social_emisor = fields.Char(string="Razón Social Emisor", index=True, readonly=True)
    razon_social_receptor = fields.Char(string="Razón Social Receptor", index=True, readonly=True)
    serie = fields.Char(string="Serie", readonly=True)
    folio = fields.Char(string="Folio", readonly=True)
    currency_id = fields.Many2one('res.currency', string="Moneda CFDI", readonly=True,
                                      default=lambda self: self.env.user.company_id.currency_id)  
    currency_name = fields.Char(string="Moneda CFDI Texto ", readonly=True)
    no_certificado  = fields.Char(string='Certificado', readonly=True)
    pay_method      = fields.Char(string='Método de Pago', readonly=True)
    date_audit      = fields.Datetime(string='Fecha auditoría', required=False, readonly=True, tracking=True)
    filename        = fields.Char(string='Nombre Archivo')
    file            = fields.Binary(string='Archivo XML')

    cfdi_version = fields.Char('Versión CFDI')
    _sql_constraints = [
        ('folio_fiscal_uniq', 'unique (folio_fiscal)', "Folio Fiscal (UUID) ya existe!"),
    ]


class AccountCFDItWizardZipFile(models.TransientModel):
    _name = 'account.cfdi.wizard.zipfile'
    _description = 'Wizard para importar los CFDIs descargados del SAT'
    
    zip_file        = fields.Binary(string='Archivo ZIP', required=True, 
                                    help='Seleccione el archivo ZIP exportado del portal del SAT')                


class AccountCFDItWizardAudit(models.TransientModel):
    _name = 'account.cfdi.wizard.audit'
    _description = 'Wizard para Auditar los CFDIs descargados del SAT'
    

    def audit_cfdis(self):
        cfdi_ids =  self._context.get('active_ids',[])
        return self.env['account.cfdi'].browse(cfdi_ids).audit_cfdis()

        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:        