# -*- coding: utf-8 -*-
# Part of l10n_mx_edi_retentions.
"""
Modelo de líneas de impuestos retenidos (ImpRetenidos) para el CFDI
de Retenciones e Información de Pagos v2.0.

Corresponde al nodo:
  <retenciones:ImpRetenidos
      BaseRet="2000"
      ImpuestoRet="001"
      MontoRet="580.00"
      TipoPagoRet="03"/>
"""

from odoo import api, fields, models


# Catálogo SAT de tipos de pago para retenciones
TIPO_PAGO_RET_SELECTION = [
    ('01', '01 - Pago provisional'),
    ('02', '02 - Pago provisional no objeto de ajuste'),
    ('03', '03 - Pago definitivo'),
    ('04', '04 - Pago provisional objeto de ajuste'),
    ('05', '05 - Ajuste al tipo de pago provisional'),
]

# Catálogo SAT de impuestos retenidos (coincide con l10n_mx_edi)
IMPUESTO_RET_SELECTION = [
    ('001', '001 - ISR'),
    ('002', '002 - IVA'),
    ('003', '003 - IEPS'),
]


class L10nMxEdiRetentionImpuesto(models.Model):
    """Línea de impuesto retenido — nodo ImpRetenidos del CFDI de Retenciones v2.0."""

    _name = 'l10n_mx_edi.retention.impuesto'
    _description = 'Impuesto Retenido CFDI Retenciones v2.0'
    _order = 'impuesto_ret, id'

    payment_id = fields.Many2one(
        comodel_name='account.payment',
        string='Pago',
        required=True,
        ondelete='cascade',
        index=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='payment_id.currency_id',
        store=True,
    )

    # ── ImpRetenidos attributes ──────────────────────────────────────────────

    base_ret = fields.Monetary(
        string='Base de Retención (BaseRet)',
        currency_field='currency_id',
        required=True,
        help='Monto del pago que sirve de base para la retención.',
    )
    impuesto_ret = fields.Selection(
        selection=IMPUESTO_RET_SELECTION,
        string='Impuesto Retenido (ImpuestoRet)',
        required=True,
        default='001',
        help='Tipo de impuesto retenido según catálogo SAT:\n'
             '001 = ISR, 002 = IVA, 003 = IEPS.',
    )
    monto_ret = fields.Monetary(
        string='Monto Retenido (MontoRet)',
        currency_field='currency_id',
        required=True,
        help='Monto del impuesto retenido correspondiente al pago.',
    )
    tipo_pago_ret = fields.Selection(
        selection=TIPO_PAGO_RET_SELECTION,
        string='Tipo de Pago (TipoPagoRet)',
        required=True,
        default='03',
        help='Indica si la retención es un pago provisional o definitivo.',
    )

    @api.onchange('base_ret', 'impuesto_ret')
    def _onchange_base_ret(self):
        """Sugiere el monto retenido según el impuesto (solo como guía)."""
        if not self.base_ret or not self.impuesto_ret:
            return
        rates = {'001': 0.30, '002': 0.16, '003': 0.08}
        rate = rates.get(self.impuesto_ret)
        if rate and not self.monto_ret:
            self.monto_ret = round(self.base_ret * rate, 2)
