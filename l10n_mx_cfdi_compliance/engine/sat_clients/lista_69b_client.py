# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Client to query the SAT 69-B blacklist (EFOS).

Integration note (2026-05):
    This module DELEGATES to the existing
    ``l10n_mx_xml_massive_download`` module, which already maintains
    the official SAT 69-B blacklist via:

        * Model:   ``l10n_mx.art69b.blacklist``
        * Wizard:  ``l10n_mx.art69b.import.wizard.import_csv()``
        * Cron:    ``ir_cron_update_art69b_status`` (weekly)

    To avoid duplicating the download/refresh logic and to keep a
    single source of truth, we query the pre-loaded model and let
    massive_download own the refresh lifecycle.

Returns:
    * ``True``  - RFC active in 69-B (situacion 'presuncion'/'definitivo')
    * ``False`` - RFC in DB but inactive or 'desvirtuado' (cleared)
    * ``None``  - RFC unknown to local DB (cannot conclude)
"""
from __future__ import annotations

import logging
from typing import Optional

_logger = logging.getLogger(__name__)


def is_in_69b(env, rfc: str) -> Optional[bool]:
    """Return True/False if known via local DB, ``None`` if not present.

    :param env: Odoo environment (required to access the ORM)
    :param rfc: RFC to check (case-insensitive)
    """
    rfc = (rfc or "").upper().strip()
    if not rfc or env is None:
        return None
    Blacklist = env.get("l10n_mx.art69b.blacklist")
    if Blacklist is None:
        _logger.warning(
            "l10n_mx.art69b.blacklist model missing; cannot verify 69-B")
        return None
    rec = Blacklist.sudo().search([("rfc", "=", rfc)], limit=1)
    if not rec:
        return None
    if not rec.activo:
        return False
    return rec.situacion in ("presuncion", "definitivo")


def get_69b_record(env, rfc: str):
    """Return the ``l10n_mx.art69b.blacklist`` record for ``rfc`` or empty."""
    rfc = (rfc or "").upper().strip()
    if not env:
        return None
    Blacklist = env.get("l10n_mx.art69b.blacklist")
    if Blacklist is None:
        return None
    return Blacklist.sudo().search([("rfc", "=", rfc)], limit=1)
