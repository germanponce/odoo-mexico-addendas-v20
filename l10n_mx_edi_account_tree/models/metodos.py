# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _

import logging
_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"    
    
    
    def _query_get2(self):
        obj='l'
        fiscalyear_obj = self.env['account.fiscalyear']
        fiscalperiod_obj = self.env['account.period']
        account_obj = self.env['account.account']
        fiscalyear_ids = []
        context = self.env.context.copy()
        initial_bal = context.get('initial_bal', False)
        company_clause = " "
        if context.get('company_id', False):
            # Commented by Argil Consulting
            # company_clause = " AND " +obj+".company_id = %s" % context.get('company_id', False)
            # End Comment
            # Added by Argil Consulting
            if context.get('argil_revaluation', False):
                company_clause = " AND " +obj+".company_id = %s" % context.get('company_id', False)
            else:
                company_clause = " AND " +obj+".company_id in %s" % tuple([x.id for x in self.env.user.company_ids])
        if not context.get('fiscalyear', False):
            if context.get('all_fiscalyear', False):
                #this option is needed by the aged balance report because otherwise, if we search only the draft ones, an open invoice of a closed fiscalyear won't be displayed
                fiscalyear_ids = [x.id for x in fiscalyear_obj.search([])]
            else:
                # Commented by Argil Consulting
                # fiscalyear_ids = fiscalyear_obj.search(cr, uid, [('state', '=', 'draft')])
                # End Comment
                # Added by Argil Consulting
                if context.get('argil_revaluation', False):
                    fiscalyear_ids = [x.id for x in fiscalyear_obj.search([('state', '=', 'draft'),('company_id','=',self.env.user.company_id.id)])]
                else:
                    fiscalyear_ids = [x.id for x in fiscalyear_obj.search([('state', '=', 'draft')])]
        else:
            #for initial balance as well as for normal query, we check only the selected FY because the best practice is to generate the FY opening entries
            # Commented by Argil Consulting
            # fiscalyear_ids = [context['fiscalyear']]
            # End Comment
            # Added by Argil Consulting            
            if context.get('argil_revaluation', False):
                fiscalyear_ids = [context['fiscalyear']]
            else:
                self._cr.execute("select name from account_fiscalyear where id in (%s) limit 1" % ((','.join([str(x) for x in [context['fiscalyear']]])) or '0'))
                ydata = self._cr.fetchone()
                fiscalyear_name = ydata[0] or ''
                companies = [x.id for x in self.env.user.company_ids]
                fiscalyear_ids = [x.id for x in fiscalyear_obj.search([('company_id','in', tuple(companies),), ('name','=', fiscalyear_name)])]

        fiscalyear_clause = (','.join([str(x) for x in fiscalyear_ids])) or '0'
        state = context.get('state', False)
        where_move_state = ''
        where_move_lines_by_date = ''

        if context.get('date_from', False) and context.get('date_to', False):
            if initial_bal:
                where_move_lines_by_date = " AND " +obj+".move_id IN (SELECT id FROM account_move WHERE date < '" + context['date_from']+"')"
            else:
                where_move_lines_by_date = " AND " +obj+".move_id IN (SELECT id FROM account_move WHERE date >= '" + context['date_from']+"' AND date <= '" + context['date_to']+"')"

        if state:
            if state.lower() not in ['all']:
                where_move_state= " AND "+obj+".move_id IN (SELECT id FROM account_move WHERE account_move.state = '"+state+"')"
        if context.get('period_from', False) and context.get('period_to', False) and not context.get('periods', False):
            if initial_bal:
                period_company_id = fiscalperiod_obj.browse(context['period_from']).company_id.id
                first_period = fiscalperiod_obj.search([('company_id', '=', period_company_id)], order='date_start', limit=1)[0]
                context['periods'] = fiscalperiod_obj.build_ctx_periods(first_period, context['period_from'])
            else:
                context['periods'] = fiscalperiod_obj.build_ctx_periods(context['period_from'], context['period_to'])
        if context.get('periods', False):
            xperiods = fiscalperiod_obj.search([('id','in', context['periods'])])
            xperiods = [x.name for x in xperiods]
            context['periods'] = [x.id for x in fiscalperiod_obj.search([('name','in',(tuple(xperiods,)))])]
            
            if initial_bal:
                query = obj+".period_id IN (SELECT id FROM account_period WHERE fiscalyear_id IN (%s)) %s %s" % (fiscalyear_clause, where_move_state, where_move_lines_by_date)
                period_ids = fiscalperiod_obj.search([('id', 'in', context['periods'])], order='date_start', limit=1)
                if period_ids and period_ids[0]:
                    first_period = fiscalperiod_obj.browse(period_ids[0])
                    ids = ','.join([str(x) for x in context['periods']])
                    query = obj+".period_id IN (SELECT id FROM account_period WHERE fiscalyear_id IN (%s) AND date_start <= '%s' AND id NOT IN (%s)) %s %s" % (fiscalyear_clause, first_period.date_start, ids, where_move_state, where_move_lines_by_date)
            else:
                ids = ','.join([str(x) for x in context['periods']])
                query = obj+".period_id IN (SELECT id FROM account_period WHERE fiscalyear_id IN (%s) AND id IN (%s)) %s %s" % (fiscalyear_clause, ids, where_move_state, where_move_lines_by_date)
        else:
            query = obj+".period_id IN (SELECT id FROM account_period WHERE fiscalyear_id IN (%s)) %s %s" % (fiscalyear_clause, where_move_state, where_move_lines_by_date)
            
        
        if initial_bal and not context.get('periods', False) and not where_move_lines_by_date:
            #we didn't pass any filter in the context, and the initial balance can't be computed using only the fiscalyear otherwise entries will be summed twice
            #so we have to invalidate this query
            raise UserError(_('You have not supplied enough arguments to compute the initial balance, please select a period and a journal in the context.'))


        if context.get('journal_ids', False):
            query += ' AND '+obj+'.journal_id IN (%s)' % ','.join(map(str, context['journal_ids']))

        if context.get('chart_account_id', False):
            child_ids = account_obj._get_children_and_consol([context['chart_account_id']])
            query += ' AND '+obj+'.account_id IN (%s)' % ','.join(map(str, child_ids))

        query += company_clause
        return query
        

    @api.constrains('account_id')
    def _check_no_view_consolidated_account(self):
        for line in self:
            if line.account_id.internal_group == 'view':
                raise UserError(_('Está tratando de usar cuentas acumulativas (Tipo Vista) en partidas contables (%s - %s), esto no está permitido') % (line.account_id.code, line.account_id.name))
            elif line.account_id.internal_group == 'consolidation':
                raise UserError(_('Está tratando de usar cuentas de Consolidación en partidas contables (%s - %s), esto no está permitido') % (line.account_id.code, line.account_id.name))

        
class AccountAccount(models.Model):
    _inherit = "account.account"

    
    def __compute(self):
        # compute the balance, debit and/or credit for the provided
        #account ids
        #
        query=''
        query_params=()
        mapping = {
            'balance': "COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) as balance",
            'debit': "COALESCE(SUM(l.debit), 0) as debit",
            'credit': "COALESCE(SUM(l.credit), 0) as credit",
            # by convention, foreign_balance is 0 when the account has no secondary currency, because the amounts may be in different currencies
            #'foreign_balance': "(SELECT CASE WHEN currency_id IS NULL THEN 0 ELSE COALESCE(SUM(l.amount_currency), 0) END FROM account_account WHERE id IN (l.account_id)) as foreign_balance",
        }
        #get all the necessary accounts
        children_and_consolidated = self._get_children_and_consol(self._ids)
        #compute for each account the balance/debit/credit from the move lines
        res = {}
        if children_and_consolidated:
            aml_query = self.env['account.move.line']._query_get2()
            wheres = [""]
            if query.strip():
                wheres.append(query.strip())
            if aml_query.strip():
                wheres.append(aml_query.strip())
            filters = " AND ".join(wheres)
            # IN might not work ideally in case there are too many
            # children_and_consolidated, in that case join on a
            # values() e.g.:
            # SELECT l.account_id as id FROM account_move_line l
            # INNER JOIN (VALUES (id1), (id2), (id3), ...) AS tmp (id)
            # ON l.account_id = tmp.id
            # or make _get_children_and_consol return a query and join on that
            #request = ("SELECT l.account_id as id, " +\
            #           ', '.join(mapping.values()) +
            #           " FROM account_move_line l" \
            #           " WHERE l.account_id IN %s " \
            #                + filters +
            #           " --GROUP BY l.account_id")
            
            request = ("SELECT " +\
                       ', '.join(mapping.values()) +
                       " FROM account_move_line l" \
                       " WHERE l.account_id IN %s " \
                            + filters +
                       " ")
            params = (tuple(children_and_consolidated),) + query_params
            #_logger.info("qquery: %s %s" % (request, params))
            self._cr.execute(request, params)
            res = self._cr.dictfetchall()[0]
            sign = self.browse(self._ids)[0]['sign']
            res.update({'balance':res['balance'] * float(sign)})
        return res
    
    


class AccountChartOfAccountsArgilWizard(models.TransientModel):    
    """
    For Chart of Accounts
    """
    _inherit = "account.chart_argil"

    @api.onchange('fiscalyear_id')
    def _onchange_fiscalyear(self):
        if self.fiscalyear_id:
            start_period, end_period = False, False
            self._cr.execute('''
                SELECT * FROM (SELECT p.id
                               FROM account_period p
                               LEFT JOIN account_fiscalyear f ON (p.fiscalyear_id = f.id)
                               WHERE f.id = %s
                               ORDER BY p.date_start ASC
                               LIMIT 1) AS period_start
                UNION ALL
                SELECT * FROM (SELECT p.id
                               FROM account_period p
                               LEFT JOIN account_fiscalyear f ON (p.fiscalyear_id = f.id)
                               WHERE f.id = %s
                               AND p.date_start < NOW()
                               ORDER BY p.date_stop DESC
                               LIMIT 1) AS period_stop''', (self.fiscalyear_id.id, self.fiscalyear_id.id))
            periods =  [i[0] for i in self._cr.fetchall()]
            if periods and len(periods) > 1:
                self.period_from = periods[0]
                self.period_to = periods[1]

    
    def account_chart_open_window(self):
        """
        Opens chart of Accounts
        """
        mod_obj = self.env['ir.model.data']
        act_obj = self.env['ir.actions.act_window']
        period_obj = self.env['account.period']
        fy_obj = self.env['account.fiscalyear']
        context = self._context.copy()
        
        result = mod_obj.get_object_reference('l10n_mx_edi_account_tree', 'action_account_tree_argil')        
        id = result and result[1] or False
        result = act_obj.search_read([('id','=',id)])[0]
        
        fiscalyear_id = self.fiscalyear_id.id or False
        result['periods'] = []
        if self.period_from and self.period_to:
            period_from = self.period_from.id or False
            period_to = self.period_to.id or False
            result['periods'] = period_obj.build_ctx_periods(period_from, period_to)
        result['context'] = str({'periods': result['periods'], 'state': self.target_move})
        #str({'fiscalyear': fiscalyear_id, 'periods': result['periods'], 'state': self.target_move})
        if fiscalyear_id:
            result['display_name'] += _(' - Fiscal Year: ') + self.fiscalyear_id.name + _(' - From: ') + self.period_from.name + _(' To: ') + self.period_to.name
        return result
    
            
        
        
class AccountChartOfAnalyticsArgilWizard(models.TransientModel):    
    _inherit = "account.analytic.chart_argil"
    
    def account_chart_open_window(self):
        """
        Opens chart of Accounts
        """
        mod_obj = self.env['ir.model.data']
        act_obj = self.env['ir.actions.act_window']
        context = self._context.copy()
        
        result = mod_obj.get_object_reference('l10n_mx_edi_account_tree', 'action_analytic_tree_argil')        
        id = result and result[1] or False
        result = act_obj.search_read([('id','=',id)])[0]
        res = {}
        title = ''
        if self.date_from and self.date_to:
            res['date_from'] = self.date_from
            res['date_to']   = self.date_to
            title += _('From: ') + self.date_from + _(' To ') + self.date_to
            
        result['context'] = str(res)        
        result['display_name'] += title
        return result        
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:        