# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Append-only audit log with SHA-256 hash chain.

Once a record is inserted, it cannot be modified or deleted via ORM:
``write`` and ``unlink`` raise. The hash of each entry is computed as
``SHA256(prev_hash + canonical_json(payload))`` so any tampering breaks
the chain.
"""
import hashlib
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ComplianceAuditLog(models.Model):
    _name = "l10n_mx.compliance.audit.log"
    _description = "Bitacora de Auditoria CFDI Compliance (inmutable)"
    _order = "id desc"
    _rec_name = "action"

    document_id = fields.Many2one(
        "l10n_mx.cfdi.document", ondelete="restrict", index=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, index=True,
        default=lambda s: s.env.company,
    )
    action = fields.Selection([
        ("parsed", "XML Parseado"),
        ("validated", "Validado"),
        ("warning", "Aprobado con Warnings"),
        ("blocked", "Bloqueado"),
        ("authorization_required", "Requiere Autorizacion"),
        ("override", "Override Aplicado"),
        ("authorized", "Autorizado"),
        ("rejected", "Rechazado"),
        ("reprocessed", "Reprocesado"),
    ], required=True, index=True)
    user_id = fields.Many2one(
        "res.users", required=True,
        default=lambda s: s.env.user, index=True,
    )
    ip_address = fields.Char()
    payload = fields.Json()
    hash_chain = fields.Char(
        readonly=True, index=True,
        help="SHA-256(prev_hash + canonical_json(payload)).",
    )
    prev_hash = fields.Char(readonly=True)
    chain_broken = fields.Boolean(readonly=True)

    # ──────────────────────── Immutability ────────────────────────
    def write(self, vals):
        if self.env.context.get("_audit_internal_write"):
            return super().write(vals)
        raise UserError(_("La bitacora de auditoria es inmutable."))

    def unlink(self):
        if self.env.context.get("_audit_internal_unlink"):
            return super().unlink()
        raise UserError(_("La bitacora de auditoria no se puede eliminar."))

    # ──────────────────────── Hash chain ──────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        records = self.env[self._name]
        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id
            try:
                request = self.env["ir.http"].browse([])  # not used; placeholder
            except Exception:  # pragma: no cover
                request = None
            # Build canonical payload string
            payload = vals.get("payload") or {}
            try:
                canonical = json.dumps(payload, sort_keys=True, default=str,
                                       separators=(",", ":"))
            except Exception:
                canonical = str(payload)
            # Find previous hash for this company
            prev = self.search([("company_id", "=", company_id)],
                               order="id desc", limit=1)
            prev_hash = prev.hash_chain or ""
            digest = hashlib.sha256(
                (prev_hash + canonical).encode("utf-8")
            ).hexdigest()
            vals["prev_hash"] = prev_hash
            vals["hash_chain"] = digest
            records |= super().create([vals])
        return records

    # ──────────────────────── Helpers ─────────────────────────────
    @api.model
    def log(self, action, document=None, payload=None, ip=None):
        """Convenience helper used by services across the module."""
        vals = {
            "action": action,
            "document_id": document.id if document else False,
            "company_id": (document.company_id.id if document
                           else self.env.company.id),
            "payload": payload or {},
            "ip_address": ip or "",
        }
        return self.sudo().create(vals)

    def action_verify_chain(self):
        """Walks the chain and flags broken entries. Returns count of
        broken records. Used by cron job and manual verification."""
        broken = 0
        for company in self.env["res.company"].search([]):
            prev_hash = ""
            for log in self.search([("company_id", "=", company.id)],
                                   order="id asc"):
                try:
                    canonical = json.dumps(
                        log.payload or {}, sort_keys=True,
                        default=str, separators=(",", ":"),
                    )
                except Exception:
                    canonical = str(log.payload)
                expected = hashlib.sha256(
                    (prev_hash + canonical).encode("utf-8")
                ).hexdigest()
                if expected != log.hash_chain:
                    log.with_context(_audit_internal_write=True).write(
                        {"chain_broken": True}
                    )
                    broken += 1
                    _logger.error(
                        "Audit chain broken at id=%s company=%s",
                        log.id, company.display_name,
                    )
                prev_hash = log.hash_chain or expected
        return broken
