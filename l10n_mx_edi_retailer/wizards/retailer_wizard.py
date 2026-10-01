# -*- coding: utf-8 -*-

from odoo import api, fields, models


class L10nMxEdiRetailerWizard(models.TransientModel):
    _name = 'l10n_mx_edi.retailer.wizard'
    _description = 'Complemento Detallista'

    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string="Factura",
        required=True,
    )
    status = fields.Selection(
        selection=[
            ('original', 'Original'),
            ('copy', 'Copy'),
            ('reemplaza', 'Reemplaza'),
            ('delete', 'Delete'),
        ],
        string="Estatus del Documento",
        required=True,
        default='original',
    )
    delivery = fields.Char(
        string="Folio(s) de Remisión",
        help="Número(s) emitido(s) por el receptor al recibir la mercancía, separados por coma.",
    )
    delivery_date = fields.Date(
        string="Fecha de Remisión",
        help="Fecha en la que el cliente recibió la mercancía.",
    )
    purchase_order_date = fields.Date(
        string="Fecha de Orden de Compra",
        help="Fecha de la orden de compra a la que hace referencia la factura.",
    )
    purchase_order_name = fields.Char(
        string="No. de Orden de Compra",
    )
    purchase_contact_name = fields.Char(
        string="Contacto de Compras",
        help="Número o nombre del contacto/departamento de compras del cliente.",
    )
    special_service_type = fields.Selection(
        selection=[
            ('off_invoice', 'Off Invoice'),
            ('bill_back', 'Bill Back'),
        ],
        string="Tipo de Descuento/Cargo",
    )

    @api.model
    def default_get(self, fields_list):
        # Precarga el wizard con los valores ya guardados en la factura,
        # si el wizard ya se había corrido antes para ese documento.
        res = super().default_get(fields_list)
        invoice = self.env['account.move'].browse(self.env.context.get('default_invoice_id'))
        if invoice:
            res.update({
                'status': invoice.l10n_mx_edi_retailer_status or 'original',
                'delivery': invoice.l10n_mx_edi_retailer_delivery,
                'delivery_date': invoice.l10n_mx_edi_retailer_delivery_date,
                'purchase_order_date': invoice.l10n_mx_edi_retailer_purchase_order_date,
                'purchase_order_name': invoice.l10n_mx_edi_retailer_purchase_order_name,
                'purchase_contact_name': invoice.l10n_mx_edi_retailer_purchase_contact_name,
                'special_service_type': invoice.l10n_mx_edi_retailer_special_service_type,
            })
        return res

    def action_confirm(self):
        self.ensure_one()
        self.invoice_id.write({
            'addenda_type': 'retailer',
            'l10n_mx_edi_retailer_status': self.status,
            'l10n_mx_edi_retailer_delivery': self.delivery,
            'l10n_mx_edi_retailer_delivery_date': self.delivery_date,
            'l10n_mx_edi_retailer_purchase_order_date': self.purchase_order_date,
            'l10n_mx_edi_retailer_purchase_order_name': self.purchase_order_name,
            'l10n_mx_edi_retailer_purchase_contact_name': self.purchase_contact_name,
            'l10n_mx_edi_retailer_special_service_type': self.special_service_type,
        })
        return {'type': 'ir.actions.act_window_close'}
