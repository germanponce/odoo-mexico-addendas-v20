# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Upgrade .49 -> .50: Nomina Etapa 2 (cruces B-E vs RRHH) + dashboard ligero.

Sincroniza el catalogo de reglas con el registry para dar de alta las nuevas
reglas de nomina B (empleado NOM_020-024), C (contrato NOM_030-034),
D (recibo NOM_040-045) y E (lote NOM_050-052). Todas son OPT-IN
(default_enabled=False): se asignan DESHABILITADAS a los profiles y solo aplican
en clientes que calculan la nomina en Odoo (soft-dependency vs hr.*). Idempotente.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["l10n_mx.compliance.rule"]._sync_from_registry()
    nuevas = env["l10n_mx.compliance.rule"].search_count([
        ("category", "=", "nomina"),
        ("code", "in", [
            "NOM_020_EMPLEADO_EXISTE", "NOM_030_CONTRATO_VIGENTE",
            "NOM_040_RECIBO_EXISTE", "NOM_050_LOTE_PERTENECE",
        ]),
    ])
    _logger.info(
        "cfdi_compliance .50: Nomina Etapa 2 - catalogo sincronizado "
        "(reglas ancla B-E presentes: %s/4).", nuevas)
