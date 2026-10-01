cfdi_values:
{
    'serie_number': 'CUGDL', 
    'folio_number': '32145', 
    'certificate': l10n_mx_edi.certificate(1,), 
    'certificate_number': '00001000000501707325', 
    'record': account.move(14555,), 
    'supplier': res.partner(1,),
    'customer': res.partner(3838,), 
    'customer_rfc': 'OHA051017KE7', 
    'issued_address': res.partner(38769,), 
    'currency_precision': 2, 
    'origin_type': None, 
    'origin_uuids': [], 
    'format_string': <function AccountEdiFormat._l10n_mx_edi_get_common_cfdi_values.<locals>._format_string_cfdi at 0x7fee07523b80>, 
    'format_float': <function AccountEdiFormat._l10n_mx_edi_get_common_cfdi_values.<locals>._format_float_cfdi at 0x7fedfa2808b0>, 
    'document_type': 'I', 
    'currency_name': 'MXN', 
    'payment_method_code': '99', 
    'payment_policy': 'PPD', 
    'cfdi_date': '2023-01-13T16:26:29', 
    'l10n_mx_edi_external_trade_type': '01', 
    'currency_conversion_rate': None, 
    'account_4num': None, 
    'customer_fiscal_residence': None, 
    'invoice_line_values': [
        {
            'line': account.move.line(37759,), 
            'price_unit_wo_discount': 484.69, 
            'discount_amount': 0.0, 
            'total_wo_discount': 24234.5, 
            'price_subtotal_unit': 484.69, 
            'tax_details': [
                {
                    'tax': account.tax(2,), 
                    'base': 24234.5, 
                    'tax_type': 'Tasa', 
                    'tax_amount': 0.16, 
                    'tax_name': '002', 
                    'total': 3877.52
                }, 
                {
                    'tax': account.tax(14,), 
                    'base': 24234.5, 
                    'tax_type': 'Tasa', 
                    'tax_amount': -0.005, 
                    'tax_name': None, 'total': -121.17
                }
            ], 
            'tax_details_transferred': [
                {
                    'tax': account.tax(2,), 
                    'base': 24234.5, 
                    'tax_type': 'Tasa', 
                    'tax_amount': 0.16, 
                    'tax_name': '002', 
                    'total': 3877.52
                }], 
            'tax_details_withholding': [
                {
                    'tax': account.tax(14,), 
                    'base': 24234.5, 'tax_type': 
                    'Tasa', 'tax_amount': -0.005, 
                    'tax_name': None, 
                    'total': -121.17
                }
            ], 
            'custom_numbers': []
        }
    ],
    'total_amount_untaxed_wo_discount': 24234.5, 
    'total_amount_untaxed_discount': 0.0, 
    'tax_details_transferred': [
        {'tax': account.tax(2,), 
        'tax_type': 'Tasa', 
        'tax_amount': 0.16, 
        'tax_name': '002', 
        'total': 3877.52, 
        'base': 24234.5}], 
    'tax_details_withholding': [
        {'tax': account.tax(14,), 
        'tax_type': 'Tasa', 
        'tax_amount': -0.005, 
        'tax_name': '002', 
        'total': -121.17}], 
    'total_tax_details_transferred': 3877.52, 
    'total_tax_details_withholding': -121.17, 
    'fiscal_regime': '601', 
    'tax_objected': '02'}
