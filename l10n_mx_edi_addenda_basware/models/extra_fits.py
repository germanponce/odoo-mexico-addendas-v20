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

    x_numero_proveedor = fields.Char(string='Número Proveedor')


class AddendaProduct(models.Model):
    _inherit = 'product.template'
    
    x_codido_producto_comprador = fields.Char(string='Código Producto Comprador',compute="_compute_x_codido_producto_comprador",inverse="_set_x_codido_producto_comprador", store=True)
    # x_size = fields.Char(string='Talla',compute="_compute_x_size",inverse="_set_x_size", store=True)
    # x_model = fields.Char(string='Modelo',compute="_compute_x_model",inverse="_set_x_model", store=True)
    # x_gtin = fields.Char(string="Codigo EAN (GTIN)",compute="_compute_x_gtin",inverse="_set_x_gtin", store=True)

    # @api.depends('product_variant_ids.x_gtin')
    # def _compute_x_gtin(self):
    #     unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
    #     for template in unique_variants:
    #         template.x_gtin = template.product_variant_ids.x_gtin
    #     for template in (self - unique_variants):
    #         template.x_gtin = False

    # def _set_x_gtin(self):
    #     if len(self.product_variant_ids) == 1:
    #         self.product_variant_ids.x_gtin = self.x_gtin

    @api.depends('product_variant_ids.x_codido_producto_comprador')
    def _compute_x_codido_producto_comprador(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.x_codido_producto_comprador = template.product_variant_ids.x_codido_producto_comprador
        for template in (self - unique_variants):
            template.x_codido_producto_comprador = False

    def _set_x_codido_producto_comprador(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.x_codido_producto_comprador = self.x_codido_producto_comprador

    # @api.depends('product_variant_ids.x_size')
    # def _compute_x_size(self):
    #     unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
    #     for template in unique_variants:
    #         template.x_size = template.product_variant_ids.x_size
    #     for template in (self - unique_variants):
    #         template.x_size = False

    # def _set_x_size(self):
    #     if len(self.product_variant_ids) == 1:
    #         self.product_variant_ids.x_size = self.x_size

    # @api.depends('product_variant_ids.x_model')
    # def _compute_x_model(self):
    #     unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
    #     for template in unique_variants:
    #         template.x_model = template.product_variant_ids.x_model
    #     for template in (self - unique_variants):
    #         template.x_model = False

    # def _set_x_model(self):
    #     if len(self.product_variant_ids) == 1:
    #         self.product_variant_ids.x_model = self.x_model


class AddendaProduct(models.Model):
    _inherit = 'product.product'

    x_codido_producto_comprador = fields.Char(string='Código Producto Comprador', index=True)

    # x_size = fields.Char(string='Talla', index=True)
    # x_model = fields.Char(string='Modelo', index=True)
    # x_gtin = fields.Char(string="Codigo EAN (GTIN)", index=True)

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'

    addenda_type = fields.Selection(selection_add=[('basware', 'Basware')], ondelete={'basware': 'set null'}) 

    x_orden_compra = fields.Char(string='Orden de Compra')
    x_numero_contrato = fields.Char(string='Número de Contrato')
    x_persona_referencia = fields.Char(string='Persona Referencia')
    x_email = fields.Char(string='Email')
    x_documento_transporte = fields.Char(string='Documento Transporte')
    x_numero_proveedor = fields.Char(string='Número de Proveedor')
    x_codigo_destinatario = fields.Char(string='Codigo Destinatario')

    x_iso_moneda = fields.Char(string='ISO Moneda')

    x_fecha_pago = fields.Date('Fecha Pago')

    x_termino_pago = fields.Char('Termino Pago')

    x_extra_info_ids = fields.One2many('account.move.attribute', 'sale_id', 'Extra Info')


    @api.onchange('company_id')
    def onchange_basware_onchange(self):
        if self.company_id and self.company_id.x_numero_proveedor:
            self.x_numero_proveedor = self.company_id.x_numero_proveedor


class AddendaPicking(models.Model):
    _inherit = 'stock.picking'

    addenda_type = fields.Selection(selection_add=[('basware', 'Basware')], ondelete={'basware': 'set null'}) 

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    x_orden_compra = fields.Char(string='Orden de Compra')

    x_linea_orden_compra = fields.Char(string='Linea Orden de Compra (Número)')

    x_numero_contrato = fields.Char(string='Número de Contrato')

    x_codido_producto_comprador = fields.Char(string='Código Producto Comprador', index=True)

    x_documento_transporte = fields.Char(string='Documento Transporte')

    x_extra_info_ids = fields.One2many('account.move.line.attribute', 'move_line_id', 'Extra Info')


    @api.onchange('product_id')
    def onchange_x_codido_producto_comprador(self):
        if self.product_id and self.product_id.x_codido_producto_comprador:
            self.x_codido_producto_comprador = self.product_id.x_codido_producto_comprador

    @api.onchange('move_id')
    def onchange_basware_onchange(self):
        if self.move_id and self.display_type == 'product':
            self.x_numero_contrato = self.move_id.x_numero_contrato
            self.x_orden_compra = self.move_id.x_orden_compra
            self.x_documento_transporte = self.move_id.x_documento_transporte

    def action_open_line_form(self):
        """Acción para abrir el formulario detallado de la línea"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detalle de Línea de Venta - Addenda Basware',
            'res_model': 'account.move.line',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_mx_edi_addenda_basware.account_move_line_detail_form_view').id,
            'target': 'new',  # Abre en modal
            'context': dict(self.env.context),
        }


class AccountMove(models.Model):
    _inherit = 'account.move'
        

    addenda_type = fields.Selection(selection_add=[('basware', 'Basware')], ondelete={'basware': 'set null'}) 

    x_orden_compra = fields.Char(string='Orden de Compra')
    x_numero_contrato = fields.Char(string='Número de Contrato')
    x_persona_referencia = fields.Char(string='Persona Referencia')
    x_email = fields.Char(string='Email')
    x_documento_transporte = fields.Char(string='Documento Transporte')
    x_numero_proveedor = fields.Char(string='Número de Proveedor')
    x_codigo_destinatario = fields.Char(string='Codigo Destinatario')

    x_iso_moneda = fields.Char(string='ISO Moneda')

    x_fecha_pago = fields.Date('Fecha Pago')

    x_termino_pago = fields.Char('Termino Pago')

    x_extra_info_ids = fields.One2many('account.move.attribute', 'move_id', 'Extra Info')

    def get_invoice_lines(self):
        return self.invoice_line_ids


    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            if sale_id:
                res.x_orden_compra = sale_id.x_orden_compra
                res.x_numero_contrato = sale_id.x_numero_contrato
                res.x_persona_referencia = sale_id.x_persona_referencia
                res.x_email = sale_id.x_email
                res.x_documento_transporte = sale_id.x_documento_transporte
                res.x_numero_proveedor = sale_id.x_numero_proveedor
                res.x_codigo_destinatario = sale_id.x_codigo_destinatario
                res.x_iso_moneda = sale_id.x_iso_moneda
                res.x_fecha_pago = sale_id.x_fecha_pago
                res.x_termino_pago = sale_id.x_termino_pago
                if sale_id.x_extra_info_ids:
                    x_extra_info_ids = []
                    for xextra in sale_id.x_extra_info_ids:
                        xvals = {
                                    'ttype': xextra.ttype,
                                    'value': xextra.value,
                                }
                        xline = (0,0,xvals)
                        x_extra_info_ids.append(xline)
                    res.x_extra_info_ids = x_extra_info_ids

                for invoice_line in res.invoice_line_ids:
                    invoice_line.x_orden_compra = invoice_line.sale_line_ids[0].x_orden_compra
                    invoice_line.x_linea_orden_compra = invoice_line.sale_line_ids[0].x_linea_orden_compra
                    invoice_line.x_numero_contrato = invoice_line.sale_line_ids[0].x_numero_contrato
                    invoice_line.x_codido_producto_comprador = invoice_line.sale_line_ids[0].x_codido_producto_comprador
                    invoice_line.x_documento_transporte = invoice_line.sale_line_ids[0].x_documento_transporte

                    if invoice_line.sale_line_ids[0].x_extra_info_ids:
                        x_extra_info_line_ids = []
                        for xextra_line in invoice_line.sale_line_ids[0].x_extra_info_ids:
                            xvals = {
                                        'ttype': xextra_line.ttype,
                                        'value': xextra_line.value,
                                    }
                            xline = (0,0,xvals)
                            x_extra_info_line_ids.append(xline)
                        invoice_line.x_extra_info_ids = x_extra_info_line_ids

        return res

class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(selection_add=[('coppel', 'Coppel')], ondelete={'coppel': 'set null'}) 

    x_orden_compra = fields.Char(string='Orden de Compra')

    x_linea_orden_compra = fields.Char(string='Linea Orden de Compra (Número)')

    x_numero_contrato = fields.Char(string='Número de Contrato')

    x_codido_producto_comprador = fields.Char(string='Código Producto Comprador', index=True)

    x_documento_transporte = fields.Char(string='Documento Transporte')

    x_extra_info_ids = fields.One2many('account.move.line.attribute', 'sale_line_id', 'Extra Info')

    def action_open_line_form(self):
        """Acción para abrir el formulario detallado de la línea"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detalle de Línea de Venta - Addenda Basware',
            'res_model': 'sale.order.line',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_mx_edi_addenda_basware.sale_order_line_detail_form_view').id,
            'target': 'new',  # Abre en modal
            'context': dict(self.env.context),
        }


class AccountMoveLineAttribute(models.Model):
    _name = 'account.move.line.attribute'
    _description = 'Atributos de Línea de Factura'
    _rec_name = 'ttype'

    sale_line_id = fields.Many2one(
        'sale.order.line', 
        string='Línea de Venta',
        required=True,
        ondelete='cascade'
    )

    move_line_id = fields.Many2one(
        'account.move.line', 
        string='Línea de Factura',
        required=True,
        ondelete='cascade'
    )
    ttype = fields.Char(
        string='Descripción',
        required=True
    )
    value = fields.Char(
        string='Valor',
        required=True
    )

    @api.depends('ttype', 'value')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.ttype}: {record.value}"


class AccountMoveAttribute(models.Model):
    _name = 'account.move.attribute'
    _description = 'Atributos de Factura'
    _rec_name = 'ttype'

    sale_id = fields.Many2one(
        'sale.order', 
        string='Venta',
        required=True,
        ondelete='cascade'
    )

    move_id = fields.Many2one(
        'account.move', 
        string='Factura',
        required=True,
        ondelete='cascade'
    )
    ttype = fields.Char(
        string='Descripción',
        required=True
    )
    value = fields.Char(
        string='Valor',
        required=True
    )

    @api.depends('ttype', 'value')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.ttype}: {record.value}"