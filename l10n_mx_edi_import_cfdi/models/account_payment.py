# -*- coding: utf-8 -*-
from odoo import models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def l10n_mx_edi_is_required(self):
        self.ensure_one()
        required = (
            self.reconciled_invoice_ids.filtered(lambda i: i.l10n_mx_edi_payment_sign_required is False))
        if required:
            return not required
        required = super(AccountPayment, self).l10n_mx_edi_is_required()
        return required
