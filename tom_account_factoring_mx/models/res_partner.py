from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    x_is_factoring_partner = fields.Boolean(string="Factorante")
    x_factoring_partner_id = fields.Many2one(comodel_name="res.partner", string="Factorante financiero")


