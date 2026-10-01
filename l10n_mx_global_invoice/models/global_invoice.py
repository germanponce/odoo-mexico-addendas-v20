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


############# Contactos ####################
class ResPartner(models.Model):
    _inherit ='res.partner'

    invoice_2_general_public = fields.Boolean(string='Facturar a Publico en General', help="Facturar a este cliente como publico en general.")
    use_as_general_public    = fields.Boolean(string='Cliente Publico en General', help="Comodin cliente para facturas globales.")
    
    # @api.constrains('use_as_general_public')
    # def _check_use_as_general_public(self):        
    #     for record in self:
    #         if record.use_as_general_public:
    #             res = self.search([('use_as_general_public', '=', 1), ('id','!=', record.id)])
    #             if res:
    #                 raise UserError(_("Error ! You can have only one Partner checked to Use for General Public Invoice..."))
    #     return True

    # @api.onchange('use_as_general_public')
    # def on_change_use_as_general_public(self):
    #     res = {}
    #     if self.use_as_general_public:
    #         self.invoice_2_general_public = False    

############# Herencia Metodos Pago ####################

class PosPaymentMethod(models.Model):
    _name = 'pos.payment.method'
    _inherit ='pos.payment.method'

    payment_tpv_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago SAT')

############# Herencia Facturas ####################


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit ='account.move'

    pos_order_ids = fields.Many2many('pos.order',
        'account_invoice_pos_rel_fx', 'invoice_id',  'sale_id',
        string='Pedidos POS', copy=False)

    #### Factura Global ####

    global_invoice = fields.Boolean('Factura global')

    invoice_edi_activity = fields.Boolean('Facturar como Actividad', help="Cambia la información de la factura por el concepto del impuesto y la clave 01010101.")

    fg_periodicity = fields.Selection(
        selection=[('01', '01 - Diario'),
                   ('02', '02 - Semanal'),
                   ('03', '03 - Quincenal'),
                   ('04', '04 - Mensual'),
                   ('05', '05 - Bimestral'),],
        string='Periodicidad',
    )

    fg_months = fields.Selection(
        selection=[('01', '01 - Enero'),
                   ('02', '02 - Febrero'),
                   ('03', '03 - Marzo'),
                   ('04', '04 - Abril'),
                   ('05', '05 - Mayo'),
                   ('06', '06 - Junio'),
                   ('07', '07 - Julio'),
                   ('08', '08 - Agosto'),
                   ('09', '09 - Septiembre'),
                   ('10', '10 - Octubre'),
                   ('11', '11 - Noviembre'),
                   ('12', '12 - Diciembre'),
                   ('13', '13 - Enero - Febrero'),
                   ('14', '14 - Marzo - Abril'),
                   ('15', '15 - Mayo - Junio'),
                   ('16', '16 - Julio - Agosto'),
                   ('17', '17 - Septiembre - Octubre'),
                   ('18', '18 - Noviembre - Diciembre'),],
        string='Meses',
    )

    fg_year =  fields.Char('Año')


    # @api.onchange('global_invoice')
    # def onchange_global_invoice(self):
    #     if self.global_invoice:
    #         current_date = datetime.strptime(str(self.invoice_date)[0:10], DEFAULT_SERVER_DATE_FORMAT)
    #         month = str(current_date.month)
    #         if current_date.month < 10:
    #             month = '0'+str(current_date.month)

    #         year = current_date.year

    #         if self.fg_periodicity in ('01', '02', '03', '04'):
    #             self.fg_months = str(month)
    #         else:
    #             if month in ('01','02'):
    #                 self.fg_months = '13'
    #             elif month in ('03','04'):
    #                 self.fg_months = '14'
    #             elif month in ('05','06'):
    #                 self.fg_months = '15'
    #             elif month in ('07','08'):
    #                 self.fg_months = '16'
    #             elif month in ('09','10'):
    #                 self.fg_months = '17'
    #             else:
    #                 self.fg_months = '18'
                    
    #         self.fg_year = str(year)

    # def search_product_global(self):
    #     for rec in self:
    #         product_uom = self.env['uom.uom']
    #         product_obj = self.env['product.product']
    #         company = rec.company_id
    #         if not company.product_for_global_invoice:
    #             uom_id = product_uom.search([('name','=','Actividad Facturacion')])
    #             uom_id = uom_id[0] if uom_id else False
    #             if not uom_id:
    #                 sat_udm  = self.env['product.unspsc.code']
    #                 sat_uom_id = sat_udm.search([('code','=','ACT')])
    #                 if not sat_uom_id:
    #                     raise UserError("Error!\nNo existe la Unidad de Medida [ACT] Actividades.")
    #                 category_id = self.env['uom.category'].search([('name','=','Facturacion')],limit=1)
    #                 if not category_id:
    #                     category_id = self.env['uom.category'].sudo().create({'name':'Facturacion'})
    #                 uom_id = product_uom.create({
    #                                                 'unspsc_code_id':sat_uom_id[0].id,
    #                                                 'name':'Actividad Facturacion',
    #                                                 'category_id': category_id.id,
    #                                                 'uom_type': 'reference',
    #                                                 'use_4_invoice_general_public':True,

    #                                             })

    #             sat_product_id = self.env['product.unspsc.code'].search([('code','=','01010101')])
    #             if not sat_product_id:
    #                 raise UserError("El Codigo 01010101 no existe en el Catalogo del SAT.")
    #             product_id = product_obj.search([('product_for_global_invoice','=',True)])
    #             if product_id:
    #                 product_id = product_id[0]
    #             else:
    #                 product_id = product_obj.create({
    #                         'name': 'Servicio Facturacion Global',
    #                         'uom_id': uom_id.id,
    #                         'uom_po_id': uom_id.id,
    #                         'type': 'service',
    #                         'unspsc_code_id': sat_product_id[0].id,
    #                         'product_for_global_invoice': True,
    #                     })
    #             company.write({'product_for_global_invoice': product_id.id})
    #         else:
    #             product_id = company.product_for_global_invoice

    #         return product_id

    # def update_info_to_general_public(self):
    #     if self.global_invoice or self.partner_id.invoice_2_general_public:
    #         return True
    #     return False

    # def unlink(self):    
    #     for rec in self:
    #         if rec.move_type == 'out_invoice':
    #             pos_order_obj = self.env['pos.order'].sudo()
    #             pos_rel_ids = pos_order_obj.search([('account_move','=',rec.id)])
    #             if pos_rel_ids:
    #                 pos_rel_ids.write({'account_move' : False})
    #                 pos_rel_ids.write({'state' : 'paid'})
    #                 pos_rel_ids.write({'invoice_global_ids' : False})
    #     return super(AccountMove, self).unlink()

    # def reconcile_payments_sale_order(self):
    #     for rec in self:
    #         pos_order_obj = self.env['pos.order'].sudo()
    #         #pos_rel_ids = pos_order_obj.search([('account_move','=',rec.id)])
    #         pos_rel_ids = rec.pos_order_ids
    #         context = dict(self._context)
    #         context.update({'active_id': rec.id, 'active_ids': [rec.id], 'active_model': 'account.move'})
    #         if pos_rel_ids:
    #             raise UserError("La Factura Global del POS no requiere una Conciliación Manual, en su lugar cierre el POS.")
    #             return {
    #                         'type': 'ir.actions.act_window',
    #                         # 'res_id': self.id,
    #                         'res_model': 'account.invoice.pos_reconcile_with_payments',
    #                         'view_mode': 'form',
    #                         'target': 'new',
    #                         'context': context
    #                     }
    #     res = super(AccountMove, self).reconcile_payments_sale_order()
    #     return res


    # def get_unspsc_code_dynamic(self, invoice_line):
    #     # invoice_line_vals = line_vals.get('line',{})
    #     # invoice_line = invoice_line_vals.get('record')
    #     unspsc_code_id = invoice_line.product_id.unspsc_code_id.code if invoice_line.product_id.unspsc_code_id else "NA"
    #     if invoice_line.product_global_id:
    #         unspsc_code_id = invoice_line.product_global_id.unspsc_code_id.code if invoice_line.product_global_id.unspsc_code_id else "NA"
    #     else:
    #         if invoice_line.move_id.invoice_edi_activity:
    #             product_global = invoice_line.move_id.search_product_global()
    #             unspsc_code_id = product_global.unspsc_code_id.code if product_global.unspsc_code_id else "NA"
    #     return unspsc_code_id

    # def get_edi_description_dynamic(self, edi_attr, invoice_line):
    #     # invoice_line_vals = line_vals.get('line',{})
    #     # invoice_line = invoice_line_vals.get('record')
    #     if edi_attr == 'claveunidad':
    #         description_edi = invoice_line.product_uom_id.unspsc_code_id.code if invoice_line.product_uom_id.unspsc_code_id else "NA"
    #         if invoice_line.product_global_id or invoice_line.move_id.invoice_edi_activity:
    #             description_edi = 'H87'
    #     if edi_attr == 'unidad':
    #         description_edi = invoice_line.product_uom_id.name if invoice_line.product_uom_id else "NA"
    #         if invoice_line.product_global_id or invoice_line.move_id.invoice_edi_activity:
    #             description_edi = 'Unidades'
    #     if edi_attr == 'descripcion':
    #         description_edi = invoice_line.name if invoice_line.name else "NA"
    #         if not invoice_line.product_global_id:
    #             if invoice_line.move_id.invoice_edi_activity:
    #                 ticket_reference_tax = "Venta grabada a tasa de "
    #                 ticket_reference_taxes = "Venta grabada a tasas de "
    #                 ticket_reference_taxes_2_invoice = ""
    #                 taxes_list_names = []
    #                 if invoice_line.tax_ids:
    #                     for linetax in invoice_line.tax_ids:
    #                         linetax_env_company = linetax.with_company(invoice_line.company_id)
    #                         if linetax.tax_group_id:
    #                             taxes_list_names.append(linetax.tax_group_id.name)
    #                         else:
    #                             taxes_list_names.append(linetax.name)

    #                 if not taxes_list_names:
    #                     ticket_reference_tax = "Venta grabada sin Impuesto."
    #                 else:
    #                     if len(taxes_list_names) > 1:
    #                         ticket_reference_taxes_2_invoice = ticket_reference_taxes
    #                     else:
    #                         ticket_reference_taxes_2_invoice = ticket_reference_tax
    #                     i = 1
    #                     for taxname in taxes_list_names:
    #                         ticket_reference_taxes_2_invoice =  ticket_reference_taxes_2_invoice+", "+taxname if i > 1 else ticket_reference_taxes_2_invoice+taxname
    #                         i+=1

    #                 sale_model = 'sale_line_ids' in invoice_line._fields
    #                 sale_id = False

    #                 if invoice_line.sale_line_ids:
    #                     sale_id = invoice_line.sale_line_ids[0].order_id

    #                 order_origin = sale_id.name if sale_id else ""

    #                 ticket_reference_taxes_2_invoice =  ticket_reference_taxes_2_invoice+" - "+order_origin if order_origin else ticket_reference_taxes_2_invoice

    #                 description_edi = ticket_reference_taxes_2_invoice

    #     return description_edi

    # def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values, percentage_paid=None, global_invoice=False):
    #     # EXTENDS 'l10n_mx_edi'
    #     self.ensure_one()
    #     super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values, percentage_paid=percentage_paid, global_invoice=global_invoice)
    #     if cfdi_values.get('errors'):
    #         return
    #     conceptos_list = cfdi_values.get('conceptos_list',[])
    #     for conceptoline in conceptos_list:
    #         invoice_line = conceptoline.get('line')
    #         if invoice_line:
    #             invoice_line = invoice_line.get('record')
    #         if invoice_line:
    #             clave_prod_serv = self.get_unspsc_code_dynamic(invoice_line)
    #             description = self.get_edi_description_dynamic('descripcion', invoice_line)
    #             clave_unidad = self.get_edi_description_dynamic('claveunidad', invoice_line)
    #             unidad = self.get_edi_description_dynamic('unidad', invoice_line)
    #             conceptoline['line']['clave_prod_serv'] = clave_prod_serv
    #             conceptoline['line']['description'] = description
    #             conceptoline['line']['clave_unidad'] = clave_unidad
    #             conceptoline['line']['unidad'] = unidad

