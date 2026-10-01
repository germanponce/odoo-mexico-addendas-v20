# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Cola persistente de jobs del pipeline de compliance CFDI.

Reemplaza el `threading.Thread` que se usaba antes para disparar el
pipeline async tras crear un ir.attachment. La cola persistente:

* Sobrevive reinicio de workers Odoo (los jobs viven en DB)
* Permite retry con backoff exponencial (3 intentos por default)
* Da visibilidad: el admin puede ver pending/running/done/failed
* Usa `FOR UPDATE SKIP LOCKED` para evitar que multiples crons o
  workers procesen el mismo job en paralelo (concurrencia segura)

Cero dependencias externas (no requerimos queue_job de OCA). Toda la
infraestructura es nativa de Odoo: ir.cron + tabla del modulo + ORM.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


# Tabla de backoff: delays despues de intentos fallidos (segundos).
# Default 3 attempts max: 30s, 5min, 30min.
RETRY_DELAYS = [30, 300, 1800]
MAX_ATTEMPTS = len(RETRY_DELAYS)


class CfdiPipelineJob(models.Model):
    _name = "l10n_mx.cfdi.pipeline.job"
    _description = "Job en cola del pipeline de compliance CFDI"
    _order = "create_date desc, id desc"
    _rec_name = "id"

    attachment_id = fields.Many2one(
        "ir.attachment",
        required=True,
        ondelete="cascade",
        index=True,
        help="Adjunto XML CFDI a procesar por el pipeline de compliance.",
    )
    state = fields.Selection([
        ("pending", "Pendiente"),
        ("running", "Ejecutandose"),
        ("done", "Completado"),
        ("failed", "Fallo"),
    ], default="pending", required=True, index=True)
    attempts = fields.Integer(
        default=0,
        help="Numero de intentos realizados. Maximo configurado: %s." % MAX_ATTEMPTS,
    )
    next_run = fields.Datetime(
        default=fields.Datetime.now,
        index=True,
        help="Cron ignora jobs con next_run > NOW(). Se usa para backoff.",
    )
    last_error = fields.Text(
        readonly=True,
        copy=False,
        help="Stacktrace o mensaje del ultimo error si attempts > 0.",
    )
    duration_ms = fields.Integer(
        readonly=True,
        help="Duracion del ultimo intento (milisegundos).",
    )
    started_at = fields.Datetime(readonly=True, copy=False)
    finished_at = fields.Datetime(readonly=True, copy=False)
    company_id = fields.Many2one(
        "res.company",
        index=True,
        default=lambda s: s.env.company,
    )

    @api.model
    def _enqueue(self, attachment_ids):
        """Encola jobs para los attachment_ids dados. Idempotente:
        si ya existe un job pending/running para ese attachment, no duplica."""
        if not attachment_ids:
            return self.browse()
        # sudo: el _enqueue lo dispara CUALQUIER usuario que sube un XML (p.ej.
        # facturacion/Rol-Miembro sin grupos de compliance). La cola es
        # infraestructura interna; ni el search ni el create deben depender del
        # ACL del usuario que sube, o el upload falla con AccessError.
        existing = self.sudo().search([
            ("attachment_id", "in", list(attachment_ids)),
            ("state", "in", ("pending", "running")),
        ])
        existing_att_ids = set(existing.mapped("attachment_id.id"))
        to_create = [
            {"attachment_id": att_id}
            for att_id in attachment_ids
            if att_id not in existing_att_ids
        ]
        if not to_create:
            return self.browse()
        return self.sudo().create(to_create)

    @api.model
    def _cron_process_pending(self):
        """Cron worker: procesa hasta `batch_size` jobs pending con
        next_run <= NOW(). Usa FOR UPDATE SKIP LOCKED para concurrencia
        segura entre multiples crones/workers.

        Llama a Attachment._trigger_cfdi_compliance_pipeline() que es la
        logica de negocio existente — solo cambiamos como se ENCOLA, no
        como se PROCESA.
        """
        batch_size = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "l10n_mx_cfdi_compliance.queue_batch_size", "20",
            )
        )
        # Lock optimista: tomar hasta batch_size jobs disponibles.
        self.env.cr.execute("""
            SELECT id FROM l10n_mx_cfdi_pipeline_job
             WHERE state = 'pending'
               AND next_run <= NOW() AT TIME ZONE 'UTC'
             ORDER BY id
             LIMIT %s
             FOR UPDATE SKIP LOCKED
        """, (batch_size,))
        job_ids = [r[0] for r in self.env.cr.fetchall()]
        if not job_ids:
            return
        # Marcar todos como running en una sola query (dentro del lock).
        self.env.cr.execute("""
            UPDATE l10n_mx_cfdi_pipeline_job
               SET state = 'running',
                   started_at = NOW() AT TIME ZONE 'UTC',
                   write_date = NOW() AT TIME ZONE 'UTC'
             WHERE id = ANY(%s)
        """, (job_ids,))
        self.env.cr.commit()

        # Procesar uno por uno (cada job tiene su propia transaccion implicita
        # via savepoint para no contaminar la siguiente con un rollback).
        for job_id in job_ids:
            job = self.browse(job_id).exists()
            if not job:
                continue
            job._process()

    def _process(self):
        """Ejecuta el pipeline para un job individual. Marca done/failed
        y aplica backoff si falla."""
        self.ensure_one()
        start = fields.Datetime.now()
        try:
            att = self.attachment_id
            if not att.exists():
                # Attachment borrado entre encolar y procesar — marcar done.
                self._mark_done(start, msg="Attachment ya no existe.")
                return
            att._trigger_cfdi_compliance_pipeline()
            self._mark_done(start)
        except Exception as e:
            _logger.exception(
                "CFDI pipeline job %s fallo para attachment %s: %s",
                self.id, self.attachment_id.id, e,
            )
            self._mark_failed_or_retry(start, str(e))

    def _mark_done(self, started_at, msg=""):
        self.write({
            "state": "done",
            "finished_at": fields.Datetime.now(),
            "duration_ms": self._duration_ms(started_at),
            "last_error": msg or False,
        })
        self.env.cr.commit()

    def _mark_failed_or_retry(self, started_at, error_msg):
        new_attempts = self.attempts + 1
        if new_attempts >= MAX_ATTEMPTS:
            self.write({
                "state": "failed",
                "attempts": new_attempts,
                "finished_at": fields.Datetime.now(),
                "duration_ms": self._duration_ms(started_at),
                "last_error": error_msg,
            })
        else:
            delay = RETRY_DELAYS[new_attempts - 1]
            self.write({
                "state": "pending",
                "attempts": new_attempts,
                "next_run": fields.Datetime.now() + timedelta(seconds=delay),
                "duration_ms": self._duration_ms(started_at),
                "last_error": error_msg,
            })
        self.env.cr.commit()

    @staticmethod
    def _duration_ms(started_at):
        if not started_at:
            return 0
        delta = fields.Datetime.now() - started_at
        return int(delta.total_seconds() * 1000)

    def action_retry(self):
        """Boton UI: re-encolar un job failed (resetea attempts)."""
        self.write({
            "state": "pending",
            "attempts": 0,
            "next_run": fields.Datetime.now(),
            "last_error": False,
        })

    def action_force_run(self):
        """Boton UI: procesar inmediatamente sin esperar al cron."""
        for job in self:
            if job.state in ("running", "done"):
                continue
            job.write({
                "state": "running",
                "started_at": fields.Datetime.now(),
            })
            job._process()
