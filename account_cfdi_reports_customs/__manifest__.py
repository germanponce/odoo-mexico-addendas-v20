# -*- coding: utf-8 -*-
# © <2015> <German Ponce Dominguez>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Reporte de Facturas Custom Odoo 17",
    "version": "1.8",
    "category": "Report",
    "website": "http://poncesoft.blogspot.com",
    "author": "German Ponce Dominguez (Desarrollador)",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "description": "Reporte de Factura.",
    "external_dependencies": {
        "python": [],
        "bin": [],
    },
    "depends": [
        "stock",
        "sale",
        "sale_stock",
        "sale_management",
        "l10n_mx_edi",
    ],
    "data": [
        # 'security/ir.model.access.csv',
        'reports/cfdi_report_view.xml',
        'reports/cfdi_report_02_view.xml',
        'reports/cfdi_report_payment_view.xml',
        'reports/cfdi_report_payment_02_view.xml',
        'view/account_view.xml',
    ],
    "demo": [
    ],
    "qweb": [
    ]
}
