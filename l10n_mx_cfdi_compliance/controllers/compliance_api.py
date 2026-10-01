# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""HTTP / JSON-RPC endpoints for CFDI Compliance.

Mantiene un endpoint minimo y autenticado para integraciones externas
(p.ej. portales de proveedores subiendo XMLs). No expone endpoints
publicos sin autenticacion.

(c) ANFEPI - Roberto Requejo Jimenez - https://www.anfepi.com
"""
import base64
import logging

from odoo import http, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class CfdiComplianceController(http.Controller):

    @http.route(
        "/l10n_mx_cfdi_compliance/upload",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def upload_cfdi(self, filename=None, content_b64=None, partner_id=None):
        """Recibe un XML CFDI codificado en base64 y dispara el pipeline.

        :param filename: nombre original del archivo
        :param content_b64: contenido base64 del XML
        :param partner_id: opcional, asociar al partner
        :return: dict con resultado del pipeline
        """
        if not filename or not content_b64:
            raise UserError(_("filename y content_b64 son requeridos."))
        if not request.env.user.has_group(
            "l10n_mx_cfdi_compliance.group_cfdi_compliance_user"
        ):
            raise AccessError(_("Usuario sin permisos de CFDI Compliance."))
        try:
            raw = base64.b64decode(content_b64, validate=True)
        except Exception as exc:
            raise UserError(_("Base64 invalido: %s") % exc) from exc
        attachment = request.env["ir.attachment"].sudo().create({
            "name": filename,
            "datas": base64.b64encode(raw),
            "mimetype": "application/xml",
            "res_model": "l10n_mx.cfdi.document",
            "res_id": 0,
        })
        # The ir.attachment.create override fires the pipeline automatically
        # and sets attachment.cfdi_document_id to the resulting document
        # (handles both new and duplicate-UUID cases).
        cfdi = attachment.sudo().cfdi_document_id
        if not cfdi:
            return {"ok": False, "error": "No se pudo crear el CFDI (XML invalido)."}
        return {
            "ok": True,
            "cfdi_id": cfdi.id,
            "uuid": cfdi.uuid,
            "compliance_state": cfdi.compliance_state,
            "compliance_score": cfdi.compliance_score,
        }
