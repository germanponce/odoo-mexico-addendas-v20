# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

{
    'name': 'Re-facturación Global (POS)',
    'category': 'Point of Sale',
    "version"   : "20.0.1.0",
    'author': 'German Ponce Dominguez',
    'website': 'https://poncesoft.blogspot.com',
    'description': """
        Re-facturación de pedidos de Punto de Venta ya incluidos en una
        Factura Global (CFDI a público en general): separa la Nota de
        Crédito, la re-emite a nombre del cliente real y ofrece por
        separado las operaciones manuales de asociación (NC <-> factura).

    """,
    'summary': 'Re-facturación de Notas de Crédito asociadas a Facturas Globales de POS.',
    'depends': ['base', 'point_of_sale', 'account', 'l10n_mx_edi', 'l10n_mx_edi_pos'],
    'price': 1000,
    'currency': 'USD',
    'license': 'OPL-1',
    'data': [
        'security/ir.model.access.csv',
        'views/pos_order_view.xml',
    ],
    'demo': [],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
