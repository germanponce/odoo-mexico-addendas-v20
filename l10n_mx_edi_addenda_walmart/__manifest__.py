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
    'name': "Addenda Walmart",
    'summary': """Addenda Walmart""",
    'description': """Addenda Walmart""",
    'author': "German Ponce Dominguez",
    'website': "https://poncesoft.blogspot.com",
    'category': 'Addendas',
    'version': '0.1',
    "license": "LGPL-3",
    'depends':
        [
            'account',
            'product',
            'sale',
            'stock',
            'l10n_mx_edi_addendas_base',
        ],
    'data': [
        'views/addenda_fields.xml',
        'views/addenda_walmart.xml',
        # 'security/ir.model.access.csv',
    ]
}