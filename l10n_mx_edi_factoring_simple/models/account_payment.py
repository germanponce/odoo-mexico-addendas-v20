# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Migración v17 → v19:
#   - l10n_mx_edi_cfdi_request eliminado en v19. Reemplazado por
#     l10n_mx_edi_is_cfdi_needed (Boolean). El filtro en default_get
#     se actualizó acorde.
#   - _create_payment_vals_from_wizard(batch_result) sigue disponible en v19.
#   - @api.depends("partner_id") en _compute_factoring_id sin cambios.

from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_mx_edi_factoring_id = fields.Many2one(
        comodel_name='res.partner',
        string='Empresa Factorante',
        copy=False,
        help='This payment was received from this factoring agent.',
    )

    @api.model
    def default_get(self, fields_list):
        rec = super().default_get(fields_list)
        active_ids = self._context.get('active_ids') or self._context.get('active_id')
        active_model = self._context.get('active_model')

        if not active_ids or active_model != 'account.move':
            return rec

        # v19: l10n_mx_edi_is_cfdi_needed reemplaza a l10n_mx_edi_cfdi_request == "on_invoice"
        invoices = self.env['account.move'].browse(active_ids).filtered(
            lambda m: m.is_invoice(include_receipts=True) and m.l10n_mx_edi_is_cfdi_needed
        )
        if not invoices:
            return rec

        # Factorante: primero desde la factura, luego desde el partner
        factoring = invoices[0].l10n_mx_edi_factoring_id
        if not factoring and rec.get('partner_id'):
            factoring = self.env['res.partner'].browse(rec['partner_id']).l10n_mx_edi_factoring_id

        rec['l10n_mx_edi_factoring_id'] = factoring.id
        return rec


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    l10n_mx_edi_factoring_id = fields.Many2one(
        comodel_name='res.partner',
        string='Empresa Factorante',
        compute='_compute_factoring_id',
        readonly=False,
        store=True,
        help='This payment was received from this factoring agent.',
    )

    @api.depends('partner_id')
    def _compute_factoring_id(self):
        model = self._context.get('active_model')
        active_ids = self._context.get('active_ids')
        if model != 'account.move' or not active_ids:
            return
        for wizard in self.filtered('partner_id'):
            invoices = self.env['account.move'].browse(active_ids)
            # Factorante: primero desde la factura, luego desde el partner del wizard
            factor = (
                invoices.l10n_mx_edi_factoring_id
                or wizard.partner_id.l10n_mx_edi_factoring_id
            )
            wizard.l10n_mx_edi_factoring_id = factor[:1]

    def _create_payment_vals_from_wizard(self, batch_result):
        # EXTENDS 'account'
        res = super()._create_payment_vals_from_wizard(batch_result)
        res['l10n_mx_edi_factoring_id'] = self.l10n_mx_edi_factoring_id.id
        return res
