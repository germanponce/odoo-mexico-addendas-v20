# -*- coding: utf-8 -*-
# Copyright 2026 Asesores y Soluciones ANFEPI | License OPL-1
# https://www.anfepi.com

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    l10n_mx_global_invoice_uuid = fields.Char(
        string="Factura Global del ticket",
        compute="_compute_l10n_mx_can_reinvoice",
        help="Folio fiscal de la Factura Global en la que salió este ticket.",
    )
    l10n_mx_can_reinvoice = fields.Boolean(compute="_compute_l10n_mx_can_reinvoice")

    @api.depends("l10n_mx_edi_cfdi_state", "account_move", "session_id.state")
    def _compute_l10n_mx_can_reinvoice(self):
        for order in self:
            uuid = order._l10n_mx_global_invoice_uuid()
            order.l10n_mx_global_invoice_uuid = uuid
            order.l10n_mx_can_reinvoice = (
                bool(uuid)
                and not order.account_move
                and order.session_id.state == "closed"
            )

    def _l10n_mx_global_invoice_uuid(self):
        """Folio de la Factura Global que incluyó este ticket, o False."""
        self.ensure_one()
        doc = self.l10n_mx_edi_document_ids.filtered(
            lambda d: d.state == "ginvoice_sent" and d.attachment_uuid
        ).sorted("id")
        return doc[-1:].attachment_uuid or False

    def _l10n_mx_check_reinvoiceable(self):
        """Condiciones sin las cuales refacturar dejaría mal la contabilidad."""
        self.ensure_one()
        if not self._l10n_mx_global_invoice_uuid():
            raise UserError(_(
                "Este ticket no salió en ninguna Factura Global timbrada, "
                "así que no hay nada que refacturar. Puedes facturarlo de la forma normal."
            ))
        if self.account_move:
            raise UserError(_(
                "El ticket %s ya tiene la factura %s.", self.name, self.account_move.name))
        # Odoo sólo lleva la venta del ticket al asiento de cierre de la sesión
        # si la orden NO está facturada (pos_session._create_account_move). Si
        # refacturamos con la sesión abierta, al cerrarla Odoo se saltaría este
        # ticket y, como la nota de crédito anula la factura, el ingreso y el
        # costo desaparecerían de los libros.
        if self.session_id.state != "closed":
            raise UserError(_(
                "La sesión %(sesion)s todavía está abierta. Hay que cerrarla antes de "
                "refacturar el ticket %(ticket)s: si no, al cerrar la sesión Odoo no "
                "registraría la venta ni el costo de este ticket.",
                sesion=self.session_id.name, ticket=self.name))

    def action_l10n_mx_pos_reinvoice(self):
        self.ensure_one()
        self._l10n_mx_check_reinvoiceable()
        return {
            "type": "ir.actions.act_window",
            "name": _("Refacturar ticket"),
            "res_model": "l10n_mx.pos.reinvoice.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }
