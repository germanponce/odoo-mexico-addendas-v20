# -*- encoding: utf-8 -*-
# Coded by German Ponce Dominguez
# Cherman Seingalt - german.ponce@outlook.com

from odoo import api, fields, models, _
from lxml import etree

import logging
_logger = logging.getLogger(__name__)

class AddendaSale(models.Model):
    """docstring for AddendaFields"""
    _inherit = 'sale.order'
    
    addenda_type = fields.Selection(
        selection_add=[('retailer', 'Complemento Detallista')],
        ondelete={'retailer': 'set default'},
    )

    l10n_mx_edi_retailer_status = fields.Selection(
        selection=[
            ('original', 'Original'),
            ('copy', 'Copy'),
            ('reemplaza', 'Reemplaza'),
            ('delete', 'Delete'),
        ],
        string="Estatus Detallista",
        copy=False,
    )

    l10n_mx_edi_retailer_delivery = fields.Char(
        string="Folio(s) de Remisión",
        copy=False,
        help="Número(s) emitido(s) por el receptor al recibir la mercancía, separados por coma.",
    )
    l10n_mx_edi_retailer_delivery_date = fields.Date(
        string="Fecha de Remisión",
        copy=False,
    )
    l10n_mx_edi_retailer_purchase_order_date = fields.Date(
        string="Fecha de Orden de Compra",
        copy=False,
    )
    l10n_mx_edi_retailer_purchase_order_name = fields.Char(
        string="No. de Orden de Compra",
        copy=False,
    )
    l10n_mx_edi_retailer_purchase_contact_name = fields.Char(
        string="Contacto de Compras",
        copy=False,
    )
    l10n_mx_edi_retailer_special_service_type = fields.Selection(
        selection=[
            ('off_invoice', 'Off Invoice'),
            ('bill_back', 'Bill Back'),
        ],
        string="Tipo de Descuento/Cargo",
        copy=False,
    )

    # === Ampliación de estructura del complemento (brechas contra v14 / XSD) ===
    l10n_mx_edi_retailer_entity_type = fields.Selection(
        selection=[
            ('INVOICE', 'INVOICE'),
            ('DEBIT_NOTE', 'DEBIT_NOTE'),
            ('CREDIT_NOTE', 'CREDIT_NOTE'),
            ('LEASE_RECEIPT', 'LEASE_RECEIPT'),
            ('HONORARY_RECEIPT', 'HONORARY_RECEIPT'),
            ('PARTIAL_INVOICE', 'PARTIAL_INVOICE'),
            ('TRANSPORT_DOCUMENT', 'TRANSPORT_DOCUMENT'),
            ('AUTO_INVOICE', 'AUTO_INVOICE'),
        ],
        string="Tipo de Transacción (Detallista)",
        default='INVOICE',
        copy=False,
    )
    l10n_mx_edi_retailer_invoice_creator_id = fields.Many2one(
        'res.partner',
        string="Emisor de Factura (Detallista)",
    )
    l10n_mx_edi_retailer_allow_allowance_charge = fields.Boolean(
        string="¿Descuento/Cargo Global?",
    )
    l10n_mx_edi_retailer_allowance_charge_type = fields.Selection(
        selection=[
            ('ALLOWANCE_GLOBAL', 'ALLOWANCE_GLOBAL'),
            ('CHARGE_GLOBAL', 'CHARGE_GLOBAL'),
        ],
        string="Tipo de Cargo/Descuento Global",
        default='ALLOWANCE_GLOBAL',
    )
    l10n_mx_edi_retailer_allowance_sequence_number = fields.Char(
        string="Número de Secuencia (allowanceCharge)",
    )
    l10n_mx_edi_retailer_allowance_special_services_type = fields.Selection(
        selection=[
            ('AA', 'AA'), ('AJ', 'AJ'), ('ADO', 'ADO'), ('ADT', 'ADT'), ('ADS', 'ADS'),
            ('ABZ', 'ABZ'), ('DA', 'DA'), ('EAA', 'EAA'), ('EAB', 'EAB'), ('PI', 'PI'),
            ('TAE', 'TAE'), ('SAB', 'SAB'), ('RAA', 'RAA'), ('PAD', 'PAD'), ('FG', 'FG'),
            ('FA', 'FA'), ('TD', 'TD'), ('TS', 'TS'), ('TX', 'TX'), ('TZ', 'TZ'),
            ('ZZZ', 'ZZZ'), ('VAB', 'VAB'), ('UM', 'UM'), ('DI', 'DI'), ('CAC', 'CAC'),
            ('COD', 'COD'), ('FC', 'FC'), ('FI', 'FI'), ('HD', 'HD'), ('QD', 'QD'),
        ],
        string="Tipo de Servicio Especial (allowanceCharge)",
        default='AJ',
    )
    l10n_mx_edi_retailer_allowance_percentage = fields.Float(
        string="Porcentaje Manual (allowanceCharge)",
    )
    l10n_mx_edi_retailer_total_allowance_type = fields.Selection(
        selection=[
            ('ALLOWANCE', 'ALLOWANCE'),
            ('CHARGE', 'CHARGE'),
        ],
        string="Tipo de Cargo/Descuento Total",
        default='ALLOWANCE',
    )
    l10n_mx_edi_retailer_total_special_services_type = fields.Selection(
        selection=[
            ('AA', 'AA'), ('ADS', 'ADS'), ('ADO', 'ADO'), ('ABZ', 'ABZ'), ('DA', 'DA'),
            ('EAA', 'EAA'), ('PI', 'PI'), ('TAE', 'TAE'), ('SAB', 'SAB'), ('RAA', 'RAA'),
            ('PAD', 'PAD'), ('FG', 'FG'), ('FA', 'FA'), ('TD', 'TD'), ('TS', 'TS'),
            ('TX', 'TX'), ('ZZZ', 'ZZZ'), ('VAB', 'VAB'), ('UM', 'UM'), ('DI', 'DI'),
            ('ADT', 'ADT'), ('AJ', 'AJ'), ('CAC', 'CAC'), ('COD', 'COD'), ('EAB', 'EAB'),
            ('FC', 'FC'), ('FI', 'FI'), ('HD', 'HD'), ('QD', 'QD'),
        ],
        string="Tipo de Servicio Especial (TotalAllowanceCharge)",
        default='ABZ',
    )

    # === Datos de compañía que usa el Complemento Detallista ===
    # Se muestran (solo lectura) en la factura para que el usuario detecte de
    # un vistazo si faltan por configurar en la ficha de la compañía, sin
    # tener que ir a buscarlos.
    l10n_mx_edi_retailer_company_buyer_gln = fields.Char(
        related='company_id.l10n_mx_edi_retailer_buyer_gln',
        string="GLN del Comprador (Compañía)",
    )
    l10n_mx_edi_retailer_company_seller_gln = fields.Char(
        related='company_id.l10n_mx_edi_retailer_seller_gln',
        string="GLN del Vendedor (Compañía)",
    )
    l10n_mx_edi_retailer_company_seller_alt_id = fields.Char(
        related='company_id.l10n_mx_edi_retailer_seller_alternate_party_identification',
        string="Identificador Alterno del Vendedor (Compañía)",
    )
    l10n_mx_edi_retailer_company_ship_to_gln = fields.Char(
        related='company_id.l10n_mx_edi_retailer_ship_to_gln',
        string="GLN del Destino de Envío (Compañía)",
    )
    l10n_mx_edi_retailer_company_data_missing = fields.Boolean(
        string="Faltan datos de compañía (Detallista)",
        compute='_compute_l10n_mx_edi_retailer_company_data_missing',
    )

    @api.depends(
        'company_id.l10n_mx_edi_retailer_buyer_gln',
        'company_id.l10n_mx_edi_retailer_seller_gln',
        'company_id.l10n_mx_edi_retailer_seller_alternate_party_identification',
        'company_id.l10n_mx_edi_retailer_ship_to_gln',
    )
    def _compute_l10n_mx_edi_retailer_company_data_missing(self):
        for move in self:
            company = move.company_id
            move.l10n_mx_edi_retailer_company_data_missing = not all([
                company.l10n_mx_edi_retailer_buyer_gln,
                company.l10n_mx_edi_retailer_seller_gln,
                company.l10n_mx_edi_retailer_seller_alternate_party_identification,
                company.l10n_mx_edi_retailer_ship_to_gln,
            ])


    def action_open_retailer_company_config(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Configuración de Compañía",
            'res_model': 'res.company',
            'res_id': self.company_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class AddendaOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    addenda_type = fields.Selection(
        selection_add=[('retailer', 'Complemento Detallista')],
        ondelete={'retailer': 'set null'},
    )
