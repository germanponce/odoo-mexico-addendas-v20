# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Immutable validation context passed across rules in the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CfdiValidationContext:
    """Bag of references for a single CFDI validation run.

    The :class:`~..models.cfdi_document.CfdiDocument` parsed payload
    (``cfdi``) is **read only**. Rules may write marker fields on
    ``cfdi_record`` (the ORM record) but should never mutate ``cfdi``.
    """

    env: Any                   # odoo.api.Environment
    company: Any               # res.company recordset (single)
    cfdi_record: Any           # l10n_mx.cfdi.document recordset (single)
    cfdi: Any                  # parser.CfdiDocument DTO (frozen)
    profile: Any               # l10n_mx.compliance.profile recordset (single)
    # Resolver outputs cached for downstream rules
    receptor_resolution: Optional[Dict[str, Any]] = None
    # Rule-private working memory (not persisted)
    scratchpad: Dict[str, Any] = field(default_factory=dict)
