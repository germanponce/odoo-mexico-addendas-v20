# -*- coding: utf-8 -*-
from odoo import fields, models


class MxCfdiTaxLine(models.Model):
    """Línea de impuesto leída del nodo global <cfdi:Impuestos> del CFDI."""
    _name = 'mx.cfdi.tax.line'
    _description = 'Línea de Impuesto CFDI'
    _order = 'tipo, codigo'

    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Factura',
        required=True,
        ondelete='cascade',
        index=True,
    )
    tipo = fields.Selection(
        selection=[
            ('traslado', 'Traslado'),
            ('retencion', 'Retención'),
        ],
        string='Tipo',
        required=True,
    )
    # Catálogo SAT: 001=ISR  002=IVA  003=IEPS
    codigo = fields.Char(string='Código Impuesto')
    # Catálogo SAT: Tasa | Cuota | Exento
    tipo_factor = fields.Char(string='Tipo Factor')
    tasa_o_cuota = fields.Char(string='Tasa o Cuota')
    importe = fields.Float(string='Importe', digits=(16, 4))
