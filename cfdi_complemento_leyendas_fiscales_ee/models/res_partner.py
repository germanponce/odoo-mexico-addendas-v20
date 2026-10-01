# -*- encoding: utf-8 -*-
# Coded by German Ponce Dominguez 
#     ▬▬▬▬▬.◙.▬▬▬▬▬  
#       ▂▄▄▓▄▄▂  
#    ◢◤█▀▀████▄▄▄▄▄▄ ◢◤  
#    █▄ █ █▄ ███▀▀▀▀▀▀▀ ╬  
#    ◥ █████ ◤  
#     ══╩══╩═  
#       ╬═╬  
#       ╬═╬ Dream big and start with something small!!!  
#       ╬═╬  
#       ╬═╬ You can do it!  
#       ╬═╬   Let's go...
#    ☻/ ╬═╬   
#   /▌  ╬═╬   
#   / \
# Cherman Seingalt - german.ponce@outlook.com

from odoo import api, fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit ='res.partner'

    complemento_leyendas_fiscales = fields.Boolean('C. Leyendas Fiscales', help='Este Campo activa el complemento Leyendas Fiscales en el XML durante la Facturacion.')

    leyendas_fiscales_ids = fields.One2many('complemento.leyenda.fiscal', 'partner_id', 'Leyendas Fiscales')


    @api.constrains('leyendas_fiscales_ids','complemento_leyendas_fiscales')
    def _constraint_complemento_leyendas_fiscales(self):
        if self.complemento_leyendas_fiscales and not self.leyendas_fiscales_ids:
            raise UserError("Si se habilita el complemento de leyendas fiscales, debes ingresar las leyendas fiscales que incluira el comprobante.\nPestaña -> Leyendas Fiscales.")
        return True
    