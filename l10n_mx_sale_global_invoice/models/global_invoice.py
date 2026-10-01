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


# class L10nMxEdiDocument(models.Model):
#     _inherit = 'l10n_mx_edi.document'

#     @api.model
#     def _add_base_lines_cfdi_values(self, cfdi_values, base_lines, percentage_paid=None):
#         # EXTENDS 'l10n_mx_edi'
#         super()._add_base_lines_cfdi_values(cfdi_values, base_lines=base_lines, percentage_paid=percentage_paid)
#         conceptos_list = cfdi_values['conceptos_list']
#         print ("########## conceptos_list: ", conceptos_list)

############# Contactos ####################
class ResPartner(models.Model):
    _inherit ='res.partner'

    use_as_general_public    = fields.Boolean(string='Cliente Publico en General', help="Comodin cliente para facturas globales.")
    
    @api.constrains('use_as_general_public')
    def _check_use_as_general_public(self):        
        for record in self:
            if record.use_as_general_public:
                res = self.search([('use_as_general_public', '=', 1), ('id','!=', record.id)])
                if res:
                    raise UserError("Error ! You can have only one Partner checked to Use for General Public Invoice...")
        return True

    # @api.constrains('vat')
    # def _constraint_uniq_vat(self):
    #    if self.is_company and self.vat:
    #         other_partner = self.search([('vat','=',self.vat),('id','!=',self.id),('is_company','=',True)])
    #         if other_partner:
    #             raise UserError(_("Error!\nEl RFC ya existe en la Base de Datos"))


