
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_edi_donat_auth = fields.Char(
        'Número de Autorización', help='Número del oficio en que se haya informado a la organización civil o \
        fideicomiso, la procedencia de la autorización para recibir donativos deducibles, o su renovación correspondiente otorgada por el SAT.')
    l10n_mx_edi_donat_date = fields.Date(
        'Fecha de Autorización', help='Fecha del oficio en que se haya informado a la organización civil o \
        fideicomiso, la procedencia de la autorización para recibir donativos deducibles, o su renovación correspondiente otorgada por el SAT.')
    l10n_mx_edi_donat_note = fields.Text(
        'Leyenda', help='Atributo requerido para señalar de manera expresa que el comprobante que se expide \
        se deriva de un donativo.')
