# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Resolves which compliance profile applies to a given context."""
from __future__ import annotations


class ProfileResolver:

    def resolve(self, env, company, *, move=None, purchase=None, partner=None):
        Profile = env["l10n_mx.compliance.profile"].sudo()
        # 1) Profile attached explicitly to the move
        if move and getattr(move, "compliance_profile_id", False):
            return move.compliance_profile_id
        # 2) Profile via partner override
        if partner and getattr(partner, "compliance_profile_id", False):
            if partner.compliance_profile_id.company_id == company:
                return partner.compliance_profile_id
        # 3) Default profile of the company
        if company.default_compliance_profile_id:
            return company.default_compliance_profile_id
        # 4) Any active default for that company
        return Profile.search([
            ("company_id", "=", company.id),
            ("is_default", "=", True),
            ("active", "=", True),
        ], limit=1) or Profile.search([
            ("company_id", "=", company.id),
            ("active", "=", True),
        ], limit=1)
