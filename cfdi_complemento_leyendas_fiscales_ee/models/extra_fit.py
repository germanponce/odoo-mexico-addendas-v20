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

from lxml.objectify import fromstring
from odoo import api, fields, models

from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    complemento_leyendas_fiscales = fields.Boolean('C. Leyendas Fiscales', help='Este Campo activa el complemento Leyendas Fiscales en el XML durante la Facturacion.')

    leyendas_fiscales_ids = fields.Many2many('complemento.leyenda.fiscal', 'invoice_leyendas_rel', 'move_id',
        'leyenda_id', 'Leyendas Fiscales')


    @api.constrains('leyendas_fiscales_ids','complemento_leyendas_fiscales')
    def _constraint_complemento_leyendas_fiscales(self):
        if self.complemento_leyendas_fiscales and not self.leyendas_fiscales_ids and not self.partner_id.leyendas_fiscales_ids:
            raise UserError("Si se habilita el complemento de leyendas fiscales, debes ingresar las leyendas fiscales que incluira el comprobante o en el Cliente.\nPestaña -> Leyendas Fiscales.")
        return True
    

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id.leyendas_fiscales_ids:
            self.complemento_leyendas_fiscales = True
            leyendas_ids = [x.id for x in self.partner_id.leyendas_fiscales_ids]
            self.leyendas_fiscales_ids = [(6,0, leyendas_ids)]
            # self.leyendas_fiscales_ids = self.partner_id.leyendas_fiscales_ids
        return super()._onchange_partner_id()

    # def _l10n_mx_edi_decode_cfdi(self, cfdi_data=None):
    #     """If the CFDI was signed, try to adds the schemaLocation correctly"""
    #     result = super()._l10n_mx_edi_decode_cfdi(cfdi_data=cfdi_data)
    #     if not cfdi_data:
    #         return result
    #     if not isinstance(cfdi_data, bytes):
    #         cfdi_data = cfdi_data.encode()
    #     cfdi_data = cfdi_data.replace(b'xmlns__leyendasFisc', b'xmlns:leyendasFisc')
    #     cfdi = fromstring(cfdi_data)
    #     if 'leyendasFisc' not in cfdi.nsmap:
    #         return result
    #     cfdi.attrib['{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'] = '%s %s %s' % (
    #         cfdi.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'),
    #         'http://www.sat.gob.mx/leyendasFiscales',
    #         'http://www.sat.gob.mx/sitio_internet/cfd/leyendasFiscales/leyendasFisc.xsd')
    #     result['cfdi_node'] = cfdi
    #     return result

    @api.model
    def create(self, vals):
        if not vals.get('leyendas_fiscales_ids') and vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id'])
            if partner.complemento_leyendas_fiscales:
                vals.update({
                                'leyendas_fiscales_ids': [(6, 0, partner.leyendas_fiscales_ids.ids)],
                                'complemento_leyendas_fiscales': True,
                            })
        return super().create(vals)

    def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values, percentage_paid=None, global_invoice=False):
        # EXTENDS 'l10n_mx_edi'
        self.ensure_one()
        super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values, percentage_paid=percentage_paid, global_invoice=global_invoice)
        if cfdi_values.get('errors'):
            return
        if self.complemento_leyendas_fiscales:
            cfdi_values['complemento_leyendas_fiscales'] = True
        else:
            cfdi_values['complemento_leyendas_fiscales'] = False
        if self.complemento_leyendas_fiscales:
            cfdi_values['leyendas_fiscales_ids'] = self.leyendas_fiscales_ids

class ComplementoLeyendaFiscal(models.Model):
    _name = 'complemento.leyenda.fiscal'
    _description = 'Normativas para agregar al Complemento'
    _rec_name = 'disposicion' 

    partner_id = fields.Many2one('res.partner', 'ID Ref')

    norma = fields.Char('Norma', size=128)
    disposicion = fields.Char('Disposicion Fiscal')
    texto_leyenda = fields.Char('Texto Leyenda', size=128, required=True)
