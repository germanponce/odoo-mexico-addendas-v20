from lxml import etree

from odoo.tests import tagged
from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


@tagged("post_install", "-at_install")
class TestL10nMxEdiInvoiceRetailer(TestMxEdiCommon):

    def _run_retailer_wizard(self, invoice, **vals):
        wizard = self.env['l10n_mx_edi.retailer.wizard'].with_context(
            default_invoice_id=invoice.id
        ).create(vals)
        wizard.action_confirm()

    def _configure_company_retailer_data(self, company):
        company.write({
            'l10n_mx_edi_retailer_buyer_gln': '7500000000001',
            'l10n_mx_edi_retailer_seller_gln': '7500000000002',
            'l10n_mx_edi_retailer_seller_alternate_party_identification': 'SUP-001',
            'l10n_mx_edi_retailer_ship_to_gln': '7500000000003',
        })

    def test_company_data_missing_flag(self):
        """The invoice should flag when company GLN data isn't configured"""
        invoice = self._create_invoice()
        self.assertTrue(invoice.l10n_mx_edi_retailer_company_data_missing)
        self._configure_company_retailer_data(invoice.company_id)
        self.assertFalse(invoice.l10n_mx_edi_retailer_company_data_missing)

    def test_invoice_retailer(self):
        """Basic invoice flow for an invoice with the Detallista complement"""
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice()
            self._configure_company_retailer_data(invoice.company_id)

            self._run_retailer_wizard(
                invoice,
                status="original",
                purchase_order_date=self.frozen_today.date(),
                purchase_contact_name="Azure Interior",
                special_service_type="off_invoice",
                delivery="P00011",
                delivery_date=self.frozen_today.date(),
            )

            self.assertEqual(invoice.addenda_type, 'retailer')
            self.assertEqual(invoice.l10n_mx_edi_retailer_status, 'original')

            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            self.assertEqual(invoice.l10n_mx_edi_cfdi_state, 'sent')

            attachment = invoice.l10n_mx_edi_cfdi_attachment_id
            self.assertTrue(attachment)

            xml_root = etree.fromstring(attachment.raw)
            namespaces = {'detallista': 'http://www.sat.gob.mx/detallista'}
            complement_nodes = xml_root.findall('.//detallista:detallista', namespaces)
            self.assertTrue(complement_nodes, "Complemento Detallista no fue agregado correctamente")

    def test_invoice_retailer_incomplete(self):
        """Case without contact name"""
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice()
            self._configure_company_retailer_data(invoice.company_id)

            self._run_retailer_wizard(
                invoice,
                status="original",
                purchase_order_date=self.frozen_today.date(),
                special_service_type="off_invoice",
                delivery="P00011",
                delivery_date=self.frozen_today.date(),
            )

            with self.with_mocked_pac_sign_success():
                invoice._l10n_mx_edi_cfdi_invoice_try_send()

            self.assertEqual(invoice.l10n_mx_edi_cfdi_state, 'sent')

            attachment = invoice.l10n_mx_edi_cfdi_attachment_id
            xml_root = etree.fromstring(attachment.raw)
            namespaces = {'detallista': 'http://www.sat.gob.mx/detallista'}
            complement_nodes = xml_root.findall('.//detallista:detallista', namespaces)
            self.assertTrue(complement_nodes, "Complemento Detallista no fue agregado correctamente")

    def test_invoice_retailer_wizard_prefill(self):
        """The wizard should preload the values already stored on the invoice"""
        with self.mx_external_setup(self.frozen_today):
            invoice = self._create_invoice()
            self._run_retailer_wizard(
                invoice,
                status="original",
                purchase_order_name="PO-001",
                delivery="P00011",
            )

            wizard = self.env['l10n_mx_edi.retailer.wizard'].with_context(
                default_invoice_id=invoice.id
            ).create({})
            self.assertEqual(wizard.purchase_order_name, "PO-001")
            self.assertEqual(wizard.delivery, "P00011")
