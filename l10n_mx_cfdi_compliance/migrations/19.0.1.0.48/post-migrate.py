# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Upgrade .47 -> .48: UX de permisos estilo massive (campos en res.users).

Elimina los antiguos grupos sueltos de visibilidad por tipo/direccion
(group_cfdi_type_* / group_cfdi_dir_*). La visibilidad ahora se controla con
campos por usuario (can_see_compliance_*) en la pestania 'Permisos CFDI
Compliance' de la ficha de usuario. Los campos nuevos toman su default en
columnas (nomina=False, resto True) automaticamente al agregar el modelo.
Idempotente.
"""
import logging

_logger = logging.getLogger(__name__)

_OLD_GROUP_XMLIDS = [
    "group_cfdi_type_ingreso", "group_cfdi_type_egreso", "group_cfdi_type_pago",
    "group_cfdi_type_nomina", "group_cfdi_type_traslado",
    "group_cfdi_dir_emitido", "group_cfdi_dir_recibido",
]


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    removed = 0
    for xid in _OLD_GROUP_XMLIDS:
        grp = env.ref("l10n_mx_cfdi_compliance." + xid, raise_if_not_found=False)
        imd = env["ir.model.data"].search([
            ("module", "=", "l10n_mx_cfdi_compliance"), ("name", "=", xid)])
        if grp:
            grp.unlink()
            removed += 1
        if imd:
            imd.unlink()
    _logger.info(
        "cfdi_compliance .48: UX permisos estilo massive - %s grupos viejos de "
        "visibilidad eliminados (ahora son campos res.users can_see_compliance_*).",
        removed)