######### Inicio Factura Global - VENTAS ###########

class sale_order_invoice_wizard(models.TransientModel):
    _name = "sale.order.invoice_wizard"
    _description = "Wizard Factura Global Ventas"


    @api.model  
    def default_get(self, fields):
        res = super(sale_order_invoice_wizard, self).default_get(fields)
        record_ids = self._context.get('active_ids', [])
        sale_order_obj = self.env['sale.order']
        if not record_ids:
            return {}
        tickets = []
        
        partner_id = sale_order_obj.get_customer_for_general_public().id
        
        for ticket in sale_order_obj.browse(record_ids):
            ### Restriccion de Tickets Pagados ###
            if ticket.total_payment == False:
                if ticket.payment_exception == False:
                    raise UserError(_("Solo puede facturar Pedidos Pagados o con Excepción de Pago."))

            if ticket.state in ('cancel') or ticket.invoice_status != 'to invoice':
                continue
            # flag = not bool(ticket.partner_id) or bool(ticket.partner_id.invoice_2_general_public or ticket.partner_id.id == partner_id) or False
            flag = False
            if self.env.user.company_id.invoice_public_default:
                flag = True
            else:
                flag = not bool(ticket.partner_id) or bool(ticket.partner_id.invoice_2_general_public or ticket.partner_id.id == partner_id) or False
            if ticket.amount_total > 0.0:
                tickets.append((0,0,{
                        'ticket_id'     : ticket.id,
                        'date_order'    : ticket.date_order,
                        'sale_reference' : ticket.name,
                        'user_id'       : ticket.user_id.id,
                        'partner_id'    : ticket.partner_id and ticket.partner_id.id or False,
                        'amount_total'  : ticket.amount_total,
                        'invoice_2_general_public' : flag,
                        }))
        res.update(ticket_ids=tickets)
        return res

    def _get_current_month(self):
        current_date = datetime.strptime(str(fields.Date.context_today(self))[0:10], DEFAULT_SERVER_DATE_FORMAT)

        month = current_date.month
        if month < 10:
            return '0' + str(month)
        return str(month)

    def _get_current_year(self):
        current_date = datetime.strptime(str(fields.Date.context_today(self))[0:10], DEFAULT_SERVER_DATE_FORMAT)

        year = current_date.year
        return str(year)

    fg_periodicity = fields.Selection(
        selection=[('01', '01 - Diario'),
                   ('02', '02 - Semanal'),
                   ('03', '03 - Quincenal'),
                   ('04', '04 - Mensual'),
                   ('05', '05 - Bimestral'),],
        string='Periodicidad', default="01"
    )

    fg_months = fields.Selection(
        selection=[('01', '01 - Enero'),
                   ('02', '02 - Febrero'),
                   ('03', '03 - Marzo'),
                   ('04', '04 - Abril'),
                   ('05', '05 - Mayo'),
                   ('06', '06 - Junio'),
                   ('07', '07 - Julio'),
                   ('08', '08 - Agosto'),
                   ('09', '09 - Septiembre'),
                   ('10', '10 - Octubre'),
                   ('11', '11 - Noviembre'),
                   ('12', '12 - Diciembre'),
                   ('13', '13 - Enero - Febrero'),
                   ('14', '14 - Marzo - Abril'),
                   ('15', '15 - Mayo - Junio'),
                   ('16', '16 - Julio - Agosto'),
                   ('17', '17 - Septiembre - Octubre'),
                   ('18', '18 - Noviembre - Diciembre'),],
        string='Meses', default=_get_current_month,
    )

    fg_year =  fields.Char(string='Año', default=_get_current_year)

    date       = fields.Date(string='Fecha', default=fields.Date.context_today, required=True,
                              help='This date will be used as the invoice date and period will be chosen accordingly!')
    journal_id = fields.Many2one('account.journal', string='Diario Facturacion', required=True,
                                  default=lambda self: self.env['account.journal'].search([('type', '=', 'sale'), ('company_id','=',self.env.user.company_id.id)], limit=1),
                                  help='You can select here the journal to use for the Invoice that will be created.')
    ticket_ids = fields.One2many('sale.order.invoice_wizard.line','wiz_id',string='Ventas a Facturar', required=True)

    pay_method_grouped = fields.Boolean('Agrupar por Forma de Pago', help="Agrupara los pedidos por Forma de Pago y creara una Factura por cada uno de ellos.")

    invoice_detail_products = fields.Boolean('Detalle Ventas', help="Crea la factura global con el detalle de cada venta.", default=True)



        
