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
    'name': "Addenda Fresko",
    'summary': """Addenda Fresko AMC7.1""",
    'description': """Addenda Fresko AMC 7.1""",
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
            'l10n_mx_edi_addenda_amece',
        ],
    'data': [
        'views/addenda_fields.xml',
        'views/addenda_fresko.xml',
        # 'security/ir.model.access.csv',
    ]
}