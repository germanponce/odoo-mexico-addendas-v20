# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com
# SUSCRIPTION REQUIRED — REDISTRIBUTION PROHIBITED — DECOMPILATION PROHIBITED
# See LICENSE file for full Odoo Proprietary License v1.0 terms.

{
    'name': 'XML Massive Download',
    'version': '19.0.48.16',
    'category': 'Hidden',
    'author':'ANFEPI: Roberto Requejo Jiménez y Roberto Requejo Fernández',
    'maintainer': 'ANFEPI',
    'website': 'https://www.anfepi.com',
    'support': 'soporte@anfepi.com',
    'contact_url': 'https://www.anfepi.com',
    'live_test_url': 'https://www.anfepi.com',
    # Contacto comercial: info@anfepi.com  |  Soporte tecnico: soporte@anfepi.com
    # Telefono/WhatsApp: +52 999 520 0611  |  Web: https://www.anfepi.com
    'description': """
XML Massive Download from SAT WebService
========================================

Download, import and manage XML files from SAT (Mexican Tax Authority) automatically.

Main Features:
--------------
* Automatic XML download from SAT for emitted and received invoices
* Batch processing with configurable date ranges
* Smart invoice matching and import
* Origin document tracking (Sales Orders/Purchase Orders)
* SAT status validation and updates
* Multi-company support with automatic FIEL configuration
* Performance optimized for large volumes

Origin Document Tracking:
-------------------------
* Link downloaded XMLs to their source documents (SO/PO)
* Smart search with flexible matching criteria
* Manual batch processing available
* Filters and grouping by document type

SAT vs Odoo Reconciliation Report:
----------------------------------
* Professional reconciliation report
* Compare SAT XMLs against Odoo invoices and payments
* Color-coded differences (green=match, yellow=variance, red/blue=large gaps)
* Drill-down functionality with smart buttons:
  - View related SAT XMLs
  - Access Odoo invoices/credit notes
  - Check payment complements
* Automatic calculation of variances and percentages
* Separate tracking for issued and received documents
* Filter ignored documents to focus on real differences

Technical Features:
-------------------
* Optimized database queries for better performance
* Automatic cleanup of temporary files
* Comprehensive error handling and logging
* Compatible with Odoo 17 Enterprise

    """,
    # Core hard dependencies (sin estos el modulo no carga):
    # - base, mail: Odoo core
    # - account: facturas y movimientos contables
    # - l10n_mx_edi: localizacion Mexico (CFDI)
    # - hr_payroll: campo payslip_id en account.edi.downloaded.xml.sat para
    #   vincular CFDIs tipo N (Nomina) con nominas reales. Si el cliente no
    #   usa nomina (despachos), instalar hr_payroll de todas formas (gratis
    #   y minimo), o instalar el bridge module futuro l10n_mx_xml_massive_download_payroll.
    # Soft dependencies (sale, purchase): NO en depends. El codigo verifica
    # en runtime con self.env.get('sale.order') / get('purchase.order')
    # y omite la busqueda de origen documental si el modulo no esta. Esto
    # permite que despachos contables sin sale/purchase usen el modulo sin
    # romper nada.
    'depends': ['l10n_mx_edi', 'account', 'base', 'mail', 'hr_payroll', 'stock'],
    'external_dependencies': {
        'python': ['pdf417gen'],
    },
    'data': [
        'security/security.xml',
        'security/ir_rules.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'wizard/invoice_wizard_views.xml',
        'wizard/upload_fiel_wizard.xml',
        'wizard/manual_upload_wizard_view.xml',
        'wizard/xml_upload_wizard_view.xml',
        'wizard/conciliaton_report_wizard_views.xml',
        'views/l10n_mx_edi_view.xml',
        'views/art69b_views.xml',
        'views/res_company_view.xml',
        'views/res_users_view.xml',
        'views/account_move_view.xml',
        'views/account_payment_view.xml',
        'views/account_move_line_origin_view.xml',
        'views/custom_accounting_settings_view.xml',
        'models/server_actions.xml',
        'data/server_actions.xml',
        'report/product_report.xml',
        'report/ir_actions_report.xml',
        'report/reporte_conciliacion_view_new.xml',
        'report/reporte_conciliacion_form_view.xml',
        'report/complemento_pago_reports_views.xml',
        'views/retencion_conciliacion_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'auto_install': False,
    "license": "OPL-1",

}
