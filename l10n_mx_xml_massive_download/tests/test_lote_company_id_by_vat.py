# -*- coding: utf-8 -*-
"""Tests del fix multi-company: account.edi.api.download.company_id se
auto-resuelve por VAT match.

Contexto: incidente ANFEPI 2026-05-28 — lotes para RFC ASA quedaban
pegados a company ANPAU si el admin estaba en contexto ANPAU al crear el
lote. La regla de seguridad por company_id los mostraba cruzados entre
empresas (aunque XMLs descargados estaban en empresa correcta).

Estos tests validan que:
- Al crear/modificar lote con vat = res.company.partner.vat, company_id
  se asigna a esa company automaticamente.
- Si no hay res.company con ese vat (caso single-tenant Cosal/Vencedor),
  se mantiene la company activa.
- La constraint bloquea writes que intenten forzar mismatch.
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'l10n_mx_xml_massive_download')
class TestLoteCompanyIdByVat(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Crear 2 companies con VATs distintos para simular multi-tenant
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Cliente A SA de CV',
            'is_company': True,
            'vat': 'AAA010101AAA',
        })
        cls.company_a = cls.env['res.company'].create({
            'name': 'Cliente A SA de CV',
            'partner_id': cls.partner_a.id,
            'vat': 'AAA010101AAA',
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Cliente B SA de CV',
            'is_company': True,
            'vat': 'BBB020202BBB',
        })
        cls.company_b = cls.env['res.company'].create({
            'name': 'Cliente B SA de CV',
            'partner_id': cls.partner_b.id,
            'vat': 'BBB020202BBB',
        })

    def test_company_id_resolved_by_vat_match(self):
        """Si lote.vat = res.company.partner.vat, company_id = esa company."""
        lote = self.env['account.edi.api.download'].with_company(self.company_a).create({
            'name': 'Lote test multi-tenant',
            'vat': 'BBB020202BBB',  # VAT de company_b aunque estoy en company_a
            'date_start': '2025-01-01',
            'date_end': '2025-01-31',
            'cfdi_type': 'recibidos',
        })
        self.assertEqual(lote.company_id.id, self.company_b.id,
            "Lote debe pertenecer a company B porque su VAT matchea "
            "(no a company A que es la activa)")

    def test_company_id_fallback_when_no_vat_match(self):
        """Si lote.vat no corresponde a ninguna company, mantener activa."""
        lote = self.env['account.edi.api.download'].with_company(self.company_a).create({
            'name': 'Lote test single-tenant',
            'vat': 'XXX999999XXX',  # VAT que no es de ninguna company
            'date_start': '2025-01-01',
            'date_end': '2025-01-31',
            'cfdi_type': 'recibidos',
        })
        self.assertEqual(lote.company_id.id, self.company_a.id,
            "Sin VAT match, debe caer en la company activa (fallback "
            "single-tenant tipo Cosal/Vencedor)")

    def test_constraint_blocks_vat_company_mismatch(self):
        """Constraint bloquea writes que forzarian company_id != VAT owner."""
        lote = self.env['account.edi.api.download'].with_company(self.company_a).create({
            'name': 'Lote constraint test',
            'vat': 'AAA010101AAA',
            'date_start': '2025-01-01',
            'date_end': '2025-01-31',
            'cfdi_type': 'recibidos',
        })
        self.assertEqual(lote.company_id.id, self.company_a.id)
        # Intentar forzar company_id = company_b para un VAT de company_a
        with self.assertRaises(ValidationError):
            lote.company_id = self.company_b.id

    def test_company_id_updates_on_vat_change(self):
        """Cambiar lote.vat dispara recompute de company_id."""
        lote = self.env['account.edi.api.download'].with_company(self.company_a).create({
            'name': 'Lote vat change test',
            'vat': 'AAA010101AAA',
            'date_start': '2025-01-01',
            'date_end': '2025-01-31',
            'cfdi_type': 'recibidos',
        })
        self.assertEqual(lote.company_id.id, self.company_a.id)
        lote.vat = 'BBB020202BBB'
        self.assertEqual(lote.company_id.id, self.company_b.id,
            "Cambiar VAT a uno que matchea otra company debe mover el lote")