class sale_order_invoice_wizard_line(models.TransientModel):
    _name = "sale.order.invoice_wizard.line"
    _description = "Wizard Factura Global Detalle Ventas"

    wiz_id        = fields.Many2one('sale.order.invoice_wizard',string='ID Return', ondelete="cascade")
    ticket_id     = fields.Many2one('sale.order', string='Venta')
    date_order    = fields.Datetime(related='ticket_id.date_order', string="Fecha", readonly=True)
    sale_reference = fields.Char(related='ticket_id.name', string="Referencia", readonly=True)
    user_id       = fields.Many2one("res.users", related='ticket_id.user_id', string="Vendedor", readonly=True)
    amount_total  = fields.Float("Total", readonly=True)
    partner_id    = fields.Many2one("res.partner", related='ticket_id.partner_id', string="Cliente", readonly=True)
    invoice_2_general_public = fields.Boolean('Publico en General')
    payment_tpv_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago SAT')


######### Fin Factura Global ###########

######### Inicio Factura Global - PUNTO DE VENTA ###########

class pos_order_invoice_wizard(models.TransientModel):
    _name = "pos.order.invoice_wizard"
    _description = "Wizard Factura Global POS"


    @api.model  
    def default_get(self, fields):
        res = super(pos_order_invoice_wizard, self).default_get(fields)
        record_ids = self._context.get('active_ids', [])
        pos_order_obj = self.env['pos.order']
        if not record_ids:
            return {}
        tickets = []
        
        partner_id = pos_order_obj.get_customer_for_general_public().id
        journal_id = False
        for ticket in pos_order_obj.browse(record_ids):
            ### Restriccion de Tickets Pagados ###
            # if ticket.total_payment == False:
            #     if ticket.payment_exception == False:
            #         raise UserError(_("Solo puede facturar Pedidos Pagados o con Excepción de Pago."))
            if not journal_id:
                if ticket.session_id.config_id and ticket.session_id.config_id.invoice_journal_id:
                    journal_id = ticket.session_id.config_id.invoice_journal_id.id
            if ticket.state in ('cancel','draft', 'invoiced') or (ticket.account_move and ticket.account_move.state != 'cancel'):
                continue
            # flag = not bool(ticket.partner_id) or bool(ticket.partner_id.invoice_2_general_public or ticket.partner_id.id == partner_id) or False
            flag = False
            if self.env.user.company_id.invoice_public_default:
                flag = True
            else:
                flag = not bool(ticket.partner_id) or bool(ticket.partner_id.invoice_2_general_public or ticket.partner_id.id == partner_id) or False
            
            _logger.info("\n**************************************************************")
            _logger.info("\n#### ticket.name : %s " % ticket.name)
            _logger.info("\n#### ticket.amount_total : %s " % ticket.amount_total)
            if ticket.amount_total > 0.0:
                use_ticket_for_global = True
                amount_refunded = 0.0
                _logger.info("\n#### ticket.refund_orders_count : %s " % ticket.refund_orders_count)
                if  ticket.refund_orders_count > 0.0:
                    orders_refunded_list = ticket.mapped('lines.refund_orderline_ids.order_id')
                    _logger.info("\n#### orders_refunded_list : %s " % str(orders_refunded_list))
                    if orders_refunded_list:
                        for order_refund in orders_refunded_list:
                            amount_refunded += abs(order_refund.amount_total)
                        _logger.info("\n#### amount_refunded : %s " % str(amount_refunded))
                        _logger.info("\n#### ticket.amount_total : %s " % str(ticket.amount_total))
                        if amount_refunded >= ticket.amount_total:
                            use_ticket_for_global = False
                _logger.info("\n#### use_ticket_for_global : %s " % str(use_ticket_for_global))
                _logger.info("\n**************************************************************")
                if use_ticket_for_global:
                    payment_tpv_id = False
                    if ticket.payment_ids:
                        payment_amount = 0.0
                        payment_id = False
                        for pay in ticket.payment_ids:
                            if pay.amount > payment_amount:
                                payment_amount = pay.amount
                                payment_id = pay.payment_method_id

                        if payment_id and payment_id.payment_tpv_id:
                            payment_tpv_id = payment_id.payment_tpv_id

                    tickets.append((0,0,{
                            'ticket_id'     : ticket.id,
                            'date_order'    : ticket.date_order,
                            'pos_reference' : ticket.pos_reference if ticket.pos_reference else ticket.name,
                            'user_id'       : ticket.user_id.id,
                            'partner_id'    : ticket.partner_id and ticket.partner_id.id or False,
                            'amount_total'  : ticket.amount_total,
                            'invoice_2_general_public' : flag,
                            'payment_tpv_id': payment_tpv_id.id if payment_tpv_id else False,
                            }))
            else:
                _logger.info("\n**************************************************************")
                _logger.info("\n#### Validamos que no tenga lineas positivas >>>>>>>>>>>>>>>>>>")
                use_ticket_for_global = False
                amount_total_positive = 0.0
                for line in ticket.lines:
                    if line.price_subtotal > 0.0:
                        use_ticket_for_global = True
                        amount_total_positive += line.price_subtotal_incl
                _logger.info("\n#### use_ticket_for_global : %s " % str(use_ticket_for_global))
                _logger.info("\n**************************************************************")
                if use_ticket_for_global:
                    payment_tpv_id = False
                    if ticket.payment_ids:
                        payment_amount = 0.0
                        payment_id = False
                        for pay in ticket.payment_ids:
                            if pay.amount > payment_amount:
                                payment_amount = pay.amount
                                payment_id = pay.payment_method_id

                        if payment_id and payment_id.payment_tpv_id:
                            payment_tpv_id = payment_id.payment_tpv_id

                    tickets.append((0,0,{
                            'ticket_id'     : ticket.id,
                            'date_order'    : ticket.date_order,
                            'pos_reference' : ticket.pos_reference if ticket.pos_reference else ticket.name,
                            'user_id'       : ticket.user_id.id,
                            'partner_id'    : ticket.partner_id and ticket.partner_id.id or False,
                            'amount_total'  : amount_total_positive,
                            'invoice_2_general_public' : flag,
                            'payment_tpv_id': payment_tpv_id.id if payment_tpv_id else False,
                            }))

        res.update(ticket_ids=tickets,journal_id=journal_id)
        return res

    def _get_current_month(self):
        current_date = datetime.strptime(str(fields.Date.context_today(self))[0:10], DEFAULT_SERVER_DATE_FORMAT)

        month = current_date.month
        if month < 10:
            return '0' + str(month)
        return str(month)

    def _get_current_year(self):
        current_date = datetime.strptime(str(fields.Date.context_today(self))[0:10], DEFAULT_SERVER_DATE_FORMAT)

        year = current_date.year
        return str(year)

    fg_periodicity = fields.Selection(
        selection=[('01', '01 - Diario'),
                   ('02', '02 - Semanal'),
                   ('03', '03 - Quincenal'),
                   ('04', '04 - Mensual'),
                   ('05', '05 - Bimestral'),],
        string='Periodicidad', default="01"
    )

    fg_months = fields.Selection(
        selection=[('01', '01 - Enero'),
                   ('02', '02 - Febrero'),
                   ('03', '03 - Marzo'),
                   ('04', '04 - Abril'),
                   ('05', '05 - Mayo'),
                   ('06', '06 - Junio'),
                   ('07', '07 - Julio'),
                   ('08', '08 - Agosto'),
                   ('09', '09 - Septiembre'),
                   ('10', '10 - Octubre'),
                   ('11', '11 - Noviembre'),
                   ('12', '12 - Diciembre'),
                   ('13', '13 - Enero - Febrero'),
                   ('14', '14 - Marzo - Abril'),
                   ('15', '15 - Mayo - Junio'),
                   ('16', '16 - Julio - Agosto'),
                   ('17', '17 - Septiembre - Octubre'),
                   ('18', '18 - Noviembre - Diciembre'),],
        string='Meses', default=_get_current_month,
    )

    fg_year =  fields.Char(string='Año', default=_get_current_year)


    date       = fields.Date(string='Fecha', default=fields.Date.context_today, required=True,
                              help='This date will be used as the invoice date and period will be chosen accordingly!')
    journal_id = fields.Many2one('account.journal', string='Diario Facturacion', required=True,
                                  help='You can select here the journal to use for the Invoice that will be created.')
    ticket_ids = fields.One2many('pos.order.invoice_wizard.line','wiz_id',string='Ventas a Facturar', required=True)
    
    pay_method_grouped = fields.Boolean('Agrupar por Forma de Pago', help="Agrupara los pedidos por Forma de Pago y creara una Factura por cada uno de ellos.")

    invoice_detail_products = fields.Boolean('Detalle Ventas', help="Crea la factura global con el detalle de cada venta.")

    invoice_detail_taxes = fields.Boolean('Detalle Impuesto', help="Crea la factura global con el detalle del Impuesto por la Venta.", default=True)

        
