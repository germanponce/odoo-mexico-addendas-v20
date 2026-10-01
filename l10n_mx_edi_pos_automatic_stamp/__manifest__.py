# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

{
    'name' : 'Facturas POS - Timbrado Automatico',
    'category': 'Sales',
    "version"   : "20.0.1.0",
    'author': 'German Ponce Dominguez',
    'website': 'https://poncesoft.blogspot.com',
    'description': """
        This Module allows to create Customers Advance payment from Sales order.
        * Allow user to manage the Customers Advance payment for the Sales order.
        * Manage with Multi Company & Multi Currency.
    """,
    'summary': 'Este modulo permite realizar el timbrado automatico al crear factura desde el POS.',
    'depends' : [   
                    'base', 
                    'sale', 
                    'account', 
                    'stock', 
                    'sale_stock', 
                    'l10n_mx_edi', 
                    'l10n_mx_edi_40',
                    'point_of_sale',
                ],
    'price': 1000,
    'currency': 'USD',
    'license': 'OPL-1',
    'data': [
        # 'template/global_invoice_view.xml',
        'views/pos_view.xml',
    ],
   # "assets"               : {

   #                      'point_of_sale.assets':
   #                               [
   #                                   'l10n_mx_einvoice_pos_global_invoice/static/src/js/main.js',
   #                                  ],
   #                                          },

    'demo': [],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
