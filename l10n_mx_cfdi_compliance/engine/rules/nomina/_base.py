# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Base y utilidades comunes para las reglas de la categoria Nomina.

Las severidades del spec (Critical / High / Medium) se MAPEAN a las del motor
existente (no se duplica el sistema de severidades):

    Critical -> error          (bloquea)
    High     -> authorization  (requiere autorizacion)
    Medium   -> warning        (advierte)
    info     -> info

Todas las reglas de nomina heredan de :class:`BaseNominaRule`, que las acota a
CFDIs con Complemento de Nomina 1.2 parseado (``ctx.cfdi.nomina``).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ...base_rule import (
    BaseCfdiRule, RuleResult, CATEGORY_NOMINA,
    SEVERITY_ERROR, SEVERITY_AUTHORIZATION, SEVERITY_WARNING, SEVERITY_INFO,
)

# Alias semanticos del spec -> severidad cableada en el motor.
SEV_CRITICAL = SEVERITY_ERROR
SEV_HIGH = SEVERITY_AUTHORIZATION
SEV_MEDIUM = SEVERITY_WARNING
SEV_INFO = SEVERITY_INFO

# Re-export para que los modulos de reglas importen todo desde aqui.
__all__ = [
    "BaseNominaRule", "RuleResult",
    "SEV_CRITICAL", "SEV_HIGH", "SEV_MEDIUM", "SEV_INFO",
]


def _ser(value):
    """Serializa valores no-JSON (Decimal, date) a str para ``details``."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


class BaseNominaRule(BaseCfdiRule):
    """Base de todas las reglas de Nomina.

    Solo se ejecutan cuando el CFDI trae Complemento de Nomina 1.2 parseado.
    Provee helpers de evidencia uniforme y lectura de parametros/tolerancia
    desde el ``rule_config`` del profile.
    """
    category = CATEGORY_NOMINA

    def applies(self, ctx) -> bool:
        return bool(getattr(ctx.cfdi, "nomina", None))

    # ---------------- helpers ----------------
    @staticmethod
    def evidence(valor_xml=None, valor_odoo=None, diferencia=None, **extra):
        """Construye el dict de evidencia uniforme para ``RuleResult.details``.

        Campos canonicos: ``valor_xml``, ``valor_odoo``, ``diferencia``.
        ``extra`` permite agregar contexto adicional (ej. uuid, periodo).
        """
        ev = {}
        if valor_xml is not None:
            ev["valor_xml"] = _ser(valor_xml)
        if valor_odoo is not None:
            ev["valor_odoo"] = _ser(valor_odoo)
        if diferencia is not None:
            ev["diferencia"] = _ser(diferencia)
        for k, v in extra.items():
            ev[k] = _ser(v)
        return ev

    def params(self, ctx) -> dict:
        """Parametros configurados para ESTA regla en el profile (o {})."""
        return next(
            (c.params for c in ctx.profile.rule_config_ids
             if c.rule_id.code == self.code), None,
        ) or {}

    def tolerance(self, ctx, default: str = "0.01") -> Decimal:
        """Tolerancia en MXN configurable (param ``tolerancia_mxn``)."""
        return Decimal(str(self.params(ctx).get("tolerancia_mxn", default)))
