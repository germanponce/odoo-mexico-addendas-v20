# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.sql import column_exists, create_column


class AccountMove(models.Model):
    _inherit = "account.move"

    def write(self, vals):
        res = super(AccountMove, self).write(vals)
        return res

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_mx_edi_cuenta_predial = fields.Char(string='Cuenta Predial', copy=False, tracking=True)

    def write(self, vals):
        res = super(AccountMoveLine, self).write(vals)
        return res
