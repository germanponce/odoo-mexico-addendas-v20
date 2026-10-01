# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""
Polyfill de campos v17+ sobre account.move para v15/v16.

En Odoo 17+, el modulo nativo l10n_mx_edi declara `l10n_mx_edi_cfdi_uuid`
como un campo Char almacenado sobre account.move. En v15/v16 ese campo no
existe; lo polifilamos aqui como un related/computed campo basado en
nuestro propio `stored_sat_uuid` (que ya extrae el UUID del XML adjunto).

Importacion condicional: este archivo se importa solo en v15/v16 desde
models/__init__.py.
"""
from odoo import fields, models, api  # type: ignore


class AccountMoveCompat(models.Model):
    _inherit = "account.move"

    l10n_mx_edi_cfdi_uuid = fields.Char(
        string="CFDI UUID (compat v15/v16)",
        compute="_compute_l10n_mx_edi_cfdi_uuid_compat",
        store=True,
        index=True,
        help="Polyfill v15/v16: replica el campo l10n_mx_edi_cfdi_uuid nativo de v17+.",
    )
    l10n_mx_edi_cfdi_request = fields.Selection(
        [
            ("on_invoice", "Factura"),
            ("on_payment", "Pago"),
            ("on_refund", "Nota de credito"),
        ],
        string="CFDI Request (compat v15/v16)",
        compute="_compute_l10n_mx_edi_cfdi_request_compat",
        store=True,
        help="Polyfill v15/v16: replica el campo l10n_mx_edi_cfdi_request de v17+.",
    )

    @api.depends("stored_sat_uuid")
    def _compute_l10n_mx_edi_cfdi_uuid_compat(self):
        """Alias de stored_sat_uuid (ya extraido del XML por _get_uuid_from_xml_attachment)."""
        for move in self:
            move.l10n_mx_edi_cfdi_uuid = move.stored_sat_uuid or False

    @api.depends("move_type")
    def _compute_l10n_mx_edi_cfdi_request_compat(self):
        """Mapea el move_type a su tipo de CFDI request."""
        for move in self:
            mt = move.move_type or ""
            if mt in ("out_invoice", "in_invoice"):
                move.l10n_mx_edi_cfdi_request = "on_invoice"
            elif mt in ("out_refund", "in_refund"):
                move.l10n_mx_edi_cfdi_request = "on_refund"
            else:
                move.l10n_mx_edi_cfdi_request = False
