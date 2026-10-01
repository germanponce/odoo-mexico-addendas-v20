# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""Reporte de Conciliacion: Complementos de Pago Recibidos (Proveedores).

Espejo del reporte de Clientes pero para facturas de proveedor PPD:
- move_type = 'in_invoice'
- cfdi_type = 'recibidos' en account.edi.downloaded.xml.sat
- complementos de pago tipo 'P' recibidos (no emitidos por nosotros)

Ver complemento_pago_cliente_report.py para diseno detallado.
"""
from odoo import api, fields, models, tools


class ComplementoPagoProveedorReport(models.Model):
    _name = "l10n_mx.complemento.pago.proveedor.report"
    _description = "Reporte Complementos de Pago - Proveedores (Recibidos)"
    _auto = False
    _order = "invoice_date desc, invoice_number, complement_uuid"

    invoice_id = fields.Many2one(
        "account.move", string="Factura Proveedor (ref)", readonly=True, index=True,
    )
    payment_id = fields.Many2one(
        "account.payment", string="Pago", readonly=True, index=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", readonly=True, index=True,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Proveedor", readonly=True, index=True,
    )

    rfc = fields.Char(string="RFC", readonly=True)
    razon_social = fields.Char(string="Razón Social", readonly=True)
    invoice_number = fields.Char(string="Factura", readonly=True)
    invoice_uuid = fields.Char(string="UUID Factura", readonly=True)
    invoice_date = fields.Date(string="Fecha Factura", readonly=True)
    invoice_total = fields.Monetary(
        string="Total Factura", readonly=True, currency_field="currency_id",
    )

    complement_uuid = fields.Char(string="UUID Complemento", readonly=True)
    complement_date = fields.Date(string="Fecha Complemento", readonly=True)
    monto_pagado = fields.Monetary(
        string="Monto Pagado", readonly=True, currency_field="currency_id",
    )
    saldo_insoluto = fields.Monetary(
        string="Saldo Insoluto", readonly=True, currency_field="currency_id",
    )

    estado_odoo = fields.Selection([
        ("not_paid", "No Pagado"),
        ("in_payment", "En Pago"),
        ("paid", "Pagado"),
        ("partial", "Pago Parcial"),
        ("reversed", "Revertido"),
        ("invoicing_legacy", "Invoicing Legacy"),
    ], string="Estado Factura Odoo", readonly=True)
    estado_sat_factura = fields.Selection([
        ("Vigente", "Vigente"),
        ("Cancelado", "Cancelado"),
        ("No Encontrado", "No Encontrado"),
        ("Sin Definir", "Sin Definir"),
    ], string="Estado SAT Factura", readonly=True)
    estado_sat_complemento = fields.Selection([
        ("Vigente", "Vigente"),
        ("Cancelado", "Cancelado"),
        ("No Encontrado", "No Encontrado"),
        ("Sin Definir", "Sin Definir"),
    ], string="Estado SAT Complemento", readonly=True)

    resultado = fields.Selection([
        ("success", "Verde - Correcto"),
        ("warning", "Amarillo - Advertencia"),
        ("error", "Rojo - Diferencia"),
    ], string="Resultado", readonly=True, index=True)
    observaciones = fields.Char(string="Observaciones", readonly=True)

    currency_id = fields.Many2one(
        "res.currency", string="Moneda", readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
CREATE OR REPLACE VIEW {self._table} AS

WITH
inv_pay_reconciles AS (
    SELECT
        inv_aml.move_id AS invoice_id,
        pay.id AS payment_id,
        SUM(pr.amount) AS reconciled_amount
    FROM account_partial_reconcile pr
    JOIN account_move_line inv_aml ON inv_aml.id = pr.debit_move_id
    JOIN account_move inv_m
        ON inv_m.id = inv_aml.move_id AND inv_m.move_type = 'in_invoice'
    JOIN account_move_line pay_aml ON pay_aml.id = pr.credit_move_id
    JOIN account_payment pay ON pay.move_id = pay_aml.move_id
    GROUP BY inv_aml.move_id, pay.id

    UNION ALL

    SELECT
        inv_aml.move_id AS invoice_id,
        pay.id AS payment_id,
        SUM(pr.amount) AS reconciled_amount
    FROM account_partial_reconcile pr
    JOIN account_move_line inv_aml ON inv_aml.id = pr.credit_move_id
    JOIN account_move inv_m
        ON inv_m.id = inv_aml.move_id AND inv_m.move_type = 'in_invoice'
    JOIN account_move_line pay_aml ON pay_aml.id = pr.debit_move_id
    JOIN account_payment pay ON pay.move_id = pay_aml.move_id
    GROUP BY inv_aml.move_id, pay.id
),
inv_pay_agg AS (
    SELECT invoice_id, payment_id, SUM(reconciled_amount) AS reconciled_amount
    FROM inv_pay_reconciles
    GROUP BY invoice_id, payment_id
),
-- Total reconciliado por payment (suma de TODAS las facturas que cubre).
-- Necesario porque un REP puede cubrir varias facturas y la comparacion
-- contra el amount_total del REP debe ser contra esta suma, NO contra el
-- reconciled_amount de UNA sola factura (bug v<=.57).
pay_total_reconciled AS (
    SELECT payment_id, SUM(reconciled_amount) AS total_reconciled
    FROM inv_pay_agg
    GROUP BY payment_id
),
ppd_invoices AS (
    SELECT
        inv.id,
        inv.company_id,
        inv.partner_id,
        inv.name,
        inv.invoice_date,
        inv.amount_total,
        inv.amount_residual,
        inv.payment_state,
        inv.currency_id,
        COALESCE(NULLIF(inv.stored_sat_uuid, ''), inv.l10n_mx_edi_cfdi_uuid) AS uuid_odoo
    FROM account_move inv
    LEFT JOIN l10n_mx_edi_payment_method pm
        ON pm.id = inv.l10n_mx_edi_payment_method_id
    WHERE inv.move_type = 'in_invoice'
      AND inv.state = 'posted'
      AND inv.payment_state IN ('paid', 'in_payment', 'partial')
      -- Deteccion PPD multipath:
      AND (
          inv.payment_method = 'PPD'
          OR pm.code = '99'
          OR (inv.invoice_date_due IS NOT NULL
              AND inv.invoice_date IS NOT NULL
              AND inv.invoice_date_due > inv.invoice_date)
      )
)
SELECT
    ROW_NUMBER() OVER (
        ORDER BY inv.invoice_date DESC NULLS LAST, inv.id, COALESCE(pay.id, 0)
    ) AS id,
    inv.id AS invoice_id,
    inv.company_id,
    inv.partner_id,
    p.vat AS rfc,
    p.name AS razon_social,
    inv.name AS invoice_number,
    inv.uuid_odoo AS invoice_uuid,
    inv.invoice_date,
    inv.amount_total AS invoice_total,
    pay.id AS payment_id,
    COALESCE(NULLIF(pay.stored_sat_uuid, ''), pay_move.l10n_mx_edi_cfdi_uuid) AS complement_uuid,
    pay_move.date AS complement_date,
    ipa.reconciled_amount AS monto_pagado,
    inv.amount_residual AS saldo_insoluto,
    inv.payment_state AS estado_odoo,
    inv_sat.sat_state AS estado_sat_factura,
    comp_sat.sat_state AS estado_sat_complemento,
    CASE
        WHEN inv_sat.id IS NULL THEN 'error'
        WHEN ipa.payment_id IS NULL THEN 'error'
        WHEN ipa.payment_id IS NOT NULL AND comp_sat.id IS NULL THEN 'error'
        WHEN inv.uuid_odoo IS NOT NULL AND inv_sat.name IS NOT NULL
             AND UPPER(inv_sat.name) != UPPER(inv.uuid_odoo) THEN 'error'
        WHEN COALESCE(NULLIF(pay.stored_sat_uuid, ''), pay_move.l10n_mx_edi_cfdi_uuid) IS NOT NULL
             AND comp_sat.name IS NOT NULL
             AND UPPER(comp_sat.name) != UPPER(COALESCE(NULLIF(pay.stored_sat_uuid, ''), pay_move.l10n_mx_edi_cfdi_uuid))
             THEN 'error'
        WHEN comp_sat.id IS NOT NULL
             AND ABS(COALESCE(ptr.total_reconciled, 0) - COALESCE(comp_sat.amount_total, 0)) > 0.01
             THEN 'error'
        WHEN comp_sat.sat_state = 'Cancelado' AND pay_move.state IS NOT NULL AND pay_move.state != 'cancel'
             THEN 'error'
        WHEN comp_sat.sat_state IS NOT NULL AND comp_sat.sat_state != 'Cancelado'
             AND pay_move.state = 'cancel' THEN 'error'
        WHEN comp_sat.sat_state = 'Cancelado' AND pay_move.state = 'cancel' THEN 'warning'
        WHEN comp_sat.id IS NOT NULL
             AND ABS(COALESCE(ptr.total_reconciled, 0) - COALESCE(comp_sat.amount_total, 0)) > 0
             THEN 'warning'
        ELSE 'success'
    END AS resultado,
    CASE
        WHEN inv_sat.id IS NULL THEN 'Factura no localizada en XML SAT'
        WHEN ipa.payment_id IS NULL THEN 'Factura pagada sin pago Odoo conciliado'
        WHEN ipa.payment_id IS NOT NULL AND comp_sat.id IS NULL THEN 'Pago Odoo sin Complemento de Pago recibido en SAT'
        WHEN inv.uuid_odoo IS NOT NULL AND inv_sat.name IS NOT NULL
             AND UPPER(inv_sat.name) != UPPER(inv.uuid_odoo) THEN 'UUID factura Odoo != UUID factura SAT'
        WHEN COALESCE(NULLIF(pay.stored_sat_uuid, ''), pay_move.l10n_mx_edi_cfdi_uuid) IS NOT NULL
             AND comp_sat.name IS NOT NULL
             AND UPPER(comp_sat.name) != UPPER(COALESCE(NULLIF(pay.stored_sat_uuid, ''), pay_move.l10n_mx_edi_cfdi_uuid))
             THEN 'UUID complemento Odoo != UUID complemento SAT'
        WHEN comp_sat.id IS NOT NULL
             AND ABS(COALESCE(ptr.total_reconciled, 0) - COALESCE(comp_sat.amount_total, 0)) > 0.01
             THEN 'Importe pagado distinto entre Odoo y SAT (>0.01)'
        WHEN comp_sat.sat_state = 'Cancelado' AND pay_move.state IS NOT NULL AND pay_move.state != 'cancel'
             THEN 'Complemento cancelado en SAT, activo en Odoo'
        WHEN comp_sat.sat_state IS NOT NULL AND comp_sat.sat_state != 'Cancelado'
             AND pay_move.state = 'cancel' THEN 'Complemento activo en SAT, cancelado en Odoo'
        WHEN comp_sat.sat_state = 'Cancelado' AND pay_move.state = 'cancel'
             THEN 'Complemento cancelado en ambos sistemas (informativo)'
        WHEN comp_sat.id IS NOT NULL
             AND ABS(COALESCE(ptr.total_reconciled, 0) - COALESCE(comp_sat.amount_total, 0)) > 0
             THEN 'Diferencia de redondeo (<=0.01)'
        ELSE 'OK'
    END AS observaciones,
    inv.currency_id

FROM ppd_invoices inv
INNER JOIN res_partner p ON p.id = inv.partner_id
LEFT JOIN account_edi_downloaded_xml_sat inv_sat
    ON inv_sat.invoice_id = inv.id
    AND inv_sat.cfdi_type = 'recibidos'
    AND COALESCE(inv_sat.document_type, '') IN ('I', 'E', '')
LEFT JOIN inv_pay_agg ipa ON ipa.invoice_id = inv.id
LEFT JOIN account_payment pay ON pay.id = ipa.payment_id
LEFT JOIN account_move pay_move ON pay_move.id = pay.move_id
LEFT JOIN pay_total_reconciled ptr ON ptr.payment_id = pay.id
LEFT JOIN account_edi_downloaded_xml_sat comp_sat
    ON comp_sat.payment_id = pay.id
    AND comp_sat.cfdi_type = 'recibidos'
    AND comp_sat.document_type = 'P'
;
        """)
