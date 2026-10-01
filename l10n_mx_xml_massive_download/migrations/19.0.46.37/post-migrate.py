"""Migration script — l10n_mx_xml_massive_download 19.0.46.37

Backfill de vinculacion XML SAT <-> account.move por matching UUID.

Contexto: hasta version anterior el campo xml_imported_id en account.move
solo se llenaba cuando la factura era creada desde el wizard de descarga
XML SAT. Si la factura existia ya en Odoo (creada manual u otro flujo) y
solo se extrajo el UUID del XML adjunto, xml_imported_id quedaba NULL y
el boton inteligente "XML SAT" no aparecia en el form.

A partir de esta version xml_imported_id es computed-stored basado en el
reverse account.edi.downloaded.xml.sat.invoice_id. Esta migracion popula
el reverse en datos historicos via SQL puro (rapido en bases con millones
de XMLs).

Pasos:
1. UPDATE xml.invoice_id WHERE name = move.stored_sat_uuid (case-insensitive)
   y company coincide y XML aun no esta vinculado.
2. UPDATE account_move.xml_imported_id directo via subquery — sincroniza
   el cache del campo stored sin tener que esperar a un recompute ORM
   (que seria caro en miles de moves).

Idempotente: no toca XMLs que ya tienen invoice_id, ni moves que ya tienen
xml_imported_id correcto.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # Fresh install: nada que migrar

    _logger.info(
        "anfepi: post-migrate 19.0.46.37 — backfill vinculacion XML<->move "
        "por UUID (migrando desde %s)", version,
    )

    # 1) Vincular XMLs huerfanos a facturas por UUID match.
    cr.execute("""
        UPDATE account_edi_downloaded_xml_sat xml
           SET invoice_id = move.id
          FROM account_move move
         WHERE xml.invoice_id IS NULL
           AND xml.name IS NOT NULL
           AND xml.name != ''
           AND move.stored_sat_uuid IS NOT NULL
           AND move.stored_sat_uuid != ''
           AND UPPER(xml.name) = UPPER(move.stored_sat_uuid)
           AND xml.company_id = move.company_id
           AND move.state != 'cancel'
        RETURNING xml.id
    """)
    linked = cr.rowcount
    _logger.info(
        "anfepi: vinculados %s XML(s) huerfanos a facturas por UUID match",
        linked,
    )

    # 2) Sincronizar account_move.xml_imported_id (stored compute) via SQL.
    #    Usamos DISTINCT ON para tomar 1 XML por move (el de menor id si hay
    #    multiples vinculados al mismo move, ej. cancelacion+reemision).
    cr.execute("""
        UPDATE account_move move
           SET xml_imported_id = sub.xml_id
          FROM (
              SELECT DISTINCT ON (invoice_id) invoice_id AS move_id, id AS xml_id
                FROM account_edi_downloaded_xml_sat
               WHERE invoice_id IS NOT NULL
               ORDER BY invoice_id, id
          ) sub
         WHERE move.id = sub.move_id
           AND (move.xml_imported_id IS NULL OR move.xml_imported_id != sub.xml_id)
        RETURNING move.id
    """)
    synced = cr.rowcount
    _logger.info(
        "anfepi: sincronizado xml_imported_id en %s factura(s) (boton XML SAT "
        "ahora visible en form)", synced,
    )
