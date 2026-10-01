# -*- coding: utf-8 -*-
# German Ponce Dominguez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountJournal(models.Model):
    """Agrega al diario contable un campo para seleccionar el reporte CFDI
    que se utilizará al imprimir/enviar facturas asociadas a ese diario."""

    _inherit = 'account.journal'

    cfdi_report_id = fields.Many2one(
        comodel_name='ir.actions.report',
        string='Reporte CFDI',
        domain=[('model', '=', 'account.move'), ('report_type', '=', 'qweb-pdf')],
        help="Reporte QWeb-PDF que se usará al generar el PDF de las facturas "
             "emitidas desde este diario. Si no se configura se usará el reporte "
             "estándar de Odoo (account.account_invoices).",
    )
