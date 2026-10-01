# -*- coding: utf-8 -*-
##############################################################################
#                 @author IT Admin
#
##############################################################################

{
    'name': 'CFDI Traslado Ext',
    'version': '19.01',
    'description': ''' Cambia al módulo de inventarios el módulo de traslado.
    ''',
    'category': 'Stock',
    'author': 'IT Admin',
    'website': 'www.itadmin.com.mx',
    'depends': [
        'stock', 'l10n_mx_traslado',
    ],
    'data': [
        'views/factura_traslado_view.xml',
	],
    'application': False,
    'installable': True,
    'license': 'AGPL-3',
}
