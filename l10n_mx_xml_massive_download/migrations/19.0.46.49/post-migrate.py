"""Migration 19.0.46.49 — crea indices auxiliares para los nuevos
reportes de Complemento de Pago (Clientes y Proveedores).

Los indices aceleran las queries del SQL view de los reportes,
especialmente con bases con muchas facturas/XMLs (Cosal, ANFEPI multi-empresa).

Idempotente: usa IF NOT EXISTS.
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # Fresh install: lo hara el post_init si lo agregamos

    _logger.info(
        "anfepi: post-migrate 19.0.46.49 — indices para reportes "
        "Complemento de Pago Clientes/Proveedores"
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    Report = env.get('l10n_mx.complemento.pago.cliente.report')
    if Report is not None:
        try:
            Report._create_indexes()
            _logger.info("anfepi: indices creados via _create_indexes")
        except Exception as e:
            _logger.warning("anfepi: error creando indices: %s", e)
