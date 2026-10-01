# -*- coding: utf-8 -*-
#################################################################################
# Author      : German Ponce Dominguez 
# Correo      : german.ponce@outlook.com
#################################################################################

{
    'name': "Pregunta Simple POS",
    "version"   : "20.0.1.0",
    "license": "LGPL-3",
    "category" : "Point of Sale",
    'summary': 'Facturación POS con el Uso S01 por defecto.',
    "description": """
        
        Define el Uso de CFDI S01 al facturar desde POS.
    
    """,
    "author": "German Ponce",
    "website" : "http://poncesoft.blogspot.com.mx",
    "depends" : [
                'base',
                'sale',
                'point_of_sale',
                'l10n_mx_edi_pos',
    ],
    "data": [
            #'views/pos_order_form.xml',
    ],
    
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_mx_edi_pos_default_uso_cfdi_s01/static/src/js/add_info_popup.js",
            # "l10n_mx_edi_pos_default_uso_cfdi_s01/static/src/js/PaymentScreen.js",
            "l10n_mx_edi_pos_default_uso_cfdi_s01/static/src/xml/add_info_popup.xml",
        ],
    },
    "auto_install": False,
    "installable": True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
