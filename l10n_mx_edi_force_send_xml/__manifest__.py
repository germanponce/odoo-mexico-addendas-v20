# -*- coding: utf-8 -*-
{
    'name': 'CFDI 4.0 - Envio de XML Manual (Odoo 18)',
    'summary': "Permite establecer el archivo XML a enviar manualmente al PAC",
    'description': '''
        Migración a Odoo 18 del módulo de envío manual de XML CFDI.
        
        Características:
        - Permite adjuntar un archivo XML personalizado
        - Envía el XML adjunto directamente al PAC sin generar QWeb
        - Compatible con la nueva estructura l10n_mx_edi.document de Odoo 18
        - Mantiene toda la funcionalidad de firma y timbrado
    ''',

    'author': 'German Ponce Dominguez',
    'website': 'http://poncesoft.blogspot.com',
    "support": "german.poncce@outlook.com",

    'category': 'Accounting/Localizations/EDI',
    "version"   : "20.0.1.0",
    'depends': [
        'account',
        'l10n_mx_edi',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/l10n_mx_edi_document_views.xml',
        'views/account_move_views.xml',
        'views/xml_attachment_wizard_views.xml',
    ],
    
    # 'demo': [
    #     'demo/demo_data.xml',
    # ],

    'license': "LGPL-3",
    'installable': True,
    'application': False,
    'auto_install': False,
}