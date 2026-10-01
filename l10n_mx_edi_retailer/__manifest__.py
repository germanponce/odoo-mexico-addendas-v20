# -*- encoding: utf-8 -*-
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
    "name": "Complemento Detallista Odoo E.E.",
    'summary': """Complemento Detallista """,
    'description': """Complemento Detallista""",
    'author': "German Ponce Dominguez",
    'website': "https://poncesoft.blogspot.com",
    'category': 'Addendas',
    "version"   : "20.0.1.0",
    'depends':
        [
            'account',
            'product',
            'sale',
            'stock',
            'l10n_mx_edi',
            'l10n_mx_edi_addendas_base',
        ],
    'data': [
        "security/ir.model.access.csv",
        "data/l10n_mx_edi_addenda_retailer.xml",
        "views/retailer_wizard_views.xml",
        "views/res_company_view.xml",
        "views/res_partner_view.xml",
        "views/product_template_view.xml",
        "views/sale_order_view.xml",
        "views/account_invoice_view.xml",
    ]
}