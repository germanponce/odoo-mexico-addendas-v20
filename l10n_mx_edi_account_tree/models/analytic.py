# -*- coding: utf-8 -*-
#from odoo.osv import expression, osv
#from odoo.tools.float_utils import float_round as round
#from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _



class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
        
    
    def _get_children(self, ids=[]):
        #this function search for all the children and all consolidated children (recursively) of the given account ids
        ids = list(ids)
        res = []
        record = self.search([('parent_id', 'child_of', ids)])
        ids3 = []
        for rec in record:
            res.append(rec.id)
        return res    
    
    
    @api.depends('child_parent_ids')
    def _get_child_ids(self):
        for rec_analytic in self:
            result = []
            if rec_analytic.child_parent_ids:
                for record in rec_analytic.child_parent_ids:
                    result.append(record.id)
            rec_analytic.child_id = result
        
        
    
    def __compute_argil(self):        
        analytic_line_obj = self.env['account.analytic.line']
        for rec in self:
            children_ids = rec._get_children(self._ids)
            domain = [('account_id', 'in', (tuple(children_ids,)))]
            if self._context.get('date_from', False):
                domain.append(('date', '>=', self._context['date_from']))
            if self._context.get('date_to', False):
                domain.append(('date', '<=', self._context['date_to']))

            account_amounts = analytic_line_obj.search_read(domain, ['account_id', 'amount'])
            debit = 0.0
            credit = 0.0
            for account_amount in account_amounts:            
                if account_amount['amount'] < 0.0:
                    credit += abs(account_amount['amount'])
                else:
                    debit += account_amount['amount']

            rec.argil_debit = debit
            rec.argil_credit = credit
            rec.argil_balance = debit - credit        
        
    parent_id = fields.Many2one('account.analytic.account', string='Padre', required=False, index=True)
    child_parent_ids  = fields.One2many('account.analytic.account','parent_id', string='Hijos')
    child_id          = fields.Many2many('account.analytic.account', compute=_get_child_ids,  string="Cuentas Hijo", store=False)
    argil_debit   = fields.Monetary(compute=__compute_argil, string='Debe')
    argil_credit  = fields.Monetary(compute=__compute_argil, string='Haber')
    argil_balance = fields.Monetary(compute=__compute_argil, string='Saldo')



    
class AccountChartOfAnalyticsArgilWizard(models.TransientModel):    
    """
    For Chart of Analytics
    """
    _name = "account.analytic.chart_argil"
    _description = "Account Chart Of Analytics Argil"
        
        
    date_from   = fields.Date(string='From', required=False)
    date_to     = fields.Date(string='To', required=False)
    
    
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
