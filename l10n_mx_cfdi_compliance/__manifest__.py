# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez
# License OPL-1 (see LICENSE file for full terms).
{
    "name": "CFDI Compliance Engine MX (ANFEPI)",
    "summary": "Motor de Compliance Fiscal Preventivo para CFDIs de Proveedores - Mexico",
    "description": """
CFDI Compliance Engine for Mexico
=================================

Enterprise preventive fiscal compliance engine that validates supplier CFDIs
in real-time at the very moment the XML is attached to Odoo, before any
accounting or purchase posting takes place.

Key features
------------
* Universal interception via ir.attachment (covers drag&drop, chatter, OCR,
  Documents, mass import, email gateway).
* Pluggable rule engine with Strategy + Registry pattern.
* Configurable per-company compliance profiles (info / warning / blocking /
  authorization-required severities).
* Coordinados fiscal regime supported (Art. 72-73 LISR).
* Immutable hash-chained audit log.
* Multi-company strict isolation.
* Real-time OWL compliance panel.

Author: ANFEPI - Roberto Requejo Jimenez
Website: https://www.anfepi.com
""",
    "version"   : "20.0.1.0",
    "author": "ANFEPI - Roberto Requejo Jimenez",
    "maintainer": "ANFEPI",
    "website": "https://www.anfepi.com",
    "support": "soporte@anfepi.com",
    "contact_url": "https://www.anfepi.com",
    # Contacto comercial: info@anfepi.com  |  Soporte tecnico: soporte@anfepi.com
    # Telefono/WhatsApp: +52 999 520 0611  |  Web: https://www.anfepi.com
    "license": "OPL-1",
    "category": "Accounting/Localizations/Mexico",
    "depends": [
        "base",
        "mail",
        "account",
        "purchase",
        "stock",
        "l10n_mx",
        "l10n_mx_xml_massive_download",
    ],
    "external_dependencies": {
        "python": ["lxml", "cryptography"],
    },
    "data": [
        # Security
        "security/compliance_groups.xml",
        "security/ir_rule.xml",
        "security/ir.model.access.csv",
        # Data
        "data/ir_sequence_data.xml",
        "data/ir_cron_data.xml",
        "data/compliance_rules_data.xml",
        "data/default_profiles_data.xml",
        "data/mail_templates_data.xml",
        # Wizards
        "wizards/cfdi_override_wizard_views.xml",
        "wizards/cfdi_reprocess_wizard_views.xml",
        "wizards/cfdi_import_wizard_views.xml",
        # Views
        "views/cfdi_document_views.xml",
        "views/compliance_profile_views.xml",
        "views/compliance_rule_views.xml",
        "views/compliance_result_views.xml",
        "views/audit_log_views.xml",
        "views/coordinado_relation_views.xml",
        "views/cfdi_pipeline_job_views.xml",
        "views/account_move_views.xml",
        "views/res_company_views.xml",
        "views/res_partner_views.xml",
        "views/res_users_view.xml",
        "views/account_edi_downloaded_xml_sat_views.xml",
        "views/menus.xml",
        "views/cfdi_nomina_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_mx_cfdi_compliance/static/src/components/**/*.js",
            "l10n_mx_cfdi_compliance/static/src/components/**/*.xml",
            "l10n_mx_cfdi_compliance/static/src/components/**/*.scss",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
}
