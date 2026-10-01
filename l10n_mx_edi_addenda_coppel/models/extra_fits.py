# -*- coding: utf-8 -*-

import re
from odoo import models, fields, api, _
from odoo.tools.misc import ustr
from odoo.exceptions import ValidationError

from odoo.tools.float_utils import float_repr
import base64
import requests

from lxml import etree
from lxml.objectify import fromstring
from pytz import timezone
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.tools.xml_utils import _check_with_xsd

from io import BytesIO
from zeep import Client

class AddendaCompany(models.Model):
    """docstring for AddendaCompany"""
    _inherit = 'res.company'

    x_supplier_id = fields.Char(string='Identificador Proveedor')
    x_supplier_type = fields.Char(string='Tipo de proveedor',default='2')

    x_gln = fields.Char(string='Número global de localizacion (GLN) Vendedor')


class AddendaProduct(models.Model):
    _inherit = 'product.template'
    
    x_code = fields.Char(string='Código',compute="_compute_x_code",inverse="_set_x_code", store=True)
    x_size = fields.Char(string='Talla',compute="_compute_x_size",inverse="_set_x_size", store=True)
    x_model = fields.Char(string='Modelo',compute="_compute_x_model",inverse="_set_x_model", store=True)
    x_gtin = fields.Char(string="Codigo EAN (GTIN)",compute="_compute_x_gtin",inverse="_set_x_gtin", store=True)

    @api.depends('product_variant_ids.x_gtin')
    def _compute_x_gtin(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.x_gtin = template.product_variant_ids.x_gtin
        for template in (self - unique_variants):
            template.x_gtin = False

    def _set_x_gtin(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.x_gtin = self.x_gtin

    @api.depends('product_variant_ids.x_code')
    def _compute_x_code(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.x_code = template.product_variant_ids.x_code
        for template in (self - unique_variants):
            template.x_code = False

    def _set_x_code(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.x_code = self.x_code

    @api.depends('product_variant_ids.x_size')
    def _compute_x_size(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.x_size = template.product_variant_ids.x_size
        for template in (self - unique_variants):
            template.x_size = False

    def _set_x_size(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.x_size = self.x_size

    @api.depends('product_variant_ids.x_model')
    def _compute_x_model(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.x_model = template.product_variant_ids.x_model
        for template in (self - unique_variants):
            template.x_model = False

    def _set_x_model(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.x_model = self.x_model


class AddendaProduct(models.Model):
    _inherit = 'product.product'
    
    x_code = fields.Char(string='Código', index=True)
    x_size = fields.Char(string='Talla', index=True)
    x_model = fields.Char(string='Modelo', index=True)
    x_gtin = fields.Char(string="Codigo EAN (GTIN)", index=True)

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'

    addenda_type = fields.Selection(selection_add=[('coppel', 'Coppel')], ondelete={'coppel': 'set null'}) 

    x_order_no = fields.Char(string='Num. Pedido')
    x_warehouse_code = fields.Char(string='Num. Bodega')
    x_name_warehouse = fields.Char(string='Nombre bodega')
    x_street_warehouse = fields.Char(string='Calle bodega')
    x_city_warehouse = fields.Char(string='Ciudad bodega')
    x_zip_warehouse = fields.Char(string='C.P. bodega')

    x_qty_lote = fields.Integer(string='Total de lotes')

    x_reference_date = fields.Date('Fecha Referencia')

    x_fecha_promesa_ent = fields.Date('Fecha Promesa Entrega')

    x_gln = fields.Char(string='Número global de localizacion (GLN) Entrega')

    x_bodega_destino = fields.Char(string='Codigo Bodega Destino')

    x_bodega_receptora = fields.Char(string='Codigo Bodega Receptora')

    x_flete_partner_id = fields.Many2one('res.partner', 'Proveedor Flete')

class AddendaPicking(models.Model):
    _inherit = 'stock.picking'

    addenda_type = fields.Selection(selection_add=[('coppel', 'Coppel')], ondelete={'coppel': 'set null'}) 

    x_qty_lote = fields.Integer(string='Total de lotes')


class AccountMove(models.Model):
    _inherit = 'account.move'
        

    x_cadena_original = fields.Text('Cadena Original')

    addenda_type = fields.Selection(selection_add=[('coppel', 'Coppel')], ondelete={'coppel': 'set null'}) 

    x_order_no = fields.Char(string='Num. Pedido')
    x_warehouse_code = fields.Char(string='Num. Bodega')
    x_name_warehouse = fields.Char(string='Nombre bodega')
    x_street_warehouse = fields.Char(string='Calle bodega')
    x_city_warehouse = fields.Char(string='Ciudad bodega')
    x_zip_warehouse = fields.Char(string='C.P. bodega')

    x_qty_lote = fields.Integer(string='Total de lotes')

    x_reference_date = fields.Date('Fecha Referencia')

    x_fecha_promesa_ent = fields.Date('Fecha Promesa Entrega')

    x_gln = fields.Char(string='Número global de localizacion (GLN) Entrega')

    x_bodega_destino = fields.Char(string='Codigo Bodega Destino')

    x_bodega_receptora = fields.Char(string='Codigo Bodega Receptora')

    x_flete_partner_id = fields.Many2one('res.partner', 'Proveedor Flete')


    def get_invoice_lines(self):
        return self.invoice_line_ids

    # def get_cadena_original(self):
    #     cadena_original = ""
    #     for move in self:
    #         cfdi_vals = move._l10n_mx_edi_decode_cfdi()

    #         if cfdi_doc and not cfdi_doc.attachment_id:
    #             attachment = self.env['ir.attachment'].search([('name', 'like', 'xml'), ('res_model', '=', 'account.move'), ('res_id', '=', move.id)], limit=1, order='create_date desc')
    #             if attachment:
    #                 cfdi_data = base64.decodebytes(attachment.with_context(bin_size=False).datas)
    #                 cfdi_infos = move._l10n_mx_edi_decode_cfdi(cfdi_data=cfdi_data)
    #                 cadena_original = cfdi_infos.get('cadena','')

    #     return cadena_original

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            if sale_id:
                res.addenda_type = sale_id.addenda_type
                res.x_order_no = sale_id.x_order_no
                res.x_warehouse_code = sale_id.x_warehouse_code
                res.x_name_warehouse = sale_id.x_name_warehouse
                res.x_street_warehouse = sale_id.x_street_warehouse
                res.x_city_warehouse = sale_id.x_city_warehouse
                res.x_zip_warehouse = sale_id.x_zip_warehouse
                res.x_qty_lote = sale_id.x_qty_lote
                res.x_reference_date = sale_id.x_reference_date
                res.x_fecha_promesa_ent = sale_id.x_fecha_promesa_ent
                res.x_gln = sale_id.x_gln
                res.x_bodega_destino = sale_id.x_bodega_destino
                res.x_bodega_receptora = sale_id.x_bodega_receptora
                res.x_flete_partner_id = sale_id.x_flete_partner_id.id if sale_id.x_flete_partner_id else False

        return res

class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(selection_add=[('coppel', 'Coppel')], ondelete={'coppel': 'set null'}) 

    x_qty = fields.Float(string='Prepacant')
    x_quantity = fields.Float(string='Pallet Quantity')

    def _amount_with_discount(self):
        with_discount = 0.0
        for line in self:
            with_discount += line.price_unit * (1 - (line.discount or 0.0) / 100.0)
        return with_discount

    def _compute_amount_discounted(self):
        total = 0.0
        for line in self:
            total += total + line.price_unit * (1 - (line.discount or 0.0) / 100.0)
        return total