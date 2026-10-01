# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

{
    'name' : 'Reglas Genericas para CFDI 4.0 en facturas a publico en general.',
    'category': 'Sales',
    'version': '19.0.1.0',
    'author': 'German Ponce Dominguez',
    'website': 'https://poncesoft.blogspot.com',
    'description': """
        Reglas CFDI 4.0
    """,
    'summary': 'Este modulo permite realizar facturas a publico en general.',
    'depends' : [
                    'base', 
                    'account', 
                    'l10n_mx_edi', 
                    # 'l10n_mx_edi_pos', # Descomentar si no  usan POS
                ],
    'price': 1000,
    'currency': 'USD',
    'license': 'OPL-1',
    'data': [
        # 'template/generic_invoice_edi.xml',
        # 'views/generic_invoice.xml',
        # "security/ir.model.access.csv",
    ],
    'demo': [],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
