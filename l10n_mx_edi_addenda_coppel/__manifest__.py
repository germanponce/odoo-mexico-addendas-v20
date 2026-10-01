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
    'name': "Addenda Coppel",

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
    ],
    'data' : [
        'views/addenda_coppel.xml',
        'views/addenda_fields.xml'
    ],
    'installable':True,
    'auto_install':False,    
}