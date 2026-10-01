# -*- coding: utf-8 -*-
# German Ponce Dominguez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class SaleOrder(models.Model):
    """Agrega campos logísticos a la orden de venta usados en el reporte."""

    _inherit = 'sale.order'

    via_embarque = fields.Char(
        string='Vía de Embarque',
        help="Modo o vía de transporte utilizado para el embarque (terrestre, aéreo, etc.).",
    )
    no_orden = fields.Char(
        string='No. Orden',
        help="Número de orden del cliente o referencia interna de compra.",
    )
