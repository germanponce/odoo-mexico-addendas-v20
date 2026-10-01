# -*- coding: utf-8 -*-
# Coded by German Ponce Dominguez 
#     ▬▬▬▬▬.◙.▬▬▬▬▬  
#       ▂▄▄▓▄▄▂  
#    ◢◤█▀▀████▄▄▄▄▄▄ ◢◤  
#    █▄ █ █▄ ███▀▀▀▀▀▀▀ ╬  
#    ◥ █████ ◤  
#     ══╩══╩═  
#       ╬═╬  
#       ╬═╬ Dream big and start with something small!!!  
#       ╬═╬  
#       ╬═╬ You can do it!  
#       ╬═╬   Let's go...
#    ☻/ ╬═╬   
#   /▌  ╬═╬   
#   / \
# Cherman Seingalt - german.ponce@outlook.com

{
    'name' : 'Reporte - Resumen Cobranza Pagos IEPS',
    'category': 'Accounting',
    "version"   : "20.0.1.0",
    'author': 'German Ponce Dominguez',
    'website': 'https://poncesoft.blogspot.com',
    'description': """
Reporte de operaciones bancarias y pagos
    """,
    'summary': 'Este modulo permite generar un resumen de pagos con ieps.',
    'depends' : [
                    'base', 
                    'account', 
                    'l10n_mx_edi', 
                    'l10n_mx_edi_extended', 
                ],
    'price': 1000,
    'currency': 'USD',
    'license': 'OPL-1',
    'data': [
        'views/account_view.xml',
        'report/payments_resume_report.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
