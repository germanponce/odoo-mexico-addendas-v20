# -*- coding: utf-8 -*-
# Migrado a Odoo 19 por Claude (Anthropic) a partir del original de
# German Ponce Dominguez (Odoo 17).
#
# CAMBIO DE FONDO respecto a la versión original:
# Odoo 19 ya trae nativo el campo `account.move.invoice_currency_rate`
# (editable en borrador, con botón "refresh" para volver al tipo de cambio
# automático) y lo usa de forma consistente en TODOS los cómputos de montos
# de la factura. Por eso este módulo ya no necesita duplicar el cómputo del
# tipo de cambio (`current_exchange_rate_by_date` / `_invert`,
# `company_currency_foreign`, el override de `_compute_currency_rate` en
# account.move.line): basta con decirle a Odoo QUÉ FECHA usar para calcular
# ese tipo de cambio, mediante el hook `_get_invoice_currency_rate_date()`
# que el propio core expone para este caso exacto.
#
# Lo que SÍ se conserva "tal cual" (a petición explícita, adaptado a la
# firma real de Odoo 19, verificada contra el código fuente de
# odoo/odoo@19.0):
#   - El campo `exchange_rate_date`.
#   - El override de `_compute_price_unit` en account.move.line (para que
#     el precio unitario de línea respete la fecha de referencia cuando el
#     producto está tarifado en una moneda distinta a la de la factura).
#   - El override de `_compute_payments_widget_to_reconcile_info`.
#   - El override de `action_post`.

from odoo import fields, models, api, _

import logging
_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.depends('product_id', 'product_uom_id')
    def _compute_price_unit(self):
        # EXTENDS 'account'
        # Idéntico al método real de Odoo 19, solo se cambia la fecha que se
        # pasa a `_get_tax_included_unit_price`: en vez de `line.move_id.date`
        # a secas, se usa `_get_invoice_currency_rate_date()` para que
        # respete `exchange_rate_date` cuando esté definido.
        for line in self:
            if not line.product_id or line.display_type in ('line_section', 'line_subsection', 'line_note') or line.is_imported:
                continue
            if line.move_id.is_sale_document(include_receipts=True):
                document_type = 'sale'
            elif line.move_id.is_purchase_document(include_receipts=True):
                document_type = 'purchase'
            else:
                document_type = 'other'
            line.price_unit = line.product_id._get_tax_included_unit_price(
                line.move_id.company_id,
                line.move_id.currency_id,
                line.move_id._get_invoice_currency_rate_date(),
                document_type,
                fiscal_position=line.move_id.fiscal_position_id,
                product_uom=line.product_uom_id,
            )


class AccountMove(models.Model):
    _inherit = 'account.move'

    exchange_rate_date = fields.Date(
        string="Fecha Tipo de Cambio",
        help="Fecha de referencia alterna para calcular el tipo de cambio de "
             "esta factura, en vez de usar la fecha de la factura.",
        readonly=False,
        copy=False,
    )

    def _get_invoice_currency_rate_date(self):
        # EXTENDS 'account'
        self.ensure_one()
        return self.exchange_rate_date or super()._get_invoice_currency_rate_date()

    def _compute_payments_widget_to_reconcile_info(self):
        # EXTENDS 'account'
        # Rebasado sobre el cuerpo real de Odoo 19 (que ya no coincide con
        # el de Odoo 17: agrega dominio multi-compañía, cambia el estado
        # permitido a {'draft', 'posted'} y agrega la clave 'move_ref').
        # Se agrega: cuando la factura tiene un `invoice_currency_rate`
        # (nativo, ya sea automático o editado a mano / vía
        # `exchange_rate_date`), se usa ese mismo tipo de cambio para
        # convertir los importes pendientes en vez de la tabla automática de
        # tipos de cambio, para que el widget sea consistente con el resto
        # de la factura.
        for move in self:
            move.invoice_outstanding_credits_debits_widget = False

            if move.state not in {'draft', 'posted'} \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids \
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                '|', *move._check_company_domain(move.company_id), ('company_id', 'child_of', move.company_id.id),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                ('balance', '<' if move.is_inbound() else '>', 0.0),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]

            payments_widget_vals = {
                'outstanding': True,
                'content': [],
                'move_id': move.id,
                'title': _('Outstanding credits') if move.is_inbound() else _('Outstanding debits'),
            }

            for line in self.env['account.move.line'].search(domain):

                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual_currency)
                elif move.exchange_rate_date and move.invoice_currency_rate:
                    # Tipo de cambio manual / con fecha de referencia: se
                    # respeta el mismo tipo de cambio usado en el resto de
                    # la factura en vez de la tabla automática.
                    amount = abs(line.amount_residual) * move.invoice_currency_rate
                else:
                    # Different foreign currencies.
                    amount = line.company_currency_id._convert(
                        abs(line.amount_residual),
                        move.currency_id,
                        move.company_id,
                        line.date,
                    )

                if move.currency_id.is_zero(amount):
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'currency_id': move.currency_id.id,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                    'move_ref': line.ref or "",
                })

            if payments_widget_vals['content']:
                move.invoice_outstanding_credits_debits_widget = payments_widget_vals

    def action_post(self):
        # EXTENDS 'account'
        no_exchange_difference = False
        for rec in self:
            if rec.exchange_rate_date and rec.currency_id != rec.company_id.currency_id:
                no_exchange_difference = True
                # Fuerza el recómputo de los importes de línea (price_unit
                # depende de _get_invoice_currency_rate_date) antes de contabilizar.
                for line in rec.invoice_line_ids:
                    prev_price = line.price_unit
                    line.price_unit = line.price_unit + 0.5
                    line.price_unit = prev_price

        if no_exchange_difference:
            # Evita que Odoo genere un asiento de diferencia cambiaria
            # comparando contra el tipo de cambio automático de la fecha de
            # factura, ya que aquí se está usando uno manual/con fecha de
            # referencia distinta.
            res = super(AccountMove, self.with_context(no_exchange_difference=True)).action_post()
        else:
            res = super().action_post()
        return res
