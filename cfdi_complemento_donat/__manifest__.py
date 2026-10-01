# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Complemento CFDI para Donaciones',
    'version': '1.8',
    "author" : "German Ponce Dominguez",
    'category': 'Accounting/Localizations/EDI',
    'summary': 'Complementos CFDI',
    "website" : "http://poncesoft.blogspot.com",
    'description': """

    """,
    'depends': [
                 'l10n_mx_edi_extended',
                 'l10n_mx_edi',
    ],
    'external_dependencies': {
        'python': [],
    },
    'data': [
                "data/donations.xml",
                "views/res_company_view.xml",
                "views/res_partner_view.xml",
                "views/account_move_view.xml",
    ],
    'demo': [
        
    ],
    'installable': True,
    'license': 'OEEL-1',
    'assets': {
    }
}
