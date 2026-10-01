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
   'name' : 'Complemento - Leyendas Fiscales E.E.',
    'description' : """ 

    Este Modulo Permite incorporar el Complemento de Leyendas Fiscales al generar Facturas CFDI.

    Configuracion

    - Activamos el Campo Leyendas Fiscales, en la Ficha de Clientes.

    - Al generar la Factura en el Sistema, el campo Comentario (Comment), debe incluir el texto que se llevara al nodo Comentario, en la generacion del Complemento.


    """,
    'version': '1.8',
    "author" : "German Ponce Dominguez",
    'category': 'Accounting/Localizations/EDI',
    'summary': 'Complementos CFDI',
    "website" : "http://poncesoft.blogspot.com",

    'depends': [
                    'l10n_mx_edi_extended',
                    'account',
                    'sale',
                    'l10n_mx_edi',
    ],
    'external_dependencies': {
        'python': [],
    },
    'data': [
                'security/ir.model.access.csv',
                'data/fiscal_legend_template.xml',
                'views/account_invoice_view.xml',
                'views/res_partner_views.xml',
                'views/account_views.xml',
                'views/fiscal_legend_views.xml',
                'views/l10n_mx_edi_report_invoice.xml',
    ],
    'demo': [
        
    ],
    'installable': True,
    'license': 'OEEL-1',
    'assets': {
    }
}
