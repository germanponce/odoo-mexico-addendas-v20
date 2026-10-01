# -*- coding: utf-8 -*-
from . import models
from . import wizard


def pre_init_check(cr):
    from odoo.service import common
    from odoo.exceptions import UserError
    from odoo import _

    version_info = common.exp_version()
    server_serie = version_info.get('server_serie')
    if '17.' not in server_serie:
        raise UserError(_('This module support Odoo series 17.x, found %s.') %
                      server_serie)
    return True
