# -*- coding: utf-8 -*-
"""Tests del fix de xml_imported_id como computed-stored.

Antes del refactor, el campo se llenaba solo cuando el wizard de descarga
creaba la factura. Si la factura existia y solo se vinculaba al XML por
matching de UUID, xml_imported_id quedaba NULL y el boton inteligente
"XML SAT" no aparecia en el form. Esto causo confusion en ANFEPI
productivo.

Estos tests garantizan que xml_imported_id se popula correctamente en
TODOS los flujos de vinculacion (creacion + matching + asignacion manual)
gracias al compute basado en el reverse xml.invoice_id.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_mx_xml_massive_download')
class TestXmlImportedComputed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
            'is_company': True,
        })
        cls.move = cls.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': cls.partner.id,
        })
        cls.batch = cls.env['account.edi.api.download'].create({
            'name': 'Test batch',
            'vat': cls.env.company.partner_id.vat or 'XAXX010101000',
            'date_start': '2025-01-01',
            'date_end': '2025-01-31',
            'cfdi_type': 'recibidos',
        })

    def _invalidate_move(self):
        """Invalida cache del move compat v15-v19."""
        if hasattr(self.move, 'invalidate_recordset'):
            self.move.invalidate_recordset(['xml_sat_ids', 'xml_imported_id'])
        else:
            self.move.invalidate_cache(['xml_sat_ids', 'xml_imported_id'])

    def _make_xml(self, uuid, invoice_id=False):
        return self.env['account.edi.downloaded.xml.sat'].create({
            'name': uuid,
            'invoice_id': invoice_id,
            'company_id': self.env.company.id,
            'cfdi_type': 'recibidos',
            'batch_id': self.batch.id,
            'sub_total': 100.0,
            'amount_total': 116.0,
        })

    def test_xml_imported_id_empty_when_no_xml_linked(self):
        """Sin XML apuntando a la factura, xml_imported_id es False."""
        self.assertFalse(self.move.xml_imported_id)

    def test_xml_imported_id_populated_on_xml_link(self):
        """Al asignar xml.invoice_id = move, el compute popula move.xml_imported_id."""
        xml = self._make_xml('UUID-TEST-001', invoice_id=self.move.id)
        # Force invalidation para que el compute lea xml_sat_ids fresco
        self._invalidate_move()
        self.assertEqual(self.move.xml_imported_id.id, xml.id,
            "xml_imported_id debe ser el XML que apunta a esta factura")

    def test_xml_imported_id_updates_on_unlink(self):
        """Al desvincular xml.invoice_id, move.xml_imported_id vuelve a False."""
        xml = self._make_xml('UUID-TEST-002', invoice_id=self.move.id)
        self._invalidate_move()
        self.assertTrue(self.move.xml_imported_id)
        xml.invoice_id = False
        self._invalidate_move()
        self.assertFalse(self.move.xml_imported_id,
            "Desvincular xml.invoice_id debe limpiar move.xml_imported_id")

    def test_xml_imported_id_first_xml_when_multiple(self):
        """Si multiples XMLs apuntan al mismo move (ej. cancelacion+reemision),
        xml_imported_id devuelve el primero (menor id)."""
        xml1 = self._make_xml('UUID-TEST-003a', invoice_id=self.move.id)
        xml2 = self._make_xml('UUID-TEST-003b', invoice_id=self.move.id)
        self._invalidate_move()
        self.assertIn(self.move.xml_imported_id, (xml1, xml2),
            "xml_imported_id debe ser uno de los XMLs vinculados")
