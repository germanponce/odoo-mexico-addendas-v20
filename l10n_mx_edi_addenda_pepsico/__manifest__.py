# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

{
    'name' : 'Addenda PepsiCo',
    'category': 'Sales',
    'version': '1.0',
    'author': 'German Ponce Dominguez',
    'website': 'https://poncesoft.blogspot.com',
    'description': """
        Addenda Pepsico
    """,
    'summary': 'Este modulo permite realizar la Addenda PepsiCo.',
    'depends' : ['base', 'stock', 'sale_stock', 'l10n_mx_edi', 'l10n_mx_edi_addendas_base'],
    'price': 1000,
    'currency': 'USD',
    'license': 'OPL-1',
    'data': [
        'views/account_invoice.xml',
        'views/addenda_pepsico.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: