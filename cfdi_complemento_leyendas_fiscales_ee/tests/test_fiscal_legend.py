from lxml import objectify

from odoo.addons.l10n_mx_edi_40.tests.common import TestMxEdiCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestFiscalLegend(TestMxEdiCommon):
    def test_xml_node(self):
        """Validates that the XML node ``<leyendasFisc:LeyendasFiscales>`` is
            included when the invoice contains fiscal legends, and that
            its content is generated correctly
        """
        self.certificate._check_credentials()
        isr = self.env['account.account.tag'].search([('name', '=', 'ISR')])
        iva = self.env['account.account.tag'].search([('name', '=', 'IVA')])
        self.namespaces = {
            'cfdi': 'http://www.sat.gob.mx/cfd/3',
            'leyendasFisc': 'http://www.sat.gob.mx/leyendasFiscales',
        }
        self.legend = self.env['l10n_mx_edi.fiscal.legend'].create({
            'name': "Legend's Text",
            'tax_provision': 'ISR',
            'rule': 'Article 1, paragraph 2',
        })

        xml_expected = objectify.fromstring('''
            <leyendasFisc:LeyendasFiscales
                xmlns:leyendasFisc="http://www.sat.gob.mx/leyendasFiscales"
                version="1.0">
                <leyendasFisc:Leyenda
                    disposicionFiscal="ISR"
                    norma="Article 1, paragraph 2"
                    textoLeyenda="Legend's Text"/>
            </leyendasFisc:LeyendasFiscales>''')
        invoice = self.invoice
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount <= 0).invoice_repartition_line_ids.tag_ids |= isr
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount > 0).invoice_repartition_line_ids.tag_ids |= iva
        invoice.invoice_date = False
        invoice.invoice_line_ids.product_uom_id = invoice.invoice_line_ids.product_id.uom_id
        invoice.currency_id = self.env.ref('base.MXN')
        invoice.l10n_mx_edi_legend_ids = self.legend
        invoice.action_post()
        generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        xml = objectify.fromstring(generated_files[0])
        self.assertTrue(xml.Complemento.xpath(
            'leyendasFisc:LeyendasFiscales', namespaces=self.namespaces),
            "The node '<leyendasFisc:LeyendasFiscales> should be present")
        xml_leyendas = xml.Complemento.xpath('leyendasFisc:LeyendasFiscales', namespaces=self.namespaces)[0]
        self.assertXmlTreeEqual(xml_leyendas, xml_expected)
