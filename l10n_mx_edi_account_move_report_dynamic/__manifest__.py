# -*- coding: utf-8 -*-
# German Ponce Dominguez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Reporte de Facturas Dinámicas (Selector de Reporte)",
    "version": "19.0.2.0.0",
    "category": "Report",
    "website": "http://poncesoft.blogspot.com",
    "author": "German Ponce Dominguez (Desarrollador)",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "description": "Reportes de Factura CFDI 4.0 con selector dinámico por diario. "
                   "Incluye reporte de Factura Transporte (Carta Porte 3.1).",
    "external_dependencies": {
        "python": [],
        "bin": [],
    },
    "depends": [
        "account",
        "stock",
        "sale",
        "sale_stock",
        "sale_management",
        "l10n_mx_edi",
        "l10n_mx_einvoice_waybill_complemento_ee", # Solo si usa el modulo de complemento carta porte
        "tms", # Solo si usa el modulo de complemento carta porte y tms
    ],
    "data": [
        # Reportes de Factura
        'reports/cfdi_report_view.xml',
        'reports/cfdi_report_02_view.xml',
        # Reportes de Pago
        'reports/cfdi_report_payment_view.xml',
        'reports/cfdi_report_payment_02_view.xml',
        # Reporte Transporte / Carta Porte
        'reports/cfdi_report_transporte_view.xml', # Solo si usa el modulo de complemento carta porte
        # Vistas extendidas
        'views/account_view.xml',
    ],
    "demo": [],
}
