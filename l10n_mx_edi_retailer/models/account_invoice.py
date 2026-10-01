# -*- encoding: utf-8 -*-
# Coded by German Ponce Dominguez
# Cherman Seingalt - german.ponce@outlook.com

from odoo import api, fields, models, _
from lxml import etree

import logging
_logger = logging.getLogger(__name__)


# Listas de códigos tomadas directamente del XSD oficial:
# http://www.sat.gob.mx/sitio_internet/cfd/detallista/detallista.xsd
L10N_MX_EDI_RETAILER_ENTITY_TYPE = [
    ('INVOICE', 'INVOICE'),
    ('DEBIT_NOTE', 'DEBIT_NOTE'),
    ('CREDIT_NOTE', 'CREDIT_NOTE'),
    ('LEASE_RECEIPT', 'LEASE_RECEIPT'),
    ('HONORARY_RECEIPT', 'HONORARY_RECEIPT'),
    ('PARTIAL_INVOICE', 'PARTIAL_INVOICE'),
    ('TRANSPORT_DOCUMENT', 'TRANSPORT_DOCUMENT'),
    ('AUTO_INVOICE', 'AUTO_INVOICE'),
]

L10N_MX_EDI_RETAILER_SPECIAL_SERVICE_TYPE = [
    ('AA', 'AA'), ('AJ', 'AJ'), ('ADO', 'ADO'), ('ADT', 'ADT'), ('ADS', 'ADS'),
    ('ABZ', 'ABZ'), ('DA', 'DA'), ('EAA', 'EAA'), ('EAB', 'EAB'), ('PI', 'PI'),
    ('TAE', 'TAE'), ('SAB', 'SAB'), ('RAA', 'RAA'), ('PAD', 'PAD'), ('FG', 'FG'),
    ('FA', 'FA'), ('TD', 'TD'), ('TS', 'TS'), ('TX', 'TX'), ('TZ', 'TZ'),
    ('ZZZ', 'ZZZ'), ('VAB', 'VAB'), ('UM', 'UM'), ('DI', 'DI'), ('CAC', 'CAC'),
    ('COD', 'COD'), ('FC', 'FC'), ('FI', 'FI'), ('HD', 'HD'), ('QD', 'QD'),
]

L10N_MX_EDI_RETAILER_TOTAL_SPECIAL_SERVICE_TYPE = [
    ('AA', 'AA'), ('ADS', 'ADS'), ('ADO', 'ADO'), ('ABZ', 'ABZ'), ('DA', 'DA'),
    ('EAA', 'EAA'), ('PI', 'PI'), ('TAE', 'TAE'), ('SAB', 'SAB'), ('RAA', 'RAA'),
    ('PAD', 'PAD'), ('FG', 'FG'), ('FA', 'FA'), ('TD', 'TD'), ('TS', 'TS'),
    ('TX', 'TX'), ('ZZZ', 'ZZZ'), ('VAB', 'VAB'), ('UM', 'UM'), ('DI', 'DI'),
    ('ADT', 'ADT'), ('AJ', 'AJ'), ('CAC', 'CAC'), ('COD', 'COD'), ('EAB', 'EAB'),
    ('FC', 'FC'), ('FI', 'FI'), ('HD', 'HD'), ('QD', 'QD'),
]

L10N_MX_EDI_RETAILER_ADDITIONAL_REFERENCE_TYPE = [
    ('AAE', '[AAE] Cuenta Predial'),
    ('CK', '[CK] Número de cheque'),
    ('ACE', '[ACE] Número de documento (Reemisión)'),
    ('ATZ', '[ATZ] Número de Aprobación'),
    ('DQ', '[DQ] Folio de recibo de mercancías'),
    ('IV', '[IV] Número de Factura'),
    ('ON', '[ON] Número de pedido (Comprador)'),
    ('AWR', '[AWR] Número de documento que se reemplaza'),
]


class L10nMxEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    def _decode_cfdi_attachment(self, cfdi_data):
        res = super()._decode_cfdi_attachment(cfdi_data)
        cfdi_node_custom = res.get('cfdi_node')

        if cfdi_node_custom is None:
            return res

        namespaces = {'detallista': 'http://www.sat.gob.mx/detallista'}
        detallista_node = cfdi_node_custom.find(".//detallista:detallista", namespaces)

        if detallista_node is not None:
            detallista_node.attrib.pop("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", None)
            detallista_node.attrib.pop("xmlns:detallista", None)

        res['cfdi_node'] = cfdi_node_custom
        return res

class L10nMxEdiRetailerAdditionalReference(models.Model):
    _name = 'l10n_mx_edi.retailer.additional.reference'
    _description = "Referencia Adicional del Complemento Detallista"

    move_id = fields.Many2one('account.move', string="Factura", required=True, ondelete='cascade')
    reference_type = fields.Selection(
        selection=L10N_MX_EDI_RETAILER_ADDITIONAL_REFERENCE_TYPE,
        string="Tipo de Referencia",
        required=True,
        default='ATZ',
    )
    name = fields.Char(string="Valor", required=True)


