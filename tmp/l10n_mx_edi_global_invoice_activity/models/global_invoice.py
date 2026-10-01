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

#### Gestión Zona Horaria ####

from datetime import datetime
from pytz import timezone
import pytz
import time
from datetime import timedelta


import logging
_logger = logging.getLogger(__name__)



class PosOrder(models.Model):
    _inherit ='pos.order'

    invoice_edi_activity = fields.Boolean('Facturar como Actividad', help="Cambia la información de la factura por el concepto del impuesto y la clave 01010101.")

class L10nMxEdiGlobalInvoiceCreate(models.TransientModel):
    _inherit = 'l10n_mx_edi.global_invoice.create'


    invoice_edi_activity = fields.Boolean('Facturar como Actividad', help="Cambia la información de la factura por el concepto del impuesto y la clave 01010101.")

    def action_create_global_invoice(self):
        # EXTENDS 'l10n_mx_edi'
        invoice_edi_activity = self.invoice_edi_activity
        self.ensure_one()
        if invoice_edi_activity:
            self.pos_order_ids.write({
                                        'invoice_edi_activity': invoice_edi_activity,
                                     })
        if self.pos_order_ids:
            self.pos_order_ids.with_context(invoice_edi_activity=invoice_edi_activity)._l10n_mx_edi_cfdi_global_invoice_try_send(periodicity=self.periodicity)
        else:
            super().with_context(invoice_edi_activity=invoice_edi_activity).action_create_global_invoice()

class L10nMXEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    invoice_edi_activity = fields.Boolean('Facturar como Actividad', help="Cambia la información de la factura por el concepto del impuesto y la clave 01010101.")


    def _create_update_global_invoice_document_from_pos_orders(self, orders, document_values):
        context = self._context
        document = super(L10nMXEdiDocument, self)._create_update_global_invoice_document_from_pos_orders(orders=orders, document_values=document_values)
        invoice_edi_activity = context.get('invoice_edi_activity',False)
        if invoice_edi_activity:
            document.invoice_edi_activity = invoice_edi_activity
        return document

    def get_edi_description_dynamic_attributes_like_activity(self, edi_attr, invoice_line):
        # Catálogo del SAT para impuestos
        catalogo_impuestos = {
            '001': 'ISR',
            '002': 'IVA',
            '003': 'IEPS'
        }

        # Mapeo para los tipos de factor
        tipo_factor_map = {
            'Tasa': 'tasa de',
            'Cuota': 'cuota de',
            'Exento': 'exento de'
        }

        traslados = invoice_line.get('traslados_list', [])
        retenciones = invoice_line.get('retenciones_list', [])
        description_edi = ""
        taxes_list_names = []

        # Procesar traslados
        for traslado in traslados:
            impuesto = catalogo_impuestos.get(traslado['impuesto'], f"Impuesto {traslado['impuesto']}")
            tipo_factor = tipo_factor_map.get(traslado['tipo_factor'], traslado['tipo_factor'])
            tasa_o_cuota = float(traslado['tasa_o_cuota']) * 100  # Convertir a porcentaje si aplica
            if traslado['tipo_factor'] != 'Exento':
                taxes_list_names.append(f"{impuesto} {tipo_factor} {tasa_o_cuota:.2f} %")
            else:
                taxes_list_names.append(f"{impuesto} {tipo_factor}")

        # Procesar retenciones
        for retencion in retenciones:
            impuesto = catalogo_impuestos.get(retencion['impuesto'], f"Impuesto {retencion['impuesto']}")
            tipo_factor = tipo_factor_map.get(retencion['tipo_factor'], retencion['tipo_factor'])
            tasa_o_cuota = float(retencion['tasa_o_cuota']) * 100  # Convertir a porcentaje si aplica
            taxes_list_names.append(f"Retención de {impuesto} {tipo_factor} {tasa_o_cuota:.2f} %")

        # Construir la descripción
        if not taxes_list_names:
            description_edi = "Venta grabada sin Impuesto."
        elif len(taxes_list_names) == 1:
            description_edi = f"Venta grabada a {taxes_list_names[0]}"
        else:
            description_edi = f"Venta grabada a tasas de {', '.join(taxes_list_names)}"

        return description_edi

    def get_unspsc_code_dynamic_like_activity(self, invoice_line):
        # invoice_line_vals = line_vals.get('line',{})
        # invoice_line = invoice_line_vals.get('record')
        unspsc_code_id = invoice_line.product_id.unspsc_code_id.code if invoice_line.product_id.unspsc_code_id else "NA"
        if invoice_line.product_global_id:
            unspsc_code_id = invoice_line.product_global_id.unspsc_code_id.code if invoice_line.product_global_id.unspsc_code_id else "NA"
        else:
            if invoice_line.move_id.invoice_edi_activity:
                product_global = invoice_line.move_id.search_product_global()
                unspsc_code_id = product_global.unspsc_code_id.code if product_global.unspsc_code_id else "NA"
        return unspsc_code_id


    @api.model
    def _get_global_invoice_cfdi_values(self, cfdi_values_list, date, periodicity='04', origin=None):
        context = self._context
        # EXTENDS 'l10n_mx_edi'
        cfdi_values = super(L10nMXEdiDocument, self)._get_global_invoice_cfdi_values(cfdi_values_list=cfdi_values_list, date=date, periodicity=periodicity, origin=origin)
        invoice_edi_activity = context.get('invoice_edi_activity',False)
        _logger.info("\n$#### invoice_edi_activity: %s " % invoice_edi_activity)
        if invoice_edi_activity:
            conceptos_list = cfdi_values.get('conceptos_list',[])
            for conceptoline in conceptos_list:
                # _logger.info("\n#### invoice_line: %s " % invoice_line)
                clave_prod_serv = '01010101'
                _logger.info("\n######### clave_prod_serv: %s " % clave_prod_serv)
                description = self.get_edi_description_dynamic_attributes_like_activity('descripcion', conceptoline)
                _logger.info("\n######### description: %s" % description)
                clave_unidad = 'H87'
                _logger.info("\n######### clave_unidad: %s" % clave_unidad)
                unidad = 'Unidades'
                _logger.info("\n######### unidad: %s " % unidad)

                no_identificacion = conceptoline['no_identificacion']
                # if self.invoice_origin:
                #     no_identificacion = self.invoice_origin.replace("/","").replace("-","").replace(" ","")

                conceptoline['name'] = description
                conceptoline['clave_prod_serv'] = clave_prod_serv  # Cambiar la clave del producto/servicio
                conceptoline['description'] = description  # Cambiar la descripción
                conceptoline['clave_unidad'] = clave_unidad  # Cambiar la clave de unidad
                conceptoline['unidad'] = unidad  # Cambiar la unidad
                conceptoline['no_identificacion'] = no_identificacion  # Cambiar la unidad
        return cfdi_values

