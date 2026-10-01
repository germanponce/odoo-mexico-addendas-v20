# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from odoo import models, fields, api # type: ignore

class InvoiceWizard(models.TransientModel):
    _name = 'invoice.wizard'
    _description = 'Invoice Selection Wizard'

    invoice_id = fields.Many2one('account.move', string='Invoice')

    def action_select_invoice(self):
        active_id = self.env.context.get('active_id')
        downloaded_xml = self.env['account.edi.downloaded.xml.sat'].browse(active_id)
        move = self.invoice_id
        move.xml_imported_id = downloaded_xml.id
        downloaded_xml.write({
            'state': move.state,
            'imported': True,
            'invoice_id': move.id,
        })
        # Adjuntar el XML + UUID a la poliza (aunque este publicada/conciliada): asi
        # relacionar a mano deja la factura COMPLETA (con su CFDI y UUID), no solo
        # ligada. Es solo metadata, no toca importes ni conciliacion.
        downloaded_xml._attach_xml_and_uuid_to_move(move)
        return {'type': 'ir.actions.act_window_close'}