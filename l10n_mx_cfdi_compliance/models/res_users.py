# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Permisos de visibilidad de CFDI por usuario para el modulo de Compliance.

Mismo patron UX que l10n_mx_xml_massive_download (campos booleanos en res.users +
pestania en la ficha de usuario) pero con campos PROPIOS e INDEPENDIENTES: estos
controlan la visibilidad dentro del modulo de Compliance (l10n_mx.cfdi.document),
no en la descarga SAT. Reemplazan a los antiguos grupos sueltos
group_cfdi_type_* / group_cfdi_dir_* (mejor UX: un acceso + una pestania, no
checkboxes mezclados con los grupos nativos).

La regla de registro (ir_rule.xml) usa estos campos para filtrar por TIPO de
comprobante y por DIRECCION. Manager y Auditor ven TODO (bypass).

Defaults: todos los tipos visibles EXCEPTO Nomina (informacion sensible: sueldos,
percepciones, deducciones), y ambas direcciones visibles. Asi por defecto no se
bloquea de mas y se protege lo sensible; se restringe por usuario donde aplique.
"""
from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = "res.users"

    # ── Visibilidad por TIPO de comprobante ──
    can_see_compliance_ingreso = fields.Boolean(
        string="Compliance: ver Ingreso (I)", default=True,
        help="Ver CFDIs tipo Ingreso (facturas) en el modulo de Compliance.")
    can_see_compliance_egreso = fields.Boolean(
        string="Compliance: ver Egreso (E)", default=True,
        help="Ver CFDIs tipo Egreso (notas de credito).")
    can_see_compliance_pago = fields.Boolean(
        string="Compliance: ver Pago (P)", default=True,
        help="Ver CFDIs tipo Pago (complementos de pago / REP).")
    can_see_compliance_nomina = fields.Boolean(
        string="Compliance: ver Nomina (N)", default=False,
        help="Ver CFDIs tipo Nomina. Informacion sensible (sueldos, percepciones, "
             "deducciones). Desactivado por defecto.")
    can_see_compliance_traslado = fields.Boolean(
        string="Compliance: ver Traslado (T)", default=True,
        help="Ver CFDIs tipo Traslado (carta porte).")
    # ── Visibilidad por DIRECCION ──
    can_see_compliance_emitido = fields.Boolean(
        string="Compliance: ver Emitidos", default=True,
        help="Ver CFDIs emitidos por la empresa (ventas a clientes).")
    can_see_compliance_recibido = fields.Boolean(
        string="Compliance: ver Recibidos", default=True,
        help="Ver CFDIs recibidos de proveedores (compras).")

    has_cfdi_compliance_access = fields.Boolean(
        string="Tiene acceso CFDI Compliance",
        compute="_compute_has_cfdi_compliance_access",
        help="True si el usuario pertenece al grupo CFDI Compliance / User "
             "(o uno superior que lo implique).")

    @api.depends("group_ids")
    def _compute_has_cfdi_compliance_access(self):
        grp = self.env.ref(
            "l10n_mx_cfdi_compliance.group_cfdi_compliance_user",
            raise_if_not_found=False)
        for user in self:
            user.has_cfdi_compliance_access = bool(grp) and (grp in user.group_ids)

    def get_allowed_compliance_types(self):
        """Tipos de comprobante (I/E/P/N/T) que self puede ver."""
        self.ensure_one()
        pairs = [
            ("I", self.can_see_compliance_ingreso),
            ("E", self.can_see_compliance_egreso),
            ("P", self.can_see_compliance_pago),
            ("N", self.can_see_compliance_nomina),
            ("T", self.can_see_compliance_traslado),
        ]
        return [t for t, v in pairs if v]

    def get_allowed_compliance_directions(self):
        """Direcciones (emitido/recibido) que self puede ver."""
        self.ensure_one()
        pairs = [
            ("emitido", self.can_see_compliance_emitido),
            ("recibido", self.can_see_compliance_recibido),
        ]
        return [d for d, v in pairs if v]
