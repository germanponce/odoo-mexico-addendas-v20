from odoo import _, api, models


class ResUser(models.Model):
    _inherit = "res.users"

    def _is_system(self):
        res = super(ResUser, self)._is_system()
        if not res and 'from_sat_sync' in self.env.context and self.env.context['from_sat_sync']:
            return True
        return res

