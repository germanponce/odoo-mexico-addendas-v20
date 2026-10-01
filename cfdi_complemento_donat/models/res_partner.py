
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    complemento_donaciones = fields.Boolean(
        'Complemento - Donatarias',
        help='Use this field when the invoice require the complement to '
        '"Donations". This value will be used to indicate the use of the '
        'information from the document that authorize to receive '
        'deductible donations, granted by SAT')
