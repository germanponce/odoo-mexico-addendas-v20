from odoo import _, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_register_split_payment(self):
        """Open the account.split.payment.register wizard to pay the selected journal entries.
        :return: An action opening the account.split.payment.register wizard.
        """
        return {
            "name": _("Split Payment"),
            "res_model": "account.split.payment.register",
            "view_mode": "form",
            "context": {
                "active_model": "account.move",
                "active_ids": self.ids,
            },
            "target": "new",
            "type": "ir.actions.act_window",
        }


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def reconcile(self):
        """Overriding reconcile method in order to skip the synchronization
        that is called when the lines of payment with multiples lines (like the
        one in Payment Split) which violates the `_synchronize_from_moves`
        method and in order to skip it we have to the context in the reconciliation.
        Otherwise manual reconciliation of Receivables/Payables won't be possible.
        Remember that split payment creates:
            - several lines of receivables/payables.
            - several lines that can have several currencies in one same payment.
        """
        return super(AccountMoveLine, self.with_context(skip_account_move_synchronization=True)).reconcile()
