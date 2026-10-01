# -*- coding: utf-8 -*-

from odoo import api, models

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _l10n_mx_edi_get_cadena_xslts(self):
        return 'l10n_mx_edi_40/data/4.0/cadenaoriginal_TFD_1_1.xslt', 'l10n_mx_edi_impuestos_locales/data/4.0/cadenaoriginal_impuestoslocales.xslt'
