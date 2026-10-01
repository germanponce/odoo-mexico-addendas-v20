# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import re

# Expresion Regular para el Pedimento #
_estructura_pedimento = re.compile('[0-9]{2}\s{2}[0-9]{2}\s{2}[0-9]{4}\s{2}[0-9]{7}')
#_no_identify = re.compile('([A-Z]|[a-z]|[0-9]||Ñ|ñ|!|&quot;|%|&amp;|&apos;| ́|-|:|;|&gt;|=|&lt;|@|_|,|\{|\}|`|~|á|é|í|ó|ú|Á|É|Í|Ó|Ú|ü|Ü){1,100}')


class import_info(models.Model):
    _name = "import.info"
    _description = "Information about customs"
    _order = 'name asc'

    
    name        = fields.Char(string='Número Pedimento', size=64, help="Número de Pedimento o Trámite aduanal", required=True, index=True)
    customs     = fields.Char(string='Aduana', size=64, help="Aduana usada para la importación de los productos")
    date        = fields.Date(string='Fecha', help="Fecha del Pedimento", index=True)
    package_ids = fields.One2many('stock.quant.package', 'import_id', string='Paquetes')
    lot_ids     = fields.One2many('stock.lot', 'import_id', string='Lotes')
    rate        = fields.Float(string='Tipo de Cambio', required=True, digits=(16, 4),
                               help='Tipo de Cambio utilizado en el Pedimento Aduanal')
    company_id  = fields.Many2one('res.company', string='Compañía', required=True, 
                                  default=lambda self: self.env.user.company_id.id)
    supplier_id = fields.Many2one('res.partner', string='Agencia Aduanal', index=True, 
                                  help="Agencia aduanal con la que se realizó el trámite de importación ...")
    invoice_ids = fields.Many2many('account.move', 'account_invoice_rel', 'import_id', 'invoice_id', 
                                   string='Facturas relacionadas')
    notes       = fields.Text('Observaciones')


    sat_aduana_id = fields.Char('Aduana')    
    import_consol = fields.Boolean('Pedimento Consolidado', help='Los Pedimentos Consolidados tienen como fin una estructura especial para registrar el Numero de Pedimento en el CFDI, el cual omite algunos valores.', )

    @api.onchange('sat_aduana_id')
    def onchange_sat_aduana_id(self):
        if self.sat_aduana_id:
            self.customs = self.sat_aduana_id


    @api.constrains('name','import_consol')
    def _check_pedimento(self):
        for rec in self:
            if self.import_consol == False:
                if not _estructura_pedimento.match(self.name):
                    raise ValidationError(_('Error!\nLa estructura del Pedimento debe ser de la siguiente manera:\nUltimos 2 Digitos del año de validacion seguidos por 2 espacios, 2 Digitos de la Aduana seguidos por 2 espacios, 4 Digitos del Numero de la Patente seguidos por 2 espacios, 1 Digito del año en curso seguido por 6 Digitos de la Numeracion progresiva de Aduana.\n Ej.15  48  3009  0001234'))                
                
    