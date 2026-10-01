# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright 2021 German Ponce Dominguez
#
##############################################################################

# -*- coding: utf-8 -*-
import base64
import json
import random
import re
import requests
import string

from collections import defaultdict
from datetime import datetime
from json.decoder import JSONDecodeError
from lxml import etree

from odoo import _, api, models, modules, fields, tools
from odoo.exceptions import UserError
from odoo.tools import frozendict
from odoo.tools.float_utils import float_is_zero

import logging
_logger = logging.getLogger(__name__)


CFDI_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
CANCELLATION_REASON_SELECTION = [
    ('01', "01 - Invoice issued with errors (with related document)"),
    ('02', "02 - Invoice issued with errors (no replacement)"),
    ('03', "03 - The operation was not carried out"),
    ('04', "04 - Nominative operation related to the global invoice"),
]

CANCELLATION_REASON_DESCRIPTION = (
    f"{CANCELLATION_REASON_SELECTION[0][1]}.\n"
    "This option applies when there is an error in the document data, so it must be reissued. In this case, the replacement document is"
    " referenced in the cancellation request.\n"
    f"{CANCELLATION_REASON_SELECTION[1][1]}.\n"
    "This option applies when there is an error in the invoice data and no replacement document will be generated.\n"
    f"{CANCELLATION_REASON_SELECTION[2][1]}.\n"
    "This option applies when a transaction was invoiced that does not materialize.\n"
    f"{CANCELLATION_REASON_SELECTION[3][1]}.\n"
    "This option applies when a sale was included in the global invoice of operations with the general public, but should actually be"
    " excluded since the partner has requested a CFDI to be issued in their name.\n"
)

GLOBAL_INVOICE_PERIODICITY_DEFAULT_VALUES = {
    'selection': [
        ('01', "Daily"),
        ('02', "Weekly"),
        ('03', "Fortnightly"),
        ('04', "Monthly"),
        ('05', "Bimonthly"),
    ],
    'default': '04',
    'string': "Periodicity",
    'help': "The periodicity at which you want to send the CFDI global invoices.",
}

TAX_TYPE_TO_CFDI_CODE = {'isr': '001', 'iva': '002', 'ieps': '003'}
CFDI_CODE_TO_TAX_TYPE = {v: k for k, v in TAX_TYPE_TO_CFDI_CODE.items()}

USAGE_SELECTION = [
    ('G01', 'Acquisition of merchandise'),
    ('G02', 'Returns, discounts or bonuses'),
    ('G03', 'General expenses'),
    ('I01', 'Constructions'),
    ('I02', 'Office furniture and equipment investment'),
    ('I03', 'Transportation equipment'),
    ('I04', 'Computer equipment and accessories'),
    ('I05', 'Dices, dies, molds, matrices and tooling'),
    ('I06', 'Telephone communications'),
    ('I07', 'Satellite communications'),
    ('I08', 'Other machinery and equipment'),
    ('D01', 'Medical, dental and hospital expenses.'),
    ('D02', 'Medical expenses for disability'),
    ('D03', 'Funeral expenses'),
    ('D04', 'Donations'),
    ('D05', 'Real interest effectively paid for mortgage loans (room house)'),
    ('D06', 'Voluntary contributions to SAR'),
    ('D07', 'Medical insurance premiums'),
    ('D08', 'Mandatory School Transportation Expenses'),
    ('D09', 'Deposits in savings accounts, premiums based on pension plans.'),
    ('D10', 'Payments for educational services (Colegiatura)'),
    ('S01', "Without fiscal effects"),
]


# class AccountMove(models.Model):
#     _inherit = 'account.move'

#     def _l10n_mx_edi_add_invoice_cfdi_values(self, cfdi_values, percentage_paid=None, global_invoice=False):

#         # EXTENDS 'l10n_mx_edi'
#         self.ensure_one()
#         super()._l10n_mx_edi_add_invoice_cfdi_values(cfdi_values, percentage_paid=percentage_paid, global_invoice=global_invoice)
#         if cfdi_values.get('errors'):
#             return
#         cfdi_values['record'] = self

#     def _get_fix_amount_traslados(self, retenciones_reduced_list=[]):
#         print ("########### _get_fix_amount_traslados >>>>>>>>>>>>>>> ")
#         total_traslados = 0.0
#         print ("########### retenciones_reduced_list: ",retenciones_reduced_list)
#         print ("########### total_traslados: ",total_traslados)

