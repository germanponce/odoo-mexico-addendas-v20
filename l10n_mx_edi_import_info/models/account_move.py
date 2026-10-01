# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    import_ids = fields.Many2many('import.info', 'account_invoice_line_import_info_rel', 'invoice_line_id', 'import_id',
                                        string='Pedimentos')

    @api.onchange('import_ids')
    def onchange_import_info_trade(self):
        if self.import_ids:
            import_ids = self.import_ids
            l10n_mx_edi_customs_number = ""
            if import_ids:
                for importinfo in import_ids:
                    l10n_mx_edi_customs_number = l10n_mx_edi_customs_number+", "+ importinfo.name if l10n_mx_edi_customs_number else importinfo.name
            self.with_context(check_move_validity=False).l10n_mx_edi_customs_number = l10n_mx_edi_customs_number 
            # self.env.cr.execute("update account_move_line set l10n_mx_edi_customs_number=%s where id=%s;", (l10n_mx_edi_customs_number, line.id))

    # @api.model
    # def create(self, vals):
    #     line = super(AccountMoveLine, self).create(vals)
    #     if line.import_ids:
    #         import_ids = line.import_ids
    #         l10n_mx_edi_customs_number = ""
    #         if import_ids:
    #             for importinfo in import_ids:
    #                 l10n_mx_edi_customs_number = l10n_mx_edi_customs_number+", "+ importinfo.name if l10n_mx_edi_customs_number else importinfo.name
    #         #line.l10n_mx_edi_customs_number = l10n_mx_edi_customs_number 
    #         self.env.cr.execute("update account_move_line set l10n_mx_edi_customs_number=%s where id=%s;", (l10n_mx_edi_customs_number, line.id))
    #     return line


class import_info(models.Model):
    _inherit = "import.info"    
    
    invoice_line_ids = fields.Many2many('account.move.line', 'account_invoice_line_import_info_rel', 'import_id', 'invoice_line_id',
                                         string='Líneas de Factura')

######### Odoo Enterprise ##############
class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        # OVERRIDE
        for move in self.filtered(lambda move: move.is_invoice()):
            for line in move.line_ids:
                if line.l10n_mx_edi_customs_number:
                    continue
                import_ids = line.import_ids
                l10n_mx_edi_customs_number = ""
                if import_ids:
                    for importinfo in import_ids:
                        l10n_mx_edi_customs_number = l10n_mx_edi_customs_number+", "+ importinfo.name if l10n_mx_edi_customs_number else importinfo.name
                #line.l10n_mx_edi_customs_number = l10n_mx_edi_customs_number
                self.env.cr.execute("update account_move_line set l10n_mx_edi_customs_number=%s where id=%s;", (l10n_mx_edi_customs_number, line.id))
        return super()._post(soft)
