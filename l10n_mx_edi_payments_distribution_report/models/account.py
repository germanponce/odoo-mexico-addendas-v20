# -*- coding: utf-8 -*-
# Coded by German Ponce Dominguez 
#     ▬▬▬▬▬.◙.▬▬▬▬▬  
#       ▂▄▄▓▄▄▂  
#    ◢◤█▀▀████▄▄▄▄▄▄ ◢◤  
#    █▄ █ █▄ ███▀▀▀▀▀▀▀ ╬  
#    ◥ █████ ◤  
#     ══╩══╩═  
#       ╬═╬  
#       ╬═╬ Dream big and start with something small!!!  
#       ╬═╬  
#       ╬═╬ You can do it!  
#       ╬═╬   Let's go...
#    ☻/ ╬═╬   
#   /▌  ╬═╬   
#   / \
# Cherman Seingalt - german.ponce@outlook.com


from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round
from odoo.tools.float_utils import float_compare
import datetime
import calendar

import tempfile

import xlwt
from io import BytesIO
import base64

from itertools import zip_longest
from lxml.objectify import fromstring

import logging
_logger = logging.getLogger(__name__)

logger_debug = False

format_date = "%Y-%m-%d"

class AccountMoveBankReportData(models.Model):
    _name = 'account.move.bank.report.data'
    _description = 'Datos Reporte Movimientos de Pagos'
    _order = "payment_date, id"

    @api.model  
    def default_get(self, fields):
        res = super(AccountMoveBankReportData, self).default_get(fields)
        return res

    def _get_current_user(self):
        return self.env.user.id

    name = fields.Char('Nombre Registro',size=256)

    ###### Parte 01 - Pagos ########
    payment_type = fields.Selection([
                                        ('customer','Cliente'),
                                        ('supplier','Proveedor'),
                                        ('internal_transfer','Interno')
                                    ], string="Tipo de Pago")
    partner_id = fields.Many2one('res.partner', 'Razon Social')
    entidad_federativa_id = fields.Many2one('res.country.state', related="partner_id.state_id")
    journal_id = fields.Many2one('account.journal', 'Diario')
    payment_id = fields.Many2one('account.payment', 'Pago')

    payment_date  = fields.Date(string='Fecha Pago')
    payment_uuid = fields.Char('Folio Fiscal (Pago)') # * l10n_mx_edi_cfdi_uuid
    payment_method_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago (Pagos)') # * l10n_mx_edi_payment_method_id
    payment_amount  = fields.Float(string='Monto Pagado')

    ###### Parte 02 - Facturas ########
    invoice_id = fields.Many2one('account.move', 'Factura')
    invoice_date  = fields.Date(string='Fecha Factura')
    invoice_payment_method_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago (Facturas)') # * l10n_mx_edi_payment_method_id
    l10n_mx_edi_payment_policy = fields.Selection(([('PPD','PPD'),('PUE','PUE')]), 'Metodo de Pago (Facturas)') # * l10n_mx_edi_payment_policy
    invoice_amount_untaxed  = fields.Float(string='Subtotal') # * amount_untaxed_signed
    invoice_amount_tax  = fields.Float(string='Impuestos') # * amount_tax_signed
    invoice_amount_total  = fields.Float(string='Total') # *amount_total_signed
    invoice_uuid = fields.Char('Folio Fiscal (Factura)') # * l10n_mx_edi_cfdi_uuid

    ###### Parte 03 - Parcialidades ########
    parcialidad = fields.Integer('Parcialidad')
    adeudo_anterior = fields.Float('Adeudo Anterior')
    monto_pagado = fields.Float('Monto Pagado')
    saldo = fields.Float('Monto Pagado')


    reference = fields.Char('Referencia Factura',size=256)
    statement_id = fields.Many2one('account.bank.statement', 'Estado de Cuenta')
    move_id = fields.Many2one('account.move', 'Movimiento')
    iva_amount  = fields.Float(string='Monto IVA')
    account_origin_id = fields.Many2one('account.account', 'Cuenta Origen')
    uuid = fields.Char('UUID',size=256)
    user_id = fields.Many2one('res.users', 'Usuario', default=_get_current_user)

    payment_currency_id = fields.Many2one('res.currency', string="Moneda Pago")
    invoice_currency_id = fields.Many2one('res.currency', string="Moneda Factura")
    payment_reference = fields.Char('Referencia Pago',size=256)
    company_id = fields.Many2one('res.company', string="Compañia")

