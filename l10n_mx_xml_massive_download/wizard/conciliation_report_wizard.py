# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from odoo import models, fields, api
from datetime import date

class ConciliationReportWizard(models.TransientModel):
    _name = 'conciliation.report.wizard'
    _description = 'Asistente de Reporte de Conciliación SAT vs Odoo'

    start_date = fields.Date(
        string='Fecha Inicio',
        required=True,
        default=lambda self: date(date.today().year, 1, 1)
    )
    end_date = fields.Date(
        string='Fecha Fin',
        required=True,
        default=fields.Date.today
    )
    exclude_externally_stamped = fields.Boolean(
        string="Excluir N y T emitidos (timbrado externo)",
        default=False,
        help="Marque si la nomina y/o traslados se timbran fuera de Odoo. "
             "Oculta secciones de Nomina y Traslados emitidos para evitar "
             "diferencias artificiales del 100%.",
    )
    exclude_all_emitidos = fields.Boolean(
        string="Excluir TODOS los emitidos (Facturas, NC, Pagos, N, T)",
        default=False,
        help="Si TODO el flujo de emision (facturas, notas de credito y pagos) "
             "se timbra fuera de Odoo, marque esta opcion para ocultar todas las "
             "secciones de emitidos. El reporte se concentrara solo en recibidos.",
    )
    display_unit = fields.Selection(
        [
            ('units', 'Unidades (1,234,567.89)'),
            ('units_no_dec', 'Unidades sin decimales (1,234,568)'),
            ('thousands', 'Miles (1,234.6 K)'),
            ('millions', 'Millones (1.23 M)'),
        ],
        string="Formato de Cifras",
        default='units',
        required=True,
        help="Como se mostraran los montos en el reporte. Util para reportes "
             "ejecutivos donde los millones son mas legibles que centavos.",
    )

    def action_generate_report(self):
        """Genera el reporte de conciliación y abre la vista list"""
        self.ensure_one()
        return self.env['sat.conciliation.report'].generate_report(
            self.start_date,
            self.end_date,
            exclude_externally_stamped=self.exclude_externally_stamped,
            exclude_all_emitidos=self.exclude_all_emitidos,
            display_unit=self.display_unit,
        )