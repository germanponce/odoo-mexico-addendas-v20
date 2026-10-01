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
    'name': "Carta Porte 2.0 - Extensión CFDI 4.0",

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
        'l10n_mx_edi_40',
        'l10n_mx_edi_stock',
        'l10n_mx_edi_stock_40',
        'l10n_mx_edi_addendas_base',
    ],
    'data' : [
        'security/ir.model.access.csv',
        'data/waybill.tipo.embalaje.csv',
        'data/waybill.materiales.peligrosos.csv',
        'views/extra_fits_view.xml',
        'data/waybill_template.xml',
    ],
    'installable':True,
    'auto_install':False,    
}