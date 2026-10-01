# -*- coding: utf-8 -*-
{
    'name': 'Análisis de Auditor (Metadatos SAT)',
    "version"   : "20.0.1.0",
    'category': 'Accounting/Localizations',
    'summary': 'Análisis de Facturación Electrónica - Auditoría SAT vs Odoo',
    'description': """
Análisis de Facturación Electrónica
====================================
Módulo de auditoría que compara los CFDIs registrados en Odoo con los
metadatos descargados del portal del SAT.

Funcionalidades:
- Carga de metadatos TXT/ZIP del SAT
- Comparativa de facturas: Odoo vs SAT
- Detección de facturas canceladas en Odoo pero vigentes en SAT
- Detección de facturas canceladas en SAT pero vigentes en Odoo
- Detección de facturas vigentes en Odoo sin registro en SAT
- Detección de facturas vigentes en SAT sin registro en Odoo
- Reportes PDF por categoría de discrepancia
    """,
    'author': 'German Ponce',
    'website': 'http://poncesoft.blogspot.mx',
    'depends': ['base', 'account', 'l10n_mx_edi'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'wizard/move_audit_analysis_view.xml',
        ## Reportes ##
        'report/01_report_cancel_odoo_no_sat.xml',
        'report/02_report_cancel_sat_no_odoo.xml',
        'report/03_report_posted_odoo_no_sat.xml',
        'report/04_report_posted_sat_no_odoo.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}