class pos_order_invoice_wizard_line(models.TransientModel):
    _name = "pos.order.invoice_wizard.line"
    _description = "Wizard Factura Global Tickets POS"

    wiz_id        = fields.Many2one('pos.order.invoice_wizard',string='ID Return', ondelete="cascade")
    ticket_id     = fields.Many2one('pos.order', string='Venta')
    date_order    = fields.Datetime(related='ticket_id.date_order', string="Fecha", readonly=True)
    pos_reference = fields.Char(related='ticket_id.name', string="Referencia", readonly=True)
    user_id       = fields.Many2one("res.users", related='ticket_id.user_id', string="Vendedor", readonly=True)
    amount_total  = fields.Float("Total", readonly=True)
    partner_id    = fields.Many2one("res.partner", related='ticket_id.partner_id', string="Cliente", readonly=True)
    invoice_2_general_public = fields.Boolean('Publico en General')
    payment_tpv_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago SAT')

######### Fin Factura Global - PUNTO DE VENTA ###########


######### Conciliación de Pagos Factura Global - PUNTO DE VENTA ###########

class account_invoice_pos_reconcile_with_payments(models.TransientModel):
    _name = "account.invoice.pos_reconcile_with_payments"
    _description = "Wizard to Reconcile POS Payments with Invoices from POS Orders"

    date = fields.Date(string='Fecha', help='This date will be used as the payment date !', 
                       default=fields.Date.context_today, required=True)
    

