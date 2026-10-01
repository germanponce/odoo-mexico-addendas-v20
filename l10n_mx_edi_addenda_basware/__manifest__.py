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
    'name': "Addenda Basware",

    'summary': """
        """,

    'description': """
        
    """,

    'author': "German Ponce Dominguez",
    'website': "https://poncesoft.blogspot.com",
    'category': 'Addendas',
    'version': '0.1',

    'depends': 
    [
        'account',
        'product',
        'sale',
        'stock',
        'l10n_mx_edi_addendas_base',
        'l10n_mx_edi',
        'l10n_mx_edi_extended',

    ],
    'data' : [
        'views/addenda_basware.xml',
        'views/addenda_fields.xml',
        'security/ir.model.access.csv',
    ],
    'installable':True,
    'auto_install':False,    
}