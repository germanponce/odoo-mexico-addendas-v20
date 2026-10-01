# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Upgrade .46 -> .47: categoria NOMINA (Etapa 1) - reglas A (internas) + F (contable).

post_init_hook (que llama _sync_from_registry) SOLO corre en install, no en
upgrade. Esta migracion sincroniza el catalogo desde el registry para que las
nuevas reglas NOM_* queden en el catalogo y asignadas (enabled) a todos los
profiles existentes con sus severidades por defecto. Idempotente.

El parser de Nomina 1.2 y la categoria 'nomina' se cargan con el codigo/modelo.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["l10n_mx.compliance.rule"]._sync_from_registry()
    _logger.info(
        "cfdi_compliance .47: catalogo sincronizado - categoria NOMINA Etapa 1 "
        "(reglas NOM_001..016 internas + NOM_060..064 contable) desplegada."
    )
