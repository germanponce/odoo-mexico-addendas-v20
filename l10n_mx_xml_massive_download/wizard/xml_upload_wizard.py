# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Wizard "Adjuntar XML" (boton verde en la factura de proveedor / pago).

Permite adjuntar el CFDI a un account.move (o account.payment) de dos formas:
  * subiendo un archivo .xml, o
  * eligiendo uno de los XML ya descargados del SAT (account.edi.downloaded.xml.sat).

Luego delega en move/payment.fill_xml_values_from_attatchment() que registra el
CFDI (l10n_mx_edi.document en 17/18/19), valida RFC/subtotal/total y llena los
campos fiscales (forma/metodo de pago, uso CFDI, fecha, referencia).

Originalmente vivia en el modulo aparte `account_move_advanced` (solo v17). Se
incorpora aqui, nativo y cross-version, por peticion del cliente.
"""
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class XmlUploadWizard(models.TransientModel):
    _name = "xml.upload.wizard"
    _description = "XML Upload Wizard"

    file = fields.Binary("Archivo XML")
    file_name = fields.Char("Nombre Archivo")
    downloaded_xmls = fields.Many2one(
        "account.edi.downloaded.xml.sat", string="XML descargado (Odoo)")
    move_id = fields.Many2one("account.move", string="Move")
    payment_id = fields.Many2one("account.payment", string="Payment")

    def action_submit(self):
        self.ensure_one()
        if self.file and self.downloaded_xmls:
            raise UserError(_(
                "No puede subir un archivo y elegir un XML descargado al mismo "
                "tiempo. Use solo una opcion."))
        target = self.move_id or self.payment_id
        if not target:
            raise UserError(_("No hay factura o pago destino para el XML."))
        res_model = "account.move" if self.move_id else "account.payment"

        if self.file:
            attachment = self.env["ir.attachment"].create({
                "name": self.file_name or "cfdi.xml",
                "datas": self.file,
                "res_model": res_model,
                "res_id": target.id,
                "mimetype": "application/xml",
            })
        elif self.downloaded_xmls:
            src = self.downloaded_xmls.attachment_id
            if not src:
                raise UserError(_(
                    "El XML descargado seleccionado no tiene archivo adjunto."))
            # Copiar el XML al move/pago para que quede en su chatter y lo detecten
            # los helpers nativos (stored_sat_uuid, etc.).
            attachment = self.env["ir.attachment"].create({
                "name": src.name or ((self.downloaded_xmls.name or "cfdi") + ".xml"),
                "datas": src.datas,
                "res_model": res_model,
                "res_id": target.id,
                "mimetype": "application/xml",
            })
        else:
            raise UserError(_("No se detecto ningun archivo seleccionado."))

        result = target.fill_xml_values_from_attatchment(attachment)
        # Relacion con massive_download: si el XML provino de un lote descargado
        # del SAT, generar la representacion impresa (PDF) del CFDI y adjuntarla
        # a la factura de proveedor (usa el detalle ya parseado del downloaded XML
        # via generate_pdf_attatchment). Para archivos subidos a mano no aplica
        # (no hay registro con conceptos parseados).
        if self.move_id and self.downloaded_xmls:
            try:
                self.downloaded_xmls.generate_pdf_attatchment(self.move_id.id)
            except Exception as e:
                _logger.warning(
                    "Adjuntar XML: XML adjuntado a la factura pero no se pudo "
                    "generar el PDF del CFDI %s: %s", self.downloaded_xmls.name, e)
        if result:
            return result
        return {"type": "ir.actions.act_window_close"}


class CustomValidationConfirm(models.TransientModel):
    _name = "custom.validation.confirm"
    _description = "Confirmar Validacion"

    move_id = fields.Many2one("account.move", required=True)
    attachment_id = fields.Many2one("ir.attachment", required=True)
    errors = fields.Text("Errores")

    def action_confirm(self):
        self.ensure_one()
        # Re-ejecuta el llenado ignorando las advertencias (bypass).
        self.move_id.with_context(
            bypass_validation=True
        ).fill_xml_values_from_attatchment(self.attachment_id)
        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        self.ensure_one()
        self.move_id.action_erase_fields()
        return {"type": "ir.actions.act_window_close"}
