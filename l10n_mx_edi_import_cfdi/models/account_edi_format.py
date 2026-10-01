# -*- coding: utf-8 -*-
from odoo import models


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _get_move_applicability(self, move):
        # EXTENDS account_edi
        self.ensure_one()
        if self.code != 'cfdi_3_3':
            return super()._get_move_applicability(move)

        if move.country_code != 'MX' or not move.l10n_mx_edi_sign_required:
            return None

        if move.move_type in ('out_invoice', 'out_refund') and move.company_id.currency_id.name == 'MXN':
            return {
                'post': self._l10n_mx_edi_post_invoice,
                'cancel': self._l10n_mx_edi_cancel_invoice,
                'edi_content': self._l10n_mx_edi_xml_invoice_content,
            }

        sign_not_required = (
            move._get_reconciled_invoices().filtered(lambda i: i.l10n_mx_edi_payment_sign_required is False))
        if (move.payment_id or move.statement_line_id).l10n_mx_edi_force_generate_cfdi \
            or 'PPD' in move._get_reconciled_invoices().mapped('l10n_mx_edi_payment_policy') and not sign_not_required:
            return {
                'post': self._l10n_mx_edi_post_payment,
                'cancel': self._l10n_mx_edi_cancel_payment,
                'edi_content': self._l10n_mx_edi_xml_payment_content,
            }
