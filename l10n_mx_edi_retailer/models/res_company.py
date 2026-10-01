# -*- encoding: utf-8 -*-
# Coded by German Ponce Dominguez
# Cherman Seingalt - german.ponce@outlook.com

from odoo import api, fields, models, _
from lxml import etree

import logging
_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_edi_retailer_buyer_gln = fields.Char(
        string="GLN del Comprador",
        help="Global Location Number (GLN) del comprador/cliente destinatario, "
             "requerido por el Complemento Detallista.",
    )
    l10n_mx_edi_retailer_seller_gln = fields.Char(
        string="GLN del Vendedor",
        help="Global Location Number (GLN) propio de esta compañía como "
             "vendedor, requerido por el Complemento Detallista.",
    )
    l10n_mx_edi_retailer_seller_alternate_party_identification = fields.Char(
        string="Identificador Alterno del Vendedor",
        help="Código con el que el comprador (p.ej. Detallista) identifica a "
             "esta compañía como proveedor.",
    )
    l10n_mx_edi_retailer_ship_to_gln = fields.Char(
        string="GLN del Destino de Envío",
        help="Global Location Number (GLN) del punto de entrega de la "
             "mercancía, requerido por el Complemento Detallista.",
    )
    l10n_mx_edi_retailer_seller_id_type = fields.Selection(
        selection=[
            ('SELLER_ASSIGNED_IDENTIFIER_FOR_A_PARTY', 'SELLER_ASSIGNED_IDENTIFIER_FOR_A_PARTY'),
            ('IEPS_REFERENCE', 'IEPS_REFERENCE'),
        ],
        string="Tipo de Identificación del Vendedor",
        default='SELLER_ASSIGNED_IDENTIFIER_FOR_A_PARTY',
    )
