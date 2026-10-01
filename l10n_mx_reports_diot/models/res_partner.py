from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_mx_type_of_operation = fields.Selection(
        selection_add=[
            ("02", "02 - Disposal of assets"),
            ("07", "07 - Import of goods or services"),
            ("08", "08 - Import by virtual transfer"),
            ("87", "87 - Global operations"),
        ]
    )

    def _check_l10n_mx_diot_northern_border(self):
        self.ensure_one()
        states = (
            self.env.ref("base.state_mx_bc")
            | self.env.ref("base.state_mx_son")
            | self.env.ref("base.state_mx_chih")
            | self.env.ref("base.state_mx_coah")
            | self.env.ref("base.state_mx_nl")
            | self.env.ref("base.state_mx_tamps")
        )
        if self.state_id in states:
            return True
        return False

    def _check_l10n_mx_diot_southern_border(self):
        self.ensure_one()
        states = (
            self.env.ref("base.state_mx_q_roo")
            | self.env.ref("base.state_mx_chis")
            | self.env.ref("base.state_mx_camp")
            | self.env.ref("base.state_mx_tab")
        )
        if self.state_id in states:
            return True
        return False