############# Herencia Facturas ####################


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit ='account.move'

    #### Factura Global ####

    # global_invoice = fields.Boolean('Factura global')

    invoice_edi_activity = fields.Boolean('Facturar como Actividad', help="Cambia la información de la factura por el concepto del impuesto y la clave 01010101.")

    def search_product_global(self):
        for rec in self:
            product_uom = self.env['uom.uom']
            product_obj = self.env['product.product']
            company = rec.company_id
            if not company.product_for_global_invoice:
                uom_id = product_uom.search([('name','=','Actividad Facturacion')])
                uom_id = uom_id[0] if uom_id else False
                if not uom_id:
                    sat_udm  = self.env['product.unspsc.code']
                    sat_uom_id = sat_udm.search([('code','=','ACT')])
                    if not sat_uom_id:
                        raise UserError("Error!\nNo existe la Unidad de Medida [ACT] Actividades.")
                    category_id = self.env['uom.category'].search([('name','=','Facturacion')],limit=1)
                    if not category_id:
                        category_id = self.env['uom.category'].sudo().create({'name':'Facturacion'})
                    uom_id = product_uom.create({
                                                    'unspsc_code_id':sat_uom_id[0].id,
                                                    'name':'Actividad Facturacion',
                                                    'category_id': category_id.id,
                                                    'uom_type': 'reference',
                                                    'use_4_invoice_general_public':True,

                                                })

                sat_product_id = self.env['product.unspsc.code'].search([('code','=','01010101')])
                if not sat_product_id:
                    raise UserError("El Codigo 01010101 no existe en el Catalogo del SAT.")
                product_id = product_obj.search([('product_for_global_invoice','=',True)])
                if product_id:
                    product_id = product_id[0]
                else:
                    product_id = product_obj.create({
                            'name': 'Servicio Facturacion Global',
                            'uom_id': uom_id.id,
                            'type': 'service',
                            'unspsc_code_id': sat_product_id[0].id,
                            'product_for_global_invoice': True,
                        })
                company.write({'product_for_global_invoice': product_id.id})
            else:
                product_id = company.product_for_global_invoice

            return product_id

    def update_info_to_general_public(self):
        if self.global_invoice or self.partner_id.vat == 'XAXX010101000':
            return True
        return False

    # v19 (2026-07-09): además del flag manual 'Facturar como Actividad'
    # (invoice_edi_activity), se aplican conceptos genéricos ('01010101',
    # 'Venta grabada a tasa de X', unidad H87) automáticamente cuando la factura
    # es "CFDI para público en general" (l10n_mx_edi_cfdi_to_public). Decisión del
    # usuario: público en general no debe detallar el producto.
    def get_unspsc_code_dynamic(self, invoice_line):
        # invoice_line_vals = line_vals.get('line',{})
        # invoice_line = invoice_line_vals.get('record')
        unspsc_code_id = invoice_line.product_id.unspsc_code_id.code if invoice_line.product_id.unspsc_code_id else "NA"
        if invoice_line.product_global_id:
            unspsc_code_id = invoice_line.product_global_id.unspsc_code_id.code if invoice_line.product_global_id.unspsc_code_id else "NA"
        else:
            if (invoice_line.move_id.invoice_edi_activity or invoice_line.move_id.l10n_mx_edi_cfdi_to_public):
                product_global = invoice_line.move_id.search_product_global()
                unspsc_code_id = product_global.unspsc_code_id.code if product_global.unspsc_code_id else "NA"
        return unspsc_code_id

    def get_edi_description_dynamic(self, edi_attr, invoice_line):
        # invoice_line_vals = line_vals.get('line',{})
        # invoice_line = invoice_line_vals.get('record')
        if edi_attr == 'claveunidad':
            description_edi = invoice_line.product_uom_id.unspsc_code_id.code if invoice_line.product_uom_id.unspsc_code_id else "NA"
            if invoice_line.product_global_id or (invoice_line.move_id.invoice_edi_activity or invoice_line.move_id.l10n_mx_edi_cfdi_to_public):
                description_edi = 'H87'
        if edi_attr == 'unidad':
            description_edi = invoice_line.product_uom_id.name if invoice_line.product_uom_id else "NA"
            if invoice_line.product_global_id or (invoice_line.move_id.invoice_edi_activity or invoice_line.move_id.l10n_mx_edi_cfdi_to_public):
                description_edi = 'Unidades'
        if edi_attr == 'descripcion':
            description_edi = invoice_line.name if invoice_line.name else "NA"
            if not invoice_line.product_global_id:
                if (invoice_line.move_id.invoice_edi_activity or invoice_line.move_id.l10n_mx_edi_cfdi_to_public):
                    ticket_reference_tax = "Venta grabada a tasa de "
                    ticket_reference_taxes = "Venta grabada a tasas de "
                    ticket_reference_taxes_2_invoice = ""
                    taxes_list_names = []
                    if invoice_line.tax_ids:
                        for linetax in invoice_line.tax_ids:
                            linetax_env_company = linetax.with_company(invoice_line.company_id)
                            if linetax.tax_group_id:
                                taxes_list_names.append(linetax.tax_group_id.name)
                            else:
                                taxes_list_names.append(linetax.name)

                    if not taxes_list_names:
                        ticket_reference_tax = "Venta grabada sin Impuesto."
                    else:
                        if len(taxes_list_names) > 1:
                            ticket_reference_taxes_2_invoice = ticket_reference_taxes
                        else:
                            ticket_reference_taxes_2_invoice = ticket_reference_tax
                        i = 1
                        for taxname in taxes_list_names:
                            ticket_reference_taxes_2_invoice =  ticket_reference_taxes_2_invoice+", "+taxname if i > 1 else ticket_reference_taxes_2_invoice+taxname
                            i+=1

                    sale_model = 'sale_line_ids' in invoice_line._fields
                    sale_id = False

                    if invoice_line.sale_line_ids:
                        sale_id = invoice_line.sale_line_ids[0].order_id

                    order_origin = sale_id.name if sale_id else ""

                    ticket_reference_taxes_2_invoice =  ticket_reference_taxes_2_invoice+" - "+order_origin if order_origin else ticket_reference_taxes_2_invoice

                    description_edi = ticket_reference_taxes_2_invoice

        return description_edi

    def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values, percentage_paid=None, global_invoice=False):
        # EXTENDS 'l10n_mx_edi'
        self.ensure_one()
        super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values)
        if cfdi_values.get('errors'):
            return
        conceptos_list = cfdi_values.get('conceptos_list',[])
        _logger.info("\n$#### SELF: %s" % self)
        _logger.info("\n$#### self.company_id.partner_id.zip: %s " % self.company_id.partner_id.zip)
        _logger.info("\n$#### self.global_invoice: %s " % self.global_invoice)
        if self._name == 'account.move' and self.global_invoice:
            lugar_expedicion = cfdi_values['lugar_expedicion']
            _logger.info("\n$#### lugar_expedicion: %s " % lugar_expedicion)
            cfdi_values['receptor']['domicilio_fiscal_receptor'] = lugar_expedicion
            # cfdi_values['receptor']['domicilio_fiscal_receptor'] = self.company_id.partner_id.zip
        # v19 MIGRATION FIX (2026-07-08): en v19 'conceptos_list' = [base_line['l10n_mx_cfdi_values']]
        # y NO trae la clave 'line'/'record' (era estructura v17 -> invoice_line=None -> AttributeError
        # en get_unspsc_code_dynamic). Iteramos cfdi_values['base_lines'], de donde SI se obtiene el
        # apunte contable (base_line['record']) y su dict de concepto (base_line['l10n_mx_cfdi_values']),
        # que es el mismo objeto referenciado en conceptos_list. Para lineas normales get_*_dynamic
        # devuelve lo mismo que el core; se conserva la logica de actividad/product_global_id.
        for base_line in cfdi_values.get('base_lines', []):
            invoice_line = base_line.get('record')
            conceptoline = base_line.get('l10n_mx_cfdi_values')
            if not invoice_line or not conceptoline:
                continue

            clave_prod_serv = self.get_unspsc_code_dynamic(invoice_line)
            description = self.get_edi_description_dynamic('descripcion', invoice_line)
            clave_unidad = self.get_edi_description_dynamic('claveunidad', invoice_line)
            unidad = self.get_edi_description_dynamic('unidad', invoice_line)

            no_identificacion = conceptoline.get('no_identificacion')
            if self.invoice_origin:
                no_identificacion = self.invoice_origin.replace("/","").replace("-","").replace(" ","")

            conceptoline['name'] = description
            conceptoline['clave_prod_serv'] = clave_prod_serv  # Cambiar la clave del producto/servicio
            conceptoline['description'] = description  # Cambiar la descripción
            conceptoline['clave_unidad'] = clave_unidad  # Cambiar la clave de unidad
            conceptoline['unidad'] = unidad  # Cambiar la unidad
            conceptoline['no_identificacion'] = no_identificacion  # Cambiar la unidad

            # if invoice_line:
            #     clave_prod_serv = self.get_unspsc_code_dynamic(invoice_line)
            #     print ("######### clave_prod_serv: ", clave_prod_serv)
            #     description = self.get_edi_description_dynamic('descripcion', invoice_line)
            #     print ("######### description: ", description)
            #     clave_unidad = self.get_edi_description_dynamic('claveunidad', invoice_line)
            #     print ("######### clave_unidad: ", clave_unidad)
            #     unidad = self.get_edi_description_dynamic('unidad', invoice_line)
            #     print ("######### unidad: ", unidad)
            #     conceptoline['line']['clave_prod_serv'] = clave_prod_serv
            #     conceptoline['line']['description'] = description
            #     conceptoline['line']['clave_unidad'] = clave_unidad
            #     conceptoline['line']['unidad'] = unidad
            #     #### Asociados al root de la linea
            #     conceptoline['clave_prod_serv'] = clave_prod_serv
            #     conceptoline['description'] = description
            #     conceptoline['clave_unidad'] = clave_unidad
            #     conceptoline['unidad'] = unidad
        cfdi_values['conceptos_list'] = conceptos_list
        _logger.info("\n########  cfdi_values['lugar_expedicion']: %s " % cfdi_values['lugar_expedicion'])
        _logger.info("\n########  cfdi_values['receptor']['domicilio_fiscal_receptor']: %s " % cfdi_values['receptor']['domicilio_fiscal_receptor'])
        #_logger.info("\n######### cfdi_values.get('conceptos_list',[]): %s" % cfdi_values.get('conceptos_list',[]))

