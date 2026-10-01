# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── Campos computed para separar por tipo ──
    contact_child_ids = fields.One2many(
        'res.partner', 'parent_id', string='Contactos',
        domain=[('type', '=', 'contact')],
    )
    delivery_child_ids = fields.One2many(
        'res.partner', 'parent_id', string='Direcciones de Entrega',
        domain=[('type', '=', 'delivery')],
    )
    invoice_child_ids = fields.One2many(
        'res.partner', 'parent_id', string='Direcciones de Factura',
        domain=[('type', '=', 'invoice')],
    )
    other_child_ids = fields.One2many(
        'res.partner', 'parent_id', string='Otras Direcciones',
        domain=[('type', 'not in', ['contact', 'delivery', 'invoice'])],
    )

    # ── Contadores para badges ──
    contact_child_count = fields.Integer(
        compute='_compute_child_counts', string='# Contactos',
    )
    delivery_child_count = fields.Integer(
        compute='_compute_child_counts', string='# Entregas',
    )
    invoice_child_count = fields.Integer(
        compute='_compute_child_counts', string='# Facturas',
    )

    @api.depends('child_ids', 'child_ids.type')
    def _compute_child_counts(self):
        for partner in self:
            children = partner.child_ids
            partner.contact_child_count = len(children.filtered(lambda c: c.type == 'contact'))
            partner.delivery_child_count = len(children.filtered(lambda c: c.type == 'delivery'))
            partner.invoice_child_count = len(children.filtered(lambda c: c.type == 'invoice'))

    # ── Acciones de botones ──
    def _get_contact_create_action(self, contact_type, form_title):
        self.ensure_one()
        ctx = {
            'default_parent_id': self.id,
            'default_type': contact_type,
            'default_lang': self.lang,
            'default_user_id': self.user_id.id,
        }
        if contact_type == 'contact':
            ctx.update({
                'default_street': self.street,
                'default_street2': self.street2,
                'default_city': self.city,
                'default_state_id': self.state_id.id,
                'default_zip': self.zip,
                'default_country_id': self.country_id.id,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': form_title,
            'res_model': 'res.partner',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def action_create_contact(self):
        return self._get_contact_create_action('contact', _('Nuevo Contacto'))

    def action_create_delivery_address(self):
        return self._get_contact_create_action('delivery', _('Nueva Dirección de Entrega'))

    def action_create_invoice_address(self):
        return self._get_contact_create_action('invoice', _('Nueva Dirección de Factura'))