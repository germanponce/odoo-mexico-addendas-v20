# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_mx_edi_is_indirect = fields.Boolean(
        string='Indirect Supplier',
        help="When marked, the Acknowledgment of receipt and the Purchase "
             "Order fields on the portal are required.")

    danone_supplier_type = fields.Selection(
        selection=[
            ('dairy_supplier', 'Proveedor Basado en Entregas'),
            ('general_supplier', 'Proveedor General'),
        ],
        string="Tipo de Proveedor Danone",
        default="general_supplier",
    )
