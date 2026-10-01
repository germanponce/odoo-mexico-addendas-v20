# -*- coding: utf-8 -*-
# Part of l10n_mx_edi_factoring.
#
# Extiende _get_payment_receipt_report_values para agregar la sección
# de factoraje al reporte de pago, sin depender de la estructura interna
# de cfdi_values.  Usa reconciled_invoice_ids que es estable en v19.

from odoo import models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _get_payment_receipt_report_values(self):
        
        # print ("############## _get_payment_receipt_report_values >>>>>>>>>>>>>>>>>>>")
        # print ("############## _get_payment_receipt_report_values >>>>>>>>>>>>>>>>>>>")
        # EXTENDS 'l10n_mx_edi' (via 'account')
        values = super()._get_payment_receipt_report_values()
        # print ("####### VALUES: ", values)
        factoring_lines = []
        factoring_partner = self.env['res.partner']

        for invoice in self.reconciled_invoice_ids:
            if not invoice.x_factoring_invoice_ids:
                continue
            if not factoring_partner:
                factoring_partner = invoice.partner_id.x_factoring_partner_id

            for fact_move in invoice.x_factoring_invoice_ids:
                # Líneas de crédito del asiento de factoraje que corresponden
                # a esta factura (se identifican por el nombre de la factura)
                credit_lines = fact_move.line_ids.filtered(
                    lambda l: l.credit > 0 and l.name == invoice.name
                )
                monto = sum(credit_lines.mapped('credit'))
                if not monto:
                    continue
                factoring_lines.append({
                    'invoice':       invoice,
                    'factoring_move': fact_move,
                    'ref':           fact_move.ref or fact_move.name or '',
                    'fecha':         fact_move.date,
                    'journal':       fact_move.journal_id.name,
                    'monto':         monto,
                })

        if factoring_lines:
            values['factoring'] = {
                'partner':     factoring_partner,
                'lines':       factoring_lines,
                'total_monto': sum(l['monto'] for l in factoring_lines),
                'currency':    self.currency_id,
            }

        return values
