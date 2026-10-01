# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Migración v17 → v19:
#   - states={"posted": [("readonly", False)]} eliminado: deprecated desde v16,
#     removido en v19. El readonly se maneja ahora en la vista XML directamente.
#   - cfdi_values.get('errors') sigue siendo válido en v19.

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_mx_edi_factoring_id = fields.Many2one(
        comodel_name='res.partner',
        string='Empresa Factorante',
        copy=False,
        tracking=True,
        help=(
            'This invoice will be paid by this Financial Factoring agent. '
            'The CFDI Payment Complement will be issued in their name & VAT '
            'instead of the original customer.'
        ),
    )

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        # EXTENDS 'l10n_mx_edi'
        self.ensure_one()
        super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results=pay_results)
        if cfdi_values.get('errors'):
            return
        if not self.l10n_mx_edi_factoring_id:
            return

        factor = self.l10n_mx_edi_factoring_id
        cfdi_values['receptor']['rfc'] = factor.vat
        cfdi_values['receptor']['nombre'] = factor.name
        if factor.country_id.code != 'MX':
            cfdi_values['receptor']['residencia_fiscal'] = factor.country_id.l10n_mx_edi_code
        cfdi_values['receptor']['regimen_fiscal_receptor'] = factor.l10n_mx_edi_fiscal_regime
