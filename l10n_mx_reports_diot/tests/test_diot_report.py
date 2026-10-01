from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged("diot_2025", "post_install", "post_install_l10n", "-at_install")
class TestDiotReport(TestAccountReportsCommon):
    @classmethod
    @TestAccountReportsCommon.setup_country("mx")
    def setUpClass(cls):
        super().setUpClass()
        cls.env.companies.tax_exigibility = True
        cls.env.companies.totals_below_sections = True  # TODO should be automatic

        cls.purchase_taxes = cls._get_purchase_taxes()

        cls.partner_a.write(
            {
                "state_id": cls.env.ref("base.state_mx_son").id,
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_type_of_operation": "85",
                "vat": "XAXX010101000",
            }
        )
        cls.partner_b.write({"country_id": cls.env.ref("base.us").id, "l10n_mx_type_of_operation": "85"})

    @classmethod
    def _get_purchase_taxes(cls):
        taxes = cls.env["account.tax"]
        for i in [1, 2, 7, 8, 13]:
            taxes += cls.env.ref(f"account.{cls.env.company.id}_tax{i}")
        for i in [14, 16]:
            tax = cls.env.ref(f"account.{cls.env.company.id}_tax{i}")
            tag = tax.invoice_repartition_line_ids.filtered("tag_ids").tag_ids
            rda = tax.refund_repartition_line_ids.filtered(lambda line: not line.tag_ids)
            rda.write({"tag_ids": tag.search([("name", "=", "%s RDA" % tag.name)])})
            taxes += tax

        tax16 = cls.env.ref(f"account.{cls.env.company.id}_tax14")
        # Update tax 16%
        tag = tag.search([("name", "=", "+DIOT: 16% TAX")], limit=1)
        tax16.invoice_repartition_line_ids.filtered(lambda line: line.repartition_type == "tax").tag_ids |= tag
        tag = tag.search([("name", "=", "-DIOT: 16% TAX")], limit=1)
        tax16.refund_repartition_line_ids.filtered(lambda line: line.repartition_type == "tax").tag_ids |= tag
        # Tax 16% IMP
        tax = tax16.copy(
            {
                "name": "IVA 16% COMPRAS - IMP",
            }
        )
        tag = tag.search([("name", "=", "+DIOT: 16% IMP")], limit=1)
        tax.invoice_repartition_line_ids.filtered(lambda line: line.repartition_type == "base").tag_ids = tag
        tag = tag.search([("name", "=", "-DIOT: 16% IMP")], limit=1)
        tax.refund_repartition_line_ids.filtered(lambda line: line.repartition_type == "base").tag_ids = tag
        tag = tag.search([("name", "=", "+DIOT: 16% IMP TAX")], limit=1)
        tax.invoice_repartition_line_ids.filtered(lambda line: line.repartition_type == "tax").tag_ids = tag
        tag = tag.search([("name", "=", "-DIOT: 16% IMP TAX")], limit=1)
        tax.refund_repartition_line_ids.filtered(lambda line: line.repartition_type == "tax").tag_ids = tag
        taxes += tax

        return taxes

    def test_diot_report(self):
        date_invoice = "2022-07-01"
        moves_vals = []
        for i, tax in enumerate(self.purchase_taxes):
            for partner in (self.partner_a, self.partner_b):
                # Avoid tax 8% for foreign vendor
                if partner == self.partner_b and tax.amount == 8:
                    continue
                moves_vals += [
                    {
                        "move_type": "in_invoice",
                        "partner_id": partner.id,
                        "invoice_payment_term_id": False,
                        "invoice_date": date_invoice,
                        "date": date_invoice,
                        "invoice_line_ids": [
                            Command.create(
                                {
                                    "name": f"test {tax.amount}",
                                    "quantity": 1,
                                    "price_unit": 10 + 1 * i,
                                    "tax_ids": [Command.set(tax.ids)],
                                }
                            )
                        ],
                    },
                    {
                        "move_type": "in_refund",
                        "partner_id": partner.id,
                        "invoice_payment_term_id": False,
                        "invoice_date": date_invoice,
                        "date": date_invoice,
                        "invoice_line_ids": [
                            Command.create(
                                {
                                    "name": f"test {tax.amount}",
                                    "quantity": 1,
                                    "price_unit": 10 + 2 * i,
                                    "tax_ids": [Command.set(tax.ids)],
                                }
                            )
                        ],
                    },
                ]

        moves = self.env["account.move"].create(moves_vals)
        moves.action_post()

        for move in moves:
            self.env["account.payment.register"].with_context(active_model="account.move", active_ids=move.ids).create(
                {
                    "payment_date": date_invoice,
                    "journal_id": self.company_data["default_journal_bank"].id,
                    "amount": move.amount_total,
                }
            )._create_payments()

        self.assertTrue(all(m.payment_state in ("paid", "in_payment") for m in moves))

        diot_report = self.env.ref("l10n_mx.diot_report")

        options = self._generate_options(
            diot_report, fields.Date.from_string("2022-01-01"), fields.Date.from_string("2022-12-31")
        )
        options["unfold_all"] = True

        self.maxDiff = None
        diot_report._get_lines(options)
        self.assertEqual(
            self.env[diot_report.custom_handler_model_name].action_get_diot_txt(options)["file_content"].decode(),
            "04|85|XAXX010101000|||||16|22|||15|20|-7||||||||-1||-1||||||||||||||||||||||||1|||14|||01\n"
            "05|85|||partnerb|US|American|||||15|20|-7||||||||-1||-1||||||||||||||||||||||||1|||14|||01",
        )

        # Testing a Bill with 2+ taxes on the same line
        multi_taxes = self.env["account.tax"]
        multi_taxes += self.env.ref(f"account.{self.env.company.id}_tax14")  # IVA(16%) COMPRAS
        multi_taxes += self.env.ref(f"account.{self.env.company.id}_tax1")  # RET IVA FLETES 4%
        multi_taxes += self.env.ref(f"account.{self.env.company.id}_tax2")  # RET IVA ARRENDAMIENTO 10%

        multi_tax_line_move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_payment_term_id": False,
                "invoice_date": date_invoice,
                "date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "test multi tax",
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [Command.set(multi_taxes.ids)],
                        }
                    )
                ],
            }
        )
        multi_tax_line_move.action_post()

        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=multi_tax_line_move.ids
        ).create(
            {
                "payment_date": date_invoice,
                "journal_id": self.company_data["default_journal_bank"].id,
                "amount": multi_tax_line_move.amount_total,
            }
        )._create_payments()

        options = self._generate_options(
            diot_report, fields.Date.from_string("2022-01-01"), fields.Date.from_string("2022-12-31")
        )

        diot_report._get_lines(options)
        self.assertEqual(
            self.env[diot_report.custom_handler_model_name].action_get_diot_txt(options)["file_content"].decode(),
            "04|85|XAXX010101000|||||16|22|||115|20|-7||||||||15||-1||||||||||||||||||||||||13|||14|||01\n"
            "05|85|||partnerb|US|American|||||15|20|-7||||||||-1||-1||||||||||||||||||||||||1|||14|||01",
        )

    def test_diot_report_with_refund(self):
        date_invoice = "2022-07-01"
        tax = self.env.ref(f"account.{self.env.company.id}_tax14")

        move = self.env["account.move"].create(
            {
                "move_type": "in_refund",
                "partner_id": self.partner_a.id,
                "invoice_date": date_invoice,
                "date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": f"test {tax.amount}",
                            "quantity": 1,
                            "price_unit": 100,
                            "tax_ids": [Command.set(tax.ids)],
                        }
                    )
                ],
            }
        )
        move.action_post()

        self.env["account.payment.register"].with_context(active_model="account.move", active_ids=move.ids).create(
            {
                "payment_date": date_invoice,
                "journal_id": self.company_data["default_journal_bank"].id,
                "amount": move.amount_total,
            }
        )._create_payments()

        self.assertTrue(move.payment_state in ("paid", "in_payment"))

        diot_report = self.env.ref("l10n_mx.diot_report")

        options = self._generate_options(
            diot_report, fields.Date.from_string("2022-01-01"), fields.Date.from_string("2022-12-31")
        )

        self.assertLinesValues(
            diot_report._get_lines(options),
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            [
                (
                    "",
                    "",
                    "",
                    "",
                    "",
                    "$\xa00.00",
                    "$\xa0100.00",
                    "$\xa00.00",
                    "$\xa0-16.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                ),
                (
                    "04",
                    "85",
                    "XAXX010101000",
                    "MX",
                    "Mexican",
                    "$\xa00.00",
                    "$\xa0100.00",
                    "$\xa00.00",
                    "$\xa0-16.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                ),
                (
                    "",
                    "",
                    "",
                    "",
                    "",
                    "$\xa00.00",
                    "$\xa0100.00",
                    "$\xa00.00",
                    "$\xa0-16.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                    "$\xa00.00",
                ),
            ],
            options,
        )

        self.assertEqual(
            self.env[diot_report.custom_handler_model_name].action_get_diot_txt(options)["file_content"].decode(),
            "04|85|XAXX010101000||||||||||100|||||||||-16||||||||||||||||||||||||||||||||01",
        )
