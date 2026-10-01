from odoo.exceptions import ValidationError
from odoo import api, fields, models
from collections import defaultdict
from odoo.tools import frozendict
from datetime import datetime

class AccountMove(models.Model):
    _inherit = "account.move"

    x_factoring_invoice_ids = fields.Many2many("account.move", "ir_acc_factoring_rel", "factoring_id", copy=False)
    x_in_factoring = fields.Boolean(string="En factoraje", copy=False)


    def open_factoring(self):
        partner_ids = self.mapped("partner_id")
        if len(partner_ids) > 1:
            raise ValidationError("Las facturas seleccionadas deben de ser del mismo cliente, favor de validar.")
        if not partner_ids[0].x_factoring_partner_id:
            raise ValidationError("Es necesario configurar el factorante financiero en el cliente, favor de validar.")
        factoring_id = self.env["account.factoring"].create({
            "partner_id": partner_ids[0].x_factoring_partner_id.id,
            "invoice_partner_id": partner_ids[0].id
        })
        for rec in self:
            if rec.amount_residual == 0:
                raise ValidationError(f"La factura {rec.name} ha sido pagada en su totalidad, no es posible agregarle un factoraje.")
            data = {
                "invoice_id": rec.id,
                "amount": rec.amount_residual
            }
            factoring_id.line_ids = [(0,0,data)]

        return {
            'name': "Factoraje financiero",
            'view_mode': "form",
            'res_model': 'account.factoring',
            'type': 'ir.actions.act_window',
            'res_id': factoring_id.id,
            'target': 'new',
        }

    def action_register_payment(self):
        res = super().action_register_payment()
        if self:
            print("+++++++  action_register_payment ++++++++++", self)
            res["context"]["default_x_factoring_partner_id"] = self[0].partner_id.x_factoring_partner_id.id if self else False


        return res

    def _l10n_mx_edi_add_payment_cfdi_values(self, cfdi_values, pay_results):
        res = super()._l10n_mx_edi_add_payment_cfdi_values(cfdi_values, pay_results)

        amount = self.amount_total
        has_factoring = False
        factoring_partner_id = False
        for invoice_values in pay_results['invoice_results']:
            invoice = invoice_values['invoice']

            if invoice and invoice.x_factoring_invoice_ids:
                has_factoring = True
                factoring_partner_id = invoice.partner_id.x_factoring_partner_id
                credit_line_id = invoice.x_factoring_invoice_ids.mapped("invoice_line_ids").filtered(lambda li: li.name == invoice.name and li.credit > 0)
                amount += sum(credit_line_id.mapped("credit"))

        if cfdi_values.get("monto_total_pagos"):
            cfdi_values["monto_total_pagos"] = amount
            
        #Cambiar el receptor del pago
        if has_factoring:
            cfdi_values["receptor"]["nombre"] = factoring_partner_id.name
            cfdi_values["receptor"]["rfc"] = factoring_partner_id.vat
            cfdi_values["receptor"]["residencia_fiscal"] = factoring_partner_id.country_id.l10n_mx_edi_code if  factoring_partner_id.country_id.l10n_mx_edi_code != 'MEX' else None
            cfdi_values["receptor"]["domicilio_fiscal_receptor"] = factoring_partner_id.zip
            cfdi_values["receptor"]["regimen_fiscal_receptor"] = factoring_partner_id.l10n_mx_edi_fiscal_regime or '616'

        cfdi_values = self.add_factoring_invoices(cfdi_values, pay_results)
        return res

    def add_factoring_invoices(self, cfdi_values, pay_results):
        """
            Adición de todos los elementos de los pagos realizados por factoraje
        :param cfdi_values: Se adicionan los documentos relacionados de factoraje
        :param pay_results:
        :return: cfdi_values
        """
        #Se identifica si se llevara acabo el factoraje
        add_factoring = False
        company = cfdi_values['company']
        company_curr = company.currency_id
        cfdi_date = datetime.combine(fields.Datetime.from_string(self.date), datetime.strptime('12:00:00', '%H:%M:%S').time())
        cfdi_values["documento_factoraje"] = {
            "fecha_pago": cfdi_date.strftime('%Y-%m-%dT%H:%M:%S'),
            "forma_de_pago": "17",
            "moneda": self.currency_id.name,
            "num_operacion": self.ref
        }
        invoice_results = []
        for invoice_values in pay_results['invoice_results']:
            invoice = invoice_values['invoice']
            #Se busca si la factura tiene facturas de proveedor relacionadas para realizar el factoraje
            if invoice and invoice.x_factoring_invoice_ids:
                add_factoring = True
                for factoring_id in invoice.x_factoring_invoice_ids:
                    credit_line_id = factoring_id.mapped("invoice_line_ids").filtered(lambda li: li.name == invoice.name and li.credit > 0)
                    data = {
                        "invoice_amount_currency": sum(credit_line_id.mapped("credit")),
                        "balance": sum(credit_line_id.mapped("credit")),
                        "invoice_exchange_balance": 0,
                        "payment_amount_currency": sum(credit_line_id.mapped("credit")),
                        "payment": factoring_id,
                        "invoice": invoice,
                        "number_of_payments": 2,
                        "reconciled_amount": sum(credit_line_id.mapped("credit")),
                        "amount_residual_before": invoice.amount_total - (invoice.amount_total - sum(credit_line_id.mapped("credit"))),
                        "amount_residual_after": invoice.amount_residual,
                        "payment_exchange_balance": 0,
                        "factoring": True
                    }
                    invoice_results.append(data)
        #Se obtiene el total del monto pagado
        total_in_payment_curr = sum(x['payment_amount_currency'] for x in invoice_results)
        cfdi_values["documento_factoraje"]["monto"] = total_in_payment_curr
        cfdi_values["documento_factoraje"]['tipo_cambio'] = None

        #Se obtienen los documentos relacionados asi como el calculo de los impuestos pagados dependiendo del porcentaje
        invoice_values_list = []
        for invoice_values in invoice_results:
            invoice = invoice_values['invoice']

            inv_cfdi_values = self.env['l10n_mx_edi.document']._get_company_cfdi_values(invoice.company_id)
            invoice._l10n_mx_edi_add_invoice_cfdi_values(inv_cfdi_values)

            if invoice.amount_total:
                percentage_paid = abs(invoice_values['reconciled_amount'] / invoice.amount_total)
            else:
                percentage_paid = 0.0
            for key in ('retenciones_list', 'traslados_list'):
                for tax_values in inv_cfdi_values[key]:
                    for tax_key in ('base', 'importe'):
                        if tax_values[tax_key] is not None:
                            tax_values[tax_key] = invoice.currency_id.round(tax_values[tax_key] * percentage_paid)

            if invoice.currency_id == self.currency_id:
                rate = None
            elif invoice.currency_id == company_curr != self.currency_id:
                balance = invoice_values['balance'] + invoice_values['invoice_exchange_balance']
                amount_currency = invoice_values['payment_amount_currency']
                rate = abs(balance / amount_currency) if amount_currency else 0.0
            elif self.currency_id == company_curr != invoice.currency_id:
                balance = invoice_values['balance'] + invoice_values['payment_exchange_balance']
                rate = abs(invoice_values['invoice_amount_currency'] / balance) if balance else 0.0
            elif invoice_values['payment_amount_currency']:
                rate = abs(invoice_values['invoice_amount_currency'] / invoice_values['payment_amount_currency'])
            else:
                rate = 0.0

            invoice_values_list.append({
                **inv_cfdi_values,
                'id_documento': invoice.l10n_mx_edi_cfdi_uuid,
                'equivalencia': rate,
                'num_parcialidad': invoice_values['number_of_payments'],
                'imp_pagado': invoice_values['reconciled_amount'],
                'imp_saldo_ant': invoice_values['amount_residual_before'],
                'imp_saldo_insoluto': invoice_values['amount_residual_after'],
            })
        cfdi_values["documento_factoraje"]['docto_relationado_list'] = invoice_values_list

        def update_tax_amount(key, amount):
            if cfdi_values[key] is None:
                cfdi_values[key] = 0.0
            cfdi_values[key] += amount

        def check_transferred_tax_values(tax_values, tag, tax_class, amount):
            return (
                tax_values['impuesto'] == tag
                and tax_values['tipo_factor'] == tax_class
                and company_curr.compare_amounts(tax_values['tasa_o_cuota'] or 0.0, amount) == 0
            )

        withholding_values_map = defaultdict(lambda: {'importe': 0.0})
        transferred_values_map = defaultdict(lambda: {'base': 0.0, 'importe': 0.0})
        pay_rate = cfdi_values['tipo_cambio'] or 1.0
        for cfdi_inv_values in invoice_values_list:
            inv_rate = cfdi_inv_values['equivalencia'] or 1.0
            to_mxn_rate = pay_rate / inv_rate
            for tax_values in cfdi_inv_values['retenciones_list']:
                key = frozendict({'impuesto': tax_values['impuesto']})
                withholding_values_map[key]['importe'] += self.currency_id.round(tax_values['importe'] / inv_rate)

                tax_amount_mxn = company_curr.round(tax_values['importe'] * to_mxn_rate)
                if tax_values['impuesto'] == '001':
                    update_tax_amount('total_retenciones_isr', tax_amount_mxn)
                elif tax_values['impuesto'] == '002':
                    update_tax_amount('total_retenciones_iva', tax_amount_mxn)
                elif tax_values['impuesto'] == '003':
                    update_tax_amount('total_retenciones_ieps', tax_amount_mxn)

            for tax_values in cfdi_inv_values['traslados_list']:
                key = frozendict({
                    'impuesto': tax_values['impuesto'],
                    'tipo_factor': tax_values['tipo_factor'],
                    'tasa_o_cuota': tax_values['tasa_o_cuota']
                })
                tax_amount = tax_values['importe'] or 0.0
                transferred_values_map[key]['base'] += self.currency_id.round(tax_values['base'] / inv_rate)
                transferred_values_map[key]['importe'] += self.currency_id.round(tax_amount / inv_rate)

                base_amount_mxn = company_curr.round(tax_values['base'] * to_mxn_rate)
                tax_amount_mxn = company_curr.round(tax_amount * to_mxn_rate)
                if check_transferred_tax_values(tax_values, '002', 'Tasa', 0.0):
                    update_tax_amount('total_traslados_base_iva0', base_amount_mxn)
                    update_tax_amount('total_traslados_impuesto_iva0', tax_amount_mxn)
                elif check_transferred_tax_values(tax_values, '002', 'Exento', 0.0):
                    update_tax_amount('total_traslados_base_iva_exento', base_amount_mxn)
                elif check_transferred_tax_values(tax_values, '002', 'Tasa', 0.08):
                    update_tax_amount('total_traslados_base_iva8', base_amount_mxn)
                    update_tax_amount('total_traslados_impuesto_iva8', tax_amount_mxn)
                elif check_transferred_tax_values(tax_values, '002', 'Tasa', 0.16):
                    update_tax_amount('total_traslados_base_iva16', base_amount_mxn)
                    update_tax_amount('total_traslados_impuesto_iva16', tax_amount_mxn)

        cfdi_values["documento_factoraje"]['retenciones_list'] = [
            {**k, **v}
            for k, v in withholding_values_map.items()
        ]
        cfdi_values["documento_factoraje"]['traslados_list'] = [
            {**k, **v}
            for k, v in transferred_values_map.items()
        ]

        for tax_values in cfdi_values["documento_factoraje"]['traslados_list']:
            if tax_values['tipo_factor'] == 'Exento':
                tax_values['importe'] = None
        if not add_factoring:
            cfdi_values["documento_factoraje"] = False
        return cfdi_values
