# -*- coding: utf-8 -*-
{
    'name': 'POS - Uso CFDI in Customers & Metodo Pago',
    'summary': "Set Default Customer in POS and CFDI Use.",
    'description': 'Set Default Customer in POS',

    'author': 'German Ponce Dominguez',
    'website': 'http://poncesoft.blogspot.com',
    "support": "german.poncce@outlook.com",

    'category': 'Point of Sale',
    'version': '1.8',
    'depends': ['account','l10n_mx_edi', 'account_edi'],

    'data': [
        # 'views/assets.xml', ### Los Assets ahora se entienden mediante el manifest
        'views/extra_fits_view.xml',
    ],

    'license': "AGPL-3",
    'installable': True,
    'application': False,

    'images': ['static/description/banner.png'],
}
