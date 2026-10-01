from odoo.tests import tagged

from odoo.addons.account.tests.common import TestAccountReconciliationCommon


@tagged("post_install", "-at_install")
class TestAccountPayment(TestAccountReconciliationCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.skipTest(cls, "These tests are pending for migration")

    def test_full_payment_process_01(self):
        """Paying fully invoices with same currency MXN and USD"""
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        currencies = self.currency_mxn + self.currency_usd
        journals = {self.currency_mxn.id: self.bank_journal_mxn, self.currency_usd.id: self.bank_journal_usd}
        for invo_type in ("in_invoice", "out_invoice"):
            for currency in currencies:
                inv_1 = self.create_invoice(
                    inv_type=invo_type, amount=100, currency_id=currency.id, partner=self.partner_agrolait.id
                )
                inv_2 = self.create_invoice(
                    inv_type=invo_type, amount=200, currency_id=currency.id, partner=self.partner_agrolait.id
                )
                invoices = inv_1 + inv_2
                payment = self.create_payment(invoices, payment_type[invo_type], currency, journals[currency.id])
                payment.create_payments()
                self.check_payments(invoices, 300, 3)

    def test_full_payment_process_multi_currencies_usd_01(self):
        """Paying fully invoices with different currencies with a USD payment"""
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for invo_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                inv_type=invo_type, amount=100, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                inv_type=invo_type, amount=200, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(invoices, payment_type[invo_type], self.currency_usd, self.bank_journal_usd)

            payment.create_payments()

            self.check_payments(invoices, payment.amount, 3)

    def test_full_payment_process_multi_currencies_mxn_01(self):
        """Paying fully invoices with different currencies with a MXN payment"""
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for invo_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                inv_type=invo_type, amount=100, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                inv_type=invo_type, amount=200, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(invoices, payment_type[invo_type], self.currency_mxn, self.bank_journal_mxn)

            payment.create_payments()

            self.check_payments(invoices, payment.amount, 3)

    def test_partial_payment_multi_currencies(self):
        """Partial payment on multi invoices with different currencies with a MXN payment"""
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for invo_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                inv_type=invo_type, amount=100, currency_id=self.currency_usd.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                inv_type=invo_type, amount=200, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )

            invoices = inv_1 + inv_2
            payment = self.create_payment(
                invoices, payment_type[invo_type], self.currency_mxn, self.bank_journal_mxn, 300
            )
            for inv in payment.payment_invoice_ids:
                if inv.invoice_id.currency_id == self.currency_usd:
                    inv.payment_currency_amount = 200
                else:
                    inv.payment_currency_amount = 100
            payment._onchange_payment_invoice()
            payment.create_payments()
            self.check_payments(invoices, 300, 3, "open")

    def test_change_payment_partner(self):
        """Use different partner on wizard"""
        payment_type = {"in_invoice": "outbound", "out_invoice": "inbound"}
        for invo_type in ("in_invoice", "out_invoice"):
            inv_1 = self.create_invoice(
                inv_type=invo_type, amount=100, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )
            inv_2 = self.create_invoice(
                inv_type=invo_type, amount=200, currency_id=self.currency_mxn.id, partner=self.partner_agrolait.id
            )
            invoices = inv_1 + inv_2
            payment = self.create_payment(invoices, payment_type[invo_type], self.currency_mxn, self.bank_journal_mxn)
            payment.partner_id = self.partner_deco
            payment.create_payments()
            self.check_payments(invoices, 300, 3)
            payment = self.payment_model.search([("invoice_ids", "in", invoices.ids)], order="id desc", limit=1)
            self.assertEqual(payment.partner_id, self.partner_deco, "Wrong payment partner")
