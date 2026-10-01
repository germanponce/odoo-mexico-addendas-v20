# -*- coding: utf-8 -*-
from odoo import models

class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_get_invoice_cfdi_values(self, invoice):
        cfdi_values = super(AccountEdiFormat, self)._l10n_mx_edi_get_invoice_cfdi_values(invoice)

        tax_local_tras_tot = 0.0
        for tax_detail_transferred in cfdi_values['tax_details_transferred']:
            if not tax_detail_transferred['tax_name']:
                tax_detail_transferred['tax_name'] = tax_detail_transferred['tax'].l10n_mx_cfdi_tax_key
                tax_local_tras_tot += tax_detail_transferred['total']
        
        tax_local_ret_tot = 0.0
        for tax_detail_withholding in cfdi_values['tax_details_withholding']:
            if not tax_detail_withholding['tax_name']:
                tax_detail_withholding['tax_name'] = tax_detail_withholding['tax'].l10n_mx_cfdi_tax_key
                tax_local_ret_tot += tax_detail_withholding['total']
    
        cfdi_values['tax_local_ret_tot'] = '%.2f' % abs(tax_local_ret_tot)
        cfdi_values['tax_local_tras_tot'] = '%.2f' % abs(tax_local_tras_tot)
        cfdi_values['retenciones_locales'] = list(filter(lambda d: d['tax_name'] == '004', cfdi_values['tax_details_withholding']))
        cfdi_values['traslados_locales'] = list(filter(lambda d: d['tax_name'] == '004', cfdi_values['tax_details_transferred']))

        print('tax_details_transferred: ', cfdi_values['tax_details_transferred'])
        print('tax_details_withholding: ', cfdi_values['tax_details_withholding'])
        cfdi_values['tax_details_withholding'] = list(filter(lambda d: d['tax_name'] != '004', cfdi_values['tax_details_withholding']))
        cfdi_values['tax_details_transferred'] = list(filter(lambda d: d['tax_name'] != '004', cfdi_values['tax_details_transferred']))
        print('tax_details_transferred: ', cfdi_values['tax_details_transferred'])
        print('tax_details_withholding: ', cfdi_values['tax_details_withholding'])

        # Eliminar los impuestos locales de las líneas de la factura (Nodo: Conceptos)
        for invoice_line_value in cfdi_values['invoice_line_values']:
            print("invoice_line_value['tax_details']: ", invoice_line_value['tax_details'])
            for i in range(len(invoice_line_value['tax_details'])):
                if invoice_line_value['tax_details'][i]['tax'].l10n_mx_cfdi_tax_key == '004':
                    del invoice_line_value['tax_details'][i]
                    # invoice_line_value['tax_details'][i]['tax_name'] = '004'
            print("invoice_line_value['tax_details']: ", invoice_line_value['tax_details'])
            for i in range(len(invoice_line_value['tax_details_transferred'])):
                if invoice_line_value['tax_details_transferred'][i]['tax'].l10n_mx_cfdi_tax_key == '004':
                    del invoice_line_value['tax_details_transferred'][i]
                    # invoice_line_value['tax_details_transferred'][i]['tax_name'] = '004'
            for i in range(len(invoice_line_value['tax_details_withholding'])):
                if invoice_line_value['tax_details_withholding'][i]['tax'].l10n_mx_cfdi_tax_key == '004':
                    del invoice_line_value['tax_details_withholding'][i]
                    # invoice_line_value['tax_details_withholding'][i]['tax_name'] = '004'

        return cfdi_values
