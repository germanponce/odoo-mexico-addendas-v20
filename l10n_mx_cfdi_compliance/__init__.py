# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from . import models
from . import engine
from . import wizards
from . import controllers


def post_init_hook(env):
    """Sync rule registry catalog and seed default profile per company."""
    env["l10n_mx.compliance.rule"]._sync_from_registry()
    env["res.company"]._l10n_mx_cfdi_create_default_profile()
