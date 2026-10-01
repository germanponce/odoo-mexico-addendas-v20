# -*- coding: utf-8 -*-
# German Ponce Dominguez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountMove(models.Model):
    """Extiende account.move con utilidades para reportes CFDI."""

    _inherit = 'account.move'

    # ------------------------------------------------------------------
    # Métodos de utilidad para reportes
    # ------------------------------------------------------------------

    def get_tipo_cambio(self):
        """Retorna el tipo de cambio de la divisa de la factura respecto a la
        moneda de la empresa, en la fecha de la factura.

        Retorna 1.0 si la moneda de la factura ya es la moneda de la empresa.
        """
        self.ensure_one()
        company_currency = self.company_id.currency_id
        inv_currency = self.currency_id

        if company_currency == inv_currency:
            return 1.0

        date = self.invoice_date or self.date or fields.Date.context_today(self)
        return inv_currency._convert(
            1.0,
            company_currency,
            self.company_id,
            date,
            round=False,
        )

    def get_aseguradora(self):
        aseguradora = ""
        if self.insurance_ids:
            aseguradora = self.insurance_ids[0].insurance_partner_id.name
        return aseguradora

    def get_aseguradora_poliza(self):
        aseguradora_poliza = ""
        if self.insurance_ids:
            aseguradora_poliza = self.insurance_ids[0].insurance_policy
        return aseguradora_poliza
