# -*- coding: utf-8 -*-
# Copyright 2026 Asesores y Soluciones ANFEPI | License OPL-1
# https://www.anfepi.com

import base64
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

RFC_GENERICO = "XAXX010101000"


class L10nMxPosReinvoiceWizard(models.TransientModel):
    _name = "l10n_mx.pos.reinvoice.wizard"
    _description = "Refacturar un ticket que saliÃ³ en una Factura Global"

    order_id = fields.Many2one("pos.order", required=True, readonly=True, string="Ticket")
    global_uuid = fields.Char("Factura Global", compute="_compute_datos", readonly=True)
    amount_total = fields.Monetary("Importe", compute="_compute_datos", readonly=True)
    currency_id = fields.Many2one("res.currency", compute="_compute_datos")
    partner_id = fields.Many2one(
        "res.partner", string="Facturar a nombre de", required=True,
        domain="[('parent_id','=',False)]",
        help="Cliente que va a recibir la factura nominativa.",
    )

    @api.depends("order_id")
    def _compute_datos(self):
        for w in self:
            w.global_uuid = w.order_id._l10n_mx_global_invoice_uuid()
            w.amount_total = w.order_id.amount_total
            w.currency_id = w.order_id.currency_id

    # ------------------------------------------------------------------
    def _partner_publico_general(self, order=None):
        """El cliente del propio ticket: si salio en Global, es publico en general.

        Buscar solo por RFC generico es fragil, porque puede haber mas de un
        contacto con XAXX010101000 dado de alta.
        """
        if order and order.partner_id and order.partner_id.vat == RFC_GENERICO:
            return order.partner_id
        p = self.env["res.partner"].search(
            [("vat", "=", RFC_GENERICO), ("parent_id", "=", False)],
            order="id", limit=1)
        if not p:
            raise UserError(_(
                "No encuentro el cliente con RFC %s (PÃºblico en General). "
                "Hay que darlo de alta antes de refacturar.", RFC_GENERICO))
        return p

    def _forma_pago_de_la_global(self, uuid):
        """Lee la FormaPago del XML de la Factura Global para heredarla a la nota."""
        doc = self.env["l10n_mx_edi.document"].search(
            [("attachment_uuid", "=", uuid), ("state", "=", "ginvoice_sent")], limit=1)
        if not doc or not doc.attachment_id:
            return False
        xml = base64.b64decode(doc.attachment_id.datas).decode("utf-8", "replace")
        comprobante = re.search(r"<cfdi:Comprobante[^>]*>", xml)
        if not comprobante:
            return False
        forma = re.search(r'[\s]FormaPago="([^"]*)"', comprobante.group(0))
        if not forma:
            return False
        return self.env["l10n_mx_edi.payment.method"].search(
            [("code", "=", forma.group(1))], limit=1)

    @staticmethod
    def _firma_de_lineas(move):
        return sorted(
            (l.product_id.id, float(l.quantity), float(l.price_unit),
             l.account_id.id, tuple(sorted(l.tax_ids.ids)))
            for l in move.line_ids if l.display_type == "product"
        )

    @staticmethod
    def _linea_por_cobrar(move):
        return move.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable")

    # ------------------------------------------------------------------
    def action_reinvoice(self):
        self.ensure_one()
        order = self.order_id
        # Vuelve a validar aqui, no solo en el boton: entre que se abrio el
        # asistente y se confirma, el ticket pudo cambiar de estado.
        order._l10n_mx_check_reinvoiceable()
        uuid = order._l10n_mx_global_invoice_uuid()
        if self.partner_id.vat == RFC_GENERICO:
            raise UserError(_(
                "Elige el cliente real. Refacturar a PÃºblico en General no tendrÃ­a sentido."))

        publico = self._partner_publico_general(order)
        forma_pago = self._forma_pago_de_la_global(uuid)
        hoy = fields.Date.context_today(self)

        # --- 1. Factura nominativa, a partir del propio ticket ---------
        vals = order._prepare_invoice_vals()
        vals.update({
            "partner_id": self.partner_id.id,
            "invoice_date": hoy,
            "date": hoy,
            # El ticket viene marcado como CFDI al publico en general. La
            # factura nominativa NO lo es: si se queda marcado, el SAT la
            # rechaza con #CFDI40130 (receptor XAXX010101000 sin nodo
            # Informacion Global).
            "l10n_mx_edi_cfdi_to_public": False,
            "l10n_mx_edi_usage": self.partner_id.l10n_mx_edi_usage or "G03",
        })
        factura = order._create_invoice(vals)
        factura.action_post()
        factura._l10n_mx_edi_cfdi_invoice_try_send()
        factura.invalidate_recordset()
        if factura.l10n_mx_edi_cfdi_state != "sent":
            raise UserError(_(
                "La factura %s se creÃ³ y contabilizÃ³, pero el PAC no la timbrÃ³, por lo que "
                "NO se generÃ³ la nota de crÃ©dito. Corrige lo que indica el mensaje, "
                "reintenta el timbrado desde la pestaÃ±a CFDI de esa factura y "
                "despuÃ©s emite la nota de crÃ©dito.\n\n%s",
                factura.name, factura._l10n_mx_last_edi_message()))

        # --- 2. Nota de crÃ©dito espejo, a PÃºblico en General -----------
        nota = factura._reverse_moves([{"invoice_date": hoy, "date": hoy}])
        nota.partner_id = publico.id
        nota.l10n_mx_edi_cfdi_origin = "01|%s" % uuid
        nota.l10n_mx_edi_cfdi_to_public = True
        nota.l10n_mx_edi_usage = "S01"
        if forma_pago:
            nota.l10n_mx_edi_payment_method_id = forma_pago.id
        nota.flush_recordset()
        nota.invalidate_recordset()

        # Candados: la nota tiene que ser espejo exacto antes de timbrarla.
        # Si no lo fuera, la pareja factura+nota dejaria de netear a cero y
        # moveria los saldos de ingresos o de costo de ventas.
        if self._firma_de_lineas(nota) != self._firma_de_lineas(factura):
            raise UserError(_("Las lÃ­neas de la nota de crÃ©dito no coinciden con la factura."))
        if abs(nota.amount_total - factura.amount_total) > 0.01:
            raise UserError(_(
                "El importe de la nota (%s) no coincide con el de la factura (%s).",
                nota.amount_total, factura.amount_total))

        # Al contabilizar, Odoo concilia la nota contra la factura.
        nota.with_context(l10n_mx_skip_cfdi_check=True).action_post()
        nota._l10n_mx_edi_cfdi_invoice_try_send()
        nota.invalidate_recordset()
        if nota.l10n_mx_edi_cfdi_state != "sent":
            raise UserError(_(
                "La factura %s quedÃ³ timbrada, pero la nota de crÃ©dito %s no.\n"
                "Hay que reintentar el timbrado de la nota desde su pestaÃ±a CFDI.\n\n%s",
                factura.name, nota.name, nota._l10n_mx_last_edi_message()))

        # --- 3. El saldo, a nombre del cliente real -------------------
        self._linea_por_cobrar(nota).partner_id = self.partner_id.id

        # El ticket no se toca: en Odoo 19 pos.order.state no tiene 'invoiced',
        # y basta con que account_move quede apuntando a la factura (de ahi se
        # calcula is_invoiced). La sesion ya esta cerrada, asi que su asiento
        # tampoco se recalcula.

        # --- 4. Rastro en ambos documentos ----------------------------
        cuerpo = _(
            "RefacturaciÃ³n del ticket <b>%(ticket)s</b>, que habÃ­a salido en la "
            "Factura Global <b>%(uuid)s</b>.", ticket=order.name, uuid=uuid)
        factura.message_post(body=cuerpo)
        nota.message_post(body=cuerpo)

        return {
            "type": "ir.actions.act_window",
            "name": _("Factura del ticket %s", order.name),
            "res_model": "account.move",
            "res_id": factura.id,
            "view_mode": "form",
        }


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_mx_last_edi_message(self):
        self.ensure_one()
        doc = self.env["l10n_mx_edi.document"].search(
            [("move_id", "=", self.id)], order="id desc", limit=1)
        return doc.message or _("El PAC no devolviÃ³ un mensaje.")

