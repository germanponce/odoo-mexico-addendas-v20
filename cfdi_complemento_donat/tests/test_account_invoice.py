from os.path import join
import base64
from lxml.objectify import fromstring

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon
from odoo.tools import misc
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestL10nMxEdiInvoiceDonat(TestMxEdiCommon):

    def test_l10n_mx_edi_invoice_donat(self):
        self.env['l10n_mx_edi.certificate'].search([]).unlink()
        certificate = self.env['l10n_mx_edi.certificate'].create({
            'content': base64.encodebytes(
                misc.file_open(join('l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.cer'), 'rb').read()),
            'key': base64.encodebytes(
                misc.file_open(join('l10n_mx_edi', 'demo', 'pac_credentials', 'certificate.key'), 'rb').read()),
            'password': '12345678a',
        })
        certificate._check_credentials()
        self.env.user.company_id.write({
            'vat': 'EKU9003173C9',
            'zip': '85134',
            'city': 'Ciudad Obregón',
            'country_id': self.env.ref('base.mx').id,
            'state_id': self.env.ref('base.state_mx_son').id,
            'l10n_mx_edi_pac': 'finkok',
            'l10n_mx_edi_pac_test_env': True,
            'l10n_mx_edi_fiscal_regime': '601',
            'l10n_mx_edi_certificate_ids': [(6, 0, certificate.ids)],
        })
        self.namespaces = {'donat': 'http://www.sat.gob.mx/donat'}
        self.partner_a.write({
            'complemento_donaciones': True,
        })
        self.invoice.company_id.write({
            'l10n_mx_edi_donat_auth': '12345',
            'l10n_mx_edi_donat_date': '2017-01-23',
            'l10n_mx_edi_donat_note': 'Este comprobante ampara un donativo, el cual será destinado por la donataria a '
            'los fines propios de su objeto social. En el caso de que los bienes donados hayan sido deducidos '
            'previamente para los efectos del impuesto sobre la renta, este donativo no es deducible.',
        })
        invoice = self.invoice

        isr = self.env['account.account.tag'].search([('name', '=', 'ISR')])
        iva = self.env['account.account.tag'].search([('name', '=', 'IVA')])
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount <= 0).invoice_repartition_line_ids.tag_ids |= isr
        invoice.invoice_line_ids.tax_ids.filtered(lambda t: t.amount > 0).invoice_repartition_line_ids.tag_ids |= iva

        invoice.invoice_date = False
        invoice.invoice_line_ids.product_uom_id = invoice.invoice_line_ids.product_id.uom_id
        invoice.currency_id = self.env.ref('base.MXN')

        invoice.action_post()
        generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files, invoice.edi_error_message)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        xml = fromstring(generated_files[0])
        scp = xml.Complemento.xpath('//donat:Donatarias', namespaces=self.namespaces)
        self.assertTrue(scp, 'Complement to Donatarias not added correctly')
