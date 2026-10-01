# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import time
import base64

import logging
_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit ='res.partner'

    l10n_mx_edi_usage = fields.Selection([
        ('G01', 'G01 - Adquisición de mercancias'),
        ('G02', 'G02 - Devoluciones, descuentos o bonificaciones'),
        ('G03', 'G03 - Gastos en general'),
        ('I01', 'I01 - Construcciones'),
        ('I02', 'I02 - Mobilario y equipo de oficina por inversiones'),
        ('I03', 'I03 - Equipo de transporte'),
        ('I04', 'I04 - Equipo de computo y accesorios'),
        ('I05', 'I05 - Dados, troqueles, moldes, matrices y herramienta'),
        ('I06', 'I06 - Comunicaciones telefónicas'),
        ('I07', 'I07 - Comunicaciones satelitales'),
        ('I08', 'I08 - Otra maquinaria y equipo'),
        ('D01', 'D01 - Honorarios médicos, dentales y gastos hospitalarios.'),
        ('D02', 'D02 - Gastos médicos por incapacidad o discapacidad'),
        ('D03', 'D03 - Gastos funerales'),
        ('D04', 'D04 - Donativos'),
        ('D05', 'D05 - Intereses reales efectivamente pagados por créditos hipotecarios (casa habitación)'),
        ('D06', 'D06 - Aportaciones voluntarias al SAR'),
        ('D07', 'D07 - Primas por seguros de gastos médicos'),
        ('D08', 'D08 - Gastos de transportación escolar obligatoria'),
        ('D09', 'D09 - Depósitos en cuentas para el ahorro, primas que tengan como base planes de pensiones.'),
        ('D10', 'D10 - Pagos por servicios educativos (colegiaturas)'),
        ('S01', 'Sin efectos fiscales'),
    ], 'Uso CFDI', default='S01')


    l10n_mx_edi_payment_method_id = fields.Many2one(
        comodel_name='l10n_mx_edi.payment.method',
        string="Forma de Pago",
        help="Indicates the way the invoice was/will be paid, where the options could be: "
             "Cash, Nominal Check, Credit Card, etc. Leave empty if unkown and the XML will show 'Unidentified'.")

    # @api.model
    # def create_from_ui(self, partner):
    #     res = super(ResPartner, self).create_from_ui(partner)
    #     return res


class AccountInvoice(models.Model):
    _name = 'account.move'
    _inherit ='account.move'


    @api.depends('journal_id')
    def _compute_l10n_mx_edi_payment_method_id(self):
        for move in self:
            if move.l10n_mx_edi_payment_method_id:
                move.l10n_mx_edi_payment_method_id = move.l10n_mx_edi_payment_method_id
            elif move.partner_id.l10n_mx_edi_payment_method_id:
                move.l10n_mx_edi_payment_method_id = move.partner_id.l10n_mx_edi_payment_method_id
            elif move.journal_id.l10n_mx_edi_payment_method_id:
                move.l10n_mx_edi_payment_method_id = move.journal_id.l10n_mx_edi_payment_method_id
            else:
                move.l10n_mx_edi_payment_method_id = self.env.ref('l10n_mx_edi.payment_method_otros', raise_if_not_found=False)


    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        # OVERRIDE
        res = super(AccountInvoice, self)._onchange_partner_id()
        if self.partner_id:
            self.l10n_mx_edi_usage = self.partner_id.l10n_mx_edi_usage
        if self.l10n_mx_edi_payment_method_id:
            self.l10n_mx_edi_payment_method_id = self.partner_id.l10n_mx_edi_payment_method_id.id
        return res

    @api.model
    def create(self, vals):
        res = super(AccountInvoice, self).create(vals)
        if not res.l10n_mx_edi_usage:
            res.l10n_mx_edi_usage = res.partner_id.l10n_mx_edi_usage
        if res.l10n_mx_edi_payment_method_id:
            res.l10n_mx_edi_payment_method_id = res.partner_id.l10n_mx_edi_payment_method_id.id
        return res
