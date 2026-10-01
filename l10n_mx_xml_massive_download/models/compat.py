# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""
Capa de compatibilidad para v15/v16 que polifila APIs v17+ usadas por
el modulo. Permite que el resto del codigo funcione sin cambios en
v15-v19.

Polifills:
  - CFDI_CODE_TO_TAX_TYPE: constante movida en v17 a l10n_mx_edi_document
  - account.move.l10n_mx_edi_cfdi_uuid: campo introducido en v17
  - account.move.l10n_mx_edi_cfdi_request: campo introducido en v17

Estos polifills se aplican en Odoo 15/16 solamente; en v17+ no hacen nada
(el codigo nativo de l10n_mx_edi ya provee los simbolos correspondientes).
"""

import odoo.release  # type: ignore


ODOO_VERSION = odoo.release.version_info[0]


# ════════════════════════════════════════════════════════════════════════════
# Polyfill: CFDI_CODE_TO_TAX_TYPE
# ════════════════════════════════════════════════════════════════════════════
# Mapeo SAT de codigo de impuesto -> tipo (estable por regulacion del SAT).
# En v17+ vive en odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document
# En v15/v16 no existe — lo definimos aqui de forma identica.
CFDI_CODE_TO_TAX_TYPE_FALLBACK = {
    "001": "isr",   # Impuesto Sobre la Renta
    "002": "iva",   # Impuesto al Valor Agregado
    "003": "ieps",  # Impuesto Especial sobre Produccion y Servicios
}


def get_cfdi_code_to_tax_type():
    """Retorna el mapeo CFDI_CODE_TO_TAX_TYPE, prefiriendo el nativo."""
    if ODOO_VERSION >= 17:
        try:
            from odoo.addons.l10n_mx_edi.models.l10n_mx_edi_document import (  # type: ignore
                CFDI_CODE_TO_TAX_TYPE,
            )
            return CFDI_CODE_TO_TAX_TYPE
        except (ImportError, ModuleNotFoundError):
            pass
    return CFDI_CODE_TO_TAX_TYPE_FALLBACK


# Atajo: variable a nivel de modulo para imports
CFDI_CODE_TO_TAX_TYPE = get_cfdi_code_to_tax_type()


# ════════════════════════════════════════════════════════════════════════════
# Polyfill: fields.Json (Odoo introdujo Json en 16.0; en 15.0 no existe)
# ════════════════════════════════════════════════════════════════════════════
# Patch in-place: si la version es < 16, parchea odoo.fields.Json = odoo.fields.Text
# Asi el codigo `fields.Json(...)` funciona en todas las versiones sin cambios.
if ODOO_VERSION < 16:
    import json as _json
    from odoo import fields as _fields  # type: ignore

    if not hasattr(_fields, "Json"):
        class Json(_fields.Text):  # type: ignore
            """Polyfill v15: fields.Json -> Text + serializacion JSON automatica."""
            type = "text"
            column_type = ("text", "text")

            def convert_to_column(self, value, record, values=None, validate=True):
                if value is None or value is False:
                    return None
                if isinstance(value, str):
                    return value
                return _json.dumps(value, ensure_ascii=False)

            def convert_to_cache(self, value, record, validate=True):
                if value is None or value is False:
                    return False
                if isinstance(value, (list, dict)):
                    return value
                if isinstance(value, str):
                    try:
                        return _json.loads(value)
                    except (ValueError, TypeError):
                        return False
                return value

            def convert_to_record(self, value, record):
                return value if value not in (False, None) else False

            def convert_to_read(self, value, record, use_name_get=True):
                return value if value not in (False, None) else False

        _fields.Json = Json  # patch in-place
