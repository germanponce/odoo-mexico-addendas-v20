# -*- encoding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_mx_edi_retailer_alternate_id_type = fields.Selection(
        selection=[
            ('BUYER_ASSIGNED', 'BUYER_ASSIGNED'),
            ('SUPPLIER_ASSIGNED', 'SUPPLIER_ASSIGNED'),
            ('GLOBAL_TRADE_ITEM_IDENTIFICATION', 'GLOBAL_TRADE_ITEM_IDENTIFICATION'),
            ('SERIAL_NUMBER', 'SERIAL_NUMBER'),
        ],
        string="Tipo de Identificación Alterna (Detallista)",
        default='SUPPLIER_ASSIGNED',
        help="Tipo de identificación adicional del artículo, en caso de no "
             "usar el código GTIN. Si se deja vacío, la addenda usa "
             "automáticamente el código interno del producto (BUYER_ASSIGNED) "
             "y, si difiere, también el código de proveedor (SUPPLIER_ASSIGNED).",
    )
    l10n_mx_edi_retailer_alternate_id = fields.Char(
        string="Identificación Alterna (Detallista)",
        help="Valor de la identificación alterna. Si se deja vacío, se usa "
             "el código interno / código de proveedor del producto.",
    )
