# Copyright 2018 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# ── Odoo 18 migration notes ────────────────────────────────────────────────
# 1. `from odoo import _` instead of `from odoo.tools.translate import _`.
# 2. `CustomerPortal` is still importable from purchase.controllers.portal in
#    Odoo 18.  If the import fails after an upgrade, try:
#    `from odoo.addons.portal.controllers.portal import CustomerPortal`.
# 3. The `_render_portal` helper signature is unchanged between Odoo 16-18
#    for the purchase module.  Verify after installing the update.
# 4. `portal_my_purchase_order` — `qcontext` replaced by `render_values` in
#    newer Odoo 18 portal responses.  The patched version handles both.
# ──────────────────────────────────────────────────────────────────────────

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.purchase.controllers.portal import CustomerPortal


class PurchaseOrderAttachments(CustomerPortal):
    """Recibe el formulario de carga de XML/PDF del portal de proveedores."""

    @http.route(
        ['/purchase/order_attachments/<int:order_id>'],
        type='http', auth="user", methods=['POST'], website=True,
    )
    def attach_files(self, order_id, access_token=None, **post):
        try:
            order_sudo = self._document_check_access(
                'purchase.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        def _error(msg):
            return request.render(
                'l10n_mx_portal_vendor_bills.portal_vendor_bill_error', {
                    'mensaje': msg,
                    'orden': order_sudo.name,
                    'importe': order_sudo.amount_total,
                })

        if order_sudo.invoice_status == 'no':
            return _error('La Orden no esta lista para Facturar.')

        if not any(line.qty_to_invoice for line in order_sudo.order_line):
            return _error('La orden no tiene cantidad disponible por facturar.')

        att = request.env['ir.attachment']
        xml = post.get('xml')

        cfdi_str, cfdi_bytes = att.get_cfdi_strings_4_xml(xml, order_sudo)
        if not cfdi_str:
            return _error('El archivo XML adjunto a la Orden de Compra no es un archivo valido.')

        cfdi_vals = att.get_cfdi_vals_from_xml_strong(cfdi_str, order_sudo)
        if not cfdi_vals:
            return _error('El archivo adjunto no se pudo leer por que contiene errores en su estructura.')

        validations = att.check_invoice_bill_xml_check_validations(cfdi_vals, order_sudo)
        if validations['error']:
            return _error(validations['message_error'])

        result_invoices, filename = att.parse_xml(xml, cfdi_bytes, order_sudo)
        if result_invoices.get('wrongfiles'):
            raise MissingError(str(result_invoices))

        xml_uuid = att.check_invoice_bill_xml_get_uuid(cfdi_vals, order_sudo)
        invoice_inst = result_invoices['invoices']['invoice_inst']
        invoice_inst.write({'vendor_uuid': xml_uuid})
        invoice_inst.portal_bills_insert_attachment(post, filename)
        order_sudo.insert_attachment(post, filename)

        return request.redirect(order_sudo.get_portal_url() + '&upload_success=1')

    @http.route(
        ['/my/purchase', '/my/purchase/page/<int:page>'],
        type='http', auth="user", website=True,
    )
    def portal_my_purchase_orders(
            self, page=1, date_begin=None, date_end=None,
            sortby=None, filterby=None, **kw):
        """Sobreescribe la lista de OCs para agregar filtros personalizados."""
        return self._render_portal(
            "purchase.portal_my_purchase_orders",
            page, date_begin, date_end, sortby, filterby,
            [],   # domain base
            {
                'all': {
                    'label': _('Todos'),
                    'domain': [('state', 'in', ['purchase', 'done', 'cancel'])],
                },
                'state_00_purchase': {
                    'label': _('Ordenes de Compra'),
                    'domain': [('state', '=', 'purchase')],
                },
                'state_01_done': {
                    'label': _('Hechas'),
                    'domain': [('state', '=', 'done')],
                },
                'state_02_cancel': {
                    'label': _('Canceladas'),
                    'domain': [('state', '=', 'cancel')],
                },
                'status_invoice_00_waiting': {
                    'label': _('En espera de Factura'),
                    'domain': [('invoice_status', '=', 'to invoice')],
                },
                'status_invoice_01_invoiced': {
                    'label': _('Facturado'),
                    # NOTA: with_remaining_quantity es campo computado no almacenado.
                    # En Odoo 18 filtrar por él en SQL puede fallar; evalúa
                    # almacenarlo (store=True) si necesitas este filtro.
                    'domain': [('invoice_status', '=', 'invoiced')],
                },
            },
            'all',
            "/my/purchase",
            'my_purchases_history',
            'purchase',
            'orders',
        )


class MxCustomerPortal(CustomerPortal):
    """Inyecta upload_success en el contexto del detalle de OC."""

    @http.route(
        ['/my/purchase/<int:order_id>'],
        type='http', auth="public", website=True,
    )
    def portal_my_purchase_order(self, order_id=None, access_token=None, **kw):
        res = super().portal_my_purchase_order(order_id, access_token, **kw)
        upload_success = kw.get('upload_success', False)

        # Odoo 18 puede devolver Response con `render_values` en lugar de
        # `qcontext`. Se intenta ambas rutas de forma segura.
        if hasattr(res, 'qcontext'):
            res.qcontext['upload_success'] = upload_success
        elif hasattr(res, 'render_values'):
            res.render_values['upload_success'] = upload_success
        return res
