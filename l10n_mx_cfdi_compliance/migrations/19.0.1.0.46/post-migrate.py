# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Upgrade .45 -> .46: feature visibilidad por tipo+direccion + reglas dir-aware.

post_init_hook (que llama _sync_from_registry) SOLO corre en install, no en
upgrade. Esta migracion sincroniza el catalogo de reglas desde el registry para
que la nueva regla DED_041 (Orden de Venta) quede en el catalogo y asignada a
todos los profiles existentes. Idempotente.

El campo computed+stored `direccion` lo recomputa Odoo automaticamente al cargar
el modulo (init de campo nuevo). Grupos y reglas ir.rule se cargan via XML data.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["l10n_mx.compliance.rule"]._sync_from_registry()
    _logger.info(
        "cfdi_compliance .46: catalogo sincronizado (DED_041 Orden de Venta) "
        "+ feature dir-aware desplegada."
    )
