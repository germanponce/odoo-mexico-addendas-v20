from odoo import api, fields, models

class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"


    # def _get_x_factoring_partner_id(self):
    #     print("_get_x_factoring_partner_id", self.partner_id)
    #     print("+++++    _get_x_factoring_partner_id +++++",self.env.context.get('active_id'),self.env.context.get('active_model'))
    #     if self.env.context.get('active_id') and self.env.context.get('active_model') == "account.move.line":
    #         move_obj = self.env['account.move.line'].browse(self.env.context['active_id'])
    #         print("move_obj", move_obj.partner_id.name)

    #     return False

    x_factoring_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Factorante financiero",
        domain=[('x_is_factoring_partner', '=', True)],
    )

