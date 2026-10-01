# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import frozendict


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ── Campos de factoraje ───────────────────────────────────────────────────

    x_factoring_invoice_ids = fields.Many2many(
        comodel_name='account.move',
        relation='ir_acc_factoring_rel',
        column1='factoring_id',
        copy=False,
        string='Asientos de factoraje',
        help='Asientos contables de compensación generados por operaciones de factoraje.',
    )
    x_in_factoring = fields.Boolean(
        string='En factoraje',
        copy=False,
        help='Indica que la factura de proveedor fue liquidada mediante factoraje.',
    )

    # ── Acciones ──────────────────────────────────────────────────────────────

    def open_factoring(self):
        """Abre el wizard de factoraje financiero para las facturas seleccionadas."""
        partner_ids = self.mapped('partner_id')
        if len(partner_ids) > 1:
            raise ValidationError(
                'Las facturas seleccionadas deben ser del mismo cliente. '
                'Por favor valide la selección.'
            )
        if not partner_ids[0].x_factoring_partner_id:
            raise ValidationError(
                'Es necesario configurar el Factorante financiero en el cliente '
                'antes de crear un factoraje.'
            )

        factoring_id = self.env['account.factoring'].create({
            'partner_id': partner_ids[0].x_factoring_partner_id.id,
            'invoice_partner_id': partner_ids[0].id,
        })
        for rec in self:
            if rec.amount_residual == 0:
                raise ValidationError(
                    f'La factura {rec.name} ya fue pagada en su totalidad; '
                    f'no es posible incluirla en un factoraje.'
                )
            factoring_id.line_ids = [(0, 0, {
                'invoice_id': rec.id,
                'amount': rec.amount_residual,
            })]

        return {
            'name': 'Factoraje financiero',
            'view_mode': 'form',
            'res_model': 'account.factoring',
            'type': 'ir.actions.act_window',
            'res_id': factoring_id.id,
            'target': 'new',
        }

    def action_register_payment(self):
        # EXTENDS 'account'
        res = super().action_register_payment()
        if self:
            # Propaga el factorante al wizard de registro de pago
            res['context']['default_x_factoring_partner_id'] = (
                self[0].partner_id.x_factoring_partner_id.id if self else False
            )
        return res

    # ── CFDI de Pagos 2.0 — hook principal ───────────────────────────────────

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        # EXTENDS 'l10n_mx_edi'
        res = super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results)

        # ── Recalcular monto total si hay factoraje ───────────────────────────
        amount = cfdi_values.get('monto_total_pagos', 0.0)
        # print ("### amount: ", amount)
        has_factoring = False
        factoring_partner_id = False

        for invoice_values in pay_results['invoice_results']:
            invoice = invoice_values['invoice']
            if invoice and invoice.x_factoring_invoice_ids:
                has_factoring = True
                factoring_partner_id = invoice.partner_id.x_factoring_partner_id
                credit_lines = invoice.x_factoring_invoice_ids.mapped(
                    'invoice_line_ids'
                ).filtered(lambda li: li.name == invoice.name and li.credit > 0)
                amount += sum(credit_lines.mapped('credit'))
                print ("#### credit_lines.mapped('credit'): ", credit_lines.mapped('credit'))
        # print ("### amount 2222: ", amount)
        if cfdi_values.get('monto_total_pagos') is not None:
            cfdi_values['monto_total_pagos'] = amount

        # ── Redirigir el Receptor al factorante ──────────────────────────────
        if has_factoring and factoring_partner_id:
            cfdi_values['receptor']['nombre'] = factoring_partner_id.name
            cfdi_values['receptor']['rfc'] = factoring_partner_id.vat
            cfdi_values['receptor']['residencia_fiscal'] = (
                factoring_partner_id.country_id.l10n_mx_edi_code
                if factoring_partner_id.country_id.l10n_mx_edi_code != 'MEX'
                else None
            )
            cfdi_values['receptor']['domicilio_fiscal_receptor'] = factoring_partner_id.zip
            cfdi_values['receptor']['regimen_fiscal_receptor'] = (
                factoring_partner_id.l10n_mx_edi_fiscal_regime or '616'
            )

        # ── Agregar nodo de Pago de factoraje (segundo pago20:Pago) ──────────
        cfdi_values = self._add_factoring_cfdi_values(cfdi_values, pay_results)
        return res

    # ── Construcción del segundo nodo pago20:Pago ─────────────────────────────

    def _add_factoring_cfdi_values(self, cfdi_values, pay_results):

        add_factoring = False
        company = cfdi_values['company']
        company_curr = company.currency_id

        cfdi_date = datetime.combine(
            fields.Datetime.from_string(self.date),
            datetime.strptime('12:00:00', '%H:%M:%S').time(),
        )
        cfdi_values['documento_factoraje'] = {
            'fecha_pago': cfdi_date.strftime('%Y-%m-%dT%H:%M:%S'),
            'forma_de_pago': '17',
            'moneda': self.currency_id.name,
            'num_operacion': self.ref,
        }

        # ── Recopilar documentos relacionados del factoraje ───────────────────
        invoice_results = []
        for invoice_values in pay_results['invoice_results']:
            invoice = invoice_values['invoice']
            if not (invoice and invoice.x_factoring_invoice_ids):
                continue

            add_factoring = True
            for factoring_move in invoice.x_factoring_invoice_ids:
                credit_lines = factoring_move.invoice_line_ids.filtered(
                    lambda li: li.name == invoice.name and li.credit > 0
                )
                credit_total = sum(credit_lines.mapped('credit'))
                invoice_results.append({
                    'invoice_amount_currency': credit_total,
                    'balance': credit_total,
                    'invoice_exchange_balance': 0,
                    'payment_amount_currency': credit_total,
                    'payment': factoring_move,
                    'invoice': invoice,
                    'number_of_payments': 2,
                    'reconciled_amount': credit_total,
                    'amount_residual_before': (
                        invoice.amount_total
                        - (invoice.amount_total - credit_total)
                    ),
                    'amount_residual_after': invoice.amount_residual,
                    'payment_exchange_balance': 0,
                    'factoring': True,
                })

        # ── Totales del nodo de factoraje ─────────────────────────────────────
        total_in_payment_curr = sum(x['payment_amount_currency'] for x in invoice_results)
        cfdi_values['documento_factoraje']['monto'] = total_in_payment_curr
        cfdi_values['documento_factoraje']['tipo_cambio'] = None

        # ── Documentos relacionados con impuestos prorrateados ────────────────
        invoice_values_list = []
        for inv_vals in invoice_results:
            invoice = inv_vals['invoice']

            inv_cfdi_values = self.env['l10n_mx_edi.document']._get_company_cfdi_values(
                invoice.company_id
            )
            invoice._l10n_mx_edi_add_invoice_cfdi_values(inv_cfdi_values)

            percentage_paid = (
                abs(inv_vals['reconciled_amount'] / invoice.amount_total)
                if invoice.amount_total else 0.0
            )
            for key in ('retenciones_list', 'traslados_list'):
                for tax_values in inv_cfdi_values[key]:
                    for tax_key in ('base', 'importe'):
                        if tax_values[tax_key] is not None:
                            tax_values[tax_key] = invoice.currency_id.round(
                                tax_values[tax_key] * percentage_paid
                            )

            # Tipo de cambio entre moneda de factura y moneda de pago
            if invoice.currency_id == self.currency_id:
                rate = None
            elif invoice.currency_id == company_curr != self.currency_id:
                balance = inv_vals['balance'] + inv_vals['invoice_exchange_balance']
                amount_currency = inv_vals['payment_amount_currency']
                rate = abs(balance / amount_currency) if amount_currency else 0.0
            elif self.currency_id == company_curr != invoice.currency_id:
                balance = inv_vals['balance'] + inv_vals['payment_exchange_balance']
                rate = (
                    abs(inv_vals['invoice_amount_currency'] / balance)
                    if balance else 0.0
                )
            elif inv_vals['payment_amount_currency']:
                rate = abs(
                    inv_vals['invoice_amount_currency']
                    / inv_vals['payment_amount_currency']
                )
            else:
                rate = 0.0

            # ── objeto_imp requerido por el template payment20 v19 ──────────
            # KeyError: 'objeto_imp' si no se incluye en el dict.
            objeto_imp = inv_cfdi_values.get('objeto_imp')
            if not objeto_imp:
                tax_objects = invoice.invoice_line_ids.mapped('l10n_mx_edi_tax_object')
                objeto_imp = next((t for t in tax_objects if t), '02')

            invoice_values_list.append({
                **inv_cfdi_values,
                'id_documento': invoice.l10n_mx_edi_cfdi_uuid,
                # pago20:DoctoRelacionado requiere Folio, Serie y MonedaDR
                'folio': invoice.name or '',
                'serie': '',
                'moneda': invoice.currency_id.name,
                # ObjetoImpDR — requerido en v19
                'objeto_imp': objeto_imp,
                # Tipo de cambio pago/factura
                'equivalencia': rate,
                # Parcialidad y montos
                'num_parcialidad': inv_vals['number_of_payments'],
                'imp_pagado': inv_vals['reconciled_amount'],
                'imp_saldo_ant': inv_vals['amount_residual_before'],
                'imp_saldo_insoluto': inv_vals['amount_residual_after'],
            })

        cfdi_values['documento_factoraje']['docto_relationado_list'] = invoice_values_list

        # ── Acumulación de impuestos globales del factoraje ───────────────────

        def update_tax_amount(key, amount):
            if cfdi_values[key] is None:
                cfdi_values[key] = 0.0
            cfdi_values[key] += amount

        def check_transferred(tax_values, tag, tax_class, amount):
            return (
                tax_values['impuesto'] == tag
                and tax_values['tipo_factor'] == tax_class
                and company_curr.compare_amounts(
                    tax_values['tasa_o_cuota'] or 0.0, amount
                ) == 0
            )

        withholding_map = defaultdict(lambda: {'importe': 0.0})
        transferred_map = defaultdict(lambda: {'base': 0.0, 'importe': 0.0})
        pay_rate = cfdi_values.get('tipo_cambio') or 1.0

        for cfdi_inv in invoice_values_list:
            inv_rate = cfdi_inv.get('equivalencia') or 1.0
            to_mxn = pay_rate / inv_rate

            for tv in cfdi_inv.get('retenciones_list', []):
                key = frozendict({'impuesto': tv['impuesto']})
                withholding_map[key]['importe'] += self.currency_id.round(
                    tv['importe'] / inv_rate
                )
                tax_mxn = company_curr.round(tv['importe'] * to_mxn)
                if tv['impuesto'] == '001':
                    update_tax_amount('total_retenciones_isr', tax_mxn)
                elif tv['impuesto'] == '002':
                    update_tax_amount('total_retenciones_iva', tax_mxn)
                elif tv['impuesto'] == '003':
                    update_tax_amount('total_retenciones_ieps', tax_mxn)

            for tv in cfdi_inv.get('traslados_list', []):
                key = frozendict({
                    'impuesto': tv['impuesto'],
                    'tipo_factor': tv['tipo_factor'],
                    'tasa_o_cuota': tv['tasa_o_cuota'],
                })
                tax_amount = tv['importe'] or 0.0
                transferred_map[key]['base'] += self.currency_id.round(
                    tv['base'] / inv_rate
                )
                transferred_map[key]['importe'] += self.currency_id.round(
                    tax_amount / inv_rate
                )
                base_mxn = company_curr.round(tv['base'] * to_mxn)
                tax_mxn = company_curr.round(tax_amount * to_mxn)

                if check_transferred(tv, '002', 'Tasa', 0.0):
                    update_tax_amount('total_traslados_base_iva0', base_mxn)
                    update_tax_amount('total_traslados_impuesto_iva0', tax_mxn)
                elif check_transferred(tv, '002', 'Exento', 0.0):
                    update_tax_amount('total_traslados_base_iva_exento', base_mxn)
                elif check_transferred(tv, '002', 'Tasa', 0.08):
                    update_tax_amount('total_traslados_base_iva8', base_mxn)
                    update_tax_amount('total_traslados_impuesto_iva8', tax_mxn)
                elif check_transferred(tv, '002', 'Tasa', 0.16):
                    update_tax_amount('total_traslados_base_iva16', base_mxn)
                    update_tax_amount('total_traslados_impuesto_iva16', tax_mxn)

        cfdi_values['documento_factoraje']['retenciones_list'] = [
            {**k, **v} for k, v in withholding_map.items()
        ]
        cfdi_values['documento_factoraje']['traslados_list'] = [
            {**k, **v} for k, v in transferred_map.items()
        ]

        # Los nodos Exento no llevan Importe en el XML
        for tv in cfdi_values['documento_factoraje']['traslados_list']:
            if tv['tipo_factor'] == 'Exento':
                tv['importe'] = None

        if not add_factoring:
            cfdi_values['documento_factoraje'] = False

        return cfdi_values

    # ── Reporte: sección de factoraje ────────────────────────────────────────

    def _get_bank_transaction_receipt_report_values(self):
        
        values = super()._get_bank_transaction_receipt_report_values()

        # Obtener facturas reconciliadas:
        # 1. Via origin_payment_id ( campo correcto en account.move → account.payment)
        # 2. Via matching de líneas (transacciones bancarias sin account.payment)
        if self.origin_payment_id:
            reconciled_invoices = self.origin_payment_id.reconciled_invoice_ids
        else:
            reconciled_invoices = self.env['account.move']
            for line in self.line_ids.filtered(
                lambda l: l.account_type in (
                    'asset_receivable', 'liability_payable'
                )
            ):
                for partial in line.matched_debit_ids | line.matched_credit_ids:
                    counterpart = (
                        partial.debit_move_id
                        if line == partial.credit_move_id
                        else partial.credit_move_id
                    )
                    if counterpart.move_id.is_invoice():
                        reconciled_invoices |= counterpart.move_id

        factoring_lines = []
        factoring_partner = self.env['res.partner']

        for invoice in reconciled_invoices:
            if not invoice.x_factoring_invoice_ids:
                continue
            if not factoring_partner:
                factoring_partner = invoice.partner_id.x_factoring_partner_id
            for fact_move in invoice.x_factoring_invoice_ids:
                credit_lines = fact_move.line_ids.filtered(
                    lambda l: l.credit > 0 and l.name == invoice.name
                )
                monto = sum(credit_lines.mapped('credit'))
                if not monto:
                    continue
                factoring_lines.append({
                    'invoice':        invoice,
                    'factoring_move': fact_move,
                    'ref':            fact_move.ref or fact_move.name or '',
                    'fecha':          fact_move.date,
                    'journal':        fact_move.journal_id.name,
                    'monto':          monto,
                })

        if factoring_lines:
            values['factoring'] = {
                'partner':     factoring_partner,
                'lines':       factoring_lines,
                'total_monto': sum(l['monto'] for l in factoring_lines),
                'currency':    self.currency_id,
            }

        return values
