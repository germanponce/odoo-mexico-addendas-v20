# -*- coding: utf-8 -*-
{
    'name': 'CFDI Pago - Fecha Efectiva de Pago',
    'summary': "Permite establecer la Fecha Efectiva para el complemento de pago del CFDI.",
    'description': 'Permite al usuario definir la FechaPago del complemento de pago en el XML del CFDI 4.0.',

    'author': 'German Ponce Dominguez',
    'website': 'http://anfepi.com',
    'support': 'german.ponce@outlook.com',

    'category': 'Accounting/Localizations/EDI',
    "version"   : "20.0.1.0",
    'depends': ['account', 'l10n_mx_edi'],

    'data': [
        'security/ir.model.access.csv',
        'views/extra_fits_view.xml',
    ],

    'license': 'AGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
