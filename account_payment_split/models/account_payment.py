# pylint: disable=no-utf8-coding-comment

import codecs
import json
from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from markupsafe import Markup, escape

BOM_MAP = {
    "utf-16le": codecs.BOM_UTF16_LE,
    "utf-16be": codecs.BOM_UTF16_BE,
    "utf-32le": codecs.BOM_UTF32_LE,
    "utf-32be": codecs.BOM_UTF32_BE,
}

MAP_INVOICE_TYPE_PAYMENT_SIGN = {
    "out_invoice": 1,
    "in_refund": -1,
    "in_invoice": -1,
    "out_refund": 1,
}

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    "out_invoice": "customer",
    "out_refund": "customer",
    "in_invoice": "supplier",
    "in_refund": "supplier",
}


class AccountSplitPaymentRegister(models.TransientModel):
    _name = "account.split.payment.register"
    _description = "Split Payment"

    # == Business fields ==
    payment_date = fields.Date(
        required=True, default=fields.Date.context_today, help="Settling Date for the Bills/Invoices"
    )

    amount = fields.Monetary(
        string="Payment Amount",
        required=True,
        currency_field="currency_id",
        help="Amount to be allocated/was allocated in the Invoices to be paid.",
    )

    company_currency_amount = fields.Monetary(
        compute="_compute_from_lines",
        store=True,
        string="Amount in Company Currency",
        required=True,
        currency_field="company_currency_id",
        help="Technical field to summarize what was collected from the lines in company_currency_amount field.",
    )

    # TODO: Implement communication field in the code
    communication = fields.Char(string="Memo", help="Field to be used when there is only one record to be paid")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, help="The contextual company")
    company_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        help="Currency to report the payment in company currency.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        help="Currency that will be used to make all the payments in the invoices.",
    )
    journal_id = fields.Many2one(
        "account.journal",
        domain="[('company_id', '=', company_id), ('type', 'in', ('bank', 'cash'))]",
        help="Journal that will be used to make all the payments in the invoices.",
    )

    payment_invoice_ids = fields.One2many(
        "account.register.invoices", "register_id", help="Invoices that were paid in mass"
    )
    dummy_amount = fields.Float(store=False, help="Technical field")
    custom_rate = fields.Float(
        help="If used. This rate will be written in all the invoices to pay", store=False, copy=False, digits=(18, 12)
    )

    # == Payment methods fields ==
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Payment Method",
        readonly=False,
        store=True,
        compute="_compute_payment_method_line_id",
        domain="[('id', 'in', available_payment_method_line_ids)]",
        help="Manual: Pay or Get paid by any method outside of Odoo.\n"
        "Payment Acquirers: Each payment acquirer has its own Payment Method. Request a transaction on/to a card"
        " thanks to a payment token saved by the partner when buying or subscribing online.\n"
        "Check: Pay bills by check and print it from Odoo.\n"
        "Batch Deposit: Collect several customer checks at once generating and submitting a batch deposit to your "
        "bank. Module account_batch_payment is necessary.\n"
        "SEPA Credit Transfer: Pay in the SEPA zone by submitting a SEPA Credit Transfer file to your bank. "
        "Module account_sepa is necessary.\n"
        "SEPA Direct Debit: Get paid in the SEPA zone thanks to a mandate your partner will have granted to you. "
        "Module account_sepa is necessary.\n",
    )
    available_payment_method_line_ids = fields.Many2many(
        "account.payment.method.line",
        compute="_compute_payment_method_line_fields",
        help="Technical field to be used to compute payment_method_line_id",
    )
    hide_payment_method_line = fields.Boolean(
        compute="_compute_payment_method_line_fields",
        help="Technical field used to hide the payment method if the selected journal has only one available which"
        " is 'manual'",
    )

    # == Payment difference fields ==
    there_is_a_difference = fields.Boolean(
        compute="_compute_payment_difference",
        store=True,
        help="Technical Field that determines if there is a Global or In-Line Difference",
    )
    excess_payment_difference = fields.Monetary(
        compute="_compute_payment_difference",
        store=True,
        currency_field="currency_id",
        help="Technical Sum of Excess Difference in Payment Currency",
    )
    excess_company_difference = fields.Monetary(
        compute="_compute_payment_difference",
        store=True,
        currency_field="company_currency_id",
        help="Technical Sum of Excess Difference in Company Currency",
    )
    defect_payment_difference = fields.Monetary(
        compute="_compute_payment_difference",
        store=True,
        currency_field="currency_id",
        help="Technical Sum of Excess Difference in Payment Currency",
    )
    defect_company_difference = fields.Monetary(
        compute="_compute_payment_difference",
        store=True,
        currency_field="company_currency_id",
        help="Technical Sum of Excess Difference in Company Currency",
    )
    payment_difference = fields.Monetary(
        compute="_compute_payment_difference",
        store=True,
        help="Difference to be booked as an Open Balance or as a P&L record",
    )
    company_difference = fields.Monetary(
        compute="_compute_payment_difference",
        store=True,
        string="Difference in Company Currency",
        required=True,
        currency_field="company_currency_id",
        help="Technical field to summarize the difference in Company Currency.",
    )
    payment_difference_handling = fields.Selection(
        [("open", "Keep open"), ("reconcile", "Mark as fully paid")],
        default="open",
        help="How the difference is going to be handle. Shall be kept Open or May it be send a P&L Account.",
    )
    writeoff_account_id = fields.Many2one(
        "account.account",
        string="Difference Account",
        copy=False,
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        help="Accounting where the difference is to be sent. Most likely a P&L Account.",
    )
    writeoff_label = fields.Char(
        string="Journal Item Label",
        default="Write-Off",
        help="Change label of the counterpart that will hold the payment difference",
    )

    # == Fields given through the context ==
    payment_type = fields.Selection(
        [("outbound", "Send Money"), ("inbound", "Receive Money")],
        store=True,
        copy=False,
        compute="_compute_from_lines",
        help="Type of Transaction: Collection or Payment",
    )
    partner_type = fields.Selection(
        [("customer", "Customer"), ("supplier", "Vendor")],
        store=True,
        copy=False,
        compute="_compute_from_lines",
        help="Which of Partner is being paid/collected",
    )

    # == Display purpose fields ==
    country_code = fields.Char(
        related="company_id.country_id.code", readonly=True, help="Technical Field used in l10n modules"
    )

    @api.depends("dummy_amount")
    def _compute_payment_difference(self):
        for wizard in self:
            there_is_a_difference = False
            lines = wizard.payment_invoice_ids
            wizard_amount_on_lines = sum(lines.mapped("payment_currency_amount"))
            wizard_amount_on_lines = wizard.currency_id.round(wizard_amount_on_lines)
            difference = wizard.amount - wizard_amount_on_lines
            company_currency_amount = sum(lines.mapped("company_currency_amount"))

            wizard.payment_difference = 0
            wizard.company_difference = 0
            wizard.company_currency_amount = company_currency_amount
            if wizard.currency_id.round(difference) > 0:
                # /!\ NOTE: This line is a loose end. Let us fix it soon! That first line could be at a fixed rate.
                # let us this method _convert_from_currency_to_currency(from_currency, to_currency, amount, date)
                company_difference = lines[0]._convert_from_currency_to_currency(
                    wizard.currency_id, wizard.company_currency_id, difference
                )

                there_is_a_difference = True
                wizard.payment_difference = difference
                wizard.company_difference = company_difference
                wizard.company_currency_amount = company_currency_amount + company_difference

            excess_lines = lines.filtered(lambda l: l.inline_company_difference < 0)
            defect_lines = lines.filtered(lambda l: l.inline_company_difference > 0)
            if excess_lines or defect_lines:
                there_is_a_difference = True
            wizard.there_is_a_difference = there_is_a_difference
            wizard.excess_payment_difference = abs(sum(excess_lines.mapped("inline_payment_difference")))
            wizard.excess_company_difference = abs(sum(excess_lines.mapped("inline_company_difference")))
            wizard.defect_payment_difference = abs(sum(defect_lines.mapped("inline_payment_difference")))
            wizard.defect_company_difference = abs(sum(defect_lines.mapped("inline_company_difference")))

    @api.depends("payment_invoice_ids", "amount", "dummy_amount")
    def _compute_from_lines(self):
        """Load initial values from the account.moves passed through the context."""
        for wizard in self:
            batches = wizard._get_split_batches(from_compute=True)
            batch_result = batches[0]
            wizard_values_from_batch = wizard._get_wizard_values_from_split_batch(batch_result)

            company_currency_amount = sum(wizard.payment_invoice_ids.mapped("company_currency_amount"))

            wizard.update(
                {
                    "partner_type": wizard_values_from_batch["partner_type"],
                    "payment_type": wizard_values_from_batch["payment_type"],
                    "company_currency_amount": company_currency_amount,
                }
            )

    @api.depends("payment_type", "journal_id")
    def _compute_payment_method_line_id(self):
        for wizard in self:
            available_payment_method_lines = wizard.journal_id._get_available_payment_method_lines(wizard.payment_type)

            # Select the first available one by default.
            if available_payment_method_lines:
                wizard.payment_method_line_id = available_payment_method_lines[0]._origin
            else:
                wizard.payment_method_line_id = False

    @api.depends("payment_type", "journal_id")
    def _compute_payment_method_line_fields(self):
        for wizard in self:
            wizard.available_payment_method_line_ids = wizard.journal_id._get_available_payment_method_lines(
                wizard.payment_type
            )
            if wizard.payment_method_line_id.id not in wizard.available_payment_method_line_ids.ids:
                # In some cases, we could be linked to a payment method line that has been unlinked from the journal.
                # In such cases, we want to show it on the payment.
                wizard.hide_payment_method_line = False
            else:
                wizard.hide_payment_method_line = (
                    len(wizard.available_payment_method_line_ids) == 1
                    and wizard.available_payment_method_line_ids.code == "manual"
                )

    @api.model
    def default_get(self, fields_list):
        if self._context.get("active_model") != "account.move":
            raise UserError(_("The register payment wizard should only be called on account.move records."))

        res = super().default_get(fields_list)

        if "payment_invoice_ids" not in fields_list:
            return res

        res["journal_id"] = self.env["account.journal"].search(
            [
                ("type", "in", ("bank", "cash")),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )

        payment_currency_id = self.env["res.currency"].browse(res.get("currency_id"))

        invoice_ids = self.env["account.move"].browse(self._context.get("active_ids")).sorted("invoice_date_due")
        invoice_ids = invoice_ids.filtered(
            lambda x: x.is_invoice() and x.state == "posted" and x.payment_state in ("not_paid", "partial")
        )

        if not invoice_ids:
            raise UserError(_("The register payment wizard should only be called on Open Unpaid Invoices/Bills"))

        res["payment_invoice_ids"] = [
            Command.create(
                {
                    "invoice_id": inv.id,
                    "currency_id": inv.currency_id.id,
                    "partner_id": inv.partner_id.id,
                    "date": inv.invoice_date,
                    "date_due": inv.invoice_date_due,
                    "amount": inv.currency_id.round(inv.amount_residual),
                    "payment_currency_id": payment_currency_id.id,
                }
            )
            for inv in invoice_ids
        ]
        return res

    @api.onchange("amount")
    def _onchange_amount(self):
        """Perform custom operations only if the amount actually changed

        It may happen that onchanges are executed just before creating
        payments, even when there was no changes, which may screw up amount
        values. For more info, see:
        https://github.com/odoo/odoo/issues/34429
        """
        if self.amount != self.dummy_amount:
            self._onchange_payment_invoice()

    @api.onchange("payment_invoice_ids")
    def _onchange_payment_invoice(self):
        for wizard in self:
            if wizard.amount == wizard.dummy_amount:
                cumulative_amount = sum(wizard.payment_invoice_ids.mapped("payment_currency_amount"))
                amount = wizard.currency_id.round(cumulative_amount)
                wizard.update({"amount": amount, "dummy_amount": amount})
                continue

            full_amount = wizard.amount
            for line in wizard.payment_invoice_ids.sorted("date_due"):
                update_amount = 0
                amount = line._convert_from_invoice_to_payment_currency()
                if amount <= full_amount:
                    update_amount = amount
                    full_amount -= amount
                elif amount > full_amount:
                    update_amount = full_amount
                    full_amount = 0.0

                line.update({"payment_currency_amount": update_amount})
            wizard.dummy_amount = wizard.amount

    @api.onchange("journal_id", "payment_date", "custom_rate")
    def _onchange_currency_at_payment(self):
        cumulative_amount = 0
        company_currency = self.env.company.currency_id
        self.currency_id = self.journal_id.currency_id.id or self.journal_id.company_id.currency_id.id
        for line in self.payment_invoice_ids:
            line.company_currency_id = company_currency.id
            line.payment_currency_id = self.currency_id.id
            amount = line._convert_from_invoice_to_payment_currency()
            line.payment_currency_amount = amount
            line.payment_amount = line._convert_from_payment_to_invoice_currency(amount)
            line.company_currency_amount = line._convert_from_invoice_to_company_currency(line.payment_amount)
            rate = line.payment_currency_amount / line.payment_amount if line.payment_amount else 0.0
            line.rate = 1 / rate if 0 < rate < 1 else rate
            line.use_rate = line.use_rate
            cumulative_amount += amount

            if line.currency_id == line.payment_currency_id:
                line.payment_currency_due_amount = line.amount
                line.payment_currency_date_amount = line.amount
            else:
                line.payment_currency_date_amount = line._convert_from_invoice_to_payment_currency()
                if line.currency_id == company_currency:
                    line.payment_currency_due_amount = line.currency_id._convert(
                        line.amount, line.payment_currency_id, self.env.user.company_id, line.date
                    )
                else:
                    # Better approach is to fetch them from the journal items data
                    balance = sum(line.mapped("invoice_id.line_ids.balance"))
                    amount_currency = sum(line.mapped("invoice_id.line_ids.amount_currency"))
                    amount = (
                        line.amount * balance / amount_currency
                        if amount_currency != 0
                        else line.currency_id._convert(
                            line.amount, line.payment_currency_id, self.env.user.company_id, line.date
                        )
                    )
                    line.payment_currency_due_amount = amount

        self.amount = cumulative_amount

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def _get_split_batch_communication(self, batch_result):
        """Helper to compute the communication based on the batch.
        :param batch_result:    A batch returned by '_get_split_batches'.
        :return:                A string representing a communication to be set on payment.
        """
        labels = {line.name or line.move_id.ref or line.move_id.name for line in batch_result["lines"]}
        return " ".join(sorted(labels))

    # BUSINESS LOGIC

    @api.model
    def _get_line_split_batch_key(self, line):
        """Turn the line passed as parameter to a dictionary defining on which way the lines
        will be grouped together.
        :return: A python dictionary.
        """

        # /!\ NOTE: We are minimizing the number of parameters to group records.
        # There is no need to group by `account_id` because we create one line
        # per invoice thus it cause not problem as in Odoo core.
        # If User has decide to pay with a particular bank account so it be.
        # Only the partner and the type of account are the ones to be used to
        # group records.
        return {
            "partner_id": line.partner_id.id,
            "partner_type": "customer" if line.account_id.account_type == "asset_receivable" else "supplier",
        }

    def _prepare_move_line_dict(self, pline, line, sign, amount, amount_currency):
        self.ensure_one()
        currency = pline.payment_currency_id
        amount_currency = sign * amount_currency
        # Setting the amount being paid in the journal items as was in the
        # wizard for the currency in the invoice.
        # This is quite useful when:
        # Company Currency is MXN
        # Invoice Currency is EUR
        # Payment Currency is USD
        # or:
        # Company Currency is MXN
        # Invoice Currency is USD
        # Payment Currency is MXN
        # We want the invoice to be exactly paid what was intended. This may
        # need to be override by l10n.
        if len(pline.currency_id | currency | pline.company_currency_id) == 3 or pline.company_currency_id == currency:
            currency = pline.currency_id
            amount_currency = sign * pline.payment_amount
            handling = self.payment_difference_handling
            if handling == "reconcile" or (handling == "open" and pline.inline_payment_difference < 0):
                amount_currency += sign * pline._convert_from_payment_to_invoice_currency(
                    pline.inline_payment_difference
                )
        res = {
            "reconciling_line": line,
            "name": line.name or line.move_id.ref or line.move_id.name,
            "partner_id": line.partner_id.id,
            "account_id": line.account_id.id,
            "amount_residual": sign * amount,
            "currency_id": currency.id,
            "amount_residual_currency": amount_currency,
            "amount_currency": amount_currency,
            "debit": amount if sign > 0.0 else 0.0,
            "credit": amount if sign < 0.0 else 0.0,
        }
        return res

    def _prepare_json_payment_split_data(self, payment_lines):
        self.ensure_one()
        payment_difference = self.payment_difference
        company_difference = self.company_difference
        amount = payment_difference + sum(payment_lines.mapped("payment_currency_amount"))
        company_currency_amount = company_difference + sum(payment_lines.mapped("company_currency_amount"))
        payment_invoice_ids = [
            {
                "amount": x.amount,
                "move_id": x.invoice_id.id,
                "invoice_id": x.invoice_id.id,
                "currency_id": x.currency_id.id,
                "payment_amount": x.payment_amount,
                "payment_currency_id": x.payment_currency_id.id,
                "company_currency_id": x.company_currency_id.id,
                "payment_currency_amount": x.payment_currency_amount,
                "company_currency_amount": x.company_currency_amount,
                "inline_payment_difference": x.inline_payment_difference,
                "inline_company_difference": x.inline_company_difference,
            }
            for x in payment_lines
        ]
        res = dict(
            amount=amount,
            journal_id=self.journal_id.id,
            currency_id=self.currency_id.id,
            payment_difference=payment_difference,
            company_difference=company_difference,
            payment_invoice_ids=payment_invoice_ids,
            company_currency_id=self.company_currency_id.id,
            company_currency_amount=company_currency_amount,
            payment_date=self.payment_date.strftime("%Y-%m-%d"),
        )
        return res

    def _get_json_payment_split_data(self, payment_lines):
        self.ensure_one()
        return json.dumps(self._prepare_json_payment_split_data(payment_lines))

    def _prepare_move_line_vals(self, payment_lines):
        res = []
        handling = self.payment_difference_handling
        for pline in payment_lines:
            line = pline.invoice_id.line_ids.filtered(
                lambda x: x.account_id.account_type in ("asset_receivable", "liability_payable") and not x.reconciled
            )
            sign = -1 if line.balance > 0.0 else 1
            amount = pline.company_currency_amount
            amount_currency = pline.payment_currency_amount

            if handling == "reconcile" or (handling == "open" and pline.inline_company_difference < 0):
                amount += pline.inline_company_difference
                amount_currency += pline.inline_payment_difference

            res.append(self._prepare_move_line_dict(pline, line, sign, amount, amount_currency))

        res += self._prepare_difference_move_line_vals(payment_lines)

        return res

    def _prepare_difference_move_line_vals(self, payment_lines):
        """Method to process the write-off be it general or inline"""
        res = []
        if not self.there_is_a_difference:
            return res

        handling = self.payment_difference_handling

        # /!\ NOTE: @hbto is making a big assumption the first line being sent has the behavior of the write_off.
        pline = payment_lines[0]
        line = pline.invoice_id.line_ids.filtered(
            lambda x: x.account_id.account_type in ("asset_receivable", "liability_payable") and not x.reconciled
        )
        sign = -1 if line.balance > 0.0 else 1

        label = {"g": _("[Global] "), "e": _("[Excess] "), "d": _("[Defect] ")}
        # /!\ NOTE: Global & Excess differences always booked. Only Defect difference is booked when reconcile is set
        differences = [
            ("g", True, self.payment_difference, self.company_difference, sign),
            ("e", True, self.excess_payment_difference, self.excess_company_difference, sign),
            # Becareful of sign
            ("d", handling == "reconcile", self.defect_payment_difference, self.defect_company_difference, -1 * sign),
        ]

        for diff_label, diff_handling, amount_currency, amount, diff_sign in differences:
            if not diff_handling:
                continue
            if self.currency_id.is_zero(amount) and self.currency_id.is_zero(amount_currency):
                continue
            res_line = self._prepare_move_line_dict(pline, line, diff_sign, amount, amount_currency)
            if pline.company_currency_id == pline.payment_currency_id:
                res_line.pop("currency_id")
                res_line.pop("amount_currency")
                res_line.pop("amount_residual_currency")
            res_line["name"] = label[diff_label] + self.writeoff_label
            res_line["reconciling_line"] = self.env["account.move.line"]  # This line is not to be reconciled

            if handling == "reconcile":
                res_line["account_id"] = self.writeoff_account_id.id

            res.append(res_line)

        return res

    def _get_split_batches(self, from_compute=False):
        """Group the account.move linked to the wizard together.
        Moves are grouped if they share 'partner_id' & 'partner_type'.
        : param from_compute:   Execute only one cycle because the compute only needs one
        :return: A list of batches, each one containing:
            * payment_values:   A dictionary of payment values.
            * moves:        An account.move recordset.
        """
        self.ensure_one()

        payment_lines = self.payment_invoice_ids.filtered(lambda x: x.payment_currency_amount > 0)

        if from_compute:
            payment_lines = self.payment_invoice_ids.filtered(
                lambda x: x.invoice_id.is_invoice()
                and x.invoice_id.state == "posted"
                and x.invoice_id.payment_state in ("not_paid", "partial")
            )

        lines = payment_lines.invoice_id.line_ids.filtered(
            lambda x: x.account_id.account_type in ("asset_receivable", "liability_payable") and not x.reconciled
        )._origin

        if len(lines.company_id) > 1:
            raise UserError(_("You can't create payments for entries belonging to different companies."))
        if not lines:
            raise UserError(
                _("You can't open the register payment wizard without at least one receivable/payable line.")
            )

        batches = defaultdict(
            lambda: {"lines": self.env["account.move.line"], "payment_lines": self.env["account.register.invoices"]}
        )
        for pline in payment_lines:
            line = pline.invoice_id.line_ids.filtered(
                lambda x: x.account_id.account_type in ("asset_receivable", "liability_payable") and not x.reconciled
            )._origin

            batch_key = self._get_line_split_batch_key(line)
            serialized_key = "-".join(str(v) for v in batch_key.values())
            vals = batches[serialized_key]
            vals["payment_values"] = batch_key
            vals["lines"] += line
            vals["payment_lines"] += pline

        # Compute 'payment_type'.
        for vals in batches.values():
            lines = vals["lines"]
            balance = sum(lines.mapped("balance"))
            payment_lines = vals["payment_lines"]
            vals["payment_values"]["payment_type"] = "inbound" if balance > 0.0 else "outbound"
            vals["payment_values"]["currency_id"] = self.currency_id.id
            vals["source_company_amount"] = abs(sum(payment_lines.mapped("company_currency_amount")))
            vals["source_amount_currency"] = abs(sum(payment_lines.mapped("payment_currency_amount")))
            vals["company_currency_id"] = lines.company_id.currency_id
            vals["payment_currency_id"] = self.currency_id

            if from_compute:
                # There is no need to execute the following part of the cycle as in the compute is not needed
                break

            vals["lines_to_create"] = self._prepare_move_line_vals(payment_lines)
            vals["payment_split_data"] = self._get_json_payment_split_data(payment_lines)

        return list(batches.values())

    @api.model
    def _get_wizard_values_from_split_batch(self, batch_result):
        """Extract values from the batch passed as parameter (see '_get_split_batches')
        to be mounted in the wizard view.
        :param batch_result:    A batch returned by '_get_split_batches'.
        :return:                A dictionary containing valid fields
        """
        payment_values = batch_result["payment_values"]
        lines = batch_result["lines"]
        company = lines[0].company_id

        return {
            "company_id": company.id,
            "partner_id": payment_values["partner_id"],
            "partner_type": payment_values["partner_type"],
            "payment_type": payment_values["payment_type"],
            "source_currency_id": payment_values["currency_id"],
            "source_amount_currency": batch_result["source_amount_currency"],
        }

    def _create_payment_vals_from_split_batch(self, batch_result):
        batch_values = self._get_wizard_values_from_split_batch(batch_result)

        return {
            "date": self.payment_date,
            "amount": batch_values["source_amount_currency"],
            "payment_type": batch_values["payment_type"],
            "partner_type": batch_values["partner_type"],
            "ref": self.communication or self._get_split_batch_communication(batch_result),
            "journal_id": self.journal_id.id,
            "currency_id": batch_values["source_currency_id"],
            "partner_id": batch_values["partner_id"],
            "payment_method_line_id": self.payment_method_line_id.id,
            "destination_account_id": batch_result["lines"][0].account_id.id,
            # "writeoff_account_id": self.writeoff_account_id.id,
            # "writeoff_label": self.writeoff_label,
        }

    def _init_split_payments(self, to_process, edit_mode=False):
        """Create the payments.

        :param to_process:  A list of python dictionary, one for each payment to create, containing:
                            * create_vals:  The values used for the 'create' method.
                            * to_reconcile: The journal items to perform the reconciliation.
                            * batch:        A python dict containing everything you want about the source journal items
                                            to which a payment will be created (see '_get_batches').
        :param edit_mode:   Is the wizard in edition mode.
        """

        payments = self.env["account.payment"]
        for vals in to_process:
            payments |= self._init_split_payment(vals)
        return payments

    def _init_split_payment(self, vals):
        payment_obj = self.env["account.payment"].with_context(skip_account_move_synchronization=True)
        ctx = dict(check_move_validity=False, skip_account_move_synchronization=True, force_delete=True)
        aml_obj = self.env["account.move.line"].with_context(**ctx)
        move = vals["batch"]["lines"][-1].move_id
        new_ctx = {}
        if move and "crm.team" in self.env and "team_id" in dir(move):
            new_ctx = dict(default_team_id=move.team_id.id)

        payment = payment_obj.with_context(**new_ctx).create([vals["create_vals"]])
        vals["payment"] = payment
        vals["move"] = payment.move_id
        payment.payment_split_data = vals["batch"]["payment_split_data"]

        icp_obj = self.env["ir.config_parameter"].sudo()
        skip_supplier_reconciliation = (
            self.payment_type == "outbound"
            and self.partner_type == "supplier"
            and icp_obj.get_param("skip_supplier_payment_reconciliation", False)
        )
        # /!\ NOTE: This piece of code is to avoid clashing with the payments made from hr.expense
        skip_supplier_reconciliation = (
            False if self._context.get("dont_skip_supplier_payment_reconciliation") else skip_supplier_reconciliation
        )
        skip_customer_reconciliation = (
            self.payment_type == "inbound"
            and self.partner_type == "customer"
            and icp_obj.get_param("skip_customer_payment_reconciliation", False)
        )
        skip_reconciliation = skip_supplier_reconciliation or skip_customer_reconciliation
        info = {
            "payment_id": payment.id,
            "to_reconcile": [],
        }

        company_currency_id = vals["batch"]["company_currency_id"]
        payment_currency_id = vals["batch"]["payment_currency_id"]
        amount_currency = vals["batch"]["source_amount_currency"]
        source_company_amount = vals["batch"]["source_company_amount"]

        liquidity_lines, counterpart_lines, writeoff_lines = payment._seek_for_lines()
        liquidity_lines[0]["name"] = payment.name or move.ref or payment.communication

        to_create_commands = vals["batch"]["lines_to_create"]
        to_update_commands = []
        to_delete_commands = [(2, line.id) for line in counterpart_lines + writeoff_lines]

        invoices = self.env["account.move"]
        for line_to_create in to_create_commands:
            invoices |= line_to_create.get("reconciling_line").move_id
        if skip_reconciliation:
            self._check_for_invoice_in_background_reconciliation(invoices)

        if payment_currency_id != company_currency_id:
            debit_lines = liquidity_lines.filtered("debit")[-1:]
            credit_lines = liquidity_lines.filtered("credit")[-1:]
            to_update_commands += [
                (
                    1,
                    debit_lines.id,
                    {
                        "debit": company_currency_id.round(source_company_amount),
                        "amount_currency": payment_currency_id.round(amount_currency),
                    },
                ),
                (
                    1,
                    credit_lines.id,
                    {
                        "credit": company_currency_id.round(source_company_amount),
                        "amount_currency": -1 * payment_currency_id.round(amount_currency),
                    },
                ),
            ]

        payment.with_context(**ctx).write({"line_ids": to_delete_commands + to_update_commands})

        to_reconcile = self.env["account.move.line"].with_context(**ctx)
        with self.env.norecompute():
            for line_to_create in to_create_commands:
                counterpart_aml = line_to_create.get("reconciling_line")
                invoice = counterpart_aml.move_id
                if skip_reconciliation:
                    self._approve_invoice_payment(invoice)
                line_to_create["move_id"] = payment.move_id.id
                line_to_create["payment_id"] = payment.id
                to_reconcile = line_to_create.pop("reconciling_line")

                # NOTE: When invoice is in local currency the settlement is to
                # be done in local currency. So the amount paid is depleted of
                # any trace of foreign currency. In this way the reconciliation
                # process won't affect the amount that was paid.
                if company_currency_id == invoice.currency_id:
                    line_to_create.pop("currency_id")
                    line_to_create.pop("amount_currency")
                    line_to_create.pop("amount_residual_currency")

                to_rec = aml_obj.create(line_to_create)
                to_reconcile |= to_rec
                if len(to_reconcile) == 1:
                    continue
                if skip_reconciliation:
                    info["to_reconcile"].append((invoice.id, to_rec.id))
                    continue
                vals["to_reconcile"].append(to_reconcile)
        self.flush_model()
        if self.finalize_split_payment(payment):
            return payment
        self._validate_blocking_date(payment, to_reconcile, skip_customer_reconciliation)
        self._create_reversal_payment(
            payment,
            payment.company_id.unknown_payment_account_id.id,
            fields.Date.context_today(self),
            skip_customer_reconciliation,
        )
        if skip_reconciliation:
            payment.reconciliation_data = json.dumps(info)
            payment.to_reconcile_on_background = True
        return payment

    def _approve_invoice_payment(self, invoice):
        return False

    def _validate_blocking_date(self, payment, all_counterparts, skip_customer_reconciliation):
        return False

    def finalize_split_payment(self, payment):
        return False

    def _create_reversal_payment(self, payment, account_id, date, skip_customer_reconciliation):
        return False

    def _post_split_payments(self, to_process, edit_mode=False):
        """Post the newly created payments.

        :param to_process:  A list of python dictionary, one for each payment to create, containing:
                            * create_vals:  The values used for the 'create' method.
                            * to_reconcile: The journal items to perform the reconciliation.
                            * batch:        A python dict containing everything you want about the source journal
                                            items to which a payment will be created (see '_get_split_batches').
        :param edit_mode:   Is the wizard in edition mode.
        """
        payments = self.env["account.payment"]
        for vals in to_process:
            payments |= vals["payment"]
        payments.action_post()

    def _reconcile_split_payments(self, to_process, edit_mode=False):
        """Reconcile the payments.

        :param to_process:  A list of python dictionary, one for each payment to create, containing:
                            * create_vals:  The values used for the 'create' method.
                            * to_reconcile: The journal items to perform the reconciliation.
                            * batch:        A python dict containing everything you want about the source journal
                            items to which a payment will be created (see '_get_split_batches').
        :param edit_mode:   Is the wizard in edition mode.
        """
        for payment_vals in to_process:
            for to_reconcile in payment_vals["to_reconcile"]:
                to_reconcile.with_context(skip_account_move_synchronization=True).reconcile()

    def _update_amount_because_of_write_off(self, to_process):
        self.ensure_one()
        if len(to_process) != 1:
            raise UserError(_("When processing multiple payments Write-Off is not supported"))

        create_vals = dict(to_process[0]["create_vals"])
        create_vals["amount"] = self.amount
        to_process[0]["create_vals"] = create_vals

        batch = dict(to_process[0]["batch"])
        batch["source_amount_currency"] = self.amount
        batch["source_company_amount"] = self.company_currency_amount

        to_process[0]["batch"] = batch

        return to_process

    def _get_json_dicts(self, to_process):
        # method to be inherited
        return []

    def _json_attachment(self, payments, json_datas):
        # method to be inherited
        return

    def _create_split_payments(self):
        self.ensure_one()
        batches = self._get_split_batches()

        # NOTE: edit_mode is a legacy parameter coming from `account.register.payment`.
        # May it be of use in the future.
        edit_mode = False

        to_process = []

        for batch_result in batches:
            to_process.append(
                {
                    "create_vals": self._create_payment_vals_from_split_batch(batch_result),
                    "to_reconcile": [],
                    "batch": batch_result,
                }
            )

        if not self.currency_id.is_zero(self.payment_difference):
            to_process = self._update_amount_because_of_write_off(to_process)

        json_datas = self._get_json_dicts(to_process)
        payments = self._init_split_payments(to_process, edit_mode=edit_mode)
        self._json_attachment(payments, json_datas)
        self._post_split_payments(to_process, edit_mode=edit_mode)
        self._reconcile_split_payments(to_process, edit_mode=edit_mode)
        return payments

    def action_create_payments(self):
        payments = self._create_split_payments()

        if self._context.get("dont_redirect_to_payments"):
            return True

        action = {
            "name": _("Payments"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "context": {"create": False},
        }
        if len(payments) == 1:
            action.update(
                {
                    "view_mode": "form",
                    "res_id": payments.id,
                }
            )
        else:
            action.update(
                {
                    "view_mode": "list,form",
                    "domain": [("id", "in", payments.ids)],
                }
            )
        return action

    def _retrieve_invoice_in_background_reconciliation(self, all_invoices):
        res = {}
        domain = [
            ("state", "not in", ("draft", "cancelled")),
            ("to_reconcile_on_background", "=", True),
            ("reconciliation_data", "!=", False),
            "|",
            "&",
            ("payment_type", "=", "outbound"),
            ("partner_type", "=", "supplier"),
            "&",
            ("payment_type", "=", "inbound"),
            ("partner_type", "=", "customer"),
        ]
        payments = self.env["account.payment"].search(domain, order="id")
        for payment_id, vals in payments._fetch_data_to_reconcile_in_background().items():
            to_reconcile = vals.get("to_reconcile")
            if not to_reconcile:
                continue

            forbidden_invoices = {x[0] for x in to_reconcile} & set(all_invoices.ids)
            if not forbidden_invoices:
                continue

            res[payment_id] = list(forbidden_invoices)
        return res

    def _check_for_invoice_in_background_reconciliation(self, all_invoices):
        msg = ""
        body = "\t\t(id: %s) [%s] %s\n"
        inv_obj = self.env["account.invoice"]

        for payment_id, invoices in self._retrieve_invoice_in_background_reconciliation(all_invoices).items():
            payment = self.env["account.payment"].browse(payment_id)
            # pylint: disable=translation-not-lazy
            msg += _("\nPayment: (id: %s) %s\n\tInvoices:\n") % (payment.id, payment.name)
            msg += "".join(body % (inv.id, inv.number, inv.reference) for inv in inv_obj.browse(invoices))

        if msg:
            msg = (
                _(
                    "This Payment cannot be performed.\n"
                    "There are payments which have not been reconciled.\n"
                    "And Some invoices from your current payment are present.\n\n"
                )
                + msg
                + _("\n\nMake sure that those Payments have already been reconciled and come back later when done")
            )
            raise UserError(msg)


class AccountRegisterInvoices(models.TransientModel):
    _name = "account.register.invoices"
    _description = """A model to hold invoices being paid in payment register. This model works as
                      account.payment.register lines."""
    _order = "date_due ASC"

    @api.onchange("rate", "use_rate")
    def _onchange_rate(self):
        for line in self.filtered(lambda x: x.use_rate):
            if line.currency_id == line.payment_currency_id:
                line.rate = 1
                line.use_rate = False
                continue
            amount = line._convert_from_invoice_to_payment_currency()
            line.payment_currency_amount = amount
            line.payment_amount = line._convert_from_payment_to_invoice_currency(amount)
            line.company_currency_amount = line._convert_from_payment_to_company_currency(amount)
            line.payment_currency_date_amount = line._convert_from_invoice_to_payment_currency()

        for line in self.filtered(lambda x: not x.use_rate):
            payment_amount = line.payment_amount
            payment_currency_amount = line.payment_currency_amount
            if line.currency_id == line.payment_currency_id:
                company_currency_amount = line._convert_from_invoice_to_company_currency(payment_currency_amount)
                line.update(
                    dict(
                        rate=1,
                        use_rate=False,
                        payment_amount=payment_currency_amount,
                        company_currency_amount=company_currency_amount,
                    )
                )
                line.payment_currency_date_amount = line._convert_from_invoice_to_payment_currency()

                continue
            rate = line.payment_currency_amount / payment_amount if payment_amount else 0.0
            line.rate = 1 / rate if 0 < rate < 1 else rate

            # /!\ NOTE: Future me @hbto: Don't you dare to remove this
            # assignment here. It is not redundant and does not clash with the
            # next assignment in the update below. It is a little hack for
            # the _convert_from.... method to take the custom rate in the line.
            line.use_rate = True
            company_currency_amount = line._convert_from_payment_to_company_currency(payment_currency_amount)

            line.payment_currency_date_amount = line._convert_from_invoice_to_payment_currency()
            line.update(
                dict(
                    use_rate=False,
                    payment_amount=payment_amount,
                    company_currency_amount=company_currency_amount,
                )
            )

    @api.depends("payment_currency_amount")
    def _compute_amount(self):
        for rec in self.filtered(lambda x: x.use_rate):
            rec.payment_amount = rec._convert_from_payment_to_invoice_currency(rec.payment_currency_amount)
            rec.company_currency_amount = rec._convert_from_payment_to_company_currency(rec.payment_currency_amount)
        for rec in self.filtered(lambda x: not x.use_rate):
            rec.payment_amount = rec._convert_from_payment_to_invoice_currency(rec.payment_currency_amount)
            rec.company_currency_amount = rec._convert_from_payment_to_company_currency(rec.payment_currency_amount)
            # Triggering the _onchange_rate
            if rec.currency_id == rec.payment_currency_id:
                rec.rate = 1
            else:
                rate = rec.payment_currency_amount / rec.payment_amount if rec.payment_amount else 0.0
                rec.rate = 1 / rate if 0 < rate < 1 else rate

    @api.depends("payment_currency_amount", "company_currency_amount")
    def _compute_inline_difference(self):
        for line in self:
            line.inline_payment_difference = line.payment_currency_date_amount - line.payment_currency_amount
            if line.payment_currency_id == line.company_currency_id:
                line.inline_company_difference = line.inline_payment_difference
                continue

            company_currency_date_amount = line._convert_from_invoice_to_company_currency()
            line.inline_company_difference = company_currency_date_amount - line.company_currency_amount

    def _inverse_amount(self):
        return

    @api.depends("payment_amount")
    def _compute_company_currency_amount(self):
        for rec in self.filtered(lambda r: r.use_rate):

            amount = rec.payment_currency_amount

            rec.payment_amount = rec._convert_from_payment_to_invoice_currency(amount)
            rec.company_currency_amount = rec._convert_from_payment_to_company_currency(amount)

        for rec in self.filtered(lambda r: not r.use_rate):
            amount = rec.payment_amount

            if rec.payment_currency_id == rec.company_currency_id:
                rec.company_currency_amount = rec.payment_currency_amount
            else:
                rec.company_currency_amount = rec._convert_from_invoice_to_company_currency(amount)

            rate = rec.payment_currency_amount / rec.payment_amount if rec.payment_amount else 0.0
            rec.rate = 1 / rate if 0 < rate < 1 else rate

    def _inverse_company_currency_amount(self):
        return

    invoice_id = fields.Many2one("account.move", help="Invoice being paid")
    currency_id = fields.Many2one(
        "res.currency",
        help="Currency of this invoice",
        related="invoice_id.currency_id",
    )
    date = fields.Date(help="Invoice Date")
    date_due = fields.Date(string="Due Date", help="Maturity Date in the invoice")
    partner_id = fields.Many2one("res.partner", help="Partner involved in payment")
    company_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        help="Technical field used to display the payments been made in company's currency",
    )
    company_currency_amount = fields.Monetary(
        store=True,
        compute="_compute_company_currency_amount",
        inverse="_inverse_company_currency_amount",
        currency_field="company_currency_id",
        help="Amount in currency of Company",
    )
    amount = fields.Monetary(string="Due Amount", currency_field="currency_id", help="Amount Due")
    payment_amount = fields.Monetary(
        store=True,
        compute="_compute_amount",
        inverse="_inverse_amount",
        currency_field="currency_id",
        help="Amount being paid",
    )
    payment_currency_amount = fields.Monetary(
        currency_field="payment_currency_id", help="Amount in currency of payment"
    )
    payment_currency_due_amount = fields.Monetary(
        currency_field="payment_currency_id", help="Due Amount in currency of payment at Invoice Date Rate"
    )
    payment_currency_date_amount = fields.Monetary(
        currency_field="payment_currency_id",
        help="Due Amount in currency of payment at Payment Date Rate. Technical Field",
    )
    rate = fields.Float(help="Payment rate of this Document", copy=False, digits=(18, 12))
    use_rate = fields.Boolean(help="Check if a inline custom rate is to be used")
    payment_currency_id = fields.Many2one("res.currency", help="Currency which this payment is being done")
    register_id = fields.Many2one(
        "account.split.payment.register", help="Technical field to connect to Wizard", copy=False
    )
    inline_payment_difference = fields.Monetary(
        store=True,
        compute="_compute_inline_difference",
        string="Difference in Payment Currency",
        currency_field="payment_currency_id",
        help="Technical field to summarize the difference in Payment Currency.",
    )
    inline_company_difference = fields.Monetary(
        store=True,
        compute="_compute_inline_difference",
        string="Difference in Company Currency",
        currency_field="company_currency_id",
        help="Technical field to summarize the difference in Company Currency.",
    )

    @api.model
    def _convert_from_payment_to_company_currency(self, amount=None, date=None):
        if amount is None:
            amount = self.payment_currency_amount

        from_currency = self.payment_currency_id
        to_currency = self.invoice_id.company_id.currency_id
        converted_amount = self._convert_from_currency_to_currency(from_currency, to_currency, amount, date)

        company = self.invoice_id.company_id
        company_currency = company.currency_id
        if from_currency != to_currency and to_currency == company_currency:
            offset = self._convert_from_currency_to_currency(from_currency, to_currency, to_currency.rounding, date)
            to_compare_offset = abs(converted_amount - self.amount)
            if to_compare_offset < offset / 2:
                converted_amount = self.amount
        return converted_amount

    @api.model
    def _convert_from_payment_to_invoice_currency(self, amount=None, date=None):
        self.ensure_one()
        if amount is None:
            amount = self.payment_currency_amount

        if self._convert_from_invoice_to_payment_currency(date=date) == amount:
            # if the amount converted from payment currency is the same as the amount in invoice currency
            # let us avoid rounding issues
            return self.amount

        return self._convert_from_currency_to_currency(
            self.payment_currency_id, self.invoice_id.currency_id, amount, date
        )

    @api.model
    def _convert_from_invoice_to_payment_currency(self, amount=None, date=None):
        self.ensure_one()
        if amount is None:
            amount = self.amount

        from_currency = self.invoice_id.currency_id
        to_currency = self.payment_currency_id
        return self._convert_from_currency_to_currency(from_currency, to_currency, amount, date)

    @api.model
    def _convert_from_invoice_to_company_currency(self, amount=None, date=None):
        self.ensure_one()
        if amount is None:
            amount = self.amount

        from_currency = self.invoice_id.currency_id
        to_currency = self.company_currency_id
        return self._convert_from_currency_to_currency(from_currency, to_currency, amount, date)

    @api.model
    def _convert_from_currency_to_currency(self, from_currency, to_currency, amount, date=None):
        if date is None:
            date = self.register_id.payment_date or fields.Date.context_today(self)

        company = self.invoice_id.company_id
        company_currency = company.currency_id
        if from_currency == to_currency:
            # /!\ NOTE: The custom_rate if any does not apply
            # rate = 1.00
            return amount

        custom_rate = self.rate if self.use_rate else self.register_id.custom_rate
        if not custom_rate:
            return from_currency._convert(amount, to_currency, company, date)

        # /!\ NOTE: At this point we has guarantee that all currencies are different.
        # We have previously exclude the case that from_currency and to_currency are the same.
        # And we do not support this case.
        if len(company_currency | from_currency | to_currency) == 3:
            # pylint:disable=raise-missing-from
            raise UserError(
                _(
                    "Three Currency Custom Rate is not supported.\n"
                    "For example,\n"
                    "Having the following setting:\n"
                    "- Company Currency MXN\n"
                    "- Payment Currency USD\n"
                    "- Invoice Currency EUR\n"
                    "\n"
                    "Because It is not possible to set One Custom Rate for two currencies at the Same Time\n"
                    "\n"
                    "A Custom Rate is supported when either the Payment or Invoice Currency\n"
                    "is the same than that of the Company Currency\n"
                )
            )

        # /!\ NOTE: At this point we has guarantee that at least two currencies are the same
        # We have previously exclude the case that from_currency and to_currency are the same.
        # And even that three of them are the same too. At first equality condition.
        if from_currency == company_currency:  # and to_currency != company_currency
            # /!\ NOTE: custom_rate is as many custom_rate company_currency units per to_currency units
            # custom_rate = 25. Then 25 company_currencies / 1 to_currency
            amount = to_currency.round(amount / custom_rate)
        if to_currency == company_currency:  # and from_currency != company_currency
            # /!\ NOTE: custom_rate is as many custom_rate company_currency units per from_currency units
            # custom_rate = 25. Then 25 company_currencies / 1 from_currency
            amount = to_currency.round(amount * custom_rate)
        return amount


class AccountPayment(models.Model):
    _inherit = "account.payment"

    payment_split_data = fields.Text(
        readonly=True, help="Technical field to be used to save the details in the originating wizard."
    )
    to_reconcile_on_background = fields.Boolean(
        readonly=True, help="Technical field to be used by other processes to reconcile this payment in background."
    )
    reconciliation_data = fields.Text(
        readonly=True,
        help="Technical field to be used by other processes to reconcile this payment in background. "
        "This field holds the values of the invoices that will be register a payment with a pairing Journal Item.",
    )

    def _seek_for_lines(self):
        ''' Helper used to dispatch the journal items between:
        - The lines using the temporary liquidity account.
        - The lines using the counterpart account.
        - The lines being the write-off lines.
        :return: (liquidity_lines, counterpart_lines, writeoff_lines)
        '''
        lines = super(AccountPayment, self)._seek_for_lines()
        new_lines = []
        for line_p in lines:
            if line_p and len(line_p) > 1:
                new_lines.append(line_p[-1])
            else:
                new_lines.append(line_p)

        return new_lines

    def action_draft(self):
        res = super().action_draft()
        data_to_clear = self.filtered(lambda x: x.payment_split_data)
        if not data_to_clear:
            return res

        body = _(
            "Los siguientes datos json se escribieron en este pago porque se creó a partir de una división de pago.<br/>"
            "Como el documento se configuró como borrador, el campo paid_split_data ya no es necesario:<br/>%s"
        )

        for payment in data_to_clear:
            payment.message_post(body=Markup(body % payment.payment_split_data))

        data_to_clear.write({"payment_split_data": False})
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self.write(
            {
                "reconciliation_data": json.dumps(False),
                "to_reconcile_on_background": False,
            }
        )
        return res

    def check_for_payment_in_widget_on_invoice(self, invoice, payment_id):
        """This method check for the journal_item named payment_id and analyze
        the payment widget in the invoice to verify if that payment has already
        in the widget. If the payment is not in the widget it returns True

        :param invoice: a browseable record from account.invoice model
        :param payment_id: integer key from the account.move.line model
        :return: a boolean True if the payment_id is not within the widget.
        """
        res = json.loads(invoice.payments_widget)
        if not res:
            return True

        content = res.get("content", [])
        if not content:
            return True

        for line in content:
            if line.get("payment_id") == payment_id:
                return False

        return True

    def _fetch_data_to_reconcile_in_background(self):
        res = {}
        for payment in self:
            res[payment.id] = json.loads(payment.reconciliation_data)
        return res
