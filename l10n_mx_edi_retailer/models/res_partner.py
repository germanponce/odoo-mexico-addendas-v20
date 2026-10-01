# -*- encoding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_mx_edi_retailer_gln = fields.Char(
        string="GLN (Detallista)",
        size=13,
        help="Número Global de Localización (GLN) de este partner. Se usa "
             "cuando este partner es el comprador, el destino de envío o el "
             "emisor de la factura en el Complemento Detallista. Si se deja "
             "vacío, se usa el GLN configurado en la Compañía como respaldo.",
    )
    l10n_mx_edi_retailer_alternate_id_type = fields.Selection(
        selection=[
            ('VA', '[VA] Identificación tributaria'),
            ('IA', '[IA] Número interno del proveedor'),
        ],
        string="Tipo de Identificación Alterna (Detallista)",
        default='VA',
        help="Solo aplica cuando este partner se usa como Emisor de Factura "
             "(InvoiceCreator) distinto del proveedor.",
    )
    l10n_mx_edi_retailer_alternate_id = fields.Char(
        string="Identificación Alterna (Detallista)",
        help="Solo aplica cuando este partner se usa como Emisor de Factura "
             "(InvoiceCreator) distinto del proveedor.",
    )
