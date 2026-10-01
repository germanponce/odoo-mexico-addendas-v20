# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError

from odoo.tools import float_is_zero, float_compare
from itertools import groupby
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)


# class L10nMxEdiDocument(models.Model):
#     _inherit = 'l10n_mx_edi.document'

#     @api.model
#     def _add_base_lines_cfdi_values(self, cfdi_values, base_lines, percentage_paid=None):
#         # EXTENDS 'l10n_mx_edi'
#         super()._add_base_lines_cfdi_values(cfdi_values, base_lines=base_lines, percentage_paid=percentage_paid)
#         conceptos_list = cfdi_values['conceptos_list']
#         print ("########## conceptos_list: ", conceptos_list)



class ProductProduct(models.Model):
    _inherit = 'product.product'

    product_multi_identification = fields.One2many('product.multi.identification',
                                             'product_id', string='No. de Identificacion')

    @api.model
    def create(self, vals):
        res = super(ProductProduct, self).create(vals)
        res.product_multi_identification.update({
            'template_multi': res.product_tmpl_id.id
        })
        return res

    def write(self, vals):
        res = super(ProductProduct, self).write(vals)
        self.product_multi_identification.update({
            'template_multi': self.product_tmpl_id.id
        })
        return res


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    template_multi_identification = fields.One2many('product.multi.identification',
                                              'template_multi',
                                              string='No. de Identificacion')

    @api.model
    def create(self, vals):
        res = super(ProductTemplate, self).create(vals)
        res.template_multi_identification.update({
            'product_id': res.product_variant_id.id
        })
        return res

    def write(self, vals):
        res = super(ProductTemplate, self).write(vals)
        if self.template_multi_identification:
            self.template_multi_identification.update({
                'product_id': self.product_variant_id.id
            })
        return res

class ProductMultiItendification(models.Model):
    _name = 'product.multi.identification'
    _description = 'Multiples No. de Identificacion por Cliente'
    _rec_name = "no_identificacion"

    no_identificacion = fields.Char('No. de Identificacion', required=True)

    product_id = fields.Many2one('product.product')
    template_multi = fields.Many2one('product.template')

    partner_id = fields.Many2one('res.partner', string="Cliente")

    def get_barcode_val(self, product):
        """returns barcode of record in self and product id"""
        return self.name, product

# ############# Productos ####################


# class ProductTemplate(models.Model):
#     _inherit ='product.template'

#     no_identificacion = fields.Char('No. de Identificacion',
#      compute='_compute_no_identificacion',
#         inverse='_set_no_identificacion', store=True)

#     def _set_no_identificacion(self):
#         self._set_product_variant_field('no_identificacion')

#     @api.depends('product_variant_ids.no_identificacion')
#     def _compute_no_identificacion(self):
#         self._compute_template_field_from_variant_field('no_identificacion')


# class ProductProduct(models.Model):
#     _inherit ='product.product'

#     no_identificacion = fields.Char('No. de Identificacion', index=True, help="Indica si tiene un no. de identificacion a reportar en el XML de timbrado.")


############# Herencia Facturas ####################


class AccountMove(models.Model):
    _inherit ='account.move'

    payment_conditions = fields.Text('Condiciones de Pago', help="Indica si tiene condiciones especiales a reportar en el XML de timbrado.")

    def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values, percentage_paid=None, global_invoice=False):


        # EXTENDS 'l10n_mx_edi'
        self.ensure_one()
        super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values, percentage_paid=percentage_paid, global_invoice=global_invoice)
        if cfdi_values.get('errors'):
            return

        if self.payment_conditions:
            cfdi_values['condiciones_de_pago'] =  self.payment_conditions

            conceptos_list = cfdi_values.get('conceptos_list',[])
            for conceptoline in conceptos_list:      
                invoice_line = conceptoline['line']['record'] 
                partner_id = invoice_line.move_id.partner_id
                no_identificacion_generic = ""
                no_identificacion = ""
                if invoice_line:
                    if invoice_line.product_id:
                        product_id = invoice_line.product_id
                        product_multi_identification = product_id.product_multi_identification
                        if product_multi_identification:
                            for no_identf in product_multi_identification:
                                if no_identf.partner_id == partner_id:
                                    no_identificacion = no_identf.no_identificacion
                                if not no_identf.partner_id:
                                    no_identificacion_generic = no_identf.no_identificacion
                if not no_identificacion and no_identificacion_generic:
                    no_identificacion = no_identificacion_generic
                if no_identificacion:
                    conceptoline['no_identificacion'] = no_identificacion  # Cambiar la unidad
                    
        return cfdi_values
