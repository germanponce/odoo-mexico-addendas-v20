# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results)
        if cfdi_values.get('errors'):
            return
        cfdi_values['moneda_dp'] = self.currency_id.decimal_places
