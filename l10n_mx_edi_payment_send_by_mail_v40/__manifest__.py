# -*- coding: utf-8 -*-

# Part of Probuse Consulting Service Pvt Ltd. See LICENSE file for full copyright and licensing details.

{
    'name': 'Envio Automatico de Correo (Pagos)',
    "version"   : "20.0.1.0",
    'category': 'Invoices & Payments',
    'price': 130.0,
    'currency': 'USD',
    'summary': """Automatically send payment receipt/report to customer.""",
    'description': """
Payment Receipt Send by Mail Automatically
Payment Receipt Send by Mail
customer payment receipt
customer receipt send by email
customer receipt
customer payment report
payment report send
send payment receipt

    """,
    'license': 'Other proprietary',
    'author': 'German Ponce Dominguez',
    'website': 'http://poncesoft.blogspot.com',
    'images': ['static/description/image.png'],
    'support': 'german.ponce@outlook.com',
    'depends': [
                    'account', 
                    'l10n_mx_edi',
                    'l10n_mx_edi_40'
                ],
    'data': [
        'views/res_partner.xml',
        'views/mail_template.xml',
    ],
    'installable': True,
    'auto_install': False
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
