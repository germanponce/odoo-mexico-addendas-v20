# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'EDI Factoraje Financiero',
    'summary': 'Mexican Localization for EDI documents — Financial Factoring',
    'version': '19.0.1.0.0',
    'author': 'German Ponce',
    'category': 'Hidden',
    'website': 'http://poncesoft.blogspot.com',
    'license': 'OEEL-1',
    # l10n_mx_edi_addendas_base eliminado: no se usa en este módulo (v17 legacy dep)
    'depends': ['l10n_mx_edi'],
    'data': [
        'views/account_move_view.xml',
        'views/account_payment_view.xml',
        'views/res_partner_view.xml',
        'views/l10n_mx_edi_report_payment.xml',
    ],
    'installable': True,
}
