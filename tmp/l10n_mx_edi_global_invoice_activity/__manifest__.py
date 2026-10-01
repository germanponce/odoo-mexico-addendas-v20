# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

{
    'name' : 'Factura Global como Actividad',
    'category': 'Sales',
    'version': '19.0.1.0',
    'author': 'German Ponce Dominguez',
    'website': 'https://poncesoft.blogspot.com',
    'description': """
        Reglas CFDI 4.0
    """,
    'summary': 'Este modulo permite realizar facturas a publico en general como actividades sin detalle.',
    'depends' : [
                    'base', 
                    'account', 
                    'l10n_mx_edi', 
                    'l10n_mx_edi_pos', # Descomentar si no  usan POS
                    'l10n_mx_edi_40_generic_vat',
                    'l10n_mx_edi_global_address'
                ],
    'price': 1000,
    'currency': 'USD',
    'license': 'OPL-1',
    'data': [
        'views/global_invoice.xml',
        # "security/ir.model.access.csv",
    ],
    'demo': [],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
