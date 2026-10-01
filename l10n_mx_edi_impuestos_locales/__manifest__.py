# -*- coding: utf-8 -*-
{
    'name': 'Complemento Impuestos Locales (Mexican Localization)',

    'summary': """
    """,

    'description': """
    """,

    'author': 'German Ponce & José Candelas',
    'support': 'german.ponce@outlook.com',
    'license': 'OPL-1',
    'website': 'http://poncesoft.blogspot.com',
    'currency': 'USD',
    'price': 98.00,
    'maintainer': 'German Ponce Dominguez',
    # 'live_test_url': 'https://www.youtube.com/watch?v=XXXXXXXXXXXX',
    'images': ['static/description/banner.png'],

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Accounting',
    "version"   : "20.0.1.0",

    # any module necessary for this one to work correctly
    'depends': ['account', 'l10n_mx', 'l10n_mx_edi', 'l10n_mx_edi_40'],

    # always loaded
    'data': [
        'data/4.0/cdfi.xml',
        'data/4.0/account_tax_data.xml',
        # 'views/report_invoice_document.xml',
        # 'views/account_tax_views.xml', Ya se ve el campo el módulo cnd_l10n_mx_edi_import_cfdi
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'pre_init_hook': 'pre_init_check',
}
