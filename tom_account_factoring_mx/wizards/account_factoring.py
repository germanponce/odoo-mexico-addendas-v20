from odoo import api, fields, models, Command
from odoo.exceptions import ValidationError

class AccountFactoring(models.TransientModel):
    _name = 'account.factoring'
    _description = 'Factoraje financiero'
    _rec_name = "partner_id"

    factoring_date = fields.Date(string="Fecha")
    partner_id = fields.Many2one(comodel_name="res.partner", string="Factorante financiero")
    invoice_partner_id = fields.Many2one(comodel_name="res.partner", string="Cliente")
    bill_id = fields.Many2one(comodel_name="account.move", string="Factura de proveedor")
    bill_amount = fields.Float(string="Importe proveedor", compute="compute_bill_amount", store=True)
    journal_id = fields.Many2one(comodel_name="account.journal", string="Diario")
    balance = fields.Float(string="Balance", compute="_compute_balance", store=True)
    factoring_amount = fields.Float(string="Importe de factoraje", store=True, compute="compute_factoring_amount")
    line_ids = fields.One2many(comodel_name="account.factoring.line", inverse_name="factoring_id", string="Linea de factoraje")
    amount = fields.Float(string="Importe interes")

    def check_factoring_amount(self):
        for rec in self:
            if rec.factoring_amount > rec.bill_id.amount_residual:
                raise ValidationError("El valor de factoraje no puede ser mayor al monto pendiente de la factura proveedor, favor de validar.")
    @api.depends("bill_id")
    def compute_bill_amount(self):
        for rec in self:
            rec.bill_amount = rec.bill_id.amount_residual if rec.bill_id else 0

    @api.depends("bill_id", "line_ids", "line_ids.amount","factoring_amount")
    def _compute_balance(self):
        for rec in self:
            rec.balance = rec.bill_id.amount_residual - round(rec.factoring_amount,2) if rec.bill_id else 0

    @api.depends("line_ids.amount","line_ids")
    def compute_factoring_amount(self):
        for rec in self:
            rec.factoring_amount = round(sum(rec.line_ids.mapped("amount")),2)
            
    @api.onchange("amount")
    def onchange_amount(self):
        for rec in self:
            factor = rec.amount / sum(rec.line_ids.mapped("invoice_id.amount_residual"))
            for line in rec.line_ids:
                line.amount = round(line.invoice_id.amount_residual * factor, 2)
            amount = sum(rec.line_ids.mapped("amount"))
            diff_amount = round(rec.amount - amount,2)
            rec.line_ids[0]["amount"] = rec.line_ids[0]["amount"] + diff_amount

    def create_factoring(self):
        self.check_factoring_amount()
        # Creacion de asiento contable de factoraje
        payment_method_id = self.env["l10n_mx_edi.payment.method"].sudo().search([("code","=","17")],limit=1)
        line_list = [Command.create({
            "account_id": self.bill_id.partner_id.property_account_payable_id.id,
            "partner_id": self.bill_id.partner_id.id,
            "debit": self.factoring_amount,
            "name": f"Factoraje {self.line_ids.mapped('invoice_id.name')}",
        })]
        for line in self.line_ids:
            
            line_list.append(Command.create({
                "account_id": line.invoice_id.partner_id.property_account_receivable_id.id,
                "partner_id": line.invoice_id.partner_id.id,
                "credit": line.amount,
                "name": f"{line.invoice_id.name}",
            }))
            if line.invoice_id and line.invoice_id.x_factoring_invoice_ids:
                for factoring in line.invoice_id.x_factoring_invoice_ids:
                    line.invoice_id.x_factoring_invoice_ids = [(3,factoring.id)]

        data = {
            "ref": f"Factoraje {self.line_ids.mapped('invoice_id.name')}",
            "journal_id": self.journal_id.id,
            "date": self.factoring_date,
            'l10n_mx_edi_payment_method_id': payment_method_id.id,
            'invoice_line_ids': line_list
        }
        move_id = self.env["account.move"].sudo().create(data)
        move_id.action_post()
        credit_ids = move_id.invoice_line_ids.filtered(lambda line: line.credit > 0)
        debit_id = move_id.invoice_line_ids.filtered(lambda line: line.debit > 0)
        for credit_id in credit_ids:
            line_id = self.line_ids.filtered(lambda li: li.invoice_id.name == credit_id.name)
            line_id.invoice_id.js_assign_outstanding_line(credit_id.id)
            line_id.invoice_id.x_factoring_invoice_ids = [(4, move_id.id)]
        self.bill_id.js_assign_outstanding_line(debit_id.id)
        self.bill_id.x_in_factoring = True
        return self.line_ids.mapped("invoice_id.line_ids").action_register_payment()