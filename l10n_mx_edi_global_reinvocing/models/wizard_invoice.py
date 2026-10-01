# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError

from odoo.tools import float_is_zero, float_compare
from itertools import groupby
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)


MAX_HASH_VERSION = 3

PAYMENT_STATE_SELECTION = [
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
]

TYPE_REVERSE_MAP = {
    'entry': 'entry',
    'out_invoice': 'out_refund',
    'out_refund': 'entry',
    'in_invoice': 'in_refund',
    'in_refund': 'entry',
    'out_receipt': 'out_refund',
    'in_receipt': 'in_refund',
}

EMPTY = object()

class PosConfig(models.Model):
    _inherit = "pos.config"

    cfdi_global_manual_signed = fields.Boolean('Timbrado Manual Devoluciones (Global)', default=True)

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cfdi_global_manual_signed = fields.Boolean('Timbrado Manual Devoluciones (Global)',
        related="pos_config_id.cfdi_global_manual_signed", readonly=False)

    
class PosOrder(models.Model):
    _inherit ='pos.order'

    partner_global_id = fields.Many2one('res.partner', 'Partner Previo Global')

    l10n_mx_edi_folio_fiscal_all = fields.Char(
        string='Folio Fiscal', compute='_compute_l10n_mx_edi_folio_fiscal_all')

    def _compute_l10n_mx_edi_folio_fiscal_all(self):
        # Folio fiscal (UUID) del CFDI timbrado sobre la propia orden POS
        # (global / devolucion-egreso) o del de su factura individual (account.move).
        for order in self:
            order.l10n_mx_edi_folio_fiscal_all = order.l10n_mx_edi_cfdi_uuid or order.account_move.l10n_mx_edi_cfdi_uuid or False

    ########## Desactivamos la generación automatica del CFDI ###############
    def _l10n_mx_edi_check_autogenerate_cfdi_refund(self):
        for order in self:
            if order.session_id.config_id.cfdi_global_manual_signed:
                _logger.info("\n *************** Acción desactivada .................................")
            else:
                return super(PosOrder, self)._l10n_mx_edi_check_autogenerate_cfdi_refund()
            # if (
            #     order.company_id.country_id.code == 'MX'
            #     and not order.l10n_mx_edi_cfdi_state
            #     and any(x.l10n_mx_edi_cfdi_state == 'global_sent' for x in order.refunded_order_id)
            # ):
            #     order._l10n_mx_edi_cfdi_invoice_try_send()

######### Inicio Factura Global - PUNTO DE VENTA ###########

