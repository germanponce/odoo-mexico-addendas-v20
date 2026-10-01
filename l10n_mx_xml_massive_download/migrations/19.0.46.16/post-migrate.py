"""Migration script — l10n_mx_xml_massive_download 19.0.46.14

Dos cosas al actualizar desde versiones anteriores:

1) Fix de crons con numbercall=0 (o cualquier valor finito). En versiones
   anteriores los <record> de ir.cron no definian explicitamente
   `numbercall`, asi que Odoo lo dejaba en 1 (default). Despues de la
   primera ejecucion bajaba a 0 y el cron quedaba inactivo. En produccion
   esto se manifestaba como "el cron de auto-sync paro hace dias" y los
   lotes encolados nunca se procesaban. Ahora forzamos -1 (indefinido).

2) Re-evaluacion de sync_stable en lotes existentes. Antes de esta version
   no habia heuristica clara para marcar un lote como "Completo". Aqui
   evaluamos: si el lote esta en state='imported', sin last_error y han
   pasado >72h desde date_end, lo marcamos sync_stable=True. Esto evita
   que el cliente tenga que re-correr todos los lotes manualmente para
   verlos "completados".

Se ejecuta automaticamente en `odoo-bin -u l10n_mx_xml_massive_download`.
Idempotente: corre sin hacer nada si no hay residuos.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # Fresh install: nada que migrar

    _logger.info(
        "anfepi: post-migrate 19.0.46.14 — fix crons + sync_stable retroactivo "
        "(migrando desde %s)", version,
    )
    _fix_cron_numbercall(cr)
    _backfill_sync_stable(cr)


def _fix_cron_numbercall(cr):
    """Pone numbercall=-1 en todos los crons del modulo (solo si la columna
    existe). En Odoo 19 numbercall fue removido de ir.cron, asi que en v19
    este fix es no-op. Tambien empuja nextcall a NOW() para que los crons
    arranquen pronto si estaban en el pasado.
    """
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ir_cron' AND column_name = 'numbercall'
    """)
    has_numbercall = bool(cr.fetchone())

    if has_numbercall:
        cr.execute("""
            UPDATE ir_cron
            SET numbercall = -1
            WHERE id IN (
                SELECT res_id FROM ir_model_data
                WHERE model = 'ir.cron'
                  AND module = 'l10n_mx_xml_massive_download'
            )
            AND numbercall <> -1
            RETURNING id, cron_name
        """)
        rows = cr.fetchall()
        if rows:
            _logger.info(
                "anfepi: fix numbercall=-1 en %s cron(s): %s",
                len(rows), [r[1] for r in rows],
            )
    else:
        _logger.info(
            "anfepi: ir_cron.numbercall no existe (Odoo 19+), skip fix"
        )

    cr.execute("""
        UPDATE ir_cron
        SET nextcall = NOW() AT TIME ZONE 'UTC'
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE model = 'ir.cron'
              AND module = 'l10n_mx_xml_massive_download'
        )
        AND active = true
        AND nextcall < NOW() AT TIME ZONE 'UTC'
    """)


def _backfill_sync_stable(cr):
    """Marca sync_stable=True en lotes con state='imported', sin last_error,
    y date_end > 72h en el pasado. Misma heuristica que _run_download_pipeline.
    """
    cr.execute("""
        UPDATE account_edi_api_download
        SET sync_stable = true
        WHERE state = 'imported'
          AND (last_error IS NULL OR last_error = '')
          AND date_end IS NOT NULL
          AND date_end < (NOW() AT TIME ZONE 'UTC' - INTERVAL '72 hours')::date
          AND COALESCE(sync_stable, false) = false
        RETURNING id
    """)
    rows = cr.fetchall()
    if rows:
        _logger.info(
            "anfepi: marcados %s lote(s) como sync_stable=True retroactivamente",
            len(rows),
        )
    else:
        _logger.info("anfepi: ningun lote elegible para sync_stable retroactivo")
