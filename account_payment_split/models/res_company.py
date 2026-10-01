from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    unknown_payment_account_id = fields.Many2one(
        comodel_name="account.account",
        domain=[("internal_type", "=", "other")],
    )
