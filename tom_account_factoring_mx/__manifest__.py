# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
{
    'name': "Factoraje Financiero MX",
    'summary': "Adición de pagos con factoraje en Pesos y Dolares",
    'description': """
        Pagos con Factoraje.
        28-01-2025 / FIX / Pagos completos, error de decimales. 
    """,
    'author': "TuOdoo México",
    'website': "https://tuodoomexico.com",
    'category': 'Contabilidad',
    "version"   : "20.0.1.0",
    'depends': ['base','account','l10n_mx_edi'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner.xml',
        'wizards/account_factoring.xml',
        'data/ir_actions_server.xml',
        'views/account_payment_register.xml',
        'views/payment20.xml'
    ],
    'license': 'AGPL-3'
}

