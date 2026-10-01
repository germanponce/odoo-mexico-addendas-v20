# -*- coding: utf-8 -*-
# German Ponce Dominguez
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models

_DEFAULT_REPORT = 'account.account_invoices'


class AccountMoveSend(models.AbstractModel):
    """Sobreescribe la generación del PDF de factura para usar el reporte
    configurado en el diario contable (cfdi_report_id).

    En Odoo 19 el método de referencia es _prepare_invoice_pdf_report,
    que recibe (invoice, invoice_data) y llena invoice_data con la clave
    'pdf_attachment_values' si aún no existe el adjunto PDF.
    """

    _inherit = 'account.move.send'


    @api.model
    def _prepare_invoice_pdf_report(self, invoices_data):
        """EXTENDS account — selecciona el reporte según el diario de cada factura.

        Si el diario tiene configurado ``cfdi_report_id`` se sustituye el
        reporte estándar antes de delegar al comportamiento base, de modo que
        el agrupamiento y la división de páginas siguen funcionando igual que
        en Odoo 19 original.
        """
        # Sustituir pdf_report en el invoice_data de cada factura cuyo diario
        # tenga configurado un reporte CFDI personalizado.
        for invoice, invoice_data in invoices_data.items():
            # Saltar si el PDF ya está generado
            if invoice.invoice_pdf_report_id:
                continue
            # Sólo actuar cuando el diario tiene un reporte personalizado
            if invoice.journal_id and invoice.journal_id.cfdi_report_id:
                # Sustituimos el reporte en invoice_data para que el método
                # base lo use al agrupar y renderizar.
                invoice_data['pdf_report'] = invoice.journal_id.cfdi_report_id

        # Delegar al método original de Odoo 19 con la firma correcta.
        # Éste ya maneja el agrupamiento, _pre_render_qweb_pdf y _get_splitted_report.
        return super()._prepare_invoice_pdf_report(invoices_data)
