# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ─── Validaciones XML ───────────────────────────────────────────────────

    validate_sat_status = fields.Boolean(
        related="company_id.validate_sat_status",
        string="Validar Estado CFDI (SAT)",
        readonly=False,
        help="Valida que el comprobante este vigente.",
    )
    validate_rfc_partner = fields.Boolean(
        related="company_id.validate_rfc_partner",
        string="Validar RFC Contacto",
        readonly=False,
        help="Valida que el comprobante y el contacto coincidan con el valor descrito en el XML.",
    )
    validate_rfc_company = fields.Boolean(
        related="company_id.validate_rfc_company",
        string="Validar RFC Compañia",
        readonly=False,
        help="Valida que el comprobante y la compañia receptora coincidan con el valor descrito en el XML.",
    )
    validate_unique_uuid = fields.Boolean(
        related="company_id.validate_unique_uuid",
        string="Validar UUID Único",
        readonly=False,
        help="Valida que el comprobante no este registrado ya en el sistema para otra orden de Compra.",
    )
    validate_amount_total = fields.Boolean(
        related="company_id.validate_amount_total",
        string="Validar Monto Total",
        readonly=False,
        help="Valida que el total del comprobante coincida con el total de la Orden de Compra (Con una tolerancia de 5 centavos).",
    )
    validate_fiscal_year = fields.Boolean(
        related="company_id.validate_fiscal_year",
        string="Validar Año Fiscal",
        readonly=False,
        help="Valida que el comprobante este dentro del año fiscal en curso.",
    )

    # ─── Opciones del portal ────────────────────────────────────────────────

    show_only_purchase_on_my_account = fields.Boolean(
        related="company_id.show_only_purchase_on_my_account",
        string="Solo Mostrar Compras y Facturas",
        readonly=False,
        help="Restringe el acceso a mi cuenta, solo muestra compras y facturas.",
    )
    show_document_purchase_order = fields.Boolean(
        related="company_id.show_document_purchase_order",
        string="Solicitar Orden de Compra",
        readonly=False,
        help="Habilita el campo de Orden de Compra (PDF) en el Portal.",
    )
    show_document_purchase_order_acuse = fields.Boolean(
        related="company_id.show_document_purchase_order_acuse",
        string="Solicitar Acuse de Recibo",
        readonly=False,
        help="Habilita el campo Acuse en la Orden de Compra (PDF) dentro del Portal.",
    )


class ResCompany(models.Model):
    _inherit = "res.company"

    # ─── Validaciones XML ───────────────────────────────────────────────────

    validate_sat_status = fields.Boolean(
        string="Validar Estado CFDI (SAT)",
        help="Valida que el comprobante este vigente.",
    )
    validate_rfc_partner = fields.Boolean(
        string="Validar RFC Contacto",
        help="Valida que el comprobante y el contacto coincidan con el valor descrito en el XML.",
    )
    validate_rfc_company = fields.Boolean(
        string="Validar RFC Compañia",
        help="Valida que el comprobante y la compañia receptora coincidan con el valor descrito en el XML.",
    )
    validate_unique_uuid = fields.Boolean(
        string="Validar UUID Único",
        help="Valida que el comprobante no este registrado ya en el sistema para otra orden de Compra.",
    )
    validate_amount_total = fields.Boolean(
        string="Validar Monto Total",
        help="Valida que el total del comprobante coincida con el total de la Orden de Compra (Con una tolerancia de 2 centavos).",
    )
    validate_fiscal_year = fields.Boolean(
        string="Validar Año Fiscal",
        help="Valida que el comprobante este dentro del año fiscal en curso.",
    )

    # ─── Opciones del portal ────────────────────────────────────────────────

    show_only_purchase_on_my_account = fields.Boolean(
        string="Solo Mostrar Compras y Facturas",
        help="Restringe el acceso a mi cuenta, solo muestra compras y facturas.",
        default=True,
    )
    show_document_purchase_order = fields.Boolean(
        string="Solicitar Orden de Compra",
        help="Habilita el campo de Orden de Compra (PDF) en el Portal.",
    )
    show_document_purchase_order_acuse = fields.Boolean(
        string="Solicitar Acuse de Recibo",
        help="Habilita el campo Acuse en la Orden de Compra (PDF) dentro del Portal.",
    )