class pos_order_invoice_wizard(models.TransientModel):
    _name = "pos.order.invoice_wizard"
    _description = "Wizard Factura POS"


    @api.model  
    def default_get(self, fields):
        cr = self.env.cr
        res = super(pos_order_invoice_wizard, self).default_get(fields)
        record_ids = self.env.context.get('active_ids', []) # [0:500] # BORRAR 0:500
        pos_order_obj = self.env['pos.order']
        journal_id = False
        if not record_ids:
            return {}
        tickets = []
        l10n_mx_edi_usage = ''
        payment_tpv_id = False
        is_refund = False
        l10n_mx_edi_cfdi_to_public = False
        for ticket in pos_order_obj.browse(record_ids):
            l10n_mx_edi_usage = ticket.l10n_mx_edi_usage
            payment_tpv_id = ticket.l10n_mx_edi_payment_method_id.id if ticket.l10n_mx_edi_payment_method_id else False
            if not ticket.l10n_mx_edi_cfdi_uuid:
                if ticket.amount_total > 0.0:
                    raise UserError("El Pedido POS no esta asociado a una Factura Global.")
            if ticket.session_id and ticket.session_id.config_id:
                if ticket.session_id.config_id.invoice_journal_id:
                    journal_id = ticket.session_id.config_id.invoice_journal_id.id
            if ticket.amount_total < 0.0:
                is_refund = True
            if ticket.l10n_mx_edi_cfdi_to_public:
                l10n_mx_edi_cfdi_to_public = True
        if is_refund:
            account_move_refunded = False
            if ticket.refunded_order_id:
                account_move_refunded = ticket.refunded_order_id[-1].account_move

            if l10n_mx_edi_cfdi_to_public:
                if account_move_refunded:
                    res.update(operations_extra_type='associate_nc_reinvoicing')
                else:
                    res.update(operations_extra_type='associate_pos_refund_global')
            else:
                if ticket.refunded_order_id:
                    account_move = ticket.refunded_order_id[-1].account_move
                    if account_move:
                        res.update(operations_extra_type='associate_nc_invoice_customer')
        if journal_id:
            res.update(journal_id=journal_id)
        if l10n_mx_edi_usage:
            res.update(l10n_mx_edi_usage=l10n_mx_edi_usage)
        if payment_tpv_id:
            res.update(payment_tpv_id=payment_tpv_id)
        return res

    date       = fields.Date(string='Fecha', default=fields.Date.context_today, required=True,
                              help='This date will be used as the invoice date and period will be chosen accordingly!')
    
    journal_id = fields.Many2one('account.journal', string='Diario Facturacion', required=True)

    partner_id = fields.Many2one('res.partner', 'Cliente')
    create_nc = fields.Boolean('Crear Nota de Crédito')

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

    payment_tpv_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago SAT')

    reconcile_automatic_payments = fields.Boolean('Conciliar los Pagos', help="Concilia los Pagos de los Tickets de forma automatica, este proceso puede alentar el sistema.")

    process_invoice_ok = fields.Boolean('Factura Creada')
    process_invoice_id = fields.Integer('Ultima Factura Creada')


    operations_extra_type = fields.Selection([
                                                ('none', 'Ninguna'),
                                                ('associate_nc_reinvoicing', '1. Nota de Crédito asociada con Re-facturación (Factura Cliente)'),
                                                ('associate_nc_reinvoicing_to_global', '2. Nota de Crédito asociada a Global (Devoluciones)'),
                                                ('associate_nc_invoice_customer', '3. Nota de crédito a Factura de Cliente (No Global)'),
                                                ('associate_pos_refund_global', '4. Timbrado de Devolución a (CFDI Global).'),
                                             ], 'Operaciones Extra', required=True, default="none")

    new_invoice_id = fields.Many2one('account.move', 'Asociar a Facturar')

    invoice_payment_term_id = fields.Many2one('account.payment.term', 'Terminos de Pago')

    @api.onchange('create_nc','reconcile_automatic_payments')
    def onchange_paid_invoice(self):
        if self.create_nc and self.reconcile_automatic_payments:
            raise UserError("Solo puedes Seleccionar una Opción.\n* Crear NC\n* Conciliar Pagos")

    @api.onchange('partner_id','operations_extra_type')
    def onchange_full_workflow_re_invoicing(self):
        if self.partner_id and self.operations_extra_type == 'none':
            self.create_nc = True


    ######## Operaciones Extras ########+
    @api.onchange('operations_extra_type')
    def onchange_operations_extra_type(self):
        pos_order_obj = self.env['pos.order']
        record_ids = self.env.context.get('active_ids', [])
        record_id = self.env.context.get('active_id', False)
        pos_br = pos_order_obj.browse(record_id)
        if self.operations_extra_type:
            if self.operations_extra_type == 'associate_nc_reinvoicing':
                self.new_invoice_id = pos_br.account_move if pos_br.account_move else False
                self.partner_id = pos_br.account_move.partner_id if pos_br.account_move else False
                self.create_nc = False
            elif self.operations_extra_type == 'associate_nc_reinvoicing_to_global':
                self.partner_id = pos_br.partner_id.id if pos_br.partner_id else False
                self.create_nc = False
            elif self.operations_extra_type == 'associate_nc_invoice_customer':
                self.partner_id = pos_br.partner_id
                self.create_nc = False
            elif self.operations_extra_type == 'associate_pos_refund_global':
                self.partner_id = pos_br.partner_id.id if pos_br.partner_id else False
                self.create_nc = False

    def generate_credit_note_and_related_to_global(self, ticket):
        public_partner_prev = ticket.partner_id
        l10n_mx_edi_origin = ""
        ticket_origin = ""
        if ticket.refunded_order_id:
            l10n_mx_edi_origin = ticket.refunded_order_id[-1].l10n_mx_edi_cfdi_uuid
            ticket_origin = ticket.refunded_order_id[-1].name
        if not l10n_mx_edi_origin:
            raise UserError("El ticket origen (%s) de la devolción no tiene un folio fiscal global." % ticket_origin)

        ticket_company_id = ticket.company_id
        lines_to_invoice = []
        move_vals = ticket._prepare_invoice_vals()
        credit_note_br = ticket._create_invoice(move_vals)
        sh_pos_order_analytic_account = False
        for ticket_line in ticket.lines:
            if ticket_line.sh_pos_order_analytic_account:
                sh_pos_order_analytic_account = ticket_line.sh_pos_order_analytic_account

        for line in credit_note_br.invoice_line_ids:
            if sh_pos_order_analytic_account:
                sh_pos_order_analytic_account_id = sh_pos_order_analytic_account.id
                line.write({'analytic_distribution' : {sh_pos_order_analytic_account_id: 100} })

        import pytz

        timezone = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')


        condonation_l10n_mx_edi_payment_method_id = self.env['l10n_mx_edi.payment.method'].search([('code','=','15')], limit=1)

        l10n_mx_edi_payment_method_id = condonation_l10n_mx_edi_payment_method_id if condonation_l10n_mx_edi_payment_method_id else self.payment_tpv_id
        # l10n_mx_edi_usage = 'G02'
        # l10n_mx_edi_usage = self.l10n_mx_edi_usage
        l10n_mx_edi_usage = 'S01'

        l10n_mx_edi_origin_cn = ""
        if l10n_mx_edi_origin:
            l10n_mx_edi_origin_cn = '01|'+l10n_mx_edi_origin if l10n_mx_edi_origin else ''

        credit_note_br.write({
                                    'l10n_mx_edi_payment_policy': 'PUE',
                                    # 'l10n_mx_edi_payment_method_id': condonation_l10n_mx_edi_payment_method_id.id,
                                    'l10n_mx_edi_cfdi_origin': l10n_mx_edi_origin_cn,
                                    'narration': 'Factura Global [ '+l10n_mx_edi_origin+' ]',
                                    'journal_id': self.journal_id.id,
                                    # 'l10n_mx_edi_usage': 'G02',
                                    'l10n_mx_edi_usage': l10n_mx_edi_usage,
                             })
        if not credit_note_br.l10n_mx_edi_payment_method_id:
            credit_note_br.l10n_mx_edi_payment_method_id = self.payment_tpv_id.id

        # self.write({
        #                 'process_invoice_ok': True,
        #                 'process_invoice_id': credit_note_br.id
        #             })
        # credit_note_br.l10n_mx_edi_payment_method_id = condonation_l10n_mx_edi_payment_method_id.id if condonation_l10n_mx_edi_payment_method_id else self.payment_tpv_id.id
        # credit_note_br.l10n_mx_edi_usage = 'G02'
        credit_note_br.l10n_mx_edi_usage = l10n_mx_edi_usage

        if l10n_mx_edi_origin:
            credit_note_br.write({
                                    'l10n_mx_edi_cfdi_origin': l10n_mx_edi_origin_cn,
                                 })

        #### Revisión de Lineas ######
        for line in credit_note_br.invoice_line_ids:
            if line.price_subtotal == 0.0:
                line.unlink()

        if not credit_note_br.l10n_mx_edi_payment_method_id:
            credit_note_br.l10n_mx_edi_payment_method_id = self.payment_tpv_id.id

        body_html = "Creación de la Nota de Credito de la Factura Global: <strong>%s</strong>" % l10n_mx_edi_origin if l10n_mx_edi_origin else ""
        credit_note_br.message_post(
                                    body=body_html
                                )

        #### Validamos la Factura ####
        credit_note_br.sudo().with_company(ticket_company_id)._post()
        if not credit_note_br.l10n_mx_edi_cfdi_uuid:
            if credit_note_br.state == 'draft':
                credit_note_br._post()
            #### Timbrando ####
            # v19 MIGRATION FIX: 'account.move.send' ya es un AbstractModel en
            # Odoo 19 (no se puede instanciar con .create()), y el campo
            # 'l10n_mx_edi_checkbox_cfdi' ya no existe -- el CFDI MX ahora se ofrece
            # automaticamente via _get_all_extra_edis()/_is_mx_edi_applicable(). La
            # forma correcta y soportada de timbrar por codigo es llamar
            # directo al metodo que usa el propio core en ese mismo wizard.
            credit_note_br._l10n_mx_edi_cfdi_invoice_try_send()
            if credit_note_br.l10n_mx_edi_cfdi_state != 'sent':
                raise UserError("Este asistente ya creó la nota de credito, pero no pudo timbrarse debido a errores de captura de datos fiscales, verifica desde el modulo contable la factura con el ID: %s. Verificala y corrige los datos o eliminala y vuelvela a refacturar." % credit_note_br.id)
        
        ##### Aplicando el Pago a la Factura - Aplicando Pagos del Pedido al POS ORDER ####
        ticket.write({
                        'invoice_status': 'invoiced', 
                        'account_move':  credit_note_br.id,
                        'partner_id': self.partner_id.id,
                        'l10n_mx_edi_cfdi_to_public': False,
                        'partner_global_id': public_partner_prev.id,
                    })
        context = self.env.context
        # credit_note_br = self.env['account.move'].sudo().with_context(default_move_type='out_refund').create(invoice_vals)
        # credit_note_br._post(soft=False)
        #### Forzamos el Commit para Guardar la Nota de Credito Conciliada ####
        ticket._apply_invoice_payments()

        return credit_note_br

    def generate_credit_note_associate_invoice_customer(self, ticket):
        public_partner_prev = ticket.partner_id
        
        l10n_mx_edi_origin = ""
        ticket_origin_br = ""
        ticket_origin_invoice = False
        if ticket.refunded_order_id:
            for ticket_origin in ticket.refunded_order_id:
                ticket_origin_br = ticket_origin
                if ticket_origin.account_move:
                    ticket_origin_invoice = ticket_origin.account_move
        if ticket_origin_invoice and ticket_origin_invoice.l10n_mx_edi_cfdi_uuid:
            l10n_mx_edi_origin = ticket_origin_invoice.l10n_mx_edi_cfdi_uuid
        if not l10n_mx_edi_origin:
            raise UserError("El ticket origen (%s) de la devolción no tiene un folio fiscal o una factura." % ticket_origin_br.name)
            
        ticket_company_id = ticket.company_id
        lines_to_invoice = []
        move_vals = ticket._prepare_invoice_vals()
        credit_note_br = ticket._create_invoice(move_vals)
        sh_pos_order_analytic_account = False
        for ticket_line in ticket.lines:
            if ticket_line.sh_pos_order_analytic_account:
                sh_pos_order_analytic_account = ticket_line.sh_pos_order_analytic_account

        for line in credit_note_br.invoice_line_ids:
            if sh_pos_order_analytic_account:
                sh_pos_order_analytic_account_id = sh_pos_order_analytic_account.id
                line.write({'analytic_distribution' : {sh_pos_order_analytic_account_id: 100} })

        import pytz

        timezone = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')

        condonation_l10n_mx_edi_payment_method_id = self.env['l10n_mx_edi.payment.method'].search([('code','=','15')], limit=1)

        l10n_mx_edi_payment_method_id = condonation_l10n_mx_edi_payment_method_id if condonation_l10n_mx_edi_payment_method_id else self.payment_tpv_id
        # l10n_mx_edi_usage = 'G02'
        # l10n_mx_edi_usage = self.l10n_mx_edi_usage
        l10n_mx_edi_usage = 'S01'

        l10n_mx_edi_origin_cn = ""
        if l10n_mx_edi_origin:
            l10n_mx_edi_origin_cn = '01|'+l10n_mx_edi_origin if l10n_mx_edi_origin else ''

        credit_note_br.write({
                                    'l10n_mx_edi_payment_policy': 'PUE',
                                    # 'l10n_mx_edi_payment_method_id': condonation_l10n_mx_edi_payment_method_id.id,
                                    'l10n_mx_edi_cfdi_origin': l10n_mx_edi_origin_cn,
                                    'narration': 'Factura Origen [ '+l10n_mx_edi_origin+' ]',
                                    'journal_id': self.journal_id.id,
                                    # 'l10n_mx_edi_usage': 'G02',
                                    'l10n_mx_edi_usage': l10n_mx_edi_usage,
                             })
        if not credit_note_br.l10n_mx_edi_payment_method_id:
            if ticket.payment_tpv_id:
                credit_note_br.l10n_mx_edi_payment_method_id = ticket.payment_tpv_id.id
        # self.write({
        #                 'process_invoice_ok': True,
        #                 'process_invoice_id': credit_note_br.id
        #             })
        # credit_note_br.l10n_mx_edi_payment_method_id = condonation_l10n_mx_edi_payment_method_id.id if condonation_l10n_mx_edi_payment_method_id else self.payment_tpv_id.id
        # credit_note_br.l10n_mx_edi_usage = 'G02'
        credit_note_br.l10n_mx_edi_usage = l10n_mx_edi_usage

        if l10n_mx_edi_origin:
            credit_note_br.write({
                                    'l10n_mx_edi_cfdi_origin': l10n_mx_edi_origin_cn,
                                 })

        #### Revisión de Lineas ######
        for line in credit_note_br.invoice_line_ids:
            if line.price_subtotal == 0.0:
                line.unlink()

        if not credit_note_br.l10n_mx_edi_payment_method_id:
            credit_note_br.l10n_mx_edi_payment_method_id = ticket.payment_tpv_id.id

        body_html = "Creación de la Nota de Credito de la Factura de Cliente: <strong>%s</strong>" % l10n_mx_edi_origin if l10n_mx_edi_origin else ""
        credit_note_br.message_post(
                                    body=body_html
                                )

        #### Validamos la Factura ####
        credit_note_br.sudo().with_company(ticket_company_id)._post()
        if not credit_note_br.l10n_mx_edi_cfdi_uuid:
            if credit_note_br.state == 'draft':
                credit_note_br._post()
            #### Timbrando ####
            # v19 MIGRATION FIX: 'account.move.send' ya es un AbstractModel en
            # Odoo 19 (no se puede instanciar con .create()), y el campo
            # 'l10n_mx_edi_checkbox_cfdi' ya no existe -- el CFDI MX ahora se ofrece
            # automaticamente via _get_all_extra_edis()/_is_mx_edi_applicable(). La
            # forma correcta y soportada de timbrar por codigo es llamar
            # directo al metodo que usa el propio core en ese mismo wizard.
            credit_note_br._l10n_mx_edi_cfdi_invoice_try_send()
            if credit_note_br.l10n_mx_edi_cfdi_state != 'sent':
                raise UserError("Este asistente ya creó la nota de credito, pero no pudo timbrarse debido a errores de captura de datos fiscales, verifica desde el modulo contable la factura con el ID: %s. Verificala y corrige los datos o eliminala y vuelvela a refacturar." % credit_note_br.id)
        
        ##### Aplicando el Pago a la Factura - Aplicando Pagos del Pedido al POS ORDER ####
        ticket.write({
                        'invoice_status': 'invoiced', 
                        'account_move':  credit_note_br.id,
                        'partner_id': self.partner_id.id,
                        'l10n_mx_edi_cfdi_to_public': False,
                    })
        context = self.env.context
        # credit_note_br = self.env['account.move'].sudo().with_context(default_move_type='out_refund').create(invoice_vals)
        # credit_note_br._post(soft=False)
        #### Forzamos el Commit para Guardar la Nota de Credito Conciliada ####
        ticket._apply_invoice_payments()

        return credit_note_br

    def generate_associate_pos_refund_global(self, ticket):
        _logger.info("\n############ generate_associate_pos_refund_global >>>>>>>>>>>>>>>>>>> ")
        if (
            ticket.company_id.country_id.code == 'MX'
            and not ticket.l10n_mx_edi_cfdi_state
            and any(x.l10n_mx_edi_cfdi_state == 'global_sent' for x in ticket.refunded_order_id)
        ):
            _logger.info("\n########## ticket.refunded_order_id: %s " % ticket.refunded_order_id)
            ctx2 = {
                        'active_model':'pos.order',
                        'active_ids': [ticket.id],
                        'active_id': ticket.id
                    }
            result_global_refund = ticket.with_context(ctx2)._l10n_mx_edi_cfdi_invoice_try_send()
        return ticket

    def execute_operations_extra_type(self):
        _logger.info("\n############ execute_operations_extra_type >>>>>>>>>>>>>>>>>>> ")
        invoice_ids = []
        pos_order_obj = self.env['pos.order']
        record_ids = self.env.context.get('active_ids', [])
        record_id = self.env.context.get('active_id', False)
        pos_br = pos_order_obj.browse(record_id)
        pos_partner_global_id = pos_br.partner_global_id
        pos_partner_id = pos_br.partner_id
        for rec in self:
            new_partner_id = rec.new_invoice_id.partner_id
            new_invoice_id = rec.new_invoice_id
            l10n_mx_edi_origin = pos_br.l10n_mx_edi_cfdi_uuid
            if rec.operations_extra_type == 'associate_nc_reinvoicing':
                credit_note_id = self.with_context(pos_order_ids=record_ids).create_refund_and_reconcile(new_invoice_id)
                #credit_note_id = self.with_context(pos_order_ids=record_ids).create_refund_from_global(invoice_vals, )
                credit_note_br = self.env['account.move'].sudo().browse(credit_note_id)
                condonation_l10n_mx_edi_payment_method_id = self.env['l10n_mx_edi.payment.method'].search([('code','=','15')], limit=1)
                # if not credit_note_br.l10n_mx_edi_payment_method_id:
                if not credit_note_br.l10n_mx_edi_payment_method_id:
                    if self.payment_tpv_id:
                        credit_note_br.l10n_mx_edi_payment_method_id = self.payment_tpv_id.id

                # credit_note_br.l10n_mx_edi_payment_method_id = condonation_l10n_mx_edi_payment_method_id.id if condonation_l10n_mx_edi_payment_method_id else self.payment_tpv_id.id
                # credit_note_br.l10n_mx_edi_usage = 'G02'
                # credit_note_br.l10n_mx_edi_usage = new_invoice_id.l10n_mx_edi_usage
                credit_note_br.l10n_mx_edi_usage = 'S01'

                if l10n_mx_edi_origin:
                    l10n_mx_edi_origin_cn = '01|'+l10n_mx_edi_origin if l10n_mx_edi_origin else ''
                    credit_note_br.write({
                                            'l10n_mx_edi_cfdi_origin': l10n_mx_edi_origin_cn,
                                         })

                credit_note_br.write({'invoice_origin_rel_id': new_invoice_id.id})

                if not credit_note_br.l10n_mx_edi_cfdi_uuid:
                    if credit_note_br.state == 'draft':
                        credit_note_br._post()

                    #### Timbrando ####
                    # v19 MIGRATION FIX: ver nota en generate_credit_note_and_related_to_global.
                    credit_note_br._l10n_mx_edi_cfdi_invoice_try_send()


                body_html = "Nota de Credito de la Factura Global: <strong>%s</strong>" % l10n_mx_edi_origin if l10n_mx_edi_origin else ""
                new_invoice_id.message_post(
                                            body=body_html
                                        )

                invoice_ids.append(int(new_invoice_id.id))
                invoice_ids.append(int(credit_note_id))
            elif rec.operations_extra_type == 'associate_nc_reinvoicing_to_global':
                credit_note_br = self.generate_credit_note_and_related_to_global(pos_br)
                invoice_ids.append(int(credit_note_br.id))
            elif rec.operations_extra_type == 'associate_nc_invoice_customer':
                credit_note_br = self.generate_credit_note_associate_invoice_customer(pos_br)
                invoice_ids.append(int(credit_note_br.id))
            elif rec.operations_extra_type == 'associate_pos_refund_global':
                pos_signed_global = self.generate_associate_pos_refund_global(pos_br)
                action = {'type': 'ir.actions.act_window_close'}
                return action
        if len(invoice_ids) > 1:
            action_invoices = self.env.ref('account.action_move_out_invoice_type')
            action = action_invoices.read()[0]
            action['context'] = {}
            action['domain'] = [('id', 'in',invoice_ids)]
            return action
        else:
            return {
                        'name': "Re-facturación",
                        'view_mode': 'form',
                        'view_id': self.env.ref('account.view_move_form').id,
                        'res_model': 'account.move',
                        'context': "{}", # self.env.context
                        'type': 'ir.actions.act_window',
                        'res_id': invoice_ids[0] if invoice_ids else False,
                    }
                
    ######## Refacturación #############
    def create_re_invoice_from_sales(self):
        invoice_ids = []
        pos_order_obj = self.env['pos.order']
        record_ids = self.env.context.get('active_ids', [])
        if self.create_nc and self.reconcile_automatic_payments:
            raise UserError("Solo puedes Seleccionar una Opción.\n* Crear NC\n* Conciliar Pagos")
        # print ("######### process_invoice_ok: ", self.process_invoice_ok)
        # print ("######### process_invoice_id: ", self.process_invoice_id)
        if self.process_invoice_ok:
            process_invoice_id = self.process_invoice_id or 0
            raise UserError("Este asistente ya creó la factura, pero no pudo timbrarse debido a errores de captura de datos fiscales, verifica desde el modulo contable la factura con el ID: %s. Verificala y corrige los datos o eliminala y vuelvela a refacturar." % process_invoice_id)
        lines_to_invoice = []
        l10n_mx_edi_origin = ""
        public_partner_prev = False
        for ticket in pos_order_obj.browse(record_ids):
            public_partner_prev = ticket.partner_id
            l10n_mx_edi_origin = ticket.l10n_mx_edi_cfdi_uuid
            ticket_company_id = ticket.company_id
            for line in ticket.lines:
                product_id = line.product_id
                account = product_id.property_account_income_id or product_id.categ_id.property_account_income_categ_id
                if not account:
                    raise UserError(_('Por favor crea una cuenta para el producto: "%s" (id:%d) - or for its category: "%s".') %
                        (product_id.name, product_id.id, product_id.categ_id.name))

                fpos = ticket.fiscal_position_id or self.partner_id.property_account_position_id
                if fpos:
                    account = fpos.map_account(account)            

                tax_ids_after_fiscal_position = line.tax_ids_after_fiscal_position.ids if line.tax_ids_after_fiscal_position else False
                line_vals = {
                                #'noidentificacion': product_id.default_code,
                                'product_id': product_id.id,
                                'name': product_id.display_name,
                                'quantity': line.qty,
                                'account_id': account.id,
                                'product_uom_id': line.product_uom_id.id,
                                'tax_ids': [(6,0,tax_ids_after_fiscal_position)] if tax_ids_after_fiscal_position else False,
                                'price_unit':line.price_unit,
                                'discount': line.discount,
                                #'sale_line_ids': [(6,0,order_line_ids)],
                                #'analytic_account_id': ticket.account_analytic_id.id if ticket.account_analytic_id else False,
                            }
                if line.sh_pos_order_analytic_account:
                    sh_pos_order_analytic_account = line.sh_pos_order_analytic_account

                    sh_pos_order_analytic_account_id = sh_pos_order_analytic_account.id
                    line_vals.update({'analytic_distribution' : {sh_pos_order_analytic_account_id: 100} })

                lines_to_invoice.append((0,0,line_vals))

        import pytz

        timezone = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')

        invoice_vals = {
                            'partner_id': self.partner_id.id,
                            'l10n_mx_edi_payment_policy': 'PUE',
                            'l10n_mx_edi_usage': self.l10n_mx_edi_usage,
                            'l10n_mx_edi_payment_method_id': self.payment_tpv_id.id,
                            'journal_id': self.journal_id.id,
                            'invoice_date': self.date,
                            'invoice_line_ids': lines_to_invoice,
                            'narration': 'Factura Global [ '+l10n_mx_edi_origin+' ]',
                            'move_type': 'out_invoice',
                        }
        if self.invoice_payment_term_id:
            invoice_vals['invoice_payment_term_id'] = self.invoice_payment_term_id.id
        invoice_id = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(invoice_vals)
        invoice_id.write({'journal_id': self.journal_id.id})
        self.write({
                        'process_invoice_ok': True,
                        'process_invoice_id': invoice_id.id
                    })
        #### Revisión de Lineas ######
        for line in invoice_id.invoice_line_ids:
            if line.price_subtotal == 0.0:
                line.unlink()

        if not invoice_id.l10n_mx_edi_payment_method_id:
            invoice_id.l10n_mx_edi_payment_method_id = self.payment_tpv_id.id

        body_html = "Re-facturación de la Factura Global: <strong>%s</strong>" % l10n_mx_edi_origin if l10n_mx_edi_origin else ""
        invoice_id.message_post(
                                    body=body_html
                                )

        #### Validamos la Factura ####
        invoice_id.sudo().with_company(ticket_company_id)._post()
        # print ("######### process_invoice_ok: ", self.process_invoice_ok)
        # print ("######### invoice_id: ", invoice_id)
        if not invoice_id.l10n_mx_edi_cfdi_uuid:
            if invoice_id.state == 'draft':
                invoice_id._post()
            #### Timbrando ####
            # v19 MIGRATION FIX: ver nota en generate_credit_note_and_related_to_global.
            invoice_id._l10n_mx_edi_cfdi_invoice_try_send()
            # if invoice_id.l10n_mx_edi_cfdi_state != 'sent':
            #     process_invoice_id = self.process_invoice_id or 0
            #     raise UserError("Este asistente ya creó la factura, pero no pudo timbrarse debido a errores de captura de datos fiscales, verifica desde el modulo contable la factura con el ID: %s. Verificala y corrige los datos o eliminala y vuelvela a refacturar." % process_invoice_id)
        
        ##### Aplicando el Pago a la Factura - Aplicando Pagos del Pedido al POS ORDER ####
        self.env['pos.order'].browse(record_ids).write({
                                                            'invoice_status': 'invoiced', 
                                                            'account_move':  invoice_id.id,
                                                            'partner_id': self.partner_id.id,
                                                            'l10n_mx_edi_cfdi_to_public': False,
                                                            'partner_global_id': public_partner_prev.id,
                                                        })

        invoice_ids = [invoice_id.id]
        ######## Creación de NC #############
        if self.create_nc:
            credit_note_id = self.with_context(pos_order_ids=record_ids).create_refund_and_reconcile(invoice_id)
            #credit_note_id = self.with_context(pos_order_ids=record_ids).create_refund_from_global(invoice_vals, )
            credit_note_br = self.env['account.move'].sudo().browse(credit_note_id)
            condonation_l10n_mx_edi_payment_method_id = self.env['l10n_mx_edi.payment.method'].search([('code','=','15')], limit=1)
            # if not credit_note_br.l10n_mx_edi_payment_method_id:
            # credit_note_br.l10n_mx_edi_payment_method_id = condonation_l10n_mx_edi_payment_method_id.id if condonation_l10n_mx_edi_payment_method_id else self.payment_tpv_id.id
            if not credit_note_br.l10n_mx_edi_payment_method_id:
                if self.payment_tpv_id:
                    credit_note_br.l10n_mx_edi_payment_method_id = self.payment_tpv_id.id
            # credit_note_br.l10n_mx_edi_usage = 'G02'
            # credit_note_br.l10n_mx_edi_usage = invoice_id.l10n_mx_edi_usage
            credit_note_br.l10n_mx_edi_usage = 'S01'

            if l10n_mx_edi_origin:
                l10n_mx_edi_origin_cn = '01|'+l10n_mx_edi_origin if l10n_mx_edi_origin else ''
                credit_note_br.write({
                                        'l10n_mx_edi_cfdi_origin': l10n_mx_edi_origin_cn,
                                     })

            credit_note_br.write({'invoice_origin_rel_id': invoice_id.id})

            if not credit_note_br.l10n_mx_edi_cfdi_uuid:
                if credit_note_br.state == 'draft':
                    credit_note_br._post()

                #### Timbrando ####
                # v19 MIGRATION FIX: ver nota en generate_credit_note_and_related_to_global.
                credit_note_br._l10n_mx_edi_cfdi_invoice_try_send()


            body_html = "Nota de Credito de la Factura Global: <strong>%s</strong>" % l10n_mx_edi_origin if l10n_mx_edi_origin else ""
            invoice_id.message_post(
                                        body=body_html
                                    )

            invoice_ids.append(int(credit_note_id))

        ##### Aplicando el Pago a la Factura - Aplicando Pagos del Pedido al POS ORDER ####

        if self.reconcile_automatic_payments:
            if record_ids:
                tickets_n = len(record_ids)
                tickt_i = 1
                if self.reconcile_automatic_payments:
                    for ticket in pos_order_obj.browse(record_ids):
                        _logger.info("\n########### Ticket %s de %s .................... " % (tickt_i, tickets_n))
                        tickt_i += 1
                        # BORRAR - DESCOMENTAR
                        if ticket.account_move:
                            ticket._apply_invoice_payments()

        if len(invoice_ids) > 1:
            action_invoices = self.env.ref('account.action_move_out_invoice_type')
            action = action_invoices.read()[0]
            action['context'] = {}
            action['domain'] = [('id', 'in',invoice_ids)]
            return action
        else:
            return {
                        'name': "Re-facturación",
                        'view_mode': 'form',
                        'view_id': self.env.ref('account.view_move_form').id,
                        'res_model': 'account.move',
                        'context': "{}", # self.env.context
                        'type': 'ir.actions.act_window',
                        'res_id': invoice_ids[0] if invoice_ids else False,
                    }

    ####### Generacion y Conciliacion Automatica Nota de Credito #######

    def create_refund_from_global(self, invoice_vals):
        context = self.env.context
        invoice_vals['move_type'] = 'out_refund'
        _logger.info("\n############ invoice_vals: %s " % invoice_vals)
        credit_note_id = self.env['account.move'].sudo().with_context(default_move_type='out_refund').create(invoice_vals)
        credit_note_id._post(soft=False)
        #### Forzamos el Commit para Guardar la Nota de Credito Conciliada ####
        return credit_note_id.id


    def create_refund_and_reconcile(self, invoice_origin):
        context = self.env.context
        credit_note_id = False
        pos_order_ids = context.get('pos_order_ids', [])
        global_refund_partially = context.get('global_refund_partially', False)
        _logger.info("\n############ create_refund_and_reconcile >>>>>>>>>>>>>>>> ")
        _logger.info("\n############ global_refund_partially: %s " % global_refund_partially)
        #### Nota de Credito Automatica #####

        wizard_invoice_refund = self.env["account.move.reversal"].sudo()
        wizard_context = {
            'active_id': invoice_origin.id,
            'active_ids': [invoice_origin.id],
            'active_model': 'account.move',
            'origin_reinvoice_pos': True,
        }
        reason_refund = 'NC - Re-facturación'
        ## Almacenamos la Ref. del nombre del Pedido en Linea ##
        wizard_vals = {
                        'move_ids': [(6,0, [invoice_origin.id])],
                        'reason': reason_refund,
                        # 'filter_refund': 'refund',
                        # 'refund_method': 'cancel',
                        'journal_id': self.journal_id.id
                       }
        wizard_inst = wizard_invoice_refund.with_context(wizard_context).create(wizard_vals)

        _logger.info("\n::::::::::::: wizard_inst >>>>>>>>>>>>>>>> %s " % wizard_inst)
        ## Variables para regresar el Diario a su estado Original ##
        
        #### Creamos la Nota de Credito #####
        refund_result = wizard_inst.with_context(reinvoice_from_global=True, pos_order_ids=pos_order_ids, global_refund_partially=global_refund_partially).reverse_moves()
        _logger.info("\n::::::::::::: refund_result >>>>>>>>>>>>>>>> %s " % refund_result )
        if 'domain' in refund_result:
            domain_from_res = refund_result['domain']
            if len(refund_result['domain']) > 1:
                extract_domain_ids = refund_result['domain'][1][2]
                if type(extract_domain_ids) == list:
                    credit_note_id = extract_domain_ids[0]
                    self.refund_invoice_credit_id = credit_note_id
                    _logger.info("\n::::::::::::: credit_note_id >>>>>>>>>>>>>>>> %s " % credit_note_id )
        else:
            if 'res_id' in refund_result:
                res_id_from_res = refund_result['res_id']
                if res_id_from_res:
                    credit_note_id = res_id_from_res
                    _logger.info("\n::::::::::::: credit_note_id >>>>>>>>>>>>>>>> %s " % credit_note_id )
        #### Forzamos el Commit para Guardar la Nota de Credito Conciliada ####
        return credit_note_id

