# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Portal for purchase documents",
    "summary": """
        Allows suppliers to upload documents related to Purchase Orders
        such as:

        - Invoice's XML file
        - Invoice's PDF file
        - Purchase order
        - Acknowledgment of receipt
    """,
    "version"   : "20.0.1.0",
    "author": "German Ponce Dominguez & Vauxoo",
    "category": "Localization/Mexico",
    "website": "https://poncesoft.blogspot.com",
    "license": "LGPL-3",
    "depends": [
        'purchase',
        'website',
        'l10n_mx_edi',  # Odoo official l10n_mx_edi (v17/18+)
        'portal',
    ],
    "demo": [],
    "data": [
        'security/ir.model.access.csv',
        'views/settings_view.xml',
        'security/purchase_security.xml',
        'views/portal_templates.xml',
        'views/portal_template_error.xml',
        'views/portal_sale_view.xml',
        'views/partner_view.xml',
        'views/account_invoice_view.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            # 'l10n_mx_portal_vendor_bills/static/src/js/attachments_form.js',
        ],
    },
    "installable": True,
    "auto_install": False,
}
