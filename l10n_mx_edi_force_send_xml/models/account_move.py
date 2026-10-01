# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_open_xml_wizard(self):
        """Abre wizard para adjuntar XML personalizado"""
        self.ensure_one()
        
        # Buscar documento EDI existente
        edi_doc = self.l10n_mx_edi_document_ids.filtered(lambda d: d.state != 'xml_signed')[:1]
        
        return {
            'name': _('Adjuntar XML Personalizado'),
            'type': 'ir.actions.act_window',
            'res_model': 'xml.attachment.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_mx_edi_force_send_xml.view_xml_attachment_wizard_form').id,
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_document_id': edi_doc.id if edi_doc else False,
                'default_use_custom_xml': True,
            }
        }