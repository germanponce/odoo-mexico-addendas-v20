# coding: utf-8

from odoo import api, tools, SUPERUSER_ID
from datetime import date
import logging
_logger = logging.getLogger(__name__)


def post_init_hook(env):
    cr = env.cr
    y = date.today().year
    companies = env['res.company'].search([])
    for company in companies:
        for x in range(y-5,y+1):
            xstart = date(x, 1,1)
            xend   = date(x,12,31)
            fy_previous = env['account.fiscalyear'].search([('name','=',x)])
            if not fy_previous:
                fy = env['account.fiscalyear'].create({'name' : str(x),
                                                       'date_start' : xstart,
                                                       'date_stop'  : xend,
                                                   'company_id' : company.id})
            
    cr.execute(
        """update account_move_line aml set period_id = (select ap.id from account_period ap where ap.company_id=aml.company_id and aml.date >= ap.date_start and aml.date <= ap.date_stop limit 1);
        update account_move am set period_id = (select ap.id from account_period ap where ap.company_id=am.company_id and am.date >= ap.date_start and am.date <= ap.date_stop limit 1);
        """)
