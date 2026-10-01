# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Universal CFDI interception point.

Every code path that ends up creating an ``ir.attachment`` (drag&drop,
chatter, OCR, Documents, mass import, email gateway) is captured here.
"""
import base64
import logging

from odoo import api, fields, models

from ..engine.parser.cfdi_parser import is_cfdi_xml

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    cfdi_document_id = fields.Many2one(
        "l10n_mx.cfdi.document", index=True, copy=False,
    )
    # is_cfdi_xml: True si el attachment parece ser un CFDI XML (validado por
    # nombre/mimetype Y contenido).
    #
    # v.68: store=False (compute on-demand). El install/upgrade del modulo
    # NO recomputa este campo sobre el universo de attachments existentes
    # (puede ser cientos de miles en bases productivas). Esto evita:
    #   - Bulk recompute al install/upgrade (toma minutos a horas)
    #   - Cascadas de FileNotFoundError si el filestore tiene archivos
    #     huerfanos (records en BD sin archivo fisico).
    #
    # Trade-off: las busquedas con domain ('is_cfdi_xml', '=', True) NO
    # pueden generarse como SQL filter. Para esto el modulo usa filtro por
    # name/mimetype directamente en SQL y luego .filtered(_is_cfdi_xml_safe).
    # Ver account_move._check_cfdi_compliance_before_post.
    is_cfdi_xml = fields.Boolean(compute="_compute_is_cfdi_xml", store=False)

    def _compute_is_cfdi_xml(self):
        for att in self:
            try:
                att.is_cfdi_xml = att._is_cfdi_xml()
            except Exception:
                att.is_cfdi_xml = False

    def _is_cfdi_xml(self):
        self.ensure_one()
        name = (self.name or "").lower()
        mt = (self.mimetype or "").lower()
        if not (name.endswith(".xml") or "xml" in mt):
            return False
        # Acceder a self.datas puede lanzar FileNotFoundError si el filestore
        # tiene un attachment huerfano (record existe en BD pero el archivo
        # fisico fue eliminado). Tipico en bases productivas migradas/restauradas.
        # No es fatal: solo significa que no podemos determinar si es CFDI XML.
        try:
            datas = self.datas
        except (FileNotFoundError, OSError):
            return False
        if not datas:
            return False
        try:
            raw = base64.b64decode(datas)
        except Exception:
            return False
        try:
            return is_cfdi_xml(raw)
        except Exception:
            return False

    @api.model_create_multi
    def create(self, vals_list):
        attachments = super().create(vals_list)
        # Skip in install / module update transactions to avoid bootstrap noise
        if self.env.context.get("install_mode") or \
                self.env.context.get("_skip_cfdi_compliance"):
            return attachments
        # SOLUCION 2026-05-31 (reemplaza threading.Thread anterior):
        # Encolamos un job persistente por cada XML CFDI detectado. El
        # cron `_cron_process_pending` de `l10n_mx.cfdi.pipeline.job` lo
        # procesara con retry/backoff. Beneficios vs. threading.Thread:
        #   - Sobrevive restart de workers
        #   - Retry automatico con backoff (3 intentos)
        #   - UI de monitoreo en Tecnico > Pipeline Jobs
        #   - FOR UPDATE SKIP LOCKED previene doble-procesamiento
        # Ver l10n_mx.cfdi.pipeline.job._enqueue para detalles.
        att_ids = [a.id for a in attachments if a._is_cfdi_xml_safe()]
        if att_ids:
            self.env["l10n_mx.cfdi.pipeline.job"]._enqueue(att_ids)
        return attachments

    def _is_cfdi_xml_safe(self):
        """Wrapper que no rompe attachment.create si hay error de parseo."""
        try:
            return self._is_cfdi_xml()
        except Exception:
            return False

    def _trigger_cfdi_compliance_pipeline(self):
        """For each XML CFDI attachment create the document and run the
        compliance pipeline. Errors are caught so a malformed XML never
        breaks the surrounding business transaction."""
        Doc = self.env["l10n_mx.cfdi.document"].sudo()
        for att in self:
            try:
                if not att._is_cfdi_xml():
                    continue
                # Resolve target move/purchase from res_model/res_id
                related_move = related_po = None
                if att.res_model == "account.move" and att.res_id:
                    related_move = self.env["account.move"].sudo().browse(att.res_id)
                elif att.res_model == "purchase.order" and att.res_id:
                    related_po = self.env["purchase.order"].sudo().browse(att.res_id)
                doc = Doc._create_from_attachment(
                    att, company=att.company_id or self.env.company,
                    related_move=related_move, related_purchase=related_po,
                )
                doc._run_compliance_pipeline()
                # Back-link so account.move/purchase show the CFDI directly
                if related_move and not related_move.cfdi_document_id:
                    related_move.sudo().write({"cfdi_document_id": doc.id})
                if att.cfdi_document_id != doc:
                    att.sudo().write({"cfdi_document_id": doc.id})
            except Exception as e:
                _logger.exception("CFDI compliance pipeline failed for attachment %s: %s",
                                  att.id, e)