class AccountMoveBankReportWizard(models.TransientModel):
    _name = 'account.move.bank.report.wizard'
    _description = 'Asistente Reporte Resumen de Pagos'

    @api.model  
    def default_get(self, fields):
        res = super(AccountMoveBankReportWizard, self).default_get(fields)
        
        child_company_ids = self.get_child_company_ids([self.env.company.id])

        journal_ids = self.env['account.journal'].search([('type', '=', 'bank'), ('company_id','in',child_company_ids)])
        
        if journal_ids:
            res.update(journal_ids=[(6,0,[x.id for x in journal_ids])])
        res.update(company_ids=[(6,0,self.env.companies.ids)])
        return res

    def _get_date(self):
        currentDate = datetime.date.today()
        firstDayOfMonth = datetime.date(currentDate.year, currentDate.month, 1)
        return firstDayOfMonth

    def _get_date_end(self):
        currentDate = datetime.date.today()
        lastDayOfMonth = datetime.date(currentDate.year, currentDate.month, calendar.monthrange(currentDate.year, currentDate.month)[1])
        return lastDayOfMonth

    date       = fields.Date(string='Fecha Inicio', default=_get_date, required=True)
    date_stop       = fields.Date(string='Fecha fin', default=_get_date_end, required=True)

    company_ids = fields.Many2many('res.company', 'wizard_report_company_rel', 'wizard_br_id', 'company_id',
                                     string='Compañías', required=True)

    journal_ids = fields.Many2many('account.journal', 'wizard_report_bank_journal_rel', 'wizard_br_id', 'journal_id',
                                     string='Diarios Contables', required=True)

    report_type = fields.Selection([('customers','Clientes'),('suppliers','Proveedores'),('both','Todo')], string="Tipo de Pagos", default="customers", required=True)

    report_output = fields.Selection([('pdf','PDF'),('view','Análisis')], string="Tipo de Reporte", default="view")

    file_ready = fields.Boolean('Archivo Listo')

    datas_fname = fields.Char('Nombre Archivo',size=256)

    file = fields.Binary("Reporte")

    def get_child_company_ids(self, company_ids):
        """METODO RECURSIVO QUE OBTIENE LOS IDS DE UBICACIONES HIJAS DE UNA UBICACION DADA"""
        new_company_ids = []
        company_obj = self.env['res.company'].sudo()
        res = company_obj.browse(company_ids).sudo()
        #SE RECORREN LOS IDS
        for rec in company_obj.with_context(active_test=False).browse(company_ids):           
            child_ids = [x.id for x in rec.child_ids]
            location_inactives = company_obj.search([('id', 'child_of', child_ids)])
            if location_inactives:
                location_inactives_list = [x.id for x in location_inactives]
                child_ids.extend(location_inactives_list)
            new_company_ids.extend(child_ids)

        if new_company_ids != []:
            new_company_ids = self.get_child_company_ids(new_company_ids)
        new_company_ids.extend(company_ids)
        new_company_ids = list(set(new_company_ids))
        return new_company_ids


    def get_current_report(self):
        data_obj = self.env['account.move.bank.report.data']
        data_list_payments_ids = []

        data_list_payments_ids = self.insert_data_from_payments()

        if self.report_output == 'pdf':
            res = self.generate_report_resumen_pdf(data_list_payments_ids)
            return res
        else:
            return {
                'domain': [('id', 'in', data_list_payments_ids)],
                'name': 'Reporte Resumen de Pagos',
                'view_mode': 'list,form',
                'view_type': 'form',
                'context': {'tree_view_ref': 'l10n_mx_edi_payments_distribution_report.account_move_bank_report_tree'},
                'res_model': 'account.move.bank.report.data',
                'type': 'ir.actions.act_window'
                }
                    
        return True

    def _get_global_taxes(self, roundnumber=2, invoice=False):
        
        round_char = "%."+str(roundnumber)+"f"

        taxes = {}
        #### Cambio Retenciones ####
        taxes_retenciones_ids = []
        for line in invoice.invoice_line_ids.filtered('price_subtotal'):
            price = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)
            # tax_line = {tax['id']: tax for tax in line.tax_ids.compute_all(
            #     price, line.currency_id, line.quantity, line.product_id, line.partner_id, self.move_type in ('in_refund', 'out_refund'))['taxes']}
            taxes_line = line.filtered('price_subtotal').tax_ids.flatten_taxes_hierarchy()
            for tax in taxes_line:
                if logger_debug:
                    _logger.info("\n#### tax :%s " % tax)

                if tax.amount_type =='percent':
                    tax_importe = abs(tax.amount) / 100.0 * line.price_subtotal
                elif tax.amount_type =='fixed':
                    tax_importe = abs(tax.amount)
                else:
                    continue

                rate = round(abs(tax.amount), roundnumber)

                tax_amount = round_char % tax_importe
                line_base = round_char % (line.price_subtotal or 0.0)

                if logger_debug:
                    _logger.info("\n#### tax.amount :%s " % tax.amount)
                    _logger.info("\n#### tax_amount :%s " % tax_amount)
                    _logger.info("\n#### line_base :%s " % line_base)

                if tax.id not in taxes:
                    tags_name = ""
                    if tax.invoice_repartition_line_ids:
                        for invrepart in tax.invoice_repartition_line_ids:
                            for tag in invrepart.tag_ids:
                                tags_name = tags_name+" | "+tag.name if tags_name else tag.name
                    if not tags_name:
                        tags_name = tax.name

                    if not 'IVA' in tags_name.upper():
                        if 'IVA' in tax.name.upper():
                            tags_name = tags_name+" | "+'IVA'
                    taxes.update({tax.id: {
                        'name': tags_name,
                        'amount': tax_amount,
                        'rate': rate if tax.amount_type == 'fixed' else rate / 100.0,
                        'tax_amount': tax_amount, #tax_dict.get('amount', tax.amount),
                        'amount_base': line_base,
                    }})

                else:
                    amount_old = float(taxes[tax.id]['amount'])
                    tax_amount_old = float(taxes[tax.id]['tax_amount'])
                    amount_base_old = float(taxes[tax.id]['amount_base'])

                    amount_new = amount_old + float(tax_amount)
                    tax_amount_new = tax_amount_old + float(tax_amount)
                    amount_base_new = amount_base_old + float(line_base)

                    taxes[tax.id].update({
                        'amount': round_char %  amount_new,
                        'tax_amount': round_char %  tax_amount_new,
                        'amount_base': round_char %  amount_base_new,
                    })

        return taxes

    def insert_data_from_payments(self, data_list_payments_ids=[]):
        if self.report_output == 'view':
            cr = self.env.cr
            cr.execute("""
                        delete from account_move_bank_report_data where user_id=%s;
                        """, (self.env.user.id, ))
            cr.commit()
        data_obj = self.env['account.move.bank.report.data']
        invoice_obj = self.env['account.move']
        
        # _name = 'account.move.bank.report.data'
        # journal_id = fields.Many2one('account.journal', 'Diario')
        # move_id = fields.Many2one('account.move', 'Movimiento')
        # payment_date  = fields.Date(string='Fecha Pago')
        # payment_amount  = fields.Float(string='Monto Pago')
        # iva_amount  = fields.Float(string='Monto IVA')
        # account_origin_id = fields.Many2one('account.account', 'Cuenta Origen')
        # partner_id = fields.Many2one('res.partner', 'Contacto')
        # invoice_id = fields.Many2one('account.move', 'Factura')
        # invoice_date  = fields.Date(string='Fecha Factura')
        # invoice_amount  = fields.Float(string='Monto Factura')
        # reference = fields.Char('Referencia',size=256)
        # uuid = fields.Char('UUID',size=256)
        
        # Customer Payments: ('partner_type', '=', 'customer')
        # Vendor Payments: ('partner_type', '=', 'supplier')
        # Transfers: ('is_internal_transfer', '=', True)

        ### Pagos ####

        payment_obj = self.env['account.payment']
        custom_domain = [
                            ('date','>=',self.date),
                            ('date','<=',self.date_stop),
                            ('state','=','posted'),
                            ('journal_id','in',tuple(self.journal_ids.ids)),
                        ]
        if self.report_type == 'customers':
            custom_domain.append(('payment_type','=','inbound'))
        elif self.report_type == 'suppliers':
            custom_domain.append(('payment_type','=','outbound'))
        payment_ids = payment_obj.search(custom_domain, order="date")
        # payment_ids = payment_obj.search([('id','=',932)])

        if not payment_ids:
            raise UserError("No se encontro información.")

        user_id = self.env.user.id
        for payment in payment_ids:
            iva_amount = 0.0 ## Pendiente sacar el dato.
            invoice_br = False ## Pendiente sacar el dato.
            partner_type = payment.partner_type
            payment_type = "internal_transfer"
            if payment.payment_type == 'inbound':
                payment_type = "customer"
            if payment.payment_type == 'outbound':
                cpayment_type = "supplier"

            # if partner_type == 'customer':
            #     payment_type = "customer"
            # elif partner_type == 'supplier':
            #     payment_type = "supplier"

            name = "Pago: %s" % payment.name

            if payment_type == "customer" :
                invoices_related_to_payment = payment.reconciled_invoice_ids
            elif payment_type == 'supplier':
                invoices_related_to_payment = payment.reconciled_bill_ids

            if not invoices_related_to_payment:
                invoices_related_to_payment = invoice_obj.search([('payment_id','=',payment.id),
                                                                  ('move_type','in',('out_invoice','out_refund','in_invoice','in_refund'))])


            payment_info_vals = payment._get_payment_receipt_report_values()
            signed_edi = payment_info_vals.get('cfdi')
            payment_invoices_dict = {

                                    }
            if signed_edi:

                move_line_ids = self.env['account.move.line'].browse(list(set(payment.line_ids._reconciled_lines()) - set(payment.line_ids.ids)))
                invoice_ids = move_line_ids.mapped('move_id')

                cfdi = signed_edi
                payment_info = cfdi.get('payment_info')

                docs_related = cfdi['invoices']

                for payinv_doc in docs_related:
                    payinv_invoice_doc= payinv_doc['invoice']
                    payinv_doc_invoice= payinv_doc['invoice'].name
                    payinv_doc_uuid= payinv_doc['uuid']
                    payinv_doc_parcialidad= payinv_doc['partiality']
                    payinv_doc_invoice_saldo_anterior= float(payinv_doc['previous_balance'])
                    payinv_doc_invoice_monto_pagado= float(payinv_doc['amount_paid'])
                    payinv_doc_invoice_saldo= float(payinv_doc['balance'])

                    payment_invoices_dict[payinv_doc_invoice] = {
                                                                    'payinv_invoice_doc': payinv_invoice_doc,
                                                                    'payinv_doc_invoice': payinv_doc_invoice,
                                                                    'payinv_doc_uuid': payinv_doc_uuid,
                                                                    'payinv_doc_parcialidad': payinv_doc_parcialidad,
                                                                    'payinv_doc_invoice_saldo_anterior': payinv_doc_invoice_saldo_anterior,
                                                                    'payinv_doc_invoice_monto_pagado': payinv_doc_invoice_monto_pagado,
                                                                    'payinv_doc_invoice_saldo': payinv_doc_invoice_saldo,
                                                                }
                        
            if invoices_related_to_payment:
                #### buscamos los montos que le corresponden a cada factura ####
                only_one_invoice = True if len(invoices_related_to_payment) == 1 else False
                for invoice in invoices_related_to_payment.sorted(key=lambda x: (x.invoice_date_due, x.name)):
                    ### Si no es Factura de Cliente no Genera la Relación de Pago y Factura ####
                    if logger_debug:
                        _logger.info("\n#### invoice.id: %s " % invoice)
                        _logger.info("\n#### invoice.name: %s " % invoice.name)
                        _logger.info("\n#### invoice.invoice_date: %s " % invoice.invoice_date)
                        _logger.info("\n#### payment.id: %s " % payment.id)
                        _logger.info("\n#### payment.name: %s " % payment.name)

                    monto_aplicado = 0.0 
                    monto_pago = 0.0
                    if not only_one_invoice:
                        for xline in payment.move_id.line_ids:
                            if payment_type == "customer" :
                                for r in xline.matched_debit_ids:
                                    _logger.info("=====================")
                                    for x in r._fields:
                                        _logger.info("%s: %s" % (x, r[x]))
                                    if r.debit_move_id.move_id.id == invoice.id:
                                        if invoice.currency_id == invoice.company_id.currency_id == payment.currency_id:
                                            monto_pago = r.amount
                                        elif (invoice.company_id.currency_id == payment.currency_id and \
                                            invoice.currency_id != invoice.company_id.currency_id) or \
                                            invoice.currency_id == payment.currency_id:
                                            monto_pago = r.debit_amount_currency
                                        else:
                                            ### Modificación invoice_date ####
                                            monto_pago = invoice.company_id.currency_id.with_context({'date': invoice.invoice_date}).compute(r.amount, invoice.currency_id)

                            elif payment_type == 'supplier':
                                for r in xline.matched_credit_ids:
                                    _logger.info("=====================")
                                    for x in r._fields:
                                        _logger.info("%s: %s" % (x, r[x]))
                                    if r.credit_move_id.move_id.id == invoice.id:
                                        if invoice.currency_id == invoice.company_id.currency_id == payment.currency_id:
                                            monto_pago = r.amount
                                        elif (invoice.company_id.currency_id == payment.currency_id and \
                                            invoice.currency_id != invoice.company_id.currency_id) or \
                                            invoice.currency_id == payment.currency_id:
                                            monto_pago = r.debit_amount_currency
                                        else:
                                            ### Modificación invoice_date ####
                                            monto_pago = invoice.company_id.currency_id.with_context({'date': invoice.invoice_date}).compute(r.amount, invoice.currency_id)
                    else:
                        if invoice.currency_id == invoice.company_id.currency_id == payment.currency_id:
                            monto_pago = payment.amount
                        elif (invoice.company_id.currency_id == payment.currency_id and \
                            invoice.currency_id != invoice.company_id.currency_id) or \
                            invoice.currency_id == payment.currency_id:
                            monto_pago = payment.amount
                        else:
                            ### Modificación invoice_date ####
                            monto_pago = invoice.company_id.currency_id.with_context({'date': invoice.invoice_date}).compute(payment.amount, invoice.currency_id)
                    
                    if monto_pago:
                        #### Sacamos los Impuestos ####
                        invoice_taxes = self._get_global_taxes(2, invoice)

                        ##### buscamos el porcentaje que le corresponde al pago ####
                        if logger_debug:
                            _logger.info("\n###### monto_pago: %s " % monto_pago)
                        monto_pago_payment_currency = 0.0
                        invoice_id = invoice
                        invoice_amount_total = invoice_id.amount_total
                        invoice_amount_total_payment_currency = 0.0

                        x_date = fields.Date.context_today(self)
                        if payment.currency_id==payment.company_id.currency_id or payment.currency_id == invoice_id.currency_id:
                            x_date = payment.date
                        elif payment.currency_id != invoice_id.currency_id:
                            x_date = invoice_id.invoice_date

                        invoice_currency_rate = 1
                        if not invoice_id or invoice_id.currency_id == payment.env.user.company_id.currency_id:
                            invoice_currency_rate = 1.0
                        else:
                            invoice_currency_rate = round(invoice_id.currency_id.with_context({'date': payment.date}).compute(1, payment.currency_id, round=False), 6)
                        
                        #revisa la cantidad que se va a pagar en el docuemnto
                        equivalencia_dr  = round(invoice_currency_rate,6)
                        if payment.currency_id.id != invoice_id.currency_id.id:
                            if payment.currency_id.name == 'MXN':
                                if logger_debug:
                                    _logger.info("\n########## Factura Moneda E. Pago en Pesos >>>> ")
                                invoice_amount_total_payment_currency = invoice_id.amount_total / equivalencia_dr
                                monto_pago_payment_currency = monto_pago / equivalencia_dr
                            else:
                                if logger_debug:
                                    _logger.info("\n########## Factura Moneda E. Pago en Moneda E. >>>> ")
                                invoice_amount_total_payment_currency = invoice_id.amount_total / equivalencia_dr
                                monto_pago_payment_currency = monto_pago / equivalencia_dr
                        else:
                            equivalencia_dr = 1
                            invoice_amount_total_payment_currency = invoice_id.amount_total
                            monto_pago_payment_currency = monto_pago

                        if equivalencia_dr == 1:
                           decimal_presicion = 2
                        else:
                           decimal_presicion = 6


                        paid_percentage = monto_pago_payment_currency / invoice_amount_total_payment_currency

                        if paid_percentage >= 0.9999:
                            paid_percentage = 1.0

                        if logger_debug:
                            _logger.info("\n########## paid_percentage: %s " % paid_percentage)
                            _logger.info("\n########## invoice_taxes: %s " % invoice_taxes)

                        ##### buscamos el monto de IVA que le corresponde al pago ####
                        for tax in invoice_taxes.keys():
                            tax_vals = invoice_taxes[tax]
                            tax_name = tax_vals.get('name')
                            tax_amount = float(tax_vals.get('amount',0.0))
                            if 'IVA' in tax_name.upper():
                                iva_amount = tax_amount * paid_percentage
                                break
                        if iva_amount > 0.0:
                            if invoice.currency_id == invoice.company_id.currency_id == payment.currency_id:
                                _logger.info("\n######## 000000 El monto de IVA es el mismo que la moneda. ")
                            else:
                                if payment.currency_id == invoice.company_id.currency_id:
                                    _logger.info("\n######## 1111 El monto de IVA - Pago en MXN")
                                    iva_amount = round(invoice_id.currency_id.with_context({'date': payment.date}).compute(iva_amount, payment.currency_id, round=False), 6)
                                else:
                                    _logger.info("\n######## 2222 El monto de IVA - Pago en Otra Moneda")
                                    iva_amount = round(payment.currency_id.with_context({'date': payment.date}).compute(iva_amount, invoice_id.currency_id, round=False), 6)
                    
                        ##################################################################

                    name = "Pago: %s" % payment.name
                    if invoice:
                        name = name+" "+" Factura: "+invoice.name
                    
                    payment_uuid = payment.l10n_mx_edi_cfdi_uuid
                    payment_method_id = payment.l10n_mx_edi_payment_method_id.id if payment.l10n_mx_edi_payment_method_id else False

                    l10n_mx_edi_payment_policy = invoice.l10n_mx_edi_payment_policy
                    invoice_payment_method_id = invoice.l10n_mx_edi_payment_method_id.id if invoice.l10n_mx_edi_payment_method_id else False
                    invoice_amount_untaxed = invoice.amount_untaxed_signed
                    invoice_amount_tax = invoice.amount_tax_signed
                    invoice_amount_total = invoice.amount_total_signed
                    invoice_uuid = invoice.l10n_mx_edi_cfdi_uuid

                    parcialidad = 0.0
                    adeudo_anterior = 0.0
                    monto_pagado = 0.0
                    saldo = 0.0

                    if payment_invoices_dict:
                        for invoice_doc_rel in payment_invoices_dict.keys():
                            invoice_name = invoice.name
                            invoice_doct_vals = payment_invoices_dict.get(invoice_name,{})
                            if invoice_doct_vals:
                                parcialidad = invoice_doct_vals.get('payinv_doc_parcialidad',0)
                                adeudo_anterior = invoice_doct_vals.get('payinv_doc_invoice_saldo_anterior',0.0)
                                monto_pagado = invoice_doct_vals.get('payinv_doc_invoice_monto_pagado',0.0)
                                saldo = invoice_doct_vals.get('payinv_doc_invoice_saldo',0.0)
                    xvals = {   
                            ### Parte 01 - Pagos ####
                            'name': name,
                            'payment_type': payment_type,
                            'partner_id': payment.partner_id.id,
                            'journal_id': payment.journal_id.id,
                            'payment_id': payment.id,
                            'payment_date': payment.date,
                            'payment_uuid': payment_uuid,
                            'payment_method_id': payment_method_id,
                            'payment_amount': payment.amount,

                            ### Parte 02 - Facturas ####
                            'invoice_id': invoice.id if invoice else False,
                            'invoice_date': invoice.invoice_date if invoice else False,
                            'invoice_payment_method_id': invoice_payment_method_id,
                            'l10n_mx_edi_payment_policy': l10n_mx_edi_payment_policy,
                            'invoice_amount_untaxed': invoice_amount_untaxed,
                            'invoice_amount_tax': invoice_amount_tax,
                            'invoice_amount_total': invoice_amount_total,
                            'invoice_uuid': invoice_uuid,

                            ### Parte 03 - Parcialidades ####
                            'parcialidad': parcialidad,
                            'adeudo_anterior': adeudo_anterior,
                            'monto_pagado': monto_pagado,
                            'saldo': saldo,

                            'move_id': payment.move_id.id,
                            'payment_currency_id': payment.currency_id.id,
                            'payment_reference': payment.ref,
                            'iva_amount': iva_amount,
                            'account_origin_id': payment.destination_account_id.id,
                            'invoice_currency_id': invoice.currency_id.id if invoice else False,
                            'reference': invoice.ref if invoice else False,
                            'uuid': invoice.l10n_mx_edi_cfdi_uuid if invoice else False,
                            'user_id': user_id,
                            'company_id': payment.company_id.id,
                        }
                    data_id = data_obj.create(xvals)
                    data_list_payments_ids.append(data_id.id)


            else:
                payment_uuid = payment.l10n_mx_edi_cfdi_uuid
                payment_method_id = payment.l10n_mx_edi_payment_method_id.id if payment.l10n_mx_edi_payment_method_id else False

                xvals = {   
                            ### Parte 01 - Pagos ####
                            'name': name,
                            'payment_type': payment_type,
                            'partner_id': payment.partner_id.id,
                            'journal_id': payment.journal_id.id,
                            'payment_id': payment.id,
                            'payment_date': payment.date,
                            'payment_uuid': payment_uuid,
                            'payment_method_id': payment_method_id,
                            'payment_amount': payment.amount,

                            'move_id': payment.move_id.id,
                            'payment_currency_id': payment.currency_id.id,
                            'payment_reference': payment.ref,
                            'user_id': user_id,
                            'company_id': payment.company_id.id,
                        }
                data_id = data_obj.create(xvals)
                data_list_payments_ids.append(data_id.id)
        
        return data_list_payments_ids

    def generate_report_resumen_pdf(self, data_list_payments_ids):
        report_data_brs = self.env['account.move.bank.report.data'].browse(data_list_payments_ids)

        year = str(self.date).split('-')[0]
        datas = {'payment_invoices_doc_list': report_data_brs}
        datas['year'] = year
        datas['date'] = self.date
        datas['date_stop'] = self.date_stop
        datas['company_ids'] = self.company_ids
        datas['journal_ids'] = self.journal_ids 
        datas['report_type'] = self.report_type 

        companies = ""
        for x in self.company_ids:
            companies = companies+ x.name if companies else x.name
        
        journals = ""
        for y in self.journal_ids:
            journals = journals+ y.name if journals else y.name

        datas['companies'] = companies
        datas['journals'] = journals

        report_from_action = self.env.ref('l10n_mx_edi_payments_distribution_report.report_payments_resumen_action')
        current_date_str = str(fields.Date.context_today(self)).replace('-','')
        fname_report_aux_01 = 'Resumen de Pagos (%s)' % current_date_str
        fname_report_aux_02 = fname_report_aux_01+'.pdf'
        context = self._context
        result, format = self.env["ir.actions.report"].sudo()._render_qweb_pdf(report_from_action.id, [data_list_payments_ids[0]], datas)
        # # TODO in trunk, change return format to binary to match message_post expected format
        result = base64.b64encode(result)
        self.write({
                        'datas_fname':fname_report_aux_02,
                        # 'file':base64.encodebytes(data),
                        'file': result,
                        'file_ready': True
                    })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.bank.report.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            'name' : 'Reporte Generado'
            }

    def download_waybill_data_excel(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        file_url = base_url+"/web/content?model=account.move.bank.report.wizard=file&filename_field=datas_fname&id=%s&&download=true" % (self.id,)
        self.generate_report_waybill_xlsx()
        return {
                 'type': 'ir.actions.act_url',
                 'url': file_url,
                 'target': 'new'
                }

    def _reopen_wizard(self):
        return { 'type'     : 'ir.actions.act_window',
                 'res_id'   : self.id,
                 'view_mode': 'form',
                 'view_type': 'form',
                 'res_model': 'account.move.bank.report.wizard',
                 'target'   : 'new',
                 'name'     : 'Resultado del Reporte'}
    