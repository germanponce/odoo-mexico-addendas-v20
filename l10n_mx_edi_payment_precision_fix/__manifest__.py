# -*- coding: utf-8 -*-
{
    "name": "MX EDI - Corrección de Precisión en Complemento de Pagos",
    "summary": "Corrige BaseP/ImporteP en pago20:TrasladoP/RetencionP para que respeten los decimales de la moneda del pago (2 para MXN) en vez de forzar 6 decimales siempre.",
    'description': 'Corrección Pagos 2',

    'author': 'German Ponce Dominguez',
    "website": "https//anfepi.com",
    "support": "german.poncce@outlook.com",

    'category': 'Timbrado Fiscal',
    'version': '1.9',
    'depends': ['account','l10n_mx_edi', 'account_edi'],

    'data': [
        "data/payment20_view.xml",

    ],

    'license': "AGPL-3",
    'installable': True,
    'application': False,
}