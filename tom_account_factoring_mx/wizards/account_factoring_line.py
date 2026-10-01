from odoo import api, fields, models

class AccountFactoringLine(models.TransientModel):
    _name = 'account.factoring.line'
    _description = 'Linea de factoraje'

    invoice_id = fields.Many2one(comodel_name="account.move", string="Factura")
    factoring_id = fields.Many2one(comodel_name="account.factoring", string="Factoraje")
    amount = fields.Float(string="Importe")

