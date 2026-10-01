# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_mx_edi_factoring_id = fields.Many2one(
        comodel_name='res.partner',
        string='Empresa Factorante',
        copy=False,
        help=(
            'This partner is allowed to receive payments with a financial '
            'factoring agent. If set, the factoring will be proposed by '
            'default when a payment is registered. The Payment Complement '
            'will be issued in the factoring agent\'s name & VAT.'
        ),
    )
    l10n_mx_edi_factoring = fields.Boolean(
        string='Es Empresa Factorante',
        help='Mark this partner as a financial factoring agent.',
    )