class AccountMove(models.Model):
    _inherit ='account.move'

    invoice_origin_rel_id = fields.Many2one('account.move', 'Factura Origen de la NC')

    def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values):
        # v19 MIGRATION FIX: la firma real del core ya no trae los kwargs
        # 'percentage_paid'/'global_invoice' (versiones anteriores). Python no
        # se quejaba por tenerlos de más (nunca se usaban), pero se limpian
        # para que la firma quede igual a la del core.
        # EXTENDS 'l10n_mx_edi'
        self.ensure_one()
        super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values)
        if cfdi_values.get('errors'):
            return
        context = self.env.context
        _logger.info("\n############ context: %s " % context)
        _logger.info("\n############ self: %s " % self)
        _logger.info("\n############ self.move_type: %s " % self.move_type)
        invoice_origin_rel_id = self.invoice_origin_rel_id
        _logger.info("\n############ invoice_origin_rel_id: %s " % invoice_origin_rel_id)
        pos_order_obj = self.env['pos.order'].sudo()
        if invoice_origin_rel_id:
            if self.move_type == 'out_refund':
                _logger.info("\n############ Es una NC asociada a una global del POS: %s " % invoice_origin_rel_id.invoice_origin)
                pos_order_id = pos_order_obj.search([('account_move','=',invoice_origin_rel_id.id)])
                _logger.info("\n############ pos_order_id: %s " % pos_order_id)
                if pos_order_id:
                    _logger.info("\n############ Partner de la Global: %s " % pos_order_id.partner_global_id)
                    emission_zip = False
                    partner_global_id = False
                    if pos_order_id.partner_global_id:
                        partner_global_id = pos_order_id.partner_global_id
                        emission_zip = pos_order_id.emission_zip if pos_order_id.emission_zip else ''
                        if not emission_zip:
                            if pos_order_id.session_id.config_id.emission_zip:
                                emission_zip = pos_order_id.session_id.config_id.emission_zip
                            else:
                                if pos_order_id.session_id.config_id.contact_global_id:
                                    emission_zip = pos_order_id.session_id.config_id.contact_global_id.zip
                    if not emission_zip and partner_global_id:
                        emission_zip = partner_global_id.zip or self.partner_id.zip
                    _logger.info("\n############ Código Postal Emisión: %s " % emission_zip)
                    if emission_zip:
                        cfdi_values['receptor']['domicilio_fiscal_receptor'] = emission_zip
                        cfdi_values['lugar_expedicion'] = emission_zip
                    if partner_global_id:
                        cfdi_values['receptor']['rfc'] = partner_global_id.vat
                        cfdi_values['receptor']['nombre'] = partner_global_id.name
        _logger.info("\n**********  cfdi_values['receptor']['domicilio_fiscal_receptor']: %s " % cfdi_values['receptor']['domicilio_fiscal_receptor'])
        _logger.info("\n**********  cfdi_values['lugar_expedicion']: %s " % cfdi_values['lugar_expedicion'])
        _logger.info("\n**********  cfdi_values['receptor']['rfc']: %s " % cfdi_values['receptor']['rfc'])
        _logger.info("\n**********  cfdi_values['receptor']['nombre']: %s " % cfdi_values['receptor']['nombre'])

        uso_cfdi = self.get_edi_receptor_dynamic_info('usocfdi', cfdi_values['receptor']['uso_cfdi'])
        rfc_receptor = cfdi_values['receptor']['rfc']
        tipo_de_comprobante = cfdi_values['tipo_de_comprobante']
        _logger.info("\n########## rfc_receptor: %s " % rfc_receptor)
        _logger.info("\n########## uso_cfdi: %s " % uso_cfdi)
        _logger.info("\n########## tipo_de_comprobante: %s " % tipo_de_comprobante)

        if rfc_receptor in ('XAXX010101000', 'XEXX010101000'):
            uso_cfdi = 'S01'
            cfdi_values['receptor']['uso_cfdi'] = uso_cfdi
        

            if tipo_de_comprobante == 'E':
                # v19 MIGRATION FIX: 'conceptos_list' ya no existe en cfdi_values.
                # Cada línea ahora es un "base_line" (dict de
                # account.tax._prepare_base_line_for_taxes_computation) dentro
                # de cfdi_values['base_lines'], y los valores de presentación
                # del <cfdi:Concepto> (clave_prod_serv, description,
                # clave_unidad, unidad, no_identificacion) viven en
                # base_line['l10n_mx_cfdi_values'], no en la línea directamente.
                clave_prod_serv = '84111506'
                description = 'Devolución de mercancias'
                clave_unidad = 'ACT'
                unidad = 'Actividad'

                for base_line in cfdi_values.get('base_lines', []):
                    l10n_mx_cfdi_values = base_line.setdefault('l10n_mx_cfdi_values', {})
                    l10n_mx_cfdi_values.update({
                        'clave_prod_serv': clave_prod_serv,
                        'description': description,
                        'clave_unidad': clave_unidad,
                        'unidad': unidad,
                    })
                    # 'no_identificacion' se deja tal cual la calculó el core
                    # (no se sobreescribe, igual que en el original).
        # Nota: el método ya no necesita 'return cfdi_values' -- el core lo
        # muta en el lugar y no usa el valor de retorno.


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    def _prepare_default_reversal(self, move):
        context = self.env.context
        origin_reinvoice_pos = context.get('origin_reinvoice_pos', False)
        default_vals = super(AccountMoveReversal, self)._prepare_default_reversal(move)
        if origin_reinvoice_pos:
            default_vals['invoice_date_due'] = move.invoice_date_due
            default_vals['invoice_date'] = move.invoice_date
        return default_vals


class L10nMXEdiDocumentSerieFix(models.Model):
    _inherit = 'l10n_mx_edi.document'

    @api.model
    def _add_document_name_cfdi_values(self, cfdi_values, document_name):
        # v19 FIX (2026-07-09): en devoluciones POS el nombre trae el prefijo
        # "REEMBOLSO DE " (traduccion es_MX del nombre nativo del reembolso), lo que
        # hace que la Serie del CFDI (derivada del nombre) supere los 25 chars del SAT
        # (#CFDI40101). Se quita ese prefijo para que la Serie sea la de la caja
        # (ej. "QUINTAS CAJA 3 - "). No afecta facturas (no llevan ese prefijo).
        if document_name:
            _pref = 'REEMBOLSO DE '
            if document_name[:len(_pref)].upper() == _pref:
                document_name = document_name[len(_pref):]
        return super()._add_document_name_cfdi_values(cfdi_values, document_name)
