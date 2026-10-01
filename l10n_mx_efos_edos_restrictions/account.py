# -*- encoding: utf-8 -*-
###########################################################################
##################### GERMAN PONCE DOMINGUEZ ##############################
###################### german.ponce@outlook.com ###########################

from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import datetime
import logging

_logger = logging.getLogger(__name__)
from datetime import datetime, date

import csv
import requests


class AccountMove(models.Model):
    _inherit ='account.move'

    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_efos_edos(self):
        if self.partner_id:
            cr = self.env.cr
            vat = self.partner_id.vat
            vat = vat.replace(' ','').upper()
            if vat:
                cr.execute("""
                    select rfc from res_partner_efo_edo where UPPER(rfc)=%s and omitir_validacion=False;
                    """, (vat, ))
                cr_res = cr.fetchall()
                if cr_res and cr_res[0] and cr_res[0][0]:
                    raise UserError("El RFC del cliente seleccionado corresponde a una empresa dentro del listado de EFOS y EDOS.")
        res = super(AccountMove, self)._onchange_partner_id()
        return res


    def action_post(self):
        cr = self.env.cr
        for rec in self:
            if rec.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                vat = rec.partner_id.vat
                vat = vat.replace(' ','').upper()
                if vat:
                    cr.execute("""
                        select rfc from res_partner_efo_edo where UPPER(rfc)=%s and omitir_validacion=False;
                        """, (vat, ))
                    cr_res = cr.fetchall()
                    if cr_res and cr_res[0] and cr_res[0][0]:
                        raise UserError("El RFC del cliente seleccionado corresponde a una empresa dentro del listado de EFOS y EDOS.")
        
        result = super(AccountMove, self).action_post()
        return result

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit ='res.partner'

    status_ok = fields.Char('Status', help='Indica que el registro no tiene problemas de EFOS o EDOS.', default='OK')
   

    def button_info_efo(self):
        raise UserError("El registro se encuentra dentro del listado de EFOS y EDOS.")
    

    @api.constrains('vat')
    def _constraint_efo_edo(self):
        cr = self.env.cr
        for rec in self:
            vat = rec.vat
            vat = vat.replace(' ','').upper()
            if vat:
                cr.execute("""
                    select rfc from res_partner_efo_edo where UPPER(rfc)=%s and omitir_validacion=False;
                    """, (vat, ))
                cr_res = cr.fetchall()
                if cr_res and cr_res[0] and cr_res[0][0]:
                    raise UserError("El RFC ingresado corresponde a una empresa dentro del listado de EFOS y EDOS.")
                
                cr.execute("""
                    select rfc from res_partner_efo_edo where UPPER(rfc)=%s;
                    """, (vat, ))
                cr_res = cr.fetchall()
                if cr_res and cr_res[0] and cr_res[0][0]:
                    rec.status_ok='ADVERTENCIA'

        return True
    

    #### Consulta Automatica de Descargas
    @api.model
    def _run_download_efos_edos_list_from_sat(self):
        _logger.info("\n:::::::::::::::::::::::::: Descargando el listado de EFOs y EDOS del portal del SAT. Fecha: %s >>>>>>>  " % fields.Date.context_today(self))
        cr = self.env.cr
        efo_edo_obj = self.env['res.partner.efo.edo']
        CSV_URL = 'http://omawww.sat.gob.mx/cifras_sat/Documents/Listado_Completo_69-B.csv'
        try:
            list_final_vals_efos_edos = []
            with requests.Session() as s:
                download = s.get(CSV_URL)
                decoded_content = download.content.decode('ISO-8859-1')
                cr_csv = csv.reader(decoded_content.splitlines(), delimiter=',')
                my_list = list(cr_csv)
                # my_list = my_list[0:10]
                i = 0
                for row in my_list:
                    if i > 2:
                        vals = {
                                'name': row[2],
                                'rfc': row[1],
                                'situacion': row[3],
                                'numero_fecha': row[4],
                                'omitir_validacion': False,
                        }
                        list_final_vals_efos_edos.append(vals)
                    else:
                        _logger.info("\n:::::::::::::::::::::::::: Cabeceras del CSV: %s >>>>>>>  " % row)
                    i+=1
            if list_final_vals_efos_edos:
                cr.execute("""
                    delete from res_partner_efo_edo;
                    """)
                cr.execute("""
                    update res_partner set status_ok='OK';
                    """)
                for vals_efo_edo in list_final_vals_efos_edos:
                    efo_edo_obj.create(vals_efo_edo)
                cr.execute("""
                    update res_partner set status_ok='ADVERTENCIA'
                           Where vat in (select rfc from res_partner_efo_edo);
                    """)
        except:
            _logger.info("\n:::::::::::::::::::::::::: No se pudo obtener el CSV de EFOS y EDOS, revise la url del archivo %s. Fecha: %s >>>>>>>  " % (CSV_URL, fields.Date.context_today(self)))

class ResPartnerEfoEdo(models.Model):
    _name = 'res.partner.efo.edo'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Registros de la lista de EFOs y EDOs publicada SAT'
    
    name = fields.Char('Nombre', size=128)
    rfc = fields.Char('RFC', size=64)
    situacion = fields.Char('Situación del contribuyente', size=128)
    numero_fecha = fields.Char('Número y fecha de oficion', size=128)
    omitir_validacion = fields.Boolean('No validar', help='Si se habilita este campo aunque el cliente se encuentre en el listado se podra seleccionar.', track_visibility="onchange")