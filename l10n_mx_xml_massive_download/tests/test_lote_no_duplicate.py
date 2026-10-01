# -*- coding: utf-8 -*-
"""Tests del constraint anti-duplicado/traslape de lotes + guard de unlink.

Contexto: Vencedor productivo acumulo lotes duplicados (mayo recibidos x4 en
coordinadas) porque action_download recreaba los sublotes en cada re-encolado
y no existia restriccion de unicidad. Ademas el ACL no permitia eliminarlos.

Valida:
- Duplicado exacto (mismo RFC+tipo+rango) -> ValidationError.
- Rango traslapado (mismo RFC+tipo) -> ValidationError.
- Rango no traslapado / distinto tipo / distinto RFC -> permitido.
- unlink de lote en 'processing' -> UserError; unlink normal -> OK.
"""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError


@tagged('post_install', '-at_install', 'l10n_mx_xml_massive_download')
class TestLoteNoDuplicate(TransactionCase):

    def _mk(self, ds='2026-01-01', de='2026-01-31', tipo='recibidos',
            vat='XQD999999XXX'):
        return self.env['account.edi.api.download'].create({
            'name': 'Lote test dup',
            'vat': vat,
            'date_start': ds,
            'date_end': de,
            'cfdi_type': tipo,
        })

    def test_exact_duplicate_blocked(self):
        self._mk()
        with self.assertRaises(ValidationError):
            self._mk()

    def test_overlap_blocked(self):
        self._mk(ds='2026-01-01', de='2026-01-31')
        with self.assertRaises(ValidationError):
            self._mk(ds='2026-01-15', de='2026-02-15')

    def test_non_overlap_ok(self):
        self._mk(ds='2026-01-01', de='2026-01-31')
        rec = self._mk(ds='2026-02-01', de='2026-02-28')
        self.assertTrue(rec.id)

    def test_different_type_ok(self):
        self._mk(tipo='recibidos')
        rec = self._mk(tipo='emitidos')
        self.assertTrue(rec.id)

    def test_different_vat_ok(self):
        self._mk(vat='XQD999999XXX')
        rec = self._mk(vat='YQD888888YYY')
        self.assertTrue(rec.id)

    def test_unlink_processing_blocked(self):
        rec = self._mk()
        rec.state = 'processing'
        with self.assertRaises(UserError):
            rec.unlink()

    def test_unlink_normal_ok(self):
        rec = self._mk()
        rid = rec.id
        rec.unlink()
        self.assertFalse(
            self.env['account.edi.api.download'].browse(rid).exists())
