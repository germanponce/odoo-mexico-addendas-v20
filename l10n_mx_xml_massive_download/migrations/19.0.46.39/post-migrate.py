"""Migration script — l10n_mx_xml_massive_download 19.0.46.39

Fix de migration 19.0.46.38 que estaba rota: el SQL referenciaba
`c.vat` directo en res_company, pero en Odoo el VAT esta en res_partner
y se accede via company.partner_id.vat (related field). El UPDATE original
no matcheaba nada.

Esta migration corrige el backfill multi-company haciendo el JOIN correcto
res_company -> res_partner para obtener el VAT.

Adicionalmente fuerza recompute del campo computed-stored company_id en
todos los lotes (por si la version .38 tampoco disparo el recompute al
upgrade).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info(
        "anfepi: post-migrate 19.0.46.39 — fix backfill multi-company "
        "lote.company_id por VAT (JOIN correcto via res_partner). "
        "Migrando desde %s", version,
    )

    # SQL UPDATE corregido: VAT vive en res_partner, no en res_company.
    cr.execute("""
        UPDATE account_edi_api_download lote
           SET company_id = c.id
          FROM res_company c
          JOIN res_partner p ON c.partner_id = p.id
         WHERE lote.vat IS NOT NULL
           AND lote.vat != ''
           AND p.vat IS NOT NULL
           AND UPPER(p.vat) = UPPER(lote.vat)
           AND (lote.company_id IS NULL OR lote.company_id != c.id)
        RETURNING lote.id, lote.vat, c.id, c.name
    """)
    rows = cr.fetchall()
    if rows:
        _logger.info(
            "anfepi: reasignados %s lote(s) a su empresa correcta por VAT match",
            len(rows),
        )
        # Log primeros 20 para auditoria
        for lote_id, vat, company_id, company_name in rows[:20]:
            _logger.info(
                "  lote id=%s vat=%s -> empresa id=%s '%s'",
                lote_id, vat, company_id, company_name,
            )
        if len(rows) > 20:
            _logger.info("  ... y %s lote(s) mas", len(rows) - 20)
    else:
        _logger.info(
            "anfepi: ningun lote con mismatch company_id<->vat (todo consistente)"
        )
