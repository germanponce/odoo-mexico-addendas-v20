# -*- coding: utf-8 -*-
{
    'name': 'Factoraje Financiero MX',
    'summary': 'Adición de pagos con factoraje en Pesos y Dólares',
    'description': """
        Complemento de Factoraje Financiero para CFDI de Pagos 2.0.
        Permite registrar operaciones de factoraje, generando el asiento
        contable de compensación y emitiendo el CFDI P con dos nodos
        pago20:Pago: uno para el pago ordinario y otro para el factoraje.
    """,
    'author': 'German Ponce Dominguez',
    'website': 'https://poncesoft.blogspot.com',
    'category': 'Contabilidad',
    'version': '19.0.1.0.0',
    'depends': [
                    'base', 
                    'account', 
                    'l10n_mx_edi', 
                    'l10n_mx_edi_extended'
               ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner.xml',
        'wizards/account_factoring.xml',
        'data/ir_actions_server.xml',
        'views/account_payment_register.xml',
        'views/payment20.xml',
        'views/factoring_report.xml',
    ],
    'license': 'AGPL-3',
}