######### Inicio Herencia Objetos y Metodos  Punto de Venta ###########


class PosSession(models.Model):
    _inherit ='pos.session'


class PosOrderLineGlobalConcept(models.Model):
    _name = 'pos.order.line.global.concept'
    _description = 'Concetps de Facturación Global'
    _rec_name = 'noidentificacion' 

    noidentificacion = fields.Char('NoIdentificacion', size=128)
    product_id = fields.Many2one('product.product', 'Producto')
    uom_id = fields.Many2one('uom.uom', 'Unidad de Medida')
    invoice_line_tax_ids = fields.Many2many('account.tax',
        'pos_order_account_invoice_line_global_tax', 'global_line_id', 'tax_id',
        string='Impuestos',)
    quantity = fields.Float('Cantidad', digits=(14,2), default=1.0)
    price_unit = fields.Float('Total')
    sale_id = fields.Many2one('pos.order', 'ID Ref')

class PosOrder(models.Model):
    _inherit = "pos.order"
        
    invoice_2_general_public = fields.Boolean(string='Facturado a Publico en General', 
                                              help="La factura se realizo a Publico en General.")

    global_line_ids = fields.One2many('pos.order.line.global.concept', 'sale_id', 'Conceptos de Facturacion Global')

    type_invoice_global = fields.Selection([('simple','Cliente'),
                                            ('general_public','Publico en General')], 'Facturado a', default="simple")

    partner_original_id =  fields.Many2one('res.partner', 'Partner Pedido Original')

    invoice_global_ids = fields.Many2many('account.move',
        'account_invoice_pos_rel_fx', 'sale_id', 'invoice_id',
        string='Facturas', copy=False)
    
    payment_tpv_id = fields.Many2one('l10n_mx_edi.payment.method', 'Forma de Pago SAT')

    pay_forma_id = fields.Many2one('l10n_mx_edi.payment.method', string='Forma de pago')


