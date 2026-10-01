# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
import base64
import logging
from dataclasses import asdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from ..engine.parser.cfdi_parser import parse_cfdi, CfdiParseError
from ..engine.pipeline import CfdiCompliancePipeline
from ..engine.resolvers.profile_resolver import ProfileResolver

_logger = logging.getLogger(__name__)


COMPLIANCE_STATES = [
    ("pending", "Pendiente"),
    ("validating", "Validando"),
    ("passed", "Aprobado"),
    ("warning", "Aprobado con Warnings"),
    ("blocked", "Bloqueado"),
    ("authorization_required", "Requiere Autorizacion"),
    ("authorized", "Autorizado con Override"),
    ("rejected", "Rechazado"),
    ("error", "Error Tecnico"),
]


class CfdiDocument(models.Model):
    _name = "l10n_mx.cfdi.document"
    _description = "Documento CFDI (representacion normalizada)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True
    _order = "fecha desc, id desc"
    _rec_name = "display_name"

    # Identification
    uuid = fields.Char(required=True, index=True, tracking=True)
    serie = fields.Char()
    folio = fields.Char()
    fecha = fields.Datetime(index=True)
    fecha_timbrado = fields.Datetime()
    company_id = fields.Many2one(
        "res.company", required=True, index=True,
        default=lambda s: s.env.company,
    )
    currency_id = fields.Many2one("res.currency")

    # Attachment
    attachment_id = fields.Many2one(
        "ir.attachment", required=True, ondelete="restrict", copy=False,
    )
    xml_hash = fields.Char(index=True, copy=False)

    # Emisor / Receptor
    rfc_emisor = fields.Char(index=True)
    nombre_emisor = fields.Char()
    regimen_fiscal_emisor = fields.Char()
    rfc_receptor = fields.Char(index=True)
    nombre_receptor = fields.Char()
    regimen_fiscal_receptor = fields.Char()
    domicilio_fiscal_receptor = fields.Char()
    uso_cfdi = fields.Char()

    # Money
    subtotal = fields.Monetary()
    descuento = fields.Monetary()
    total = fields.Monetary(index=True)
    moneda = fields.Char()
    tipo_cambio = fields.Float(digits=(12, 6))
    total_impuestos_trasladados = fields.Monetary()
    total_impuestos_retenidos = fields.Monetary()

    # Pago
    forma_pago = fields.Char()
    metodo_pago = fields.Selection([("PUE", "PUE"), ("PPD", "PPD")])
    tipo_comprobante = fields.Selection([
        ("I", "Ingreso"), ("E", "Egreso"), ("T", "Traslado"),
        ("N", "Nomina"), ("P", "Pago"),
    ])
    # Direccion del CFDI relativo a la compania: emitido si la empresa es el
    # emisor, recibido si es el receptor. Stored+index para usarse como filtro
    # en ir.rule (visibilidad por direccion) y en applies() de reglas
    # (ej: OC relacionada solo aplica a recibido). Compute barato (string cmp).
    direccion = fields.Selection(
        [("emitido", "Emitido"), ("recibido", "Recibido")],
        compute="_compute_direccion", store=True, index=True,
    )
    exportacion = fields.Char()

    # Compliance state
    compliance_state = fields.Selection(
        COMPLIANCE_STATES, default="pending", index=True, tracking=True,
        copy=False,
    )
    compliance_score = fields.Integer(tracking=True, copy=False)
    profile_id = fields.Many2one("l10n_mx.compliance.profile", copy=False)
    result_ids = fields.One2many("l10n_mx.compliance.result", "document_id")
    result_count = fields.Integer(compute="_compute_result_count")
    last_pipeline_ms = fields.Integer(copy=False)
    last_validation_date = fields.Datetime(copy=False, tracking=True)

    # Relations
    related_move_id = fields.Many2one("account.move", index=True)
    related_purchase_id = fields.Many2one("purchase.order", index=True)

    # Coordinados
    receptor_company_id = fields.Many2one("res.company")
    coordinado_relation_id = fields.Many2one("l10n_mx.cfdi.coordinado.relation")
    is_coordinado_cross = fields.Boolean(index=True)

    # UI
    display_name = fields.Char(compute="_compute_display_name", store=True)
    state_color = fields.Integer(compute="_compute_state_color")

    _uuid_company_uniq = models.Constraint(
        "UNIQUE(uuid, company_id)",
        "El UUID ya existe en esta compania.",
    )

    # ──────────────── Computed ────────────────
    @api.depends("uuid", "rfc_emisor", "total")
    def _compute_display_name(self):
        for r in self:
            r.display_name = (
                f"{r.rfc_emisor or '?'} - {r.uuid[:8] if r.uuid else '?'} "
                f"- ${r.total or 0:,.2f}"
            )

    @api.depends("compliance_state")
    def _compute_state_color(self):
        mapping = {
            "passed": 10, "warning": 3, "authorized": 4,
            "blocked": 1, "authorization_required": 5,
            "rejected": 1, "error": 1,
            "validating": 7, "pending": 0,
        }
        for r in self:
            r.state_color = mapping.get(r.compliance_state, 0)

    @api.depends("result_ids")
    def _compute_result_count(self):
        for r in self:
            r.result_count = len(r.result_ids)

    @api.depends("rfc_emisor", "rfc_receptor", "company_id.vat")
    def _compute_direccion(self):
        for r in self:
            rfc = (r.company_id.vat or "").strip().upper()
            emisor = (r.rfc_emisor or "").strip().upper()
            receptor = (r.rfc_receptor or "").strip().upper()
            if rfc and emisor == rfc:
                r.direccion = "emitido"
            elif rfc and receptor == rfc:
                r.direccion = "recibido"
            else:
                r.direccion = False

    # ──────────────── Factory ────────────────
    @api.model
    def _create_from_attachment(self, attachment, company=None, *,
                                related_move=None, related_purchase=None):
        """Create or fetch a CFDI document for an attachment.

        Returns the document recordset (single). If a document for the same
        UUID + company already exists, returns it without re-parsing.
        """
        if not attachment:
            raise UserError(_("Adjunto vacio"))
        company = company or attachment.company_id or self.env.company

        try:
            xml_bytes = base64.b64decode(attachment.datas)
        except Exception as e:
            raise UserError(_("No se pudo decodificar el adjunto: %s") % e) from e

        try:
            cfdi = parse_cfdi(xml_bytes)
        except CfdiParseError as e:
            self.env["l10n_mx.compliance.audit.log"].sudo().log(
                "parsed", payload={"error": str(e),
                                   "attachment_id": attachment.id},
            )
            raise UserError(_("XML CFDI invalido: %s") % e) from e

        # Idempotency: same uuid in same company → return existing
        existing = self.sudo().search([
            ("uuid", "=", cfdi.uuid),
            ("company_id", "=", company.id),
        ], limit=1)
        if existing:
            if not existing.attachment_id:
                existing.attachment_id = attachment
            if related_move and not existing.related_move_id:
                existing.related_move_id = related_move
            if related_purchase and not existing.related_purchase_id:
                existing.related_purchase_id = related_purchase
            return existing

        currency = self.env["res.currency"].search(
            [("name", "=", cfdi.moneda or "MXN")], limit=1)
        vals = {
            "uuid": cfdi.uuid,
            "company_id": company.id,
            "attachment_id": attachment.id,
            "xml_hash": cfdi.xml_hash,
            "serie": cfdi.serie,
            "folio": cfdi.folio,
            "fecha": cfdi.fecha,
            "fecha_timbrado": cfdi.fecha_timbrado,
            "rfc_emisor": cfdi.rfc_emisor,
            "nombre_emisor": cfdi.nombre_emisor,
            "regimen_fiscal_emisor": cfdi.regimen_fiscal_emisor,
            "rfc_receptor": cfdi.rfc_receptor,
            "nombre_receptor": cfdi.nombre_receptor,
            "regimen_fiscal_receptor": cfdi.regimen_fiscal_receptor,
            "domicilio_fiscal_receptor": cfdi.domicilio_fiscal_receptor,
            "uso_cfdi": cfdi.uso_cfdi,
            "subtotal": float(cfdi.subtotal),
            "descuento": float(cfdi.descuento),
            "total": float(cfdi.total),
            "moneda": cfdi.moneda,
            "tipo_cambio": float(cfdi.tipo_cambio),
            "total_impuestos_trasladados": float(cfdi.total_impuestos_trasladados),
            "total_impuestos_retenidos": float(cfdi.total_impuestos_retenidos),
            "forma_pago": cfdi.forma_pago,
            "metodo_pago": cfdi.metodo_pago or False,
            "tipo_comprobante": cfdi.tipo_comprobante or False,
            "exportacion": cfdi.exportacion,
            "currency_id": currency.id,
            "related_move_id": related_move.id if related_move else False,
            "related_purchase_id": related_purchase.id if related_purchase else False,
        }
        doc = self.sudo().create(vals)
        attachment.sudo().write({"cfdi_document_id": doc.id})
        self.env["l10n_mx.compliance.audit.log"].sudo().log(
            "parsed", document=doc,
            payload={"uuid": cfdi.uuid, "rfc_emisor": cfdi.rfc_emisor,
                     "total": str(cfdi.total)},
        )
        return doc

    # ──────────────── Pipeline ────────────────
    def action_run_compliance(self):
        for doc in self:
            doc._run_compliance_pipeline()
        return True

    def _run_compliance_pipeline(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_("Documento sin adjunto XML."))
        # Resolve profile
        resolver = ProfileResolver()
        profile = resolver.resolve(
            self.env, self.company_id,
            move=self.related_move_id, purchase=self.related_purchase_id,
        )
        if not profile:
            self.write({
                "compliance_state": "error",
                "compliance_score": 0,
            })
            self.env["l10n_mx.compliance.audit.log"].sudo().log(
                "validated", document=self,
                payload={"error": "Sin perfil de compliance configurado"},
            )
            return False
        # Parse XML again (immutability) - cheap, parser is fast
        xml_bytes = base64.b64decode(self.attachment_id.datas)
        try:
            cfdi_dto = parse_cfdi(xml_bytes)
        except CfdiParseError as e:
            self.write({"compliance_state": "error"})
            self.env["l10n_mx.compliance.audit.log"].sudo().log(
                "validated", document=self,
                payload={"error": f"parse: {e}"},
            )
            return False

        self.write({"compliance_state": "validating", "profile_id": profile.id})
        # Wipe previous results to keep history in audit log only
        self.result_ids.sudo().unlink()

        pipeline = CfdiCompliancePipeline(self.env, profile, self, cfdi_dto)
        outcome = pipeline.run()

        Result = self.env["l10n_mx.compliance.result"].sudo()
        for cfg, res, ms in outcome.results:
            sev = cfg.severity
            if profile.transition_mode and sev == "error":
                sev = "warning"
            Result.create({
                "document_id": self.id,
                "rule_id": cfg.rule_id.id,
                "severity": sev,
                "passed": res.passed,
                "message": res.message,
                "details": res.details,
                "execution_ms": ms,
                "score_impact": res.score_impact,
                "sequence": cfg.sequence,
            })

        # Determine state taking transition_mode into account
        state = outcome.state
        if profile.transition_mode and state == "blocked":
            state = "warning"
        if outcome.score < profile.min_score_warning and state == "warning":
            state = "blocked" if not profile.transition_mode else "warning"

        self.write({
            "compliance_state": state,
            "compliance_score": outcome.score,
            "last_pipeline_ms": outcome.elapsed_ms,
            "last_validation_date": fields.Datetime.now(),
        })
        # .52: audit.log.action es una Selection acotada (validated/warning/blocked/
        # authorization_required/authorized/rejected/...). compliance_state incluye
        # valores que NO son acciones de bitacora ('passed','error','validating'). Pasar
        # el state crudo rompia la re-evaluacion de docs que quedan 'passed' (ValueError
        # "Wrong value for ...action: 'passed'"). Mapear a un action valido.
        _audit_action = state if state in (
            "warning", "blocked", "authorization_required", "rejected", "authorized",
        ) else "validated"
        self.env["l10n_mx.compliance.audit.log"].sudo().log(
            _audit_action, document=self,
            payload={
                "state": state,
                "score": outcome.score,
                "elapsed_ms": outcome.elapsed_ms,
                "results": [
                    {"rule": cfg.rule_id.code, "passed": res.passed,
                     "severity": cfg.severity, "msg": res.message}
                    for cfg, res, _ms in outcome.results
                ],
            },
        )
        # Notify via bus for real-time UI refresh
        try:
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id, "l10n_mx_cfdi_compliance/validated",
                {"document_id": self.id, "state": state,
                 "score": outcome.score},
            )
        except Exception:  # pragma: no cover - bus optional
            pass
        # Activity if needs authorization
        if state == "authorization_required":
            self._create_authorization_activity()
        return True

    def _create_authorization_activity(self):
        self.ensure_one()
        try:
            group = self.env.ref(
                "l10n_mx_cfdi_compliance.group_cfdi_compliance_authorizer"
            )
            # v19: res.groups.users fue removido. Se busca en res.users
            # filtrando por group_ids (M2M) y por compania.
            authorizers = self.env["res.users"].sudo().search([
                ("group_ids", "in", group.id),
                ("company_ids", "in", self.company_id.id),
            ])
        except ValueError:
            authorizers = self.env["res.users"]
        user = authorizers[:1] or self.env.user
        self.activity_schedule(
            "mail.mail_activity_data_warning",
            user_id=user.id,
            summary=_("CFDI requiere autorizacion (override)"),
            note=_("Documento %s con score %s necesita override autorizado.")
                  % (self.display_name, self.compliance_score),
        )

    # ──────────────── User actions ────────────────
    def action_view_results(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Resultados de Compliance"),
            "res_model": "l10n_mx.compliance.result",
            "view_mode": "list,form",
            "domain": [("document_id", "=", self.id)],
            "context": {"default_document_id": self.id},
        }

    def action_open_override_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Autorizar Override"),
            "res_model": "l10n_mx.cfdi.override.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_document_id": self.id},
        }

    def action_reject(self):
        self.ensure_one()
        if not self.env.user.has_group(
                "l10n_mx_cfdi_compliance.group_cfdi_compliance_authorizer"):
            raise UserError(_("Solo un autorizador puede rechazar un CFDI."))
        self.compliance_state = "rejected"
        self.env["l10n_mx.compliance.audit.log"].sudo().log(
            "rejected", document=self,
            payload={"by": self.env.user.login},
        )

    def action_reprocess(self):
        for doc in self:
            doc._run_compliance_pipeline()
            self.env["l10n_mx.compliance.audit.log"].sudo().log(
                "reprocessed", document=doc,
                payload={"by": self.env.user.login},
            )

    @api.ondelete(at_uninstall=False)
    def _check_no_delete_when_posted(self):
        for doc in self:
            if doc.related_move_id and doc.related_move_id.state == "posted":
                raise UserError(_(
                    "No se puede eliminar un CFDI vinculado a una factura publicada."
                ))
