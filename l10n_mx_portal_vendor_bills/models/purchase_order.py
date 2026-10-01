# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import base64
from odoo import models, api, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    vendor_uuid = fields.Char('Folio Fiscal (Portal)')

    @api.model
    def portal_bills_insert_attachment(self, files, filename):
        """Adjunta archivos PDF/PO/Acuse a la factura generada desde el portal."""
        attachment = self.env['ir.attachment'].sudo()
        suffixes = {
            'purchase_order': 'PO',
            'receipt': 'AC',
        }
        for fname, xml_file in files.items():
            if not xml_file:
                continue
            suffix = suffixes.get(fname, '')
            new_name = filename if not suffix else '%s_%s' % (filename, suffix)
            new_name = new_name.replace("/", "_").replace("__", "_")
            # xml_file.mimetype puede ser 'application/pdf', 'text/xml', etc.
            ext = xml_file.mimetype.split('/')[-1]
            attachment |= attachment.create({
                'name': '%s.%s' % (new_name, ext),
                'datas': base64.b64encode(xml_file.read()),
                'res_model': self._name,
                'res_id': self.id,
            })
        return attachment


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    with_remaining_quantity = fields.Boolean(
        string='Cantidad Pendiente por Facturar',
        compute='_get_with_remaining_quantity',
        # store=False por defecto — no se puede usar en domain de búsqueda SQL
        # a menos que se almacene. En Odoo 18 el portal filtra en Python.
    )

    @api.depends('order_line', 'order_line.qty_to_invoice', 'state')
    def _get_with_remaining_quantity(self):
        for rec in self:
            with_remaining_quantity = False
            if rec.state not in ('cancel', 'done'):
                for line in rec.order_line:
                    if line.qty_to_invoice:
                        with_remaining_quantity = True
                    elif line.qty_received and line.qty_to_invoice <= line.product_qty:
                        with_remaining_quantity = True
                # Si la recepción está completa y no hay pendiente, marcar False
                if rec.receipt_status == 'full':
                    with_remaining_quantity = False
            rec.with_remaining_quantity = with_remaining_quantity

    @api.model
    def insert_attachment(self, files, filename):
        """Adjunta archivos a la Orden de Compra (copia espejo a la factura)."""
        attachment = self.env['ir.attachment'].sudo()
        suffixes = {
            'purchase_order': 'PO',
            'receipt': 'AC',
        }
        for fname, xml_file in files.items():
            if not xml_file:
                continue
            suffix = suffixes.get(fname, '')
            new_name = filename if not suffix else '%s_%s' % (filename, suffix)
            new_name = new_name.replace("/", "_").replace("__", "_")
            ext = xml_file.mimetype.split('/')[-1]
            attachment |= attachment.create({
                'name': '%s.%s' % (new_name, ext),
                'datas': base64.b64encode(xml_file.read()),
                'res_model': self._name,
                'res_id': self.id,
            })
        return attachment
