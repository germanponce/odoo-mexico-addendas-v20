# -*- coding: utf-8 -*-

{
    "name" : "Tipo de Cambio Manual en Odoo",
    "version"   : "20.0.1.0",
    "depends" : [
                    'base',
                    'account',
                    'stock_account',
                    'l10n_mx_edi',
                    ],
    "author": "German Ponce Dominguez",
    "summary": "",
    "description": """

    Tipo de Cambio Manual en Odoo 19 Integrado con la LdM
    """,
    "price": 150,
    "currency": "EUR",
    'category': 'Accounting',
    "website" : "https://poncesoft.blogpost.com",
    "data" :[
             "views/account_invoice.xml",
    ],
    "auto_install": False,
    "installable": True,
    "license": "OPL-1",
}
