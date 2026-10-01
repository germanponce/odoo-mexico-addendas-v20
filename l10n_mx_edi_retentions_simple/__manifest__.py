# -*- coding: utf-8 -*-
{
    'name': 'México | Retentions CFDI | Versión Simplificada',
    'author': 'German Ponce Dominguez',
    'category': 'Accounting',
    'sequence': 50,
    'summary': 'Retentions CFDI — Complemento de Retenciones e Información de Pagos (SAT)',
    'website': 'https://poncesoft.blogspot.com',
    'version': '19.0.1.0.0',
    'description': """
Retentions CFDI
-------------------------------------------------
Genera CFDI de Retenciones e Información de Pagos (versión 1.0) para pagos a
receptores extranjeros, con firma digital SHA-1 y timbrado vía PAC Finkok.
Compatible con Odoo 19.
    """,
    'depends': [
        'base',
        'account',
        'l10n_mx_edi',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/retentions_cfdi.xml',
        'report/retention_cfdi_report.xml',
        'views/inherit_account_payment_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
