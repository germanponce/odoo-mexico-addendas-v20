# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

{
    'name' : 'Correccion de Decimales Factura Global',
    'category': 'Sales',
    'version': '19.0.1.0',
    'author': 'German Ponce Dominguez',
    'website': 'https://poncesoft.blogspot.com',
    'description': """
        Reglas CFDI 4.0
    """,
    'summary': 'Fix Factura Electronica',
    'depends' : [
                    'base', 
                    'account', 
                    'point_of_sale',
                    'l10n_mx_edi', 
                    'l10n_mx_edi_pos', # Descomentar si no  usan POS
                    'l10n_mx_edi_40_generic_vat'
                ],
    'price': 1000,
    'currency': 'USD',
    'license': 'OPL-1',
    'data': [
        # 'views/global_template_view.xml',
    ],
    'demo': [],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
