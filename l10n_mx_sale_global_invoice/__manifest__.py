# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

{
    'name' : 'Factura Global (Ventas SO)',
    'category': 'Sales',
    "version"   : "20.0.1.0",
    'author': 'German Ponce Dominguez',
    'website': 'https://poncesoft.blogspot.com',
    'description': """
        This Module allows to create Customers Advance payment from Sales order.
        * Allow user to manage the Customers Advance payment for the Sales order.
        * Manage with Multi Company & Multi Currency.
    """,
    'summary': 'Este modulo permite realizar la factua Global.',
    'depends' : ['base', 'sale', 'account', 'stock', 'sale_stock', 'l10n_mx_edi'],
    'price': 1000,
    'currency': 'USD',
    'license': 'OPL-1',
    'data': [
        'template/global_invoice_view.xml',
        'views/global_invoice.xml',
        'views/parameter.xml',
        "security/ir.model.access.csv",
    ],
    'demo': [],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
