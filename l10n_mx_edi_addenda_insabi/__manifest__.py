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
    'name': "Addenda INSABI",
    'summary': """Addenda INSABI """,
    'description': """Addenda INSABI""",
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
            'l10n_mx_edi_addendas_base',
        ],
    'data': [
        'views/addenda_fields.xml',
        'views/addenda_insabi.xml',
        # 'security/ir.model.access.csv',
    ]
}