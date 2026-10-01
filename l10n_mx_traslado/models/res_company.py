# -*- coding: utf-8 -*-
import base64
import json
import requests
from odoo import fields, models,api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil import parser

class ResCompany(models.Model):
    _inherit = 'res.company'

    proveedor_timbrado= fields.Selection(
        selection=[('servidor', 'Principal'),
                   ('servidor2', 'Respaldo'),],
        string='Servidor de timbrado', default='servidor'
    )
    api_key = fields.Char('API Key')
    modo_prueba = fields.Boolean('Modo prueba')
    regimen_fiscal = fields.Selection(
        selection=[('601', 'General de Ley Personas Morales'),
                   ('603', 'Personas Morales con Fines no Lucrativos'),
                   ('605', 'Sueldos y Salarios e Ingresos Asimilados a Salarios'),
                   ('606', 'Arrendamiento'),
                   ('608', 'Demás ingresos'),
                   ('609', 'Consolidación'),
                   ('610', 'Residentes en el Extranjero sin Establecimiento Permanente en México'),
                   ('611', 'Ingresos por Dividendos (socios y accionistas)'),
                   ('612', 'Personas Físicas con Actividades Empresariales y Profesionales'),
                   ('614', 'Ingresos por intereses'),
                   ('616', 'Sin obligaciones fiscales'),
                   ('620', 'Sociedades Cooperativas de Producción que optan por diferir sus ingresos'),
                   ('621', 'Incorporación Fiscal'),
                   ('622', 'Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras'),
                   ('623', 'Opcional para Grupos de Sociedades'),
                   ('624', 'Coordinados'),
                   ('628', 'Hidrocarburos'),
                   ('607', 'Régimen de Enajenación o Adquisición de Bienes'),
                   ('629', 'De los Regímenes Fiscales Preferentes y de las Empresas Multinacionales'),
                   ('630', 'Enajenación de acciones en bolsa de valores'),
                   ('615', 'Régimen de los ingresos por obtención de premios'),
                   ('625', 'Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas'),
                   ('626', 'Régimen Simplificado de Confianza'),],
        string='Régimen Fiscal', 
    )
    archivo_cer = fields.Binary('Archivo .cer')
    archivo_key = fields.Binary('Archivo .key')
    contrasena = fields.Char('Contraseña')
    nombre_fiscal = fields.Char('Razón social')
    saldo_timbres =  fields.Float('Saldo de timbres', readonly=True)
    saldo_alarma =  fields.Float('Alarma timbres', default=10)
    correo_alarma =  fields.Char('Correo de alarma')

    rfc_patron = fields.Char('RFC Patrón')
    serie_timbrado = fields.Char('Serie traslado')
    registro_patronal = fields.Char('Registro patronal')
    fecha_csd = fields.Datetime('Vigencia CSD', readonly=True)
    estado_csd =  fields.Char('Estado CSD', readonly=True)
    aviso_csd =  fields.Char('Aviso vencimiento (días antes)', default=14)

    @api.model
    def get_saldo_by_cron(self):
        companies = self.search([('proveedor_timbrado','!=',False)])
        for company in companies:
            company.get_saldo()
            if company.saldo_timbres < company.saldo_alarma and company.correo_alarma:
                email_template = self.env.ref("nomina_cfdi_ee.email_template_alarma_de_saldo",False)
                if not email_template:return
                emails = company.correo_alarma.split(",")
                for email in emails:
                    email = email.strip()
                    if email:
                        email_template.send_mail(company.id, force_send=True,email_values={'email_to':email})
            if company.aviso_csd and company.fecha_csd and company.correo_alarma: #valida vigencia de CSD
                if datetime.today() + timedelta(days=int(company.aviso_csd)) > fields.Datetime.from_string(company.fecha_csd):
                   email_template = self.env.ref("nomina_cfdi_ee.email_template_alarma_de_csd",False)
                   if not email_template:return
                   emails = company.correo_alarma.split(",")
                   for email in emails:
                       email = email.strip()
                       if email:
                          email_template.send_mail(company.id, force_send=True,email_values={'email_to':email})
        return True

    def get_saldo(self):
        if not self.vat:
           raise UserError(_('Falta colocar el RFC'))
        if not self.proveedor_timbrado:
           raise UserError(_('Falta seleccionar el proveedor de timbrado'))
        values = {
                 'rfc': self.vat,
                 'api_key': self.proveedor_timbrado,
                 'modo_prueba': self.modo_prueba,
                 }
        url=''
        if self.proveedor_timbrado == 'servidor':
            url = '%s' % ('https://facturacion.itadmin.com.mx/api/saldo')

        if not url:
            return
        try:
            response = requests.post(url,auth=None,data=json.dumps(values),headers={"Content-type": "application/json"})
            json_response = response.json()
        except Exception as e:
            print(e)
            json_response = {}

        if not json_response:
            return

        estado_factura = json_response['estado_saldo']
        if estado_factura == 'problemas_saldo':
            raise UserError(_(json_response['problemas_message']))
        if json_response.get('saldo'):
            xml_saldo = base64.b64decode(json_response['saldo'])
        values2 = {
                    'saldo_timbres': xml_saldo
                  }
        self.update(values2)

    def validar_csd(self):
        values = {
                 'rfc': self.vat,
                 'archivo_cer': self.archivo_cer.decode("utf-8"),
                 'archivo_key': self.archivo_key.decode("utf-8"),
                 'contrasena': self.contrasena,
                 }
        url=''
        if self.proveedor_timbrado == 'servidor':
            url = '%s' % ('https://facturacion.itadmin.com.mx/api/validarcsd')
        elif self.proveedor_timbrado == 'servidor2':
            url = '%s' % ('https://facturacion2.itadmin.com.mx/api/validarcsd')
        if not url:
            return
        try:
            response = requests.post(url,auth=None,data=json.dumps(values),headers={"Content-type": "application/json"})
            json_response = response.json()
        except Exception as e:
            print(e)
            json_response = {}

        if not json_response:
            return
        #_logger.info('something ... %s', response.text)

        respuesta = json_response['respuesta']
        if json_response['respuesta'] == 'Certificados CSD correctos':
           self.fecha_csd = parser.parse(json_response['fecha'])
           values2 = {
               'fecha_csd': self.fecha_csd,
               'estado_csd': json_response['respuesta'],
               }
           self.update(values2)
        else:
           raise UserError(respuesta)

    def borrar_csd(self):
        values = {
                 'rfc': self.vat,
                 }
        url=''
        if self.proveedor_timbrado == 'servidor':
            url = '%s' % ('https://facturacion.itadmin.com.mx/api/borrarcsd')
        elif self.proveedor_timbrado == 'servidor2':
            url = '%s' % ('https://facturacion2.itadmin.com.mx/api/borrarcsd')
        if not url:
            return
        try:
            response = requests.post(url,auth=None,data=json.dumps(values),headers={"Content-type": "application/json"})
            json_response = response.json()
        except Exception as e:
            print(e)
            json_response = {}

        if not json_response:
            return
        #_logger.info('something ... %s', response.text)
        respuesta = json_response['respuesta']
        raise UserError(respuesta)

    def borrar_estado(self):
           values2 = {
               'fecha_csd': '',
               'estado_csd': '',
               }
           self.update(values2)

    def button_dummy(self):
        self.get_saldo()
        return True
