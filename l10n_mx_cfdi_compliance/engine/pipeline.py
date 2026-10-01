# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Pipeline executor: runs all enabled rules of a profile against a CFDI."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Any

from .base_rule import (
    CfdiRuleRegistry, RuleResult,
    SEVERITY_ERROR, SEVERITY_AUTHORIZATION, SEVERITY_WARNING, SEVERITY_INFO,
)
from .context import CfdiValidationContext

_logger = logging.getLogger(__name__)


@dataclass
class PipelineOutcome:
    results: List[Tuple[Any, RuleResult, int]] = field(default_factory=list)
    score: int = 100
    has_blocker: bool = False
    needs_authorization: bool = False
    short_circuited: bool = False
    elapsed_ms: int = 0

    @property
    def state(self) -> str:
        if self.has_blocker:
            return "blocked"
        if self.needs_authorization:
            return "authorization_required"
        if any(not r.passed and cfg.severity == SEVERITY_WARNING
               for cfg, r, _ in self.results):
            return "warning"
        return "passed"


class CfdiCompliancePipeline:
    """Runs the active rules of a profile, computes score and verdict."""

    def __init__(self, env, profile, cfdi_record, cfdi_dto):
        self.env = env
        self.profile = profile
        self.cfdi_record = cfdi_record
        self.cfdi_dto = cfdi_dto
        self.ctx = CfdiValidationContext(
            env=env, company=profile.company_id,
            cfdi_record=cfdi_record, cfdi=cfdi_dto, profile=profile,
        )

    def run(self) -> PipelineOutcome:
        outcome = PipelineOutcome()
        t_start = time.perf_counter()
        # Order: SAT → nomina → coordinados → accounting → deductibility → specific → antifraud
        order = ["sat", "nomina", "coordinados", "accounting", "deductibility",
                 "specific", "antifraud"]
        configs = self.profile.rule_config_ids.filtered(lambda c: c.enabled)
        configs = configs.sorted(key=lambda c: (
            order.index(c.rule_id.category) if c.rule_id.category in order else 99,
            c.sequence,
        ))

        score = 100.0
        for cfg in configs:
            rule_cls = CfdiRuleRegistry.get(cfg.rule_id.code)
            if rule_cls is None:
                _logger.warning("Rule code %s configured but not found in registry",
                                cfg.rule_id.code)
                continue
            rule = rule_cls()
            try:
                if not rule.applies(self.ctx):
                    continue
            except Exception:  # pragma: no cover - defensive
                _logger.exception("applies() failed for %s", cfg.rule_id.code)
                continue

            t0 = time.perf_counter()
            try:
                res = rule.execute(self.ctx)
            except Exception as exc:
                _logger.exception("Rule %s raised", cfg.rule_id.code)
                res = RuleResult(
                    passed=False,
                    message=f"Error técnico al ejecutar regla: {exc}",
                    details={"exception": str(exc)},
                    score_impact=-5,
                )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            outcome.results.append((cfg, res, elapsed_ms))

            if not res.passed:
                weight_factor = (cfg.weight or 10) / 10.0
                score += res.score_impact * weight_factor
                if cfg.severity == SEVERITY_ERROR:
                    outcome.has_blocker = True
                    if rule.short_circuit_on_fail or (
                        cfg.params or {}
                    ).get("short_circuit"):
                        outcome.short_circuited = True
                        break
                elif cfg.severity == SEVERITY_AUTHORIZATION:
                    outcome.needs_authorization = True
            else:
                score += max(0, res.score_impact) * 0.1  # small bonus

        outcome.score = max(0, min(100, int(round(score))))
        outcome.elapsed_ms = int((time.perf_counter() - t_start) * 1000)
        return outcome
