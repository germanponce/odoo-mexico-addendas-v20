# -*- encoding: utf-8 -*-


from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class AccountGeneralLedgerWizardMX(models.TransientModel):
    _name="account.general_ledger.wizard"
    _description ="Wizard para obtener el Reporte de Diario General"
    
    
    date_from  = fields.Date(string="Fecha Inicial", required=True, default=fields.Date.context_today)
    date_to    = fields.Date(string="Fecha Final", required=True, default=fields.Date.context_today)
    journal_ids = fields.Many2many('account.journal', string='Diarios Contables', required=True, 
                                   default=lambda self: self.env['account.journal'].search([('company_id', '=', self.company_id.id)]))
    company_id = fields.Many2one('res.company', string='Company', required=True, 
                                 default=lambda self: self.env.company)
    target_move = fields.Selection([('posted', 'Confirmadas'),
                                    ('all', 'No Confirmadas y Confirmadas'),
                                    ], string='Tomar pólizas', required=True, default='posted')
    
    sort_selection = fields.Selection([('date', 'Fecha'), 
                                       ('name', 'Número de Póliza'),], 
                                      string='Ordenar por', required=True, default='date')
    
    flag = fields.Boolean(string="Bandera", default=False,
                         help="Si esta activo entonces el usuario seleccionó las pólizas a imprimir, caso contrario la información viene de Wizard")
    
    @api.model
    def default_get(self, fields):
        rec = super(AccountGeneralLedgerWizardMX, self).default_get(fields)
        active_ids = self._context.get('active_ids', False)
        active_model = self._context.get('active_model', False)
        rec.update({'journal_ids': self.env['account.journal'].search([]).ids})
        # Check for selected account moves
        if not active_ids and active_model !='account.move':
            return rec
        rec.update({'flag': True})
        return rec

    
    def get_report_info(self):
        if not self.journal_ids:
            raise ValidationError(_("Aviso !\nEs necesario seleccionar por lo menos un Diario Contable para obtener el reporte"))        
        domain = [('date','>=',self.date_from),
                  ('date','<=',self.date_to),
                  ('company_id','=',self.company_id.id),
                  ('journal_id','in',self.journal_ids.ids),]
        if self.target_move == 'posted':
            domain.append(('state','=','posted'))
        return self.env['account.move'].search(domain,order=self.sort_selection)
    
    
    def get_report(self):
        active_ids = self._context.get('active_ids', False)
        active_model = self._context.get('active_model', False)
        # Check for selected account moves
        datas = {}
        if self.flag:
            records = self.env['account.move'].browse(active_ids)
            return self.env.ref('l10n_mx_edi_account_report_general_journey.report_general_ledger_action')\
            .report_action(records)
        else:
            records = self.get_report_info()
            datas.update({'model' : 'account.move',
                          'ids'   : records.ids,})
            datas['form'] = self.read(['date_from', 'date_to', 'journal_ids', 
                              'target_move', 'sort_selection', 'flag'])[0]

            if not records:
                raise UserError("No existe información")
            
            return self.env.ref('l10n_mx_edi_account_report_general_journey.report_general_ledger_action')\
                .report_action(records)

        
        
        
        
        