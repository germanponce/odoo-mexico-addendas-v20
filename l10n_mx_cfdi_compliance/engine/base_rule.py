# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Base classes and registry for the CFDI compliance rule engine.

This module defines the contract every rule must follow and a global
registry populated at import time. The registry is then synchronised
to the ``l10n_mx.compliance.rule`` model so users can configure each
rule from the UI per-company.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import CfdiValidationContext

_logger = logging.getLogger(__name__)


SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"
SEVERITY_AUTHORIZATION = "authorization"

CATEGORY_SAT = "sat"
CATEGORY_ACCOUNTING = "accounting"
CATEGORY_DEDUCTIBILITY = "deductibility"
CATEGORY_SPECIFIC = "specific"
CATEGORY_ANTIFRAUD = "antifraud"
CATEGORY_COORDINADOS = "coordinados"
CATEGORY_NOMINA = "nomina"


@dataclass(frozen=True)
class RuleResult:
    """Immutable result returned by a rule's ``execute()`` method."""
    passed: bool
    message: str = ""
    details: Optional[dict] = None
    score_impact: int = 0
    extra_state: Optional[dict] = field(default=None)


class BaseCfdiRule(ABC):
    """Abstract base for every compliance rule.

    Subclasses must declare class-level attributes ``code``, ``name``,
    ``category`` and override :meth:`execute`. They may optionally
    override :meth:`applies` to short-circuit themselves based on the
    current context (e.g. only run on ``tipo_comprobante='I'``).
    """

    code: str = ""
    name: str = ""
    description: str = ""
    category: str = CATEGORY_SAT
    requires_internet: bool = False
    sat_reference: str = ""
    default_severity: str = SEVERITY_WARNING
    default_weight: int = 10
    # If False, the rule is assigned DISABLED to profiles (opt-in). Util para
    # cruces que solo aplican a clientes que procesan el flujo en Odoo (ej.
    # nomina contable cuando el XML viene de descarga SAT sin nomina en Odoo:
    # las validaciones internas del XML si corren, el cruce contable no).
    default_enabled: bool = True
    # If True, the engine aborts the pipeline when this rule fails.
    short_circuit_on_fail: bool = False

    @abstractmethod
    def execute(self, ctx: "CfdiValidationContext") -> RuleResult:
        """Run the rule. MUST be deterministic and side-effect free
        beyond optionally writing to ``ctx.cfdi_record`` for marker
        fields (e.g. setting ``is_coordinado_cross``).
        """

    def applies(self, ctx: "CfdiValidationContext") -> bool:  # noqa: D401
        """Return True if the rule should run for this context."""
        return True


class CfdiRuleRegistry:
    """Process-wide registry of available rules, keyed by ``code``."""

    _rules: Dict[str, Type[BaseCfdiRule]] = {}

    @classmethod
    def register(cls, rule_cls: Type[BaseCfdiRule]) -> Type[BaseCfdiRule]:
        if not rule_cls.code:
            raise ValueError(f"Rule {rule_cls.__name__} has no code defined")
        if rule_cls.code in cls._rules and cls._rules[rule_cls.code] is not rule_cls:
            _logger.warning(
                "Replacing existing rule %s (%s -> %s)",
                rule_cls.code, cls._rules[rule_cls.code].__name__, rule_cls.__name__,
            )
        cls._rules[rule_cls.code] = rule_cls
        return rule_cls

    @classmethod
    def get(cls, code: str) -> Optional[Type[BaseCfdiRule]]:
        return cls._rules.get(code)

    @classmethod
    def all(cls) -> List[Type[BaseCfdiRule]]:
        return list(cls._rules.values())

    @classmethod
    def clear(cls) -> None:  # pragma: no cover (only for tests)
        cls._rules.clear()


def cfdi_rule(cls):
    """Decorator used by rule classes to register themselves."""
    return CfdiRuleRegistry.register(cls)