class AccountMove(models.Model):
    _inherit = 'account.move'

    addenda_type = fields.Selection(
        selection_add=[('retailer', 'Complemento Detallista')],
        ondelete={'retailer': 'set default'},
    )

    # === Campos nativos del Complemento Detallista ===
    # Reemplazan el campo empacado `x_complement_retailer_data` (antes
    # definido vía ir.model.fields) por campos reales del modelo, declarados
    # por herencia en Python. Se muestran dentro de la página "Addendas"
    # (name="addendas_extra_fits") que agrega l10n_mx_edi_addendas_base.
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
        selection=L10N_MX_EDI_RETAILER_ENTITY_TYPE,
        string="Tipo de Transacción (Detallista)",
        compute='_compute_l10n_mx_edi_retailer_entity_type',
        store=True,
        readonly=False,
        copy=False,
        help="Se calcula automáticamente (INVOICE / CREDIT_NOTE) según el "
             "tipo de documento, pero puede sobreescribirse manualmente para "
             "los demás valores permitidos por el XSD (DEBIT_NOTE, "
             "LEASE_RECEIPT, HONORARY_RECEIPT, PARTIAL_INVOICE, "
             "TRANSPORT_DOCUMENT, AUTO_INVOICE).",
    )

    @api.depends('move_type')
    def _compute_l10n_mx_edi_retailer_entity_type(self):
        for move in self:
            move.l10n_mx_edi_retailer_entity_type = 'CREDIT_NOTE' if move.move_type == 'out_refund' else 'INVOICE'

    # InvoiceCreator (emisor de la factura, si es distinto del proveedor)
    l10n_mx_edi_retailer_invoice_creator_id = fields.Many2one(
        'res.partner',
        string="Emisor de Factura (Detallista)",
        help="Úsalo solo si el emisor real de la factura es distinto del "
             "proveedor (p.ej. un agente de facturación). El GLN y la "
             "identificación alterna se leen de la ficha de este partner.",
    )

    # AdditionalInformation: referencias adicionales manuales (p.ej. ATZ),
    # complementarias a las que ya se generan automáticamente (AAE, CK, ACE,
    # DQ, IV, ON, AWR).
    l10n_mx_edi_retailer_additional_reference_ids = fields.One2many(
        'l10n_mx_edi.retailer.additional.reference', 'move_id',
        string="Referencias Adicionales (Detallista)",
    )

    # allowanceCharge (descuento/cargo global de la factura)
    l10n_mx_edi_retailer_allow_allowance_charge = fields.Boolean(
        string="¿Descuento/Cargo Global?",
        help="Si está desmarcado, el nodo allowanceCharge no se incluye en "
             "el complemento.",
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
        selection=L10N_MX_EDI_RETAILER_SPECIAL_SERVICE_TYPE,
        string="Tipo de Servicio Especial (allowanceCharge)",
        default='AJ',
    )
    l10n_mx_edi_retailer_allowance_percentage = fields.Float(
        string="Porcentaje Manual (allowanceCharge)",
        help="Si se deja en 0, se usa el porcentaje de descuento calculado "
             "automáticamente a partir de las líneas de la factura.",
    )

    # TotalAllowanceCharge (bloque de descuento total)
    l10n_mx_edi_retailer_total_allowance_type = fields.Selection(
        selection=[
            ('ALLOWANCE', 'ALLOWANCE'),
            ('CHARGE', 'CHARGE'),
        ],
        string="Tipo de Cargo/Descuento Total",
        default='ALLOWANCE',
    )
    l10n_mx_edi_retailer_total_special_services_type = fields.Selection(
        selection=L10N_MX_EDI_RETAILER_TOTAL_SPECIAL_SERVICE_TYPE,
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

    @api.model
    def create(self, vals):
        res = super(AccountMove, self).create(vals)
        if res.move_type == 'out_invoice':
            sale_model = 'sale_line_ids' in res.invoice_line_ids._fields
            sale_id = res.mapped('invoice_line_ids.sale_line_ids.order_id') if sale_model else False
            picking_ids = sale_id.picking_ids.filtered(lambda x: x.state == 'done' and x.date_done)
            if sale_id:
                res.addenda_type = sale_id.addenda_type
                res.l10n_mx_edi_retailer_status = sale_id.l10n_mx_edi_retailer_status
                res.l10n_mx_edi_retailer_delivery = sale_id.l10n_mx_edi_retailer_delivery
                res.l10n_mx_edi_retailer_delivery_date = sale_id.l10n_mx_edi_retailer_delivery_date
                res.l10n_mx_edi_retailer_purchase_order_date = sale_id.l10n_mx_edi_retailer_purchase_order_date
                res.l10n_mx_edi_retailer_purchase_order_name = sale_id.l10n_mx_edi_retailer_purchase_order_name
                res.l10n_mx_edi_retailer_purchase_contact_name = sale_id.l10n_mx_edi_retailer_purchase_contact_name
                res.l10n_mx_edi_retailer_special_service_type = sale_id.l10n_mx_edi_retailer_special_service_type
                res.l10n_mx_edi_retailer_entity_type = sale_id.l10n_mx_edi_retailer_entity_type
                res.l10n_mx_edi_retailer_invoice_creator_id = sale_id.l10n_mx_edi_retailer_invoice_creator_id
                res.l10n_mx_edi_retailer_allow_allowance_charge = sale_id.l10n_mx_edi_retailer_allow_allowance_charge
                res.l10n_mx_edi_retailer_allowance_charge_type = sale_id.l10n_mx_edi_retailer_allowance_charge_type
                res.l10n_mx_edi_retailer_allowance_sequence_number = sale_id.l10n_mx_edi_retailer_allowance_sequence_number
                res.l10n_mx_edi_retailer_allowance_special_services_type = sale_id.l10n_mx_edi_retailer_allowance_special_services_type
                res.l10n_mx_edi_retailer_allowance_percentage = sale_id.l10n_mx_edi_retailer_allowance_percentage
                res.l10n_mx_edi_retailer_total_allowance_type = sale_id.l10n_mx_edi_retailer_total_allowance_type
                res.l10n_mx_edi_retailer_total_special_services_type = sale_id.l10n_mx_edi_retailer_total_special_services_type

                # if picking_ids:
                #     x_order_remision = ""
                #     for pick in picking_ids:
                #         x_order_remision = pick.name.replace('/','-')
                #     res.x_order_remision = x_order_remision
        return res


    def action_open_retailer_wizard(self):
        """ Abre el wizard del Complemento Detallista, precargado con los
        valores ya guardados en la factura (si el wizard ya se corrió antes).
        """
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'l10n_mx_edi_retailer.action_open_wizard_retailer'
        )
        action['context'] = {'default_invoice_id': self.id}
        return action

    def get_retailer_complement_values(self):

        self.ensure_one()

        document_type = 'E' if self.move_type == 'out_refund' else 'I'

        currency_name = 'MXN'
        if self.currency_id != self.company_id.currency_id:
            currency_name = self.currency_id.name
        currency_precision = self.currency_id.decimal_places

        # TODO verificar: tipo de cambio a exponer en <currency><rateOfChange>.
        rate = 1.0
        if self.currency_id != self.company_id.currency_id:
            rate = self.currency_id._get_conversion_rate(
                self.currency_id, self.company_id.currency_id, self.company_id, self.invoice_date or fields.Date.today()
            )

        pay_term = self.invoice_payment_term_id
        payment_terms_event = 'DATE_OF_INVOICE' if self.invoice_date == self.invoice_date_due else 'EFFECTIVE_DATE'

        net_payment_terms_type = 'BASIC_NET'
        if pay_term and pay_term.line_ids and pay_term.line_ids[-1].delay_type in (
            'days_after_end_of_month', 'days_after_end_of_next_month', 'days_end_of_month_on_the'
        ):
            net_payment_terms_type = 'END_OF_MONTH'

        pay_term_period_days = 0
        if pay_term and self.invoice_date_due and self.invoice_date:
            pay_term_period_days = (self.invoice_date_due - self.invoice_date).days

        total_price_discount = sum(
            (line.price_unit * line.quantity) - line.price_subtotal
            for line in self.invoice_line_ids.filtered(lambda l: not l.display_type)
        )
        percentage_discount = 0.0
        if total_price_discount and self.amount_untaxed:
            percentage_discount = (total_price_discount / self.amount_untaxed) * 100

        tax_lines = self.line_ids.filtered(lambda l: l.tax_line_id)
        withholding_lines = tax_lines.filtered(lambda l: l.tax_line_id.amount < 0)
        transferred_lines = tax_lines - withholding_lines
        total_tax_details_transferred = abs(sum(transferred_lines.mapped('balance')))
        total_tax_details_withholding = abs(sum(withholding_lines.mapped('balance')))

        # TODO verificar: qué folio corresponde aquí (ACE = Remisión).
        folio = self.name

        return {
            'document_type': document_type,
            'currency_name': currency_name,
            'currency_precision': currency_precision,
            'rate': rate,
            'folio': folio,
            'paymentTermsEvent': payment_terms_event,
            'netPaymentTermsType': net_payment_terms_type,
            'pay_term_period_days': pay_term_period_days,
            'percentage_discount': percentage_discount,
            'total_price_discount': total_price_discount,
            'total_tax_details_transferred': total_tax_details_transferred,
            'total_tax_details_withholding': total_tax_details_withholding,
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def get_retailer_line_tax_details(self):
        self.ensure_one()
        move = self.move_id
        tax_details = self.tax_ids.compute_all(
            self.price_unit * (1 - (self.discount / 100.0)),
            currency=self.currency_id,
            quantity=self.quantity,
            product=self.product_id,
            partner=self.partner_id,
            is_refund=move.move_type in ('out_refund', 'in_refund'),
        )
        result = []
        for tax_res in tax_details.get('taxes', []):
            tax = self.env['account.tax'].browse(tax_res['id'])
            result.append({
                'tax_percentage': tax.amount,
                'tax_amount': tax_res['amount'],
                'tax_category': 'RETENIDO' if tax.amount < 0 else 'TRANSFERIDO',
            })
        return result
