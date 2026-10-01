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
    "name"      : "Ejercicio Fiscal y Periodos Mensuales", 
    "version"   : "20.0.1.0",
    'summary'   : 'Ejercicio Fiscal y Periodos Mensuales',
    'sequence'  : 20,
    "author"    : "German Ponce Dominguez", 
    "category"  : "Account", 
    "description": """

Ejercicio Fiscal y Periodos Mensuales
=====================================

El Año Fiscal en México es prácticamente un año Natural.

Para México es necesario tener 13 periodOs, por ejemplo para el Año Fiscal 2019
se necesita:


Periodo => Periodo de Apertura

-  01/2019    =>   [   ]
-  02/2019    =>   [   ]
-  03/2019    =>   [   ]
-  04/2019    =>   [   ]
-  05/2019    =>   [   ]
-  06/2019    =>   [   ]
-  07/2019    =>   [   ]
-  08/2019    =>   [   ]
-  09/2019    =>   [   ]
-  10/2019    =>   [   ]
-  11/2019    =>   [   ]
-  12/2019    =>   [   ]
-  13/2019    =>   [ X ]

    """, 
    "website" : "https://www.fixdoo.mx",
    'license': 'Other proprietary',
    "depends": [
        "account", 
    ], 

    "data": [
        'security/ir.model.access.csv',
        "views/account_view.xml",
            ], 
    "installable": True, 
    "post_init_hook": "post_init_hook",
}