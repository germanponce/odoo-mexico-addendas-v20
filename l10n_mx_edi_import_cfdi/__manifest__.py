# -*- coding: utf-8 -*-
{
    "name": "Importar Facturas de Clientes o Proveedores desde archivos XML (Localización Mexicana)",

    'summary': """
    Importación múltiples facturas de clientes o proveedores en un archivo zip comprimido.""",

    'description': """
    Capacidad de importar masivamente facturas de clientes/proveedores como saldos iniciales (sin detalles de líneas de factura) ó facturas regulares (con las líneas de facturas completas).
    Capacidad de importar desde un archivo xml o múltiples archivos xml comprimidos en archivo zip.
    Seleccione si se crearán los clientes/proveedores proveedores que no existan su catálogo.
    Se carga también los archivos Pdf siempre y cuando se llame igual que el xml
    """,

    'author': 'German Ponce Dominguez',
    'support': 'germanponce@outlook.com',
    'license': 'OPL-1',
    'website': 'http://poncesoft.blogspot.com',
    'currency': 'USD',
    'price': 199.00,
    'category': 'Accounting',
    'version': '1.8',

    # any module necessary for this one to work correctly
    'depends': [
        'account',
        'account_edi',
        'l10n_mx_edi', 
        'l10n_mx_reports',
        'sale',
        'analytic'
    ],

    # always loaded
    'data': [
        'data/account_tax_data.xml',
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/account_views.xml',
	    'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'wizard/upload_edi_invoices.xml',
    ],
    'installable': True,
    'auto_install': False,
    'pre_init_hook': 'pre_init_check',
}