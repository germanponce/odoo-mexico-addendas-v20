# -*- coding: utf-8 -*-
#
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)


class AccountAccount(models.Model):
    _inherit = "account.account"

    account_type = fields.Selection(selection_add=[('view', 'Acumulativa'),
                                           ('consolidation', 'Consolidación')],
                            ondelete={'view': 'set default', 'consolidation': 'set default'} , default="asset_current")

    internal_group = fields.Selection(selection_add=[('view', 'Acumulativa'),
                                           ('consolidation', 'Consolidación')
                                           ],
                            ondelete={'view': 'set default', 'consolidation': 'set default'}, default="asset")
    
    @api.depends('parent_id')
    def _get_level(self):
        for rec in self:
            level = 0
            parent = rec.parent_id or False
            while parent:
                level += 1
                parent = parent.parent_id or False
            rec.level = level

    
    @api.depends('child_parent_ids')
    def _get_child_ids(self):
        for account_rec in self:
            result = []
            if account_rec.child_parent_ids:
                for record in account_rec.child_parent_ids:
                    result.append(record.id)            

            if account_rec.child_consol_ids:
                for acc in account_rec.child_consol_ids:
                    if acc.id not in result:
                        result.append(acc.id)
            account_rec.child_id = result
        

    def _get_children_and_consol(self, ids=[]):
        #this function search for all the children and all consolidated children (recursively) of the given account ids
        ids = list(ids)
        res = []
        record = self.search([('parent_id', 'child_of', ids)])
        ids3 = []
        for rec in record:
            res.append(rec.id)
            for child in rec.child_consol_ids:
                res.append(child.id)
        #if record:
        #    res2 = self._get_children_and_consol()
        return res    
    
    
    
    def _compute_argil(self):
        for rec in self:
            query=''
            context = self._context.copy()
            context2 = context.copy()
            periods = context.get('periods', False)

            res2 = False
            if context.get('periods', False) and not context.get('period_from', False) and not context.get('period_to', False):
                #_logger.info("NO DEBERIA ENTRAR AQUI ....")
                subquery = """select p2.id from account_period p2
                                where p2.name2 < (select min(name2) from account_period p1
                                                  where id in (%s));
                    """ % (str(periods).replace('[','').replace(']',''))
                self._cr.execute( subquery )
                period_ids = [period_id[0] for period_id in self._cr.fetchall() ]
                res2 = {}
                if period_ids:
                    context2.update({'periods': period_ids, 'period_id': False})
                    #_logger.info("context2: %s" % context2)
                    res2 = rec.with_context(context2).__compute()
            res1 = rec.__compute()
            rec.argil_initial_balance = (periods and res2 and 'balance' in res2) and res2['balance'] or 0.0
            rec.argil_balance_all = ('balance' in res1 and res1['balance'] or 0.0) + ((periods and res2  and 'balance' in res2) and res2['balance'] or 0.0) 
            rec.debit  = 'debit' in res1 and res1['debit'] or 0.0
            rec.credit = 'credit' in res1 and res1['credit'] or 0.0
            rec.balance= 'balance' in res1 and res1['balance'] or 0.0
        
    
    argil_initial_balance = fields.Monetary(compute=_compute_argil, string='Initial Balance')
    argil_balance_all     = fields.Monetary(compute=_compute_argil, string='Balance All')
    balance               = fields.Monetary(compute=_compute_argil, string='Balance')
    credit                = fields.Monetary(compute=_compute_argil, string='Credit')
    debit                 = fields.Monetary(compute=_compute_argil, string='Debit')

    parent_id = fields.Many2one('account.account', string='Cuenta Padre', required=False, index=True)
    sign      = fields.Selection([('1.0', 'Deudora'), 
                                  ('-1.0', 'Acreedora')], 
                                  string='Naturaleza', required=True, default='1.0',
                                  help="Determina la naturaleza de la cuenta usada en los reportes")

    partner_breakdown = fields.Boolean(string='Desglosar Empresas en Balanza', index=True, default=False, 
                                       help= 'Si activa esta casilla se desglosará en la Balanza de Comprobación las empresas que conforman los cargos / abonos y saldos de esta cuenta')
    
    level             = fields.Integer(string='Nivel', store=True, readonly=True, compute='_get_level')

    
    child_parent_ids  = fields.One2many('account.account','parent_id', string='Children')
    child_consol_ids  = fields.Many2many('account.account', 'account_account_consol_rel', 'child_id', 'parent_id', string='Consolidated Children')
    child_id          = fields.Many2many('account.account', compute=_get_child_ids,  string="Child Accounts", store=False)

    
    @api.constrains('parent_id')
    def _check_parent_id_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('Error ! You cannot create recursive accounts.'))
        return True
    

    @api.depends('account_type')
    def _compute_internal_group(self):
        for account in self:
            if account.account_type:
                if account.account_type in ('off_balance', 'view','consolidation'):
                    account.internal_group = account.account_type
                else:
                    account.internal_group = account.account_type.split('_')[0]


class AccountChartOfAccountsArgilWizard(models.TransientModel):    
    """
    For Chart of Accounts
    """
    _name = "account.chart_argil"
    _description = "Account chart special"
    
    
    fiscalyear_id = fields.Many2one('account.fiscalyear', string='Periodo Anual', required=True,
                                   default=lambda self: self.env['account.fiscalyear'].search([('date_start', '<=', fields.Date.today()), ('date_stop', '>=', fields.Date.today()), ('company_id', '=', self.env.user.company_id.id)], limit=1))
    period_from   = fields.Many2one('account.period', string='Periodo Inicial', required=True,
                                   default=lambda self: self.env['account.period'].search([('date_start', '<=', fields.Date.today()), ('date_stop', '>=', fields.Date.today()), ('company_id', '=', self.env.user.company_id.id)], limit=1))
    
    period_to     = fields.Many2one('account.period', string='Periodo Final',required=True,
                                   default=lambda self: self.env['account.period'].search([('date_start', '<=', fields.Date.today()), ('date_stop', '>=', fields.Date.today()), ('company_id', '=', self.env.user.company_id.id)], limit=1))
    target_move   = fields.Selection([
                                        ('posted', 'All Posted Entries'),
                                        ('all', 'All Entries'),
                                ], string='Movimientos a incluir',required=True, default='posted')


    
    
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
