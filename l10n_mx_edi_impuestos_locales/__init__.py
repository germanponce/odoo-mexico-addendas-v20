# -*- coding: utf-8 -*-
from . import models
from odoo import _

def pre_init_check(cr):
    from odoo.service import common
    from odoo.exceptions import Warning
    version_info = common.exp_version()
    server_serie = version_info.get('server_serie')
    if server_serie != '14.0':
        raise Warning(_('Module support Odoo series 14.0, found %s.') % server_serie)
    return True
