# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # ──────────────────────────────────────────────────────────────────────────
    # Validaciones CFDI de Proveedor
    # Cada campo activa/desactiva una validación específica.
    # Cuando está activo y la validación falla, se bloquea la confirmación.
    # ──────────────────────────────────────────────────────────────────────────

    # ── Receptor ─────────────────────────────────────────────────────────────
    l10n_mx_cfdi_val_version = fields.Boolean(
        string='Validar versión CFDI 4.0',
        default=False,
        help='Verifica que el atributo "Version" del CFDI sea "4.0".',
    )
    l10n_mx_cfdi_val_rfc_receptor = fields.Boolean(
        string='Validar RFC Receptor',
        default=False,
        help=(
            'Verifica que el RFC del Receptor en el XML coincida '
            'con el RFC de la empresa (company.partner_id.vat).'
        ),
    )
    l10n_mx_cfdi_val_rs_receptor = fields.Boolean(
        string='Validar Razón Social Receptor',
        default=False,
        help=(
            'Verifica que la Razón Social del Receptor en el XML '
            'coincida con el nombre de la empresa (sanitizado).'
        ),
    )
    l10n_mx_cfdi_val_cp_receptor = fields.Boolean(
        string='Validar CP Receptor',
        default=False,
        help=(
            'Verifica que el DomicilioFiscalReceptor del XML coincida '
            'con el código postal de la empresa.'
        ),
    )

    # ── Tipo de comprobante ───────────────────────────────────────────────────
    l10n_mx_cfdi_val_tipo_comprobante = fields.Boolean(
        string='Validar Tipo de Comprobante',
        default=False,
        help=(
            '"I" para facturas de proveedor (in_invoice), '
            '"E" para notas de crédito (in_refund).'
        ),
    )

    # ── Moneda ───────────────────────────────────────────────────────────────
    l10n_mx_cfdi_val_moneda = fields.Boolean(
        string='Validar Moneda (MXN o USD)',
        default=False,
        help='Verifica que la moneda del CFDI sea MXN o USD.',
    )

    # ── UUID duplicado ────────────────────────────────────────────────────────
    l10n_mx_cfdi_val_uuid_duplicado = fields.Boolean(
        string='Validar UUID duplicado',
        default=False,
        help=(
            'Verifica que el Folio Fiscal (UUID) no exista ya '
            'en otra factura de proveedor no cancelada.'
        ),
    )

    # ── Emisor ────────────────────────────────────────────────────────────────
    l10n_mx_cfdi_val_rfc_emisor = fields.Boolean(
        string='Validar RFC Emisor',
        default=False,
        help=(
            'Verifica que el RFC del Emisor en el XML coincida '
            'con el RFC del proveedor registrado en el sistema.'
        ),
    )
    l10n_mx_cfdi_val_rs_emisor = fields.Boolean(
        string='Validar Razón Social Emisor',
        default=False,
        help=(
            'Verifica que el Nombre del Emisor en el XML coincida '
            'con el nombre del proveedor (sanitizado).'
        ),
    )
    l10n_mx_cfdi_val_regimen_emisor = fields.Boolean(
        string='Validar Régimen Fiscal Emisor',
        default=False,
        help=(
            'Verifica que el RegimenFiscal del Emisor en el XML coincida '
            'con el régimen fiscal registrado en el proveedor.'
        ),
    )
    l10n_mx_cfdi_val_cp_emisor = fields.Boolean(
        string='Validar CP Emisor (LugarExpedición)',
        default=False,
        help=(
            'Verifica que el LugarExpedicion del CFDI coincida '
            'con el código postal del proveedor.'
        ),
    )

    l10n_mx_cfdi_val_sat_amount = fields.Boolean(
        string='Monto Factura',
        default=False,
    )

    # ── SAT ──────────────────────────────────────────────────────────────────
    l10n_mx_cfdi_val_sat_status = fields.Boolean(
        string='Validar Estatus SAT',
        default=False,
        help=(
            'Verifica que el estado del CFDI ante el SAT sea "Vigente". '
            'Requiere haber consultado el SAT (botón "Actualizar SAT").'
        ),
    )
