# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
import odoo.release  # type: ignore

from . import compat
from . import l10n_mx_account_edi_download
from . import account_move
from . import account_move_line
from . import custom_accounting_settings
from . import res_company
from . import res_users
from . import account_payment
from . import retencion_conciliacion
from .art69b import blacklist

# Polyfill v15/v16: campos que v17+ ya provee nativos en l10n_mx_edi
if odoo.release.version_info[0] < 17:
    from . import compat_account_move