######### Inicio Herencia Objetos y Metodos  Ventas ###########


class SaleOrderLineGlobalConcept(models.Model):
    _name = 'sale.order.line.global.concept'
    _description = 'Concetps de Facturación Global'
    _rec_name = 'noidentificacion' 

    noidentificacion = fields.Char('NoIdentificacion', size=128)
    product_id = fields.Many2one('product.product', 'Producto')
    uom_id = fields.Many2one('uom.uom', 'Unidad de Medida')
    invoice_line_tax_ids = fields.Many2many('account.tax',
        'sale_order_account_invoice_line_global_tax', 'global_line_id', 'tax_id',
        string='Impuestos',)
    quantity = fields.Float('Cantidad', digits=(14,2), default=1.0)
    price_unit = fields.Float('Total')
    sale_id = fields.Many2one('sale.order', 'ID Ref')


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit ='sale.order'

    @api.depends('order_line.invoice_lines')
    def _get_invoiced(self):
        # The invoice_ids are obtained thanks to the invoice lines of the SO
        # lines, and we also search for possible refunds created directly from
        # existing invoices. This is necessary since such a refund is not
        # directly linked to the SO.
        for order in self:
            if order.invoice_global_ids:
                invoice_ids = [x.id for x in order.invoice_global_ids]
                invoices = self.env['account.move'].browse(invoice_ids)
            else:
                invoices = order.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
            order.invoice_ids = invoices
            order.invoice_count = len(invoices)

    invoice_2_general_public = fields.Boolean(string='Facturado a Publico en General', 
                                              help="La factura se realizo a Publico en General.")

    type_invoice_global = fields.Selection([('simple','Cliente'),
                                            ('general_public','Publico en General')], 'Facturado a', default="simple")

    global_line_ids = fields.One2many('sale.order.line.global.concept', 'sale_id', 'Conceptos de Facturacion Global')
    invoice_global_ids = fields.Many2many('account.move',
        'account_invoice_sale_rel', 'sale_id', 'invoice_id',
        string='Facturas', copy=False)

