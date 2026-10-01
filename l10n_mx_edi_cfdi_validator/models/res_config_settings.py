# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ──────────────────────────────────────────────────────────────────────────
    # Todos los campos son related a res.company para que los cambios
    # en los ajustes persistan por empresa.
    # ──────────────────────────────────────────────────────────────────────────

    # ── Receptor ─────────────────────────────────────────────────────────────
    l10n_mx_cfdi_val_version = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_version',
        string='Versión CFDI 4.0',
        readonly=False,
    )
    l10n_mx_cfdi_val_rfc_receptor = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_rfc_receptor',
        string='RFC Receptor',
        readonly=False,
    )
    l10n_mx_cfdi_val_rs_receptor = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_rs_receptor',
        string='Razón Social Receptor',
        readonly=False,
    )
    l10n_mx_cfdi_val_cp_receptor = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_cp_receptor',
        string='CP Receptor',
        readonly=False,
    )

    # ── Comprobante / Moneda / UUID ───────────────────────────────────────────
    l10n_mx_cfdi_val_tipo_comprobante = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_tipo_comprobante',
        string='Tipo de Comprobante',
        readonly=False,
    )
    l10n_mx_cfdi_val_moneda = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_moneda',
        string='Moneda (MXN o USD)',
        readonly=False,
    )
    l10n_mx_cfdi_val_uuid_duplicado = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_uuid_duplicado',
        string='UUID duplicado',
        readonly=False,
    )

    # ── Emisor ────────────────────────────────────────────────────────────────
    l10n_mx_cfdi_val_rfc_emisor = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_rfc_emisor',
        string='RFC Emisor',
        readonly=False,
    )
    l10n_mx_cfdi_val_rs_emisor = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_rs_emisor',
        string='Razón Social Emisor',
        readonly=False,
    )
    l10n_mx_cfdi_val_regimen_emisor = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_regimen_emisor',
        string='Régimen Fiscal Emisor',
        readonly=False,
    )
    l10n_mx_cfdi_val_cp_emisor = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_cp_emisor',
        string='CP Emisor (LugarExpedición)',
        readonly=False,
    )

    l10n_mx_cfdi_val_sat_amount = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_sat_amount',
        string='Monto Factura',
        readonly=False,
    )


    # ── SAT ──────────────────────────────────────────────────────────────────
    l10n_mx_cfdi_val_sat_status = fields.Boolean(
        related='company_id.l10n_mx_cfdi_val_sat_status',
        string='Estatus SAT',
        readonly=False,
    )
