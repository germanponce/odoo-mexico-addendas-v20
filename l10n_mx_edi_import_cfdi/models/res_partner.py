# -*- coding: utf-8 -*-
from odoo import models, fields
ACCOUNT_DOMAIN = "['&', '&', '&', ('deprecated', '=', False), ('account_type', 'not in', ('asset_receivable','liability_payable','asset_cash','liability_credit_card')), ('company_id', '=', current_company_id), ('is_off_balance', '=', False)]"
ACCOUNT_DOMAIN = "[('deprecated', '=', False), ('company_id', '=', current_company_id)]"

class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_mx_edi_sign_required = fields.Boolean(
        string='Sign CFDI?',
        default=True,
        help='If this field is active, the invoices for this customer by default will be signed.')

    # Cuenta de gasto por defecto
    property_default_account_expense_id = fields.Many2one(
        'account.account', string='Cuenta de gasto por defecto',
        domain=ACCOUNT_DOMAIN,
        company_dependent=True)
