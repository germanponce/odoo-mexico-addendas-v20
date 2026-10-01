# -*- coding: utf-8 -*-
# German Ponce Dominguez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models

# Mapeo SAT: tipo de impuesto → clave CFDI
TAX_TYPE_TO_CFDI_CODE = {'isr': '001', 'iva': '002', 'ieps': '003'}


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # ------------------------------------------------------------------
    # Métodos de utilidad para reportes
    # ------------------------------------------------------------------

    def get_taxes_line_details(self):
        """Devuelve una lista con el detalle de cada impuesto de la línea.

        Cada elemento es una lista con:
            [nombre_impuesto, factor_type, base, tasa, importe]

        Ejemplo:
            ['002-IVA', 'Tasa', 100.00, 0.16, 16.00]
        """
        taxes_list = []
        price = self.price_unit * (1.0 - (self.discount or 0.0) / 100.0)
        move_is_refund = self.move_id.move_type in ('in_refund', 'out_refund')

        tax_computed = {
            t['id']: t
            for t in self.tax_ids.compute_all(
                price,
                quantity=self.quantity,
                currency=self.currency_id,
                product=self.product_id,
                partner=self.partner_id,
                is_refund=move_is_refund,
            )['taxes']
        }

        for tax in self.tax_ids:
            tax_dict = tax_computed.get(tax.id, {})
            amount = round(abs(tax_dict.get('amount', tax.amount / 100.0 * float('%.2f' % self.price_subtotal))), 2)
            rate = round(abs(tax.amount), 2)
            amount_base = round(abs(tax_dict.get('base', self.price_subtotal)), 2)
            tax_rate = rate if tax.amount_type == 'fixed' else rate / 100.0

            cfdi_code = TAX_TYPE_TO_CFDI_CODE.get(tax.l10n_mx_tax_type, '002')
            label_map = {'001': '001-ISR', '002': '002-IVA', '003': '003-IEPS'}
            tax_name = label_map.get(cfdi_code, cfdi_code)

            taxes_list.append([tax_name, tax.l10n_mx_factor_type, amount_base, tax_rate, amount])

        return taxes_list
