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
    _inherit = 'pos.order'

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
        invoice_edi_activity = context.get('invoice_edi_activity', False)
        if invoice_edi_activity:
            document.invoice_edi_activity = invoice_edi_activity
        return document

    def get_edi_description_dynamic_attributes_like_activity(self, edi_attr, base_line):
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

        # v19 MIGRATION FIX: en el core actual, el detalle de impuestos de cada
        # línea ya no viene en 'traslados_list'/'retenciones_list' dentro de un
        # diccionario tipo "invoice_line" — ahora cada base_line trae su propio
        # 'tax_details' (con 'tax_details_per_record'/totales agregados) armado
        # por account.tax. Se usa 'tax_details' directamente.
        tax_details = base_line.get('tax_details', {}) or {}
        taxes_data = tax_details.get('taxes_data', [])
        taxes_list_names = []

        for tax_data in taxes_data:
            tax = tax_data.get('tax')
            if not tax:
                continue
            tax_name = {'ISR': '001', 'IVA': '002', 'IEPS': '003'}
            impuesto_code = {'isr': '001', 'iva': '002', 'ieps': '003'}.get((tax.l10n_mx_tax_type or '').lower(), '002')
            impuesto = catalogo_impuestos.get(impuesto_code, f"Impuesto {impuesto_code}")
            is_withholding = tax.amount < 0.0
            tipo_factor = 'Exento' if tax.amount == 0.0 else ('Cuota' if tax.amount_type == 'fixed' else 'Tasa')
            tipo_factor_label = tipo_factor_map.get(tipo_factor, tipo_factor)
            tasa_o_cuota = abs(tax.amount)
            if tipo_factor != 'Exento':
                label = f"{impuesto} {tipo_factor_label} {tasa_o_cuota:.2f} %"
            else:
                label = f"{impuesto} {tipo_factor_label}"
            if is_withholding:
                label = f"Retención de {label}"
            taxes_list_names.append(label)

        if not taxes_list_names:
            description_edi = "Venta grabada sin Impuesto."
        elif len(taxes_list_names) == 1:
            description_edi = f"Venta grabada a {taxes_list_names[0]}"
        else:
            description_edi = f"Venta grabada a tasas de {', '.join(taxes_list_names)}"

        return description_edi

    def get_unspsc_code_dynamic_like_activity(self, invoice_line):
        unspsc_code_id = invoice_line.product_id.unspsc_code_id.code if invoice_line.product_id.unspsc_code_id else "NA"
        if getattr(invoice_line, 'product_global_id', False):
            unspsc_code_id = invoice_line.product_global_id.unspsc_code_id.code if invoice_line.product_global_id.unspsc_code_id else "NA"
        else:
            if invoice_line.move_id.invoice_edi_activity:
                product_global = invoice_line.move_id.search_product_global()
                unspsc_code_id = product_global.unspsc_code_id.code if product_global.unspsc_code_id else "NA"
        return unspsc_code_id

    def _add_global_invoice_cfdi_values(self, cfdi_values, cfdi_lines, document_date=None, periodicity='04', origin=None):
        # EXTENDS 'l10n_mx_edi'
        # v19 MIGRATION FIX: el método real del core se llama
        # `_add_global_invoice_cfdi_values` (antes `_get_global_invoice_cfdi_values`)
        # y MUTA `cfdi_values` en el lugar, ya no regresa un diccionario nuevo.
        context = self._context
        super()._add_global_invoice_cfdi_values(
            cfdi_values, cfdi_lines, document_date=document_date, periodicity=periodicity, origin=origin,
        )
        invoice_edi_activity = context.get('invoice_edi_activity', False)
        if invoice_edi_activity:
            # v19 MIGRATION FIX: los conceptos ya no viven en
            # cfdi_values['conceptos_list'] con claves libres (name,
            # clave_prod_serv, description, clave_unidad, unidad,
            # no_identificacion) — ahora cada línea es un "base_line" (dict
            # de account.tax._prepare_base_line_for_taxes_computation) sin
            # esas claves de presentación. Se agregan directamente sobre cada
            # base_line, ya que 'l10n_mx_cfdi_values' es el diccionario que
            # `_add_base_lines_cfdi_values` usa para construir <cfdi:Concepto>.
            for base_line in cfdi_values.get('base_lines', []):
                clave_prod_serv = '01010101'
                description = self.get_edi_description_dynamic_attributes_like_activity('descripcion', base_line)
                clave_unidad = 'H87'
                unidad = 'Unidades'

                l10n_mx_cfdi_values = base_line.setdefault('l10n_mx_cfdi_values', {})
                l10n_mx_cfdi_values.update({
                    'clave_prod_serv': clave_prod_serv,
                    'description': description,
                    'clave_unidad': clave_unidad,
                    'unidad': unidad,
                })