class L10nMxEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    @api.model
    def _get_global_invoice_cfdi_values(self, cfdi_values_list, date, periodicity='04', origin=None):
        results = super()._get_global_invoice_cfdi_values(cfdi_values_list=cfdi_values_list,date=date,periodicity=periodicity,origin=origin)
        return results

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
                    raise UserError("Solo puede facturar Pedidos Pagados o con Excepción de Pago.")

            if ticket.state in ('cancel') or ticket.invoice_status != 'to invoice':
                continue
            # flag = not bool(ticket.partner_id) or bool(ticket.partner_id.contact_general_public or ticket.partner_id.id == partner_id) or False
            flag = False
            if self.env.user.company_id.invoice_public_default:
                flag = True
            else:
                flag = not bool(ticket.partner_id) or bool(ticket.partner_id.contact_general_public or ticket.partner_id.id == partner_id) or False
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


    @api.onchange('fg_periodicity', 'date')
    def onchange_global_data(self):
        if not self.date:
            return {}

        current_date = datetime.strptime(str(self.date)[0:10], DEFAULT_SERVER_DATE_FORMAT)
        month = str(current_date.month)
        if current_date.month < 10:
            month = '0'+str(current_date.month)

        year = current_date.year

        if self.fg_periodicity in ('01', '02', '03', '04'):
            self.fg_months = str(month)
        else:
            if month in ('01','02'):
                self.fg_months = '13'
            elif month in ('03','04'):
                self.fg_months = '14'
            elif month in ('05','06'):
                self.fg_months = '15'
            elif month in ('07','08'):
                self.fg_months = '16'
            elif month in ('09','10'):
                self.fg_months = '17'
            else:
                self.fg_months = '18'
                
        self.fg_year = str(year)

    def check_all_public_invoice(self):
        for line in self.ticket_ids:
            line.invoice_2_general_public = True
            line.amount_total = line.ticket_id.amount_total
        return{
                'type': 'ir.actions.act_window',
                'res_id': self.id,
                'res_model': 'sale.order.invoice_wizard',
                'view_mode': 'form',
                'target': 'new',
            }
                
    def create_invoice_from_sales(self):
        invoice_obj = self.env['account.move']
        invoice_ids = []
        ### Busqueda del Cliente Publico en General ###
        general_public_partner = self.env['sale.order'].get_customer_for_general_public()
        tickets_to_set_as_general_public = []

        tickets_simple_invoice =  []
        res = {}
        for line in self.ticket_ids:
            if line.invoice_2_general_public:
                tickets_to_set_as_general_public += line.ticket_id
            else:
                tickets_simple_invoice.append(line.ticket_id)
            
        # Ponemos todos los tickets a facturar como si no fueran Publico en General, esto por si se cancelo/elimino una Factura previa
        
        if tickets_to_set_as_general_public:
            lines_to_invoice = []
            global_origin_name = ""
            ### Busqueda del Producto para Facturacion ###
            global_product_id = tickets_to_set_as_general_public[0].search_product_global()
            ### Rertorno de la cuenta para Facturación ###
            account = global_product_id.property_account_income_id or global_product_id.categ_id.property_account_income_categ_id
            if not account:
                raise UserError('Por favor crea una cuenta para el producto: "%s" (id:%d) - or for its category: "%s".' %
                    (global_product_id.name, global_product_id.id, global_product_id.categ_id.name))

            ticket_id_list = []
            for ticket in tickets_to_set_as_general_public:
                global_origin_name += ticket.name+","
                order_line_ids = [x.id for x in ticket.order_line]
                if not ticket.global_line_ids:
                    ticket.update_concepts_to_global_invoice()
                for concept in ticket.global_line_ids:
                    lines_to_invoice.append((0,0,{
                            'noidentificacion': ticket.name,
                            'product_id': concept.product_id.id,
                            'name': 'VENTA: %s' % ticket.name,
                            'quantity': 1,
                            'account_id': account.id,
                            'product_uom_id': concept.uom_id.id,
                            'tax_ids': [(6,0,[x.id for x in concept.invoice_line_tax_ids])] if concept.invoice_line_tax_ids else False,
                            'price_unit':concept.price_unit,
                            'discount': 0.0,
                            #'sale_line_ids': [(6,0,order_line_ids)]
                        }))
                ticket.write({'invoice_2_general_public': True, 'type_invoice_global': 'general_public'})

                ### Escribiendo como Facturados los Pedidos ####
                ticket.order_line.write({'invoice_status' : 'invoiced'})
                ticket_id_list.append(ticket.id)
            # metodo_pago_id = self.env['sat.metodo.pago'].search([('code','=','PUE')])
            # if not metodo_pago_id:
            #     raise UserError("Error!\nNo se encuentra el metodo de Pago PUE.")
            # metodo_pago_id = metodo_pago_id[0]
            # uso_cfdi_id = self.env['sat.uso.cfdi'].search([('code','=','S01')])
            # if not uso_cfdi_id:
            #     raise UserError("Error!\nNo se encuentra el uso de cfdi S01.")
            uso_cfdi_id = 'S01'
            metodo_pago = 'PUE'
            pay_method_id = self.env['l10n_mx_edi.payment.method'].search([('code','=','01')], limit=1)
            if not pay_method_id:
                raise UserError("Error!\nNo se encuentra el metodo de Pago 01.")

            invoice_vals = {
                'partner_id': general_public_partner.id,
                'l10n_mx_edi_payment_policy': metodo_pago,
                'l10n_mx_edi_usage': uso_cfdi_id,
                'l10n_mx_edi_payment_method_id': pay_method_id.id,
                'journal_id': self.journal_id.id,
                'invoice_date': self.date,
                'invoice_line_ids': lines_to_invoice,
                'narration': 'Factura Global [ '+global_origin_name+' ]',
                'move_type': 'out_invoice',

                'global_invoice': True,
                'fg_periodicity': self.fg_periodicity,
                'fg_months': self.fg_months,
                'fg_year': self.fg_year,
            }

            invoice_id = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(invoice_vals)
            invoice_ids.append(invoice_id.id)
            ### Grabar Facturas #####
            self.env['sale.order'].browse(ticket_id_list).write({'invoice_global_ids': [(6,0,[invoice_id.id])], 'invoice_status': 'invoiced', 'invoice_count': 1 })
            # self.env['sale.order'].browse(ticket_id_list)._get_invoiced()

            # self.env.cr.execute("""
            #     update sale_order_line set invoice_id = %s where order_id in %s;
            #     """, (invoice_id.id, tuple(ticket_id_list),))
        if tickets_simple_invoice:
            for ticket in tickets_simple_invoice:
                invoice_create_ids = ticket._create_invoice_single()
                for inv in invoice_create_ids:
                    invoice_ids.append(inv.id)
                
        ### Rertorno de la información ###
        imd = self.env['ir.model.data']
        action_ref = imd._xmlid_to_res_model_res_id('account.action_move_out_invoice_type')
        action = self.env[action_ref[0]].browse(action_ref[1])
        form_view_id = imd._xmlid_to_res_id('account.view_move_form')
        list_view_id = imd._xmlid_to_res_id('account.view_out_invoice_tree')
        if len(invoice_ids) > 1:
            return {
                        'name': 'Facturacion Global Ventas',
                        'view_mode': 'form',
                        'view_id': self.env.ref('account.view_invoice_tree').id,
                        'res_model': 'account.move',
                        'context': "{}", # self.env.context
                        'type': 'ir.actions.act_window',
                        'domain': [('id', 'in', invoice_ids)],
                    }
        else:
            return {
                        'name': 'Factura Global',
                        'view_mode': 'form',
                        'view_id': self.env.ref('account.view_move_form').id,
                        'res_model': 'account.move',
                        'context': "{}", # self.env.context
                        'type': 'ir.actions.act_window',
                        'res_id': invoice_ids[0],
                    }
                    
        

        
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

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for rec in self:
            rec.update_concepts_to_global_invoice()
        return res

    def search_product_global(self):
        for rec in self:
            product_uom = self.env['uom.uom']
            product_obj = self.env['product.product']
            company = rec.company_id
            if not company.product_for_global_invoice:
                uom_id = product_uom.search([('name','=','Actividad Facturacion')])
                uom_id = uom_id[0] if uom_id else False
                if not uom_id:
                    sat_udm  = self.env['product.unspsc.code']
                    sat_uom_id = sat_udm.search([('code','=','ACT')])
                    if not sat_uom_id:
                        raise UserError("Error!\nNo existe la Unidad de Medida [ACT] Actividades.")
                    category_id = self.env['uom.category'].search([('name','=','Facturacion')],limit=1)
                    if not category_id:
                        category_id = self.env['uom.category'].sudo().create({'name':'Facturacion'})
                    uom_id = product_uom.create({
                                                    'unspsc_code_id':sat_uom_id[0].id,
                                                    'name':'Actividad Facturacion',
                                                    'category_id': category_id.id,
                                                    'uom_type': 'reference',
                                                    'use_4_invoice_general_public':True,

                                                })

                sat_product_id = self.env['product.unspsc.code'].search([('code','=','01010101')])
                if not sat_product_id:
                    raise UserError("El Codigo 01010101 no existe en el Catalogo del SAT.")
                product_id = product_obj.search([('product_for_global_invoice','=',True)])
                if product_id:
                    product_id = product_id[0]
                else:
                    product_id = product_obj.create({
                            'name': 'Servicio Facturacion Global',
                            'uom_id': uom_id.id,
                            'type': 'service',
                            'unspsc_code_id': sat_product_id[0].id,
                            'product_for_global_invoice': True,
                        })
                company.write({'product_for_global_invoice': product_id.id})
            else:
                product_id = company.product_for_global_invoice

            return product_id

    def update_concepts_to_global_invoice(self):
        inv_ref = self.env['account.move']
        acc_tax_obj = self.env['account.tax']
        inv_line_ref = self.env['account.move.line']
        product_obj = self.env['product.product']
        sales_order_obj = self.env['sale.order']
        order_line_obj = self.env['sale.order.line']
        picking_obj = self.env['stock.picking']

        for rec in self:
            if rec.global_line_ids:
                rec.global_line_ids.unlink()
            inv_ids = []
            lines = {}
            for line in rec.order_line:
                ## Agrupamos las líneas según el impuesto
                xval = 0.0
                taxes_list = [x.id for x in line.product_id.taxes_id]
                for tax in acc_tax_obj.browse(taxes_list):
                    xval += (tax.price_include and tax.amount or 0.0)

                tax_names = ", ".join([x.name for x in line.product_id.taxes_id])
                val={
                    'tax_names'           : ", ".join([x.name for x in line.product_id.taxes_id]),
                    'taxes_id'            : ",".join([str(x.id) for x in line.product_id.taxes_id]),
                    'price_subtotal'      : line.price_subtotal * (1.0 + xval),
                    'price_subtotal_incl' : line.price_subtotal,
                    }
                key = (val['tax_names'],val['taxes_id'])
                if not key in lines:
                    lines[key] = val
                    lines[key]['price_subtotal'] = val['price_subtotal']
                    lines[key]['price_subtotal_incl'] = val['price_subtotal_incl']

                else:
                    lines[key]['price_subtotal'] += val['price_subtotal']

            global_line_ids = []
            product_global = rec.search_product_global()
            for key, line in lines.items():
                tax_name = ''
                taxes_ids = line['taxes_id'].split(',') if line['taxes_id'] else False
                if taxes_ids:
                    taxes_ids = [int(x) for x in taxes_ids]
                global_vals = {
                    'product_id': product_global.id,
                    'noidentificacion': rec.name,
                    'uom_id': product_global.uom_id.id,
                    'invoice_line_tax_ids': [(6, 0, taxes_ids)] if line['taxes_id'] else False,
                    'quantity': 1,
                    'price_unit': line['price_subtotal'],
                }
                global_line_ids.append((0,0, global_vals))
            if global_line_ids:
                rec.write({'global_line_ids': global_line_ids})



    def get_customer_for_general_public(self):
        partner_obj = self.env['res.partner']
        partner_id = partner_obj.search([('use_as_general_public','=',1)], limit=1)
        if not partner_id:
            raise UserError('Por favor, configura un cliente como Publico en General.')    
        return partner_id  


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

    use_4_invoice_general_public = fields.Boolean(string='Usar para Factura Global')
    
    
    @api.constrains('use_4_invoice_general_public')
    def _check_use_4_invoice_general_public(self):        
        for record in self:
            if record.use_4_invoice_general_public:
                res = self.search([('use_4_invoice_general_public', '=', 1)])                
                if res and res.id != record.id:
                    raise UserError("Solo puede marcar una Unidad para ser utilizada en la facturación global.")
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
