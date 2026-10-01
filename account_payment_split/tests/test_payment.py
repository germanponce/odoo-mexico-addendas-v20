from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged

from odoo.addons.account.tests.common import TestAccountReconciliationCommon

MAP_INVOICE_TYPE_PAYMENT_SIGN = {
    "out_invoice": 1,
    "in_refund": 1,
    "in_invoice": -1,
    "out_refund": -1,
}


@tagged("post_install", "-at_install")
class TestPayment(TestAccountReconciliationCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.currency_mxn = cls.env.ref("base.MXN")
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_usd.active = True
        cls.company.currency_id = cls.currency_mxn
        cls.bank_journal_euro.currency_id = cls.currency_euro_id

        # /!\ NOTE: This will avoid a raise by account_edi. That is, no e-sign will required in these test.
        journals = cls.env["account.journal"].search([])
        journals.write({"edi_format_ids": [(6, 0, [])]})

        cls.bank_journal_mxn = cls.env["account.journal"].create(
            {"name": "Bank MXN", "type": "bank", "code": "BNKMX", "currency_id": cls.currency_mxn.id}
        )

        cls.today = fields.Date.today()

        cls.currency_usd.rate_ids.sudo().unlink()
        cls.env["res.currency.rate"].create(
            {
                "name": "2019-09-28",
                "rate": 1.0 / 19.6363,
                "currency_id": cls.currency_usd.id,
                "company_id": cls.company.id,
            }
        )
        cls.env["res.currency.rate"].create(
            {
                "name": "2019-10-15",
                "rate": 1.0 / 19.3217,
                "currency_id": cls.currency_usd.id,
                "company_id": cls.company.id,
            }
        )
        cls.env["res.currency.rate"].create(
            {
                "name": "2019-10-22",
                "rate": 1.0 / 19.1492,
                "currency_id": cls.currency_usd.id,
                "company_id": cls.company.id,
            }
        )
        cls.env["res.currency.rate"].create(
            {
                "name": cls.today,
                "rate": 1.0 / 19.6829,
                "currency_id": cls.currency_usd.id,
                "company_id": cls.company.id,
            }
        )
        cls.payment_model = cls.env["account.payment"]

    def create_payment(
        self,
        invoices,
        payment_type,
        currency,
        journal,
        amount=False,
        date=False,
        custom_rate=None,
        account_id=None,
        handling="reconcile",
    ):
        """Creating payment using wizard"""
        ctx = {"active_model": "account.move", "active_ids": invoices.ids}
        date = date or (self.today + timedelta(days=1))
        register = Form(self.env["account.split.payment.register"].with_context(**ctx))
        register.payment_date = date
        register.journal_id = journal
        if amount:
            register.amount = amount
        payment = register.save()
        if account_id:
            register.writeoff_account_id = account_id
        if custom_rate:
            payment.write({"custom_rate": custom_rate})
        return payment

    def check_payments(self, payments, invoices, amount, n_aml, n_payments):

        payment_amount = sum(payments.mapped("amount"))
        payment_state = list(set(payments.mapped("state")))
        invoice_state = list(set(invoices.mapped("payment_state")))
        self.assertEqual(len(payments), n_payments)
        self.assertAlmostEqual(payment_amount, amount)
        self.assertEqual(len(payment_state), 1)
        self.assertEqual(payment_state[0], "posted")
        self.assertEqual(len(invoice_state), 1)
        self.assertIn(invoice_state[0], ("in_payment", "paid"))
        self.assertEqual(len(payments.line_ids), n_aml)

    def test_that_wizard_is_working_1(self):
        """Just running the wizard from the invoices"""

        invoice = self.create_invoice(move_type="in_invoice", invoice_amount=100, currency_id=self.currency_mxn.id)
        result = invoice.action_register_split_payment()
        expected = {
            "name": "Split Payment",
            "res_model": "account.split.payment.register",
            "view_mode": "form",
            "context": {"active_model": "account.move", "active_ids": [invoice.id]},
            "target": "new",
            "type": "ir.actions.act_window",
        }
        self.assertEqual(result, expected)

    def test_that_wizard_is_working_2(self):
        """Just running the wizard from the invoices"""

        invoices = self.create_invoice(move_type="in_invoice", invoice_amount=100, currency_id=self.currency_mxn.id)
        invoices |= self.create_invoice(move_type="in_invoice", invoice_amount=100, currency_id=self.currency_mxn.id)
        payment = self.create_payment(invoices, "outbound", self.currency_mxn, self.bank_journal_mxn)

        result = payment.action_create_payments()
        expected = {
            "name": "Payments",
            "type": "ir.actions.act_window",
            "res_model": "account.payment",
            "context": {"create": False},
            "view_mode": "form",
            "res_id": result["res_id"],
        }
        self.assertEqual(result, expected)

    def test_three_currencies_custom_rate_issue(self):
        """Just running the wizard from the invoices"""

        invoices = self.create_invoice(move_type="in_invoice", invoice_amount=100, currency_id=self.currency_usd.id)
        payment = self.create_payment(
            invoices, "outbound", self.bank_journal_euro.currency_id, self.bank_journal_euro, custom_rate=30
        )
        with self.assertRaises(UserError), self.cr.savepoint():
            payment.payment_invoice_ids._convert_from_payment_to_invoice_currency()

    def test_that_wizard_is_providing_proper_values_in_the_lines(self):
        """Just running the wizard from the invoices"""

        ##############
        # USD TO USD #
        ##############
        invoice = self._create_invoice(
            move_type="in_invoice",
            auto_validate=True,
            date_invoice="2019-09-28",
            invoice_amount=100,
            currency_id=self.currency_usd.id,
        )
        # We set zero because we want that the wizard computes the amount by itself.
        payment = self.create_payment(
            invoice, "outbound", self.currency_usd, self.bank_journal_usd, amount=0, date="2019-10-22"
        )

        self.assertAlmostEqual(payment.amount, 100.00)
        self.assertEqual(payment.currency_id, self.currency_usd)

        self.assertEqual(payment.company_currency_amount, 1914.92)
        self.assertEqual(payment.company_currency_id, self.currency_mxn)

        pline = payment.payment_invoice_ids
        self.assertEqual(pline.amount, 100)
        self.assertEqual(pline.payment_amount, 100)
        self.assertAlmostEqual(pline.payment_currency_amount, 100.00)
        self.assertEqual(pline.company_currency_amount, 1914.92)

        # Let us change the custom_rate
        payment.write({"custom_rate": 25.0})
        payment._onchange_currency_at_payment()
        self.assertAlmostEqual(payment.custom_rate, 25.0)
        self.assertAlmostEqual(payment.amount, 100.00)
        self.assertEqual(payment.currency_id, self.currency_usd)

        self.assertEqual(payment.company_currency_amount, 2500)
        self.assertEqual(payment.company_currency_id, self.currency_mxn)

        pline = payment.payment_invoice_ids
        self.assertEqual(pline.amount, 100)
        self.assertEqual(pline.payment_amount, 100)
        self.assertAlmostEqual(pline.payment_currency_amount, 100.00)
        self.assertEqual(pline.company_currency_amount, 2500.00)

        ##############
        # USD TO MXN #
        ##############
        invoice = self._create_invoice(
            move_type="in_invoice",
            auto_validate=True,
            date_invoice="2019-09-28",
            invoice_amount=100,
            currency_id=self.currency_usd.id,
        )
        # We set zero because we want that the wizard computes the amount by itself.
        payment = self.create_payment(
            invoice, "outbound", self.currency_mxn, self.bank_journal_mxn, amount=0, date="2019-10-22"
        )

        self.assertAlmostEqual(payment.amount, 1914.92)
        self.assertEqual(payment.currency_id, self.currency_mxn)

        self.assertEqual(payment.company_currency_amount, 1914.92)
        self.assertEqual(payment.company_currency_id, self.currency_mxn)

        pline = payment.payment_invoice_ids
        self.assertEqual(pline.amount, 100)
        self.assertEqual(pline.payment_amount, 100)
        self.assertAlmostEqual(pline.payment_currency_amount, 1914.92)
        self.assertEqual(pline.company_currency_amount, 1914.92)

        # Let us change the custom_rate
        payment.write({"custom_rate": 25.0})
        payment._onchange_currency_at_payment()
        self.assertAlmostEqual(payment.custom_rate, 25.0)
        self.assertAlmostEqual(payment.amount, 2500.00)
        self.assertEqual(payment.currency_id, self.currency_mxn)

        self.assertEqual(payment.company_currency_amount, 2500)
        self.assertEqual(payment.company_currency_id, self.currency_mxn)

        pline = payment.payment_invoice_ids
        self.assertEqual(pline.amount, 100)
        self.assertEqual(pline.payment_amount, 100)
        self.assertAlmostEqual(pline.payment_currency_amount, 2500.00)
        self.assertEqual(pline.company_currency_amount, 2500.00)

        ##############
        # MXN TO USD #
        ##############
        invoice = self._create_invoice(
            move_type="in_invoice",
            auto_validate=True,
            date_invoice="2019-09-28",
            invoice_amount=100,
            currency_id=self.currency_mxn.id,
        )
        # We set zero because we want that the wizard computes the amount by itself.
        payment = self.create_payment(
            invoice, "outbound", self.currency_usd, self.bank_journal_usd, amount=0, date="2019-10-22"
        )

        self.assertAlmostEqual(payment.amount, 5.22)
        self.assertEqual(payment.currency_id, self.currency_usd)

        self.assertEqual(payment.company_currency_amount, 100)
        self.assertEqual(payment.company_currency_id, self.currency_mxn)

        pline = payment.payment_invoice_ids
        self.assertEqual(pline.amount, 100)
        self.assertEqual(pline.payment_amount, 100)
        self.assertAlmostEqual(pline.payment_currency_amount, 5.22)
        self.assertEqual(pline.company_currency_amount, 100)

        # Let us change the custom_rate
        payment.write({"custom_rate": 25.0})
        payment._onchange_currency_at_payment()
        self.assertAlmostEqual(payment.custom_rate, 25.0)
        self.assertAlmostEqual(payment.amount, 4.00)
        self.assertEqual(payment.currency_id, self.currency_usd)

        self.assertEqual(payment.company_currency_amount, 100)
        self.assertEqual(payment.company_currency_id, self.currency_mxn)

        pline = payment.payment_invoice_ids
        self.assertEqual(pline.amount, 100)
        self.assertEqual(pline.payment_amount, 100)
        self.assertAlmostEqual(pline.payment_currency_amount, 4.00)
        self.assertEqual(pline.company_currency_amount, 100)

        ##############
        # MXN TO MXN #
        ##############
        invoice = self._create_invoice(
            move_type="in_invoice",
            auto_validate=True,
            date_invoice="2019-09-28",
            invoice_amount=100,
            currency_id=self.currency_mxn.id,
        )
        # We set zero because we want that the wizard computes the amount by itself.
        payment = self.create_payment(
            invoice, "outbound", self.currency_mxn, self.bank_journal_mxn, amount=0, date="2019-10-22"
        )

        self.assertEqual(payment.amount, 100)
        self.assertEqual(payment.currency_id, self.currency_mxn)

        self.assertEqual(payment.company_currency_amount, 100)
        self.assertEqual(payment.company_currency_id, self.currency_mxn)

        pline = payment.payment_invoice_ids
        self.assertEqual(pline.amount, 100)
        self.assertEqual(pline.payment_amount, 100)
        self.assertEqual(pline.payment_currency_amount, 100)
        self.assertEqual(pline.company_currency_amount, 100)

        # Ensure that cancel process works correctly
        result = payment.action_create_payments()
        payment = self.payment_model.browse(result["res_id"])
        payment.action_draft()
        payment.action_cancel()
        self.assertEqual(payment.state, "cancel", "Payment not cancelled.")

    def test_that_wizard_is_auto_splitting(self):
        """Just running the wizard from the invoices"""

        invoices = self.create_invoice(move_type="in_invoice", invoice_amount=100, currency_id=self.currency_mxn.id)
        invoices |= self.create_invoice(move_type="in_invoice", invoice_amount=100, currency_id=self.currency_mxn.id)
        payment = self.create_payment(invoices, "outbound", self.currency_mxn, self.bank_journal_mxn, amount=135)
        payment_currency_amount = payment.payment_invoice_ids.mapped("payment_currency_amount")

        self.assertIn(100, payment_currency_amount)
        self.assertIn(35, payment_currency_amount)

    def test_full_payment_process_01(self):
        """Paying fully invoices with same currency MXN and USD"""
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            currency_journal = [(self.currency_mxn, self.bank_journal_mxn), (self.currency_usd, self.bank_journal_usd)]
            for currency, journal in currency_journal:
                inv_1 = self.create_invoice(move_type=move_type, invoice_amount=100, currency_id=currency.id)
                inv_2 = self.create_invoice(move_type=move_type, invoice_amount=200, currency_id=currency.id)

                invoices = inv_1 + inv_2
                payment = self.create_payment(invoices, payment_type[move_type], currency, journal)
                payments = payment._create_split_payments()

                self.check_payments(payments, invoices, 300, 3, 1)

    def test_payment_wizard_usd_currency_payment(self):
        """Checking the computation of payment in USD for Multi-currency
        Invoices"""
        pay_amount = 11342.41
        currency = self.currency_usd

        inv_1 = self._create_invoice(
            move_type="out_invoice",
            invoice_amount=33783.84,
            currency_id=self.currency_mxn.id,
            auto_validate=True,
            date_invoice="2019-09-28",
        )
        inv_2 = self._create_invoice(
            move_type="out_invoice",
            invoice_amount=9578.17,
            currency_id=self.currency_usd.id,
            auto_validate=True,
            date_invoice="2019-10-15",
        )

        invoices = inv_1 + inv_2
        payment = self.create_payment(
            invoices, "inbound", currency, self.bank_journal_usd, pay_amount, date="2019-10-22"
        )

        pay_line_inv_1 = payment.payment_invoice_ids.filtered(lambda x: x.invoice_id == inv_1)
        pay_line_inv_2 = payment.payment_invoice_ids.filtered(lambda x: x.invoice_id == inv_2)

        self.assertAlmostEqual(
            pay_line_inv_1.payment_amount,
            33783.84,
            2,
            "Invoice in MXN Paid in USD got a wrong value in Invoice Currency",
        )
        self.assertAlmostEqual(
            pay_line_inv_1.payment_currency_amount,
            1764.24,
            2,
            "Invoice in MXN Paid in USD got a wrong value in Payment Currency",
        )
        self.assertAlmostEqual(
            pay_line_inv_1.company_currency_amount,
            33783.84,
            2,
            "Invoice in MXN Paid in USD got a wrong value in Company Currency",
        )

        self.assertAlmostEqual(
            pay_line_inv_2.payment_amount,
            9578.17,
            2,
            "Invoice in USD Paid in USD got a wrong value in Invoice Currency",
        )
        self.assertAlmostEqual(
            pay_line_inv_2.payment_currency_amount,
            9578.17,
            2,
            "Invoice in USD Paid in USD got a wrong value in Payment Currency",
        )
        self.assertAlmostEqual(
            pay_line_inv_2.company_currency_amount,
            183414.29,
            2,
            "Invoice in USD Paid in USD got a wrong value in Company Currency",
        )

    def test_payment_wizard_mxn_currency_payment(self):
        """Checking the computation of payment in MXN for Multi-currency
        Invoices"""
        pay_amount = 217198.13
        currency = self.currency_mxn

        inv_1 = self._create_invoice(
            move_type="out_invoice",
            invoice_amount=33783.84,
            currency_id=self.currency_mxn.id,
            auto_validate=True,
            date_invoice="2019-09-28",
        )
        inv_2 = self._create_invoice(
            move_type="out_invoice",
            invoice_amount=9578.17,
            currency_id=self.currency_usd.id,
            auto_validate=True,
            date_invoice="2019-10-15",
        )

        invoices = inv_1 + inv_2
        payment = self.create_payment(
            invoices, "inbound", currency, self.bank_journal_mxn, pay_amount, date="2019-10-22"
        )
        pay_line_inv_1 = payment.payment_invoice_ids.filtered(lambda x: x.invoice_id == inv_1)
        pay_line_inv_2 = payment.payment_invoice_ids.filtered(lambda x: x.invoice_id == inv_2)

        self.assertAlmostEqual(
            pay_line_inv_1.payment_amount,
            33783.84,
            2,
            "Invoice in MXN Paid in MXN got a wrong value in Invoice Currency",
        )
        self.assertAlmostEqual(
            pay_line_inv_1.payment_currency_amount,
            33783.84,
            2,
            "Invoice in MXN Paid in MXN got a wrong value in Payment Currency",
        )
        self.assertAlmostEqual(
            pay_line_inv_1.company_currency_amount,
            33783.84,
            2,
            "Invoice in MXN Paid in MXN got a wrong value in Company Currency",
        )

        self.assertAlmostEqual(
            pay_line_inv_2.payment_amount,
            9578.17,
            2,
            "Invoice in USD Paid in MXN got a wrong value in Invoice Currency",
        )
        self.assertAlmostEqual(
            pay_line_inv_2.payment_currency_amount,
            183414.29,
            2,
            "Invoice in USD Paid in MXN got a wrong value in Payment Currency",
        )
        self.assertAlmostEqual(
            pay_line_inv_2.company_currency_amount,
            183414.29,
            2,
            "Invoice in USD Paid in MXN got a wrong value in Company Currency",
        )

    def test_full_payment_process_multi_currencies_usd_01(self):
        """Paying fully invoices with different currencies with a USD
        payment"""
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self._create_invoice(
                move_type=move_type, auto_validate=True, invoice_amount=100, currency_id=self.currency_usd.id
            )
            inv_2 = self._create_invoice(
                move_type=move_type, auto_validate=True, invoice_amount=200, currency_id=self.currency_mxn.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(invoices, payment_type[move_type], self.currency_usd, self.bank_journal_usd)

            payments = payment._create_split_payments()

            self.check_payments(payments, invoices, payment.amount, 3, 1)

    def test_full_payment_process_multi_currencies_mxn_01(self):
        """Paying fully invoices with different currencies with a MXN
        payment"""
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self._create_invoice(
                move_type=move_type,
                auto_validate=True,
                date_invoice=self.today,
                invoice_amount=100,
                currency_id=self.currency_usd.id,
            )
            inv_2 = self._create_invoice(
                move_type=move_type,
                auto_validate=True,
                date_invoice=self.today,
                invoice_amount=200,
                currency_id=self.currency_mxn.id,
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(invoices, payment_type[move_type], self.currency_mxn, self.bank_journal_mxn)

            payments = payment._create_split_payments()
            self.check_payments(payments, invoices, 2168.29, 3, 1)

    # ----------------------------- Excess --------------------------------

    def test_full_payment_process_02_handling_open_mxn(self):
        """Paying MXN invoices with MXN payment(Excess) - Handling Reconcile
        payment and using different accounts for same partner"""
        payment_type = "outbound"
        invo_type = "in_invoice"

        account = self.company_data["default_account_expense"]
        invoices = self.create_invoice(move_type=invo_type, invoice_amount=300, currency_id=self.currency_mxn.id)
        invoices |= self.create_invoice(move_type=invo_type, invoice_amount=200, currency_id=self.currency_mxn.id)

        payment_wizard = self.create_payment(
            invoices, payment_type, self.currency_mxn, self.bank_journal_mxn, amount=650, account_id=None
        )
        payment_wizard._onchange_amount()
        payment_wizard.amount = 650
        payment_wizard._onchange_amount()

        self.assertEqual(payment_wizard.payment_difference, 150)
        self.assertEqual(payment_wizard.company_difference, 150)

        payment_wizard.payment_difference_handling = "reconcile"
        payment_wizard.writeoff_account_id = account.id

        payment_record = payment_wizard._create_split_payments()

        liquidity_lines, counterpart_lines, writeoff_lines = payment_record._seek_for_lines()

        self.assertAlmostEqual(abs(liquidity_lines.balance), 650)
        self.assertAlmostEqual(abs(sum(counterpart_lines.mapped("balance"))), 500)
        self.assertAlmostEqual(abs(writeoff_lines.balance), 150)
        self.assertAlmostEqual(writeoff_lines.account_id, account)

    def test_full_payment_process_02_handling_open_usd(self):
        """Paying USD invoices with USD payment(Excess) - Handling Open"""
        self.skipTest("Skipped Test. Pending for migration of the test.")
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                move_type=move_type, amount=100, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                move_type=move_type, amount=200, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(
                invoices, payment_type[move_type], self.currency_usd, self.bank_journal_usd, 400
            )

            payment.create_payments()

            payment = self.payment_model.search([("invoice_ids", "in", invoices.ids)], order="id desc", limit=1)

            # /!\ NOTE: Fetching the line with the bank value
            aml_id = payment.move_line_ids.filtered(
                lambda x: x.account_id
                in (payment.journal_id.default_debit_account_id, payment.journal_id.default_credit_account_id)
            )
            self.assertAlmostEqual(abs(aml_id.amount_currency), 400)
            # /!\ NOTE: Fetching the line with the excess value
            aml_id = payment.move_line_ids.filtered(
                lambda x: x.account_id
                not in (payment.journal_id.default_debit_account_id, payment.journal_id.default_credit_account_id)
                and not x.full_reconcile_id
            )
            self.assertAlmostEqual(abs(aml_id.amount_currency), 100)
            state = list(set(invoices.mapped("state")))
            self.assertAlmostEqual(payment.amount, 400)
            self.assertEqual(payment.state, "posted")
            self.assertEqual(len(state), 1)
            self.assertEqual(state[0], "paid")
            self.assertEqual(len(payment.move_line_ids), 4)

    def test_full_payment_process_02(self):
        """Paying MXN invoices with MXN payment(Excess)"""
        self.skipTest("Skipped Test. Pending for migration of the test.")
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                move_type=move_type, amount=100, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                move_type=move_type, amount=200, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(
                invoices, payment_type[move_type], self.currency_mxn, self.bank_journal_mxn, 400
            )

            payment.update(
                {
                    "payment_difference_handling": "reconcile",
                    "writeoff_account_id": self.diff_expense_account.id,
                }
            )
            payment.create_payments()

            self.check_payments(invoices, 400, 4)

            payment = self.payment_model.search([("invoice_ids", "in", invoices.ids)], order="id desc", limit=1)

            writeoff_line = payment.move_line_ids.filtered(lambda a: a.account_id == self.diff_expense_account)

            self.assertEqual(abs(writeoff_line.balance), 100)

    def test_full_payment_process_usd_02(self):
        """Paying USD invoices with USD payment(Excess)"""
        self.skipTest("Skipped Test. Pending for migration of the test.")
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                move_type=move_type, amount=100, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                move_type=move_type, amount=200, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(
                invoices, payment_type[move_type], self.currency_usd, self.bank_journal_usd, 400
            )
            payment.update(
                {
                    "payment_difference_handling": "reconcile",
                    "writeoff_account_id": self.diff_expense_account.id,
                }
            )
            payment.create_payments()

            self.check_payments(invoices, 400, 4)

            payment = self.payment_model.search([("invoice_ids", "in", invoices.ids)], order="id desc", limit=1)

            writeoff_line = payment.move_line_ids.filtered(lambda a: a.account_id == self.diff_expense_account)

            self.assertEqual(abs(writeoff_line.balance), 36740.88)

    def test_full_payment_process_multi_currencies_usd_02(self):
        """Pay with Excess invoices with different currencies with USD
        payment"""
        self.skipTest("Skipped Test. Pending for migration of the test.")
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                move_type=move_type, amount=100, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                move_type=move_type, amount=200, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(
                invoices, payment_type[move_type], self.currency_usd, self.bank_journal_usd, 200
            )

            payment.update(
                {
                    "payment_difference_handling": "reconcile",
                    "writeoff_account_id": self.diff_expense_account.id,
                }
            )

            payment.create_payments()

            self.check_payments(invoices, 200, 4)

            payment = self.payment_model.search([("invoice_ids", "in", invoices.ids)], order="id desc", limit=1)

            writeoff_line = payment.move_line_ids.filtered(lambda a: a.account_id == self.diff_expense_account)

            self.assertEqual(abs(writeoff_line.balance), 36540.89)

    def test_full_payment_process_multi_currencies_mxn_02(self):
        """Pay with Excess invoices with different currencies with MXN
        payment"""
        self.skipTest("Skipped Test. Pending for migration of the test.")
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                move_type=move_type, amount=100, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                move_type=move_type, amount=200, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(invoices, payment_type[move_type], self.currency_mxn, self.bank_journal_mxn)
            payment.update(
                {
                    "amount": payment.amount + 831.71,
                    "payment_difference_handling": "reconcile",
                    "writeoff_account_id": self.diff_expense_account.id,
                }
            )
            payment._onchange_payment_invoice()
            payment.create_payments()

            self.check_payments(invoices, payment.amount, 4)

            payment = self.payment_model.search([("invoice_ids", "in", invoices.ids)], order="id desc", limit=1)

            writeoff_line = payment.move_line_ids.filtered(lambda a: a.account_id == self.diff_expense_account)

            self.assertEqual(abs(writeoff_line.balance), 831.71)

    # ----------------------------- Partial --------------------------------

    def test_full_payment_process_03(self):
        """Partial Payment: invoices and payment with the same currency MXN"""
        self.skipTest("Skipped Test. Pending for migration of the test.")
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                move_type=move_type, amount=100, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                move_type=move_type, amount=200, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(
                invoices, payment_type[move_type], self.currency_mxn, self.bank_journal_mxn, 200
            )

            payment.update(
                {
                    "payment_difference_handling": "reconcile",
                    "writeoff_account_id": self.diff_expense_account.id,
                }
            )
            payment.create_payments()

            self.check_payments(invoices, 200, 4)

            payment = self.payment_model.search([("invoice_ids", "in", invoices.ids)], order="id desc", limit=1)

            writeoff_line = payment.move_line_ids.filtered(lambda a: a.account_id == self.diff_expense_account)

            self.assertEqual(abs(writeoff_line.balance), 100)

    def test_full_payment_process_usd_03(self):
        """Partial Payment: invoices and payment with the same currency USD"""
        self.skipTest("Skipped Test. Pending for migration of the test.")
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                move_type=move_type, amount=100, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                move_type=move_type, amount=200, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(
                invoices, payment_type[move_type], self.currency_usd, self.bank_journal_usd, 200
            )
            payment.update(
                {
                    "payment_difference_handling": "reconcile",
                    "writeoff_account_id": self.diff_expense_account.id,
                }
            )
            payment._onchange_payment_invoice()
            payment.create_payments()

            self.check_payments(invoices, 200, 4)

            payment = self.payment_model.search([("invoice_ids", "in", invoices.ids)], order="id desc", limit=1)

            writeoff_line = payment.move_line_ids.filtered(lambda a: a.account_id == self.diff_expense_account)

            self.assertEqual(abs(writeoff_line.balance), 36740.89)

    def test_full_payment_process_multi_currencies_usd_03(self):
        """Partial Payment: invoices with different currencies and USD
        payment"""
        self.skipTest("Skipped Test. Pending for migration of the test.")
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                move_type=move_type, amount=100, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                move_type=move_type, amount=200, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(
                invoices, payment_type[move_type], self.currency_usd, self.bank_journal_usd, 80
            )
            payment.update(
                {
                    "payment_difference_handling": "reconcile",
                    "writeoff_account_id": self.diff_expense_account.id,
                }
            )

            payment.create_payments()

            self.check_payments(invoices, 80, 4)

            payment = self.payment_model.search([("invoice_ids", "in", invoices.ids)], order="id desc", limit=1)

            writeoff_line = payment.move_line_ids.filtered(lambda a: a.account_id == self.diff_expense_account)

            self.assertEqual(abs(writeoff_line.balance), 7548.18)

    def test_full_payment_process_multi_currencies_mxn_03(self):
        """Partial Payment: invoices with different currencies and MXN
        payment"""
        self.skipTest("Skipped Test. Pending for migration of the test.")
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for move_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                move_type=move_type,
                invoice_amount=100,
                currency_id=self.currency_usd.id,
                partner=self.partner_agrolait.id,
            )
            inv_2 = self.create_invoice(
                move_type=move_type,
                invoice_amount=200,
                currency_id=self.currency_mxn.id,
                partner=self.partner_agrolait.id,
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(invoices, payment_type[move_type], self.currency_mxn, self.bank_journal_mxn)

            payment.update(
                {
                    "amount": payment.amount + 668.29,
                    "payment_difference_handling": "reconcile",
                    "writeoff_account_id": self.diff_expense_account.id,
                }
            )
            payment._onchange_payment_invoice()
            payment.create_payments()

            self.check_payments(invoices, payment.amount, 4)

            payment = self.payment_model.search([("invoice_ids", "in", invoices.ids)], order="id desc", limit=1)

            writeoff_line = payment.move_line_ids.filtered(lambda a: a.account_id == self.diff_expense_account)

            self.assertEqual(abs(writeoff_line.balance), 668.29)
