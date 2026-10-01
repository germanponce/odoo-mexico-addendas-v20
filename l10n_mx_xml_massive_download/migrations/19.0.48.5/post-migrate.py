"""Post-migrate 19.0.48.5 — desactiva el cron recurrente de auto-poblado (#B).

Los campos que llenaba (fecha_timbrado, impuestos, cuenta predial, moneda) son
ESTATICOS del XML y ya se pueblan de forma ROBUSTA AL CARGAR (el parse del pipeline
tolera XMLs mal formados desde .47.4: xmlns:schemaLocation -> xsi:schemaLocation).
Re-checar campos estaticos cada 15 min es trabajo innecesario; lo recurrente debe ser
solo lo que CAMBIA con el tiempo (vigencia SAT, Art 69-B, relacionados), que tienen su
propio cron. Para una limpieza puntual de registros historicos existe la accion manual
de servidor "Backfill Fecha de Timbrado e Impuestos" (action_backfill_timbrado_y_taxes).

Idempotente: si el cron ya esta inactivo, no hace nada. El record NO se borra (se puede
reactivar manualmente si algun caso lo amerita).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # fresh install: el XML ya viene con active=False
    cr.execute(
        """
        UPDATE ir_cron SET active = false
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module IN (
                'l10n_mx_xml_massive_download', 'l10n_mx_xml_masive_download'
            )
              AND model = 'ir.cron'
              AND name = 'ir_cron_backfill_xml_fields'
        )
        AND active = true
        RETURNING id
        """
    )
    rows = cr.fetchall()
    if rows:
        _logger.info(
            "massive .48.5: cron auto-poblado #B desactivado (%s) — los campos "
            "estaticos ya se pueblan AL CARGAR; lo recurrente queda solo para "
            "vigencia SAT / Art 69-B / relacionados",
            len(rows),
        )
    else:
        _logger.info("massive .48.5: cron auto-poblado #B ya estaba inactivo")