class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit ='product.product'

    product_for_global_invoice = fields.Boolean('Facturacion Global')

class Company(models.Model):
    _inherit = 'res.company'

    product_for_global_invoice = fields.Many2one("product.product", "Producto Facturas Globales",
                                  help="Producto para Generar el Descuento Global", company_dependent=True)

    invoice_public_default = fields.Boolean('Marcar Publico General', 
        help='Indica si el Asistente de Factura Global marcara el campo de Factura a Publico en General por defecto.', )

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    product_for_global_invoice = fields.Many2one("product.product", "Producto Facturacion Global",
                                  related='company_id.product_for_global_invoice',
                                  help="Producto para Generar el concepto del ticket Global", readonly=False)

    # @api.onchange('company_id')
    # def onchange_company_id(self):
    #     if self.company_id:
    #         company = self.company_id
    #         self.product_for_global_invoice = company.product_for_global_invoice.id
    #         res = super(ResConfigSettings, self).onchange_company_id()
    #         return res

class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit ='product.product'

    product_for_global_invoice = fields.Boolean('Facturacion Global')



class product_uom(models.Model):
    _inherit = 'uom.uom'
    """
    Adds check to indicate if this UoM will be used when creating Invoice from POS Tickets for Partner is General Public
    """

    use_4_invoice_general_public = fields.Boolean(string='Usar para Factura Global')
    
    
    @api.constrains('use_4_invoice_general_public')
    def _check_use_4_invoice_general_public(self):        
        for record in self:
            if record.use_4_invoice_general_public:
                res = self.search([('use_4_invoice_general_public', '=', 1)])                
                if res and res.id != record.id:
                    raise UserError(_("Solo puede marcar una Unidad para ser utilizada en la facturación global."))
        return True