#         return total_traslados

class L10nMXEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    def _add_base_lines_cfdi_values(self, cfdi_values, base_lines, global_invoice=False):
        # v19 MIGRATION FIX (2026-07-06): el override original era codigo de v17
        # (usaba percentage_paid / transferred_values_list / line['product'], que ya
        # no existen en v19) y tapaba al metodo del core, rompiendo la Factura Global
        # con "unexpected keyword argument 'global_invoice'". El core v19 ya maneja el
        # redondeo de decimales correctamente (_round_raw_total_excluded, tolerancia
        # estricta a 6 digitos), por lo que delegamos en el. Override neutralizado.
        res = super()._add_base_lines_cfdi_values(cfdi_values, base_lines, global_invoice=global_invoice)
        # v19 (2026-07-09): en Factura Global, agregar el folio del ticket a la
        # descripcion del concepto ("Venta - <ticket>") ademas del NoIdentificacion.
        if global_invoice:
            for base_line in base_lines:
                cv = base_line.get('l10n_mx_cfdi_values')
                if cv and cv.get('no_identificacion'):
                    cv['description'] = "Venta - %s" % cv['no_identificacion']
        return res



    # @api.model
    # def _add_base_lines_cfdi_values(self, cfdi_values, base_lines, percentage_paid=None):
    #     print ("########### _add_base_lines_cfdi_values >>>>>>>>>>>>>>> ")
    #     print ("########### cfdi_values: ",cfdi_values)
    #     print ("########### base_lines: ",base_lines)
    #     print ("########### percentage_paid: ",percentage_paid)
    #     context = self._context
    #     # EXTENDS 'l10n_mx_edi'
    #     print ("########### context: ",context)
    #     super(L10nMXEdiDocument, self)._add_base_lines_cfdi_values(cfdi_values=cfdi_values,base_lines=base_lines,percentage_paid=percentage_paid)
    #     print ("########### cfdi_values 222: ",cfdi_values)
    #     return cfdi_values
    
    # @api.model
    # def _get_global_invoice_cfdi_values(self, cfdi_values_list, date, periodicity='04', origin=None):
    #     print ("######## _get_global_invoice_cfdi_values >>>>>>>>>>>>>>>>> ")
    #     print ("########### cfdi_values_list: ",cfdi_values_list)
    #     print ("########### date: ",date)
    #     print ("########### periodicity: ",periodicity)
    #     print ("########### origin: ",origin)
    #     """ Aggregate the list of CFDI values passed as parameter into one global invoice CFDI values.

    #     :param cfdi_values_list:    A list of CFDI values.
    #     :param date:                The date of the global invoice.
    #     :param periodicity:         The periodicity. Default is '04'. See 'GLOBAL_INVOICE_PERIODICITY_DEFAULT_VALUES'.
    #     :param origin:              The origin of the CFDI when creating a replacement.
    #     :return:                    The CFDI values for the global invoice document.
    #     """

    #     def aggregate_to_one(values):
    #         values_set = set(values)
    #         return next(iter(values_set)) if len(values_set) == 1 else None

    #     def aggregate_sum_or_none(values):
    #         amounts = [x for x in values if x is not None]
    #         return sum(amounts) if amounts else None

    #     def aggregate_average_or_none(values):
    #         return sum(values) / len(values) if values else None

    #     def add_or_none(results, tax_values, key):
    #         """ Little helper to add an amount by taking care of keeping the None value (for example for 'importe' value).
    #         For some taxes, we don't want to see this attribute (e.g. Exento). So the idea is to keep the original value
    #         as None until we found a tax having a not None 'importe' amount.

    #         :param results:     The results in which we need to add the 'importe' amount.
    #         :param tax_values:  A dictionary containing the 'importe' amount of the tax.
    #         :param key:         The key to access the results.
    #         """
    #         if tax_values[key] is not None:
    #             results[key] = results[key] or 0.0
    #             results[key] += tax_values[key]

    #     if any(not x['receptor']['to_public'] for x in cfdi_values_list):
    #         raise UserError(_("You can only make a global invoice for documents marked as 'to public'."))
    #     if aggregate_to_one(x['moneda'] for x in cfdi_values_list) is None:
    #         raise UserError(_("You can't make a global invoice for invoices having different currencies."))

    #     root_company = cfdi_values_list[0]['root_company']

    #     # Sequence:
    #     sequence = self._get_global_invoice_cfdi_sequence(root_company)
    #     str_date = fields.Date.to_string(date)
    #     folio = str(sequence.number_next)
    #     serie, _interpolated_suffix = sequence._get_prefix_suffix(date=str_date, date_range=str_date)

    #     # Periodicity.
    #     document_date = max(datetime.strptime(x['fecha'], CFDI_DATE_FORMAT).date() for x in cfdi_values_list)
    #     month = document_date.month
    #     if periodicity == '05':
    #         periodicity_month = int(12 + ((month + (month % 2)) / 2))
    #     else:
    #         periodicity_month = month

    #     results = {
    #         'root_company': root_company,
    #         'company': cfdi_values_list[0]['company'],
    #         'certificate': cfdi_values_list[0]['certificate'],
    #         'sequence': sequence,
    #         'format_string': cfdi_values_list[0]['format_string'],
    #         'format_float': cfdi_values_list[0]['format_float'],
    #         'line_base_importe_dp': cfdi_values_list[0]['line_base_importe_dp'],
    #         'currency_precision': cfdi_values_list[0]['currency_precision'],

    #         'no_certificado': cfdi_values_list[0]['no_certificado'],
    #         'certificado': cfdi_values_list[0]['certificado'],
    #         'folio': folio,
    #         'serie': serie,
    #         'tipo_relacion': None,
    #         'cfdi_relationado_list': [],
    #         'information_global': {
    #             'periodicidad': periodicity,
    #             'meses': str(periodicity_month).rjust(2, '0'),
    #             'ano': str(max(int(x['fecha'][:4]) for x in cfdi_values_list)),
    #         },
    #         'emisor': cfdi_values_list[0]['emisor'],
    #         'issued_address': cfdi_values_list[0]['issued_address'],
    #         'fecha': date.strftime(CFDI_DATE_FORMAT),
    #         'metodo_pago': 'PUE',
    #         'forma_pago': max(
    #             [(x['total'], x['forma_pago']) for x in cfdi_values_list],
    #             key=lambda x: x[0],
    #         )[1],
    #         'condiciones_de_pago': None,
    #         'moneda': cfdi_values_list[0]['moneda'],
    #         'tipo_cambio': aggregate_average_or_none([x['tipo_cambio'] for x in cfdi_values_list if x['tipo_cambio']]),
    #         'tipo_de_comprobante': 'I',
    #         'exportacion': aggregate_to_one(x['exportacion'] for x in cfdi_values_list),
    #         'total_impuestos_trasladados': aggregate_sum_or_none(
    #             x.get('total_impuestos_trasladados', 0.0)
    #             for x in cfdi_values_list
    #         ),
    #         'total_impuestos_retenidos': aggregate_sum_or_none(
    #             x.get('total_impuestos_retenidos', 0.0)
    #             for x in cfdi_values_list
    #         ),
    #         'subtotal': sum(x['subtotal'] - (x['descuento'] or 0.0) for x in cfdi_values_list),
    #         'descuento': None,
    #         'total': sum(x['total'] for x in cfdi_values_list),
    #     }

    #     # Customer needs to be "Publico En General.
    #     self._add_customer_cfdi_values(results, to_public=True)

    #     # Origin.
    #     if origin:
    #         self._add_document_origin_cfdi_values(results, origin)

    #     # Lines.

    #     # Aggregated lines by pair <source document, taxes> and remove the discounts.
    #     global_withholding_reduced_values_map = defaultdict(lambda: {'base': 0.0, 'importe': None})
    #     global_transferred_values_map = defaultdict(lambda: {'base': 0.0, 'importe': None})
    #     results['conceptos_list'] = line_values_list = []
    #     for cfdi_values in cfdi_values_list:

    #         # The default values for the lines to be aggregated.
    #         lines_values_map = defaultdict(lambda: {
    #             'clave_prod_serv': '01010101',
    #             'cantidad': 1,
    #             'clave_unidad': "ACT",
    #             'unidad': None,
    #             'description': "Venta",
    #             'descuento': None,
    #             'importe': 0.0,
    #             'traslados_list': defaultdict(lambda: {'base': 0.0, 'importe': None}),
    #             'retenciones_list': defaultdict(lambda: {'base': 0.0, 'importe': None}),
    #         })

    #         # Taxes.
    #         for line_values in cfdi_values['conceptos_list']:
    #             transferred_values_map = defaultdict(lambda: {'base': 0.0, 'importe': None})
    #             withholding_values_map = defaultdict(lambda: {'base': 0.0, 'importe': None})

    #             # Split the tax amounts and keep them somewhere in order to aggregate them if necessary later.
    #             for tax_values in line_values['retenciones_list']:
    #                 tax_key = frozendict({'impuesto': tax_values['impuesto']})
    #                 add_or_none(global_withholding_reduced_values_map[tax_key], tax_values, 'importe')
    #             for result_dict, global_result_dict, result_key in (
    #                 (withholding_values_map, None, 'retenciones_list'),
    #                 (transferred_values_map, global_transferred_values_map, 'traslados_list'),
    #             ):
    #                 for tax_values in line_values[result_key]:
    #                     tax_key = frozendict({
    #                         'impuesto': tax_values['impuesto'],
    #                         'tipo_factor': tax_values['tipo_factor'],
    #                         'tasa_o_cuota': tax_values['tasa_o_cuota']
    #                     })
    #                     result_dict[tax_key]['base'] += tax_values['base']
    #                     add_or_none(result_dict[tax_key], tax_values, 'importe')
    #                     if global_result_dict is not None:
    #                         global_result_dict[tax_key]['base'] += tax_values['base']
    #                         add_or_none(global_result_dict[tax_key], tax_values, 'importe')

    #             # Build the grouping key for taxes.
    #             # This key decide if two lines belonging to the same document could be aggregated together regarding
    #             # the amounts or not.
    #             key = frozendict({
    #                 'traslados_list': frozenset(transferred_values_map.keys()),
    #                 'retenciones_list': frozenset(withholding_values_map.keys()),
    #             })
    #             aggregated_values = lines_values_map[key]

    #             # Aggregate Taxes.
    #             for tax_result_dict, key in (
    #                 (withholding_values_map, 'retenciones_list'),
    #                 (transferred_values_map, 'traslados_list'),
    #             ):
    #                 for tax_key, tax_amounts in tax_result_dict.items():
    #                     for amount_key in tax_amounts:
    #                         add_or_none(aggregated_values[key][tax_key], tax_amounts, amount_key)

    #             # Aggregate others fields.
    #             aggregated_values['importe'] += (line_values['importe'] or 0.0) - (line_values['descuento'] or 0.0)

    #         # Append lines.
    #         for line_values, aggregated_values in lines_values_map.items():
    #             cfdi_line_values = {
    #                 **line_values,
    #                 **aggregated_values,
    #                 'no_identificacion': cfdi_values['document_name'],
    #                 'traslados_list': [
    #                     {**k, **v}
    #                     for k, v in aggregated_values['traslados_list'].items()
    #                 ],
    #                 'retenciones_list': [
    #                     {**k, **v}
    #                     for k, v in aggregated_values['retenciones_list'].items()
    #                 ],
    #             }
    #             if cfdi_line_values['traslados_list'] or cfdi_line_values['retenciones_list']:
    #                 cfdi_line_values['objeto_imp'] = '02'
    #             else:
    #                 cfdi_line_values['objeto_imp'] = '01'
    #             cfdi_line_values['valor_unitario'] = cfdi_line_values['importe'] / cfdi_line_values['cantidad']

    #             # 'valor_unitario' must be different to zero.
    #             if not cfdi_line_values['valor_unitario']:
    #                 continue

    #             line_values_list.append(cfdi_line_values)

    #     # Taxes.
    #     results['retenciones_reduced_list'] = [
    #         {**k, **v}
    #         for k, v in global_withholding_reduced_values_map.items()
    #     ]
    #     results['traslados_list'] = [
    #         {**k, **v}
    #         for k, v in global_transferred_values_map.items()
    #     ]
    #     results['objeto_imp'] = '02' if results['retenciones_reduced_list'] or results['traslados_list'] else '03'

    #     # Cleanup attributes for Exento taxes.
    #     if all(x['total_impuestos_trasladados'] is None for x in cfdi_values_list):
    #         results['total_impuestos_trasladados'] = None
    #     if all(x['total_impuestos_retenidos'] is None for x in cfdi_values_list):
    #         results['total_impuestos_retenidos'] = None

