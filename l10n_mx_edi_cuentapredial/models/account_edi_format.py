# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_get_invoice_cfdi_values(self, invoice):
        # OVERRIDE
        vals = super()._l10n_mx_edi_get_invoice_cfdi_values(invoice)

        # Update line values for custom numbers
        for line_vals in vals['invoice_line_vals_list']:
            # Custom number
            line_vals['cuenta_predial'] = line_vals['line'].l10n_mx_edi_cuenta_predial or False

        return vals
