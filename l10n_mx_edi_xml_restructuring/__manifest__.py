# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

{
    'name' : 'Reestructuracion del XML',
    'category': 'Sales',
    "version"   : "20.0.1.0",
    'author': 'German Ponce Dominguez',
    'website': 'https://poncesoft.blogspot.com',
    'description': """
        Reglas CFDI 4.0
    """,
    'summary': 'Este modulo permite realizar cambios a la estructura mediante nuevos campos.',
    'depends' : [
                    'base', 
                    'account', 
                    'l10n_mx_edi', 
                    'l10n_mx_edi_extended', 
                    'l10n_mx_edi_40_generic_vat'
                ],
    'price': 1000,
    'currency': 'USD',
    'license': 'OPL-1',
    'data': [
        'views/invoice_view.xml',
        'views/product_view.xml',
        "security/ir.model.access.csv",
    ],
    'demo': [],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