class AccountInvoiceLine(models.Model):
    _name = 'account.move.line'
    _inherit ='account.move.line'

    product_global_id = fields.Many2one('product.product', 'Producto Global')

    noidentificacion = fields.Char('NoIdentificacion', size=128)


class AccountTax(models.Model):
    _inherit ='account.tax'

    property_account_income_global_id = fields.Many2one('account.account', company_dependent=True, check_company=True,
        string="Cuenta de ingresos Factura Global",
        domain="[('deprecated', '=', False)]",
        help="Cuenta utilizada para los apuntes contables de la Factura Global con Detalle de Impuestos.")


    # tax_purchase_id = tax_obj.search([('type_tax_use','=','purchase'),('amount','=',8.0),('company_id','=',env.company.id)], limit=1)

class ProductCategory(models.Model):
    _inherit ='product.category'

    property_account_income_global_id = fields.Many2one('account.account', company_dependent=True, check_company=True,
        string="Cuenta de ingresos Factura Global",
        domain="[('deprecated', '=', False)]",
        help="Cuenta utilizada para los apuntes contables de la Factura Global con Detalle de Impuestos.")


    # tax_purchase_id = tax_obj.search([('type_tax_use','=','purchase'),('amount','=',8.0),('company_id','=',env.company.id)], limit=1)
