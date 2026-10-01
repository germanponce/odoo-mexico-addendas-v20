# -*- coding: utf-8 -*-

from odoo import fields, models, api,_

class ResPartner(models.Model):
    _inherit = 'res.partner'

    codigotransportista = fields.Many2one('cve.codigo.transporte.aereo',string='Código transportista')
    cce_licencia = fields.Char('No. licencia')
    cce_latitud = fields.Float('Latitud', digits = (12,6))
    cce_longitud = fields.Float('Longitud', digits = (12,6))
