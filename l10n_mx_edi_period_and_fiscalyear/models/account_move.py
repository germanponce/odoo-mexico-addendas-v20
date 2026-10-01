# -*- coding: utf-8 -*-

import time
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Account Move
#----------------------------------------------------------

class AccountMove(models.Model):
    _inherit = "account.move"

    
    def _check_lock_date(self):
        context = self._context
        check_move_validity_period = context.get('check_move_validity_period', True)
        res = super(AccountMove, self)._check_lock_date()
        for move in self:
            if move.period_id.state == 'done':
                if check_move_validity_period:
                    raise UserError(_("You cannot add/modify entries in Closed Period %s. Check the Period state" % (move.period_id.name)))
        return res

    
    @api.depends('closing_period','date','company_id')
    def _compute_period(self):
        """Compute Period using Date Move and Closing Period check.
        """
        company_id = self.env.company.id
        for move in self:
            sql = "select id from account_period where '%s' between date_start and date_stop and %s and company_id=%s;" % (move.date, move.closing_period and 'special=true' or '(special is null or special=false)', move.company_id.id or company_id)
            self._cr.execute(sql)
            res = self._cr.fetchall()
            if res:
                period_id = res[0][0]
                move.period_id = period_id
            else:
                #move.period_id = False
                any_period_in_db = False
                sql = "select id from account_period where company_id=%s limit 1;" % (move.company_id.id or company_id, )
                self._cr.execute(sql)
                res = self._cr.fetchall()
                if res and res[0] and res[0][0]:
                    any_period_in_db = res[0][0]
                if any_period_in_db:
                    raise UserError(_('No hay Periodo definido que corresponda a la fecha de la Póliza.'))
            
    
    period_id = fields.Many2one('account.period', string='Periodo', readonly=True, required=False,
                                compute='_compute_period', store=True)            
    closing_period = fields.Boolean(string="Mes de Ajuste", default=False)

    
    
    @api.constrains('closing_period','date')
    def _check_closing_period_and_date(self):
        period_obj = self.env['account.period']
        for move in self:
            if move.closing_period:
                period = period_obj.search([('special','=', True),('date_start', '>=', move.date), ('date_stop', '<=', move.date)], limit=1)
                if not period:
                    raise ValueError(_('Warning !!!\n\nYou have no Closing Period matching Account Move Date'))

    @api.constrains('period_id')
    def _check_period_and_date(self):
        context = self._context
        check_move_validity_period = context.get('check_move_validity_period', True)
        period_obj = self.env['account.period']
        for move in self:
            if check_move_validity_period:
                if 'use_asset_management' in move.journal_id._fields and not move.journal_id.use_asset_management:
                    if move.period_id and move.period_id.state == 'done':
                        raise UserError(_("No se pueden agregar/modificar asientos del periodo %s. Revisa el estado del periodo" % (move.period_id.name)))

    def write(self, vals):
        context = self._context
        check_move_validity_period = context.get('check_move_validity_period', True)
        campos = ['invoice_date','state','partner_id']
        if any(k in vals.keys() for k in campos):
            for rec in self:
                if check_move_validity_period:
                    if 'use_asset_management' in rec.journal_id._fields and not rec.journal_id.use_asset_management:
                        if rec.period_id and rec.period_id.state == 'done':
                            raise UserError(_("No se pueden agregar/modificar asientos del periodo %s. Revisa el estado del periodo" % (rec.period_id.name)))
        result = super(AccountMove, self).write(vals)
        return result
    
#----------------------------------------------------------
# Account Move Line
#----------------------------------------------------------

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"


    period_id = fields.Many2one('account.period', string='Period', related='move_id.period_id',
                                store=True, readonly=True, index=True, copy=False)


    @api.constrains('period_id','date','parent_state')
    def _check_period_and_date(self):
        context = self._context
        check_move_validity_period = context.get('check_move_validity_period', True)
        period_obj = self.env['account.period']
        for line in self:
            if check_move_validity_period:
                if 'use_asset_management' in line.move_id.journal_id._fields and not line.move_id.journal_id.use_asset_management:
                    if line.period_id and line.period_id.state == 'done':
                        raise UserError(_("No se pueden agregar/modificar apuntes del periodo %s. Revisa el estado del periodo" % (line.period_id.name)))

    def write(self, vals):
        context = self._context
        check_move_validity_period = context.get('check_move_validity_period', True)
        campos = ['debit','credit','partner_id', 'date','name']
        if any(k in vals.keys() for k in campos):
            for rec in self:
                if check_move_validity_period:
                    if 'use_asset_management' in rec.move_id.journal_id._fields and not rec.move_id.journal_id.use_asset_management:
                        if rec.period_id and rec.period_id.state == 'done':
                            raise UserError(_("No se pueden agregar/modificar apuntes del periodo %s. Revisa el estado del periodo" % (rec.period_id.name)))
        result = super(AccountMoveLine, self).write(vals)
        return result