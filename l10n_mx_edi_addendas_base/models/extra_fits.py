# -*- coding: utf-8 -*-

import re
from odoo import models, fields, api, _
from odoo.tools.misc import ustr
from odoo.exceptions import ValidationError

import xml
import sys
import base64

#### Librerias LdM E.E. ###
from lxml import etree
from xml.dom import minidom
from xml.dom.minidom import parse, parseString

from io import BytesIO
from lxml.objectify import fromstring


class AddendaCompany(models.Model):
    """docstring for AddendaCompany"""
    _inherit = 'res.company'

class AddendaProduct(models.Model):
    _inherit = 'product.template'
    
class AddendaProduct(models.Model):
    _inherit = 'product.product'
    

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'
    
    addenda_type = fields.Selection([('na','No Aplica')], string="Addenda", default="na") 

    @api.model
    def create(self, vals):
        res = super(AddendaSale, self).create(vals)
        if res:
            if res.addenda_type:
                res.addenda_type = res.addenda_type
        return res

class AddendaSaleLine(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection([('na','No Aplica')], string="Addenda", related="order_id.addenda_type") 

class AddendaPicking(models.Model):
    _inherit = 'stock.picking'

    addenda_type = fields.Selection([('na','No Aplica')], string="Addenda", default="na") 

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    addenda_type = fields.Selection([('na','No Aplica')], string="Addenda", default="na") 

    def l10n_mx_regenerate_addenda(self):
        if not self.l10n_mx_edi_cfdi_uuid:
            raise UserError("No se puede generar una Addenda para un CFDI que no esta timbrado.")
        edidoc_signed = False

        for edidoc in self.l10n_mx_edi_document_ids:
            if edidoc.attachment_uuid:
                edidoc_signed = edidoc

        if not edidoc_signed:
            return False

        invoice = self
        addenda = invoice.partner_id.l10n_mx_edi_addenda_id or invoice.partner_id.commercial_partner_id.l10n_mx_edi_addenda_id # l10n_mx_edi.addenda
        if addenda:
            attachment_id = edidoc_signed.attachment_id

            xml_data = base64.b64decode(attachment_id.datas)
            cfdi_minidom = minidom.parseString(xml_data)
            if cfdi_minidom.getElementsByTagName('cfdi:Addenda'):
                subnode_cfdi_addenda = cfdi_minidom.getElementsByTagName('cfdi:Addenda')[0]                    
                parent = subnode_cfdi_addenda.parentNode
                parent.removeChild(subnode_cfdi_addenda)
                xml_data = cfdi_minidom.toxml('UTF-8')

            if addenda:
                cfdi_filename = invoice._l10n_mx_edi_get_invoice_cfdi_filename()
                cfdi_str = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(xml_data, addenda)
                
                datas_b64 = base64.encodebytes(cfdi_str)
                attachment_id.write({'datas' : datas_b64})
        self.l10n_mx_regenerate_addenda_try_again()
        return True

    def l10n_mx_regenerate_addenda_try_again(self):
        if not self.l10n_mx_edi_cfdi_uuid:
            raise UserError("No se puede generar una Addenda para un CFDI que no esta timbrado.")
        edidoc_signed = False

        for edidoc in self.l10n_mx_edi_document_ids:
            if edidoc.attachment_uuid:
                edidoc_signed = edidoc

        if not edidoc_signed:
            return False

        invoice = self
        addenda = invoice.partner_id.l10n_mx_edi_addenda_id or invoice.partner_id.commercial_partner_id.l10n_mx_edi_addenda_id # l10n_mx_edi.addenda
        if addenda:
            attachment_id = edidoc_signed.attachment_id

            xml_data = base64.b64decode(attachment_id.datas)
            cfdi_minidom = minidom.parseString(xml_data)
            if cfdi_minidom.getElementsByTagName('cfdi:Addenda'):
                subnode_cfdi_addenda = cfdi_minidom.getElementsByTagName('cfdi:Addenda')[0]                    
                parent = subnode_cfdi_addenda.parentNode
                parent.removeChild(subnode_cfdi_addenda)
                xml_data = cfdi_minidom.toxml('UTF-8')

            if addenda:
                cfdi_filename = invoice._l10n_mx_edi_get_invoice_cfdi_filename()
                cfdi_str = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(xml_data, addenda)
                
                datas_b64 = base64.encodebytes(cfdi_str)
                attachment_id.write({'datas' : datas_b64})

        return True