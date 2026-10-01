# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Resolves whether the receptor RFC is acceptable for the current company.

Handles three cases:

* **direct**: rfc_receptor == company.vat
* **coordinado**: rfc_receptor matches a vigent
  :class:`l10n_mx.cfdi.coordinado.relation` for this company
* **mismatch**: neither of the above
"""
from __future__ import annotations

from typing import Dict, Any


class CfdiReceptorResolver:

    def resolve(self, env, company, rfc_receptor: str, fecha) -> Dict[str, Any]:
        rfc_receptor = (rfc_receptor or "").upper().strip()
        company_vat = (company.vat or "").upper().strip()

        if company_vat and company_vat == rfc_receptor:
            return {"valid": True, "mode": "direct",
                    "receptor_company": company, "relation": None}

        date = fecha.date() if hasattr(fecha, "date") else fecha
        domain = [
            ("controladora_company_id", "=", company.id),
            ("coordinada_vat", "=", rfc_receptor),
            ("accept_cfdi_to_coordinada", "=", True),
            ("active", "=", True),
        ]
        if date:
            domain += [
                ("valid_from", "<=", date),
                "|", ("valid_to", "=", False), ("valid_to", ">=", date),
            ]
        rel = env["l10n_mx.cfdi.coordinado.relation"].sudo().search(domain, limit=1)
        if rel:
            return {
                "valid": True, "mode": "coordinado",
                "receptor_company": rel.coordinada_company_id or company,
                "relation": rel,
            }
        return {"valid": False, "mode": "mismatch",
                "receptor_company": False, "relation": None}
