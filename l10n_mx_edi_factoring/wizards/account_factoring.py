# -*- coding: utf-8 -*-
# Factoraje Financiero MX.
# Migración v18 → v19:
#   - js_assign_outstanding_line sigue disponible en v19 (internamente llama a .reconcile()).
#   - Command.create() sin cambios.
#   - invoice_line_ids → renombrado internamente; se usa line_ids al crear el move.

from odoo import api, fields, models, Command
from odoo.exceptions import ValidationError


class AccountFactoring(models.TransientModel):
    _name = 'account.factoring'
    _description = 'Factoraje financiero'
    _rec_name = 'partner_id'

    # ── Campos ────────────────────────────────────────────────────────────────

    factoring_date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.today,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Factorante financiero',
        required=True,
    )
    invoice_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente',
    )
    bill_id = fields.Many2one(
        comodel_name='account.move',
        string='Factura de proveedor',
    )
    bill_amount = fields.Float(
        string='Importe proveedor',
        compute='_compute_bill_amount',
        store=True,
        digits='Account',
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diario',
        required=False,
    )
    balance = fields.Float(
        string='Balance',
        compute='_compute_balance',
        store=True,
        digits='Account',
    )
    factoring_amount = fields.Float(
        string='Importe de factoraje',
        store=True,
        compute='_compute_factoring_amount',
        digits='Account',
    )
    line_ids = fields.One2many(
        comodel_name='account.factoring.line',
        inverse_name='factoring_id',
        string='Líneas de factoraje',
    )
    amount = fields.Float(
        string='Importe interés',
        digits='Account',
    )

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends('bill_id')
    def _compute_bill_amount(self):
        for rec in self:
            rec.bill_amount = rec.bill_id.amount_residual if rec.bill_id else 0.0

    @api.depends('bill_id', 'line_ids', 'line_ids.amount', 'factoring_amount')
    def _compute_balance(self):
        for rec in self:
            rec.balance = (
                rec.bill_id.amount_residual - round(rec.factoring_amount, 2)
                if rec.bill_id
                else 0.0
            )

    @api.depends('line_ids.amount', 'line_ids')
    def _compute_factoring_amount(self):
        for rec in self:
            rec.factoring_amount = round(sum(rec.line_ids.mapped('amount')), 2)

    # ── Onchanges ─────────────────────────────────────────────────────────────

    @api.onchange('amount')
    def _onchange_amount(self):
        """Distribuye el importe de interés proporcional entre las líneas."""
        for rec in self:
            if not rec.line_ids:
                continue
            total_residual = sum(rec.line_ids.mapped('invoice_id.amount_residual'))
            if not total_residual:
                continue
            factor = rec.amount / total_residual
            for line in rec.line_ids:
                line.amount = round(line.invoice_id.amount_residual * factor, 2)
            # Ajustar diferencia de redondeo en la primera línea
            assigned = sum(rec.line_ids.mapped('amount'))
            diff = round(rec.amount - assigned, 2)
            rec.line_ids[0].amount = rec.line_ids[0].amount + diff

    # ── Validaciones ──────────────────────────────────────────────────────────

    def _check_factoring_amount(self):
        for rec in self:
            if rec.factoring_amount > rec.bill_id.amount_residual:
                raise ValidationError(
                    'El importe de factoraje no puede ser mayor al monto pendiente '
                    'de la factura de proveedor. Verifique los importes.'
                )

    # ── Acción principal ──────────────────────────────────────────────────────

    def create_factoring(self):
        """
        Crea el asiento contable de compensación de factoraje:
          - Débito:  cuenta por pagar del proveedor (factorante) ← importe de factoraje
          - Crédito: cuentas por cobrar de cada factura de cliente

        Después reconcilia cada crédito con su factura y el débito con la factura
        de proveedor, y lanza el registro de pago ordinario.
        """
        self._check_factoring_amount()

        payment_method = self.env['l10n_mx_edi.payment.method'].sudo().search(
            [('code', '=', '17')], limit=1
        )

        # ── Construir líneas del asiento ──────────────────────────────────────
        line_list = [Command.create({
            'account_id': self.bill_id.partner_id.property_account_payable_id.id,
            'partner_id': self.bill_id.partner_id.id,
            'debit': self.factoring_amount,
            'name': f"Factoraje {self.line_ids.mapped('invoice_id.name')}",
        })]

        for line in self.line_ids:
            line_list.append(Command.create({
                'account_id': line.invoice_id.partner_id.property_account_receivable_id.id,
                'partner_id': line.invoice_id.partner_id.id,
                'credit': line.amount,
                'name': f'{line.invoice_id.name}',
            }))
            # Limpiar relaciones de factoraje anteriores
            if line.invoice_id.x_factoring_invoice_ids:
                for prev in line.invoice_id.x_factoring_invoice_ids:
                    line.invoice_id.x_factoring_invoice_ids = [(3, prev.id)]

        # ── Crear y confirmar el asiento ──────────────────────────────────────
        move_id = self.env['account.move'].sudo().create({
            'ref': f"Factoraje {self.line_ids.mapped('invoice_id.name')}",
            'journal_id': self.journal_id.id,
            'date': self.factoring_date,
            'l10n_mx_edi_payment_method_id': payment_method.id,
            'line_ids': line_list,
        })
        move_id.action_post()

        # ── Reconciliar créditos con facturas y débito con proveedor ──────────
        credit_lines = move_id.line_ids.filtered(lambda l: l.credit > 0)
        debit_line = move_id.line_ids.filtered(lambda l: l.debit > 0)

        for credit_line in credit_lines:
            factoring_line = self.line_ids.filtered(
                lambda li: li.invoice_id.name == credit_line.name
            )
            # js_assign_outstanding_line sigue disponible en v19
            factoring_line.invoice_id.js_assign_outstanding_line(credit_line.id)
            factoring_line.invoice_id.x_factoring_invoice_ids = [(4, move_id.id)]

        self.bill_id.js_assign_outstanding_line(debit_line.id)
        self.bill_id.x_in_factoring = True

        # ── Lanzar registro de pago ordinario ─────────────────────────────────
        return self.line_ids.mapped('invoice_id.line_ids').action_register_payment()
