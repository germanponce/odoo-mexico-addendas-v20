# coding: utf-8

{
    'name': 'EDI for Mexico (Cuenta Predial)',
    "version"   : "20.0.1.0",
    "author" : "German Ponce Dominguez",
    'category': 'Accounting/Localizations/EDI',
    'summary': 'Adds the CuentaPredial to CFDI v4.0',
    "website" : "http://poncesoft.blogspot.com",
    'description': """

    """,
    'depends': [
                    'account',
                    'l10n_mx_edi_40',
                    'l10n_mx_edi_extended',
                    'l10n_mx_edi_extended_40'
    ],
    'external_dependencies': {
        'python': [],
    },
    'data': [
                'data/4.0/cfdi.xml',
                'views/account_move_view.xml',
    ],
    'demo': [
        
    ],
    'installable': True,
    'license': 'OEEL-1',
    'assets': {
    }
}
