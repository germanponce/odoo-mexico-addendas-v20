# -*- encoding: utf-8 -*-
### <German Ponce Dominguez>

from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare

from werkzeug.urls import url_encode

import logging
_logger = logging.getLogger(__name__)

TAX_TYPE_TO_CFDI_CODE = {'isr': '001', 'iva': '002', 'ieps': '003'}
CFDI_CODE_TO_TAX_TYPE = {v: k for k, v in TAX_TYPE_TO_CFDI_CODE.items()}


class AccountMoveSend(models.TransientModel):
    _inherit = 'account.move.send'

    @api.model
    def _prepare_invoice_pdf_report(self, invoice, invoice_data):
        """ Prepare the pdf report for the invoice passed as parameter.
        :param invoice:         An account.move record.
        :param invoice_data:    The collected data for the invoice so far.
        """
        if invoice.invoice_pdf_report_id:
            return

        report_name = 'account.account_invoices'
        if invoice and invoice.journal_id and invoice.journal_id.cfdi_report_id:
            report_name = invoice.journal_id.cfdi_report_id.report_name
        content, _report_format = self.env['ir.actions.report']._render(report_name, invoice.ids)

        invoice_data['pdf_attachment_values'] = {
            'raw': content,
            'name': invoice._get_invoice_report_filename(),
            'mimetype': 'application/pdf',
            'res_model': invoice._name,
            'res_id': invoice.id,
            'res_field': 'invoice_pdf_report_file', # Binary field
        }


class AccountJournal(models.Model):
    _inherit ='account.journal'

    cfdi_report_id = fields.Many2one('ir.actions.report', 'Reporte CFDI')

class AccountMove(models.Model):
    _inherit ='account.move'

    def get_tipo_cambio(self):
        current_exchange_rate_by_date = 1.0
        for rec in self:
            if rec.invoice_date:
                inv_currency = rec.currency_id
                company_currency = rec.company_id.currency_id
                if company_currency != inv_currency:
                    date_ctx = rec.invoice_date or rec.date or fields.Date.context_today(rec)
                    current_exchange_rate_by_date = inv_currency._convert(
                        1, company_currency, rec.company_id, rec.invoice_date, round=False
                    )
            else:
                inv_currency = rec.currency_id
                company_currency = rec.company_id.currency_id
                if company_currency != inv_currency:
                    date_ctx = rec.date or fields.Date.context_today(rec)
                    current_exchange_rate_by_date = inv_currency._convert(
                        1, company_currency, rec.company_id, date_ctx, round=False
                    )


        return current_exchange_rate_by_date

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def get_taxes_line_details(self):
        taxes_list = []
        price = self.price_unit * (1.0 - (self.discount or 0.0) / 100.0)

        move_is_refund = True if self.move_id.move_type in ('in_refund', 'out_refund') else False
        # taxes_res = self.tax_ids.compute_all(
        #             price,
        #             quantity=self.quantity,
        #             currency=self.currency_id,
        #             product=self.product_id,
        #             partner=self.partner_id,
        #             is_refund=move_is_refund,
        #         )
        tax_line = {tax['id']: tax for tax in self.tax_ids.compute_all(
                                                                        price,
                                                                        quantity=self.quantity,
                                                                        currency=self.currency_id,
                                                                        product=self.product_id,
                                                                        partner=self.partner_id,
                                                                        is_refund=move_is_refund,
                                                                    )['taxes']}
        for tax in self.tax_ids:
            tax_info = []
            tax_dict = tax_line.get(tax.id, {})
            amount_dict = tax_dict.get(
                'amount', tax.amount / 100 * float("%.2f" % self.price_subtotal))
            amount = round(abs(amount_dict), 2)
            rate = round(abs(tax.amount), 2)
            amount_base = round(abs(tax_dict.get(
                'base',self.price_subtotal)), 2)
            tax_rate = rate if tax.amount_type == 'fixed' else rate / 100.0
            tax_name = TAX_TYPE_TO_CFDI_CODE.get(tax.l10n_mx_tax_type) or '002'
            if tax_name == '001':
                tax_name = tax_name + "-ISR"
            elif tax_name == '002':
                tax_name = tax_name + "-IVA"
            elif tax_name == '003':
                tax_name = tax_name + "-IEPS"
            elif tax_name == '003':
                tax_name = tax_name + "-Impuesto Global"
            tax_info = [tax_name, tax.l10n_mx_factor_type, amount_base, tax_rate, amount]

            taxes_list.append(tax_info)
        return taxes_list 

class SaleOrder(models.Model):
    _inherit ='sale.order'

    via_embarque = fields.Char('Via de Embarque')
    no_orden = fields.Char('No. Orden')