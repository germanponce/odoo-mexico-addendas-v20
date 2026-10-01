# -*- coding: utf-8 -*-

import base64
import logging
from datetime import datetime

from pytz import timezone

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Zona horaria oficial del SAT (Centro de México)
MX_TZ = 'America/Mexico_City'


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # =========================================================================
    # Campos de Retenciones CFDI
    # =========================================================================

    require_retention_cfdi = fields.Boolean(
        string='Generar CFDI de Retención',
        help='Al activar, este pago generará un CFDI de Retenciones e Información '
             'de Pagos (SAT) en lugar del CFDI de pago estándar.',
        copy=False,
    )
    retention_type_id = fields.Many2one(
        comodel_name='retention.type',
        string='Tipo de Retención',
        help='Clave del tipo de retención según catálogo del SAT (CveRetenc).',
    )
    l10n_mx_edi_retention_state = fields.Selection(
        selection=[
            ('draft', 'Sin timbrar'),
            ('sent', 'Timbrado'),
            ('error', 'Error'),
        ],
        string='Estado Retención CFDI',
        default='draft',
        copy=False,
        tracking=True,
    )
    l10n_mx_edi_retention_uuid = fields.Char(
        string='Folio Fiscal Retención',
        copy=False,
        readonly=True,
        help='UUID asignado por el SAT al CFDI de Retenciones.',
    )
    l10n_mx_edi_retention_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='XML Retención',
        copy=False,
        readonly=True,
        help='Archivo XML del CFDI de Retenciones timbrado.',
    )
    l10n_mx_edi_retention_error_message = fields.Text(
        string='Error Retención CFDI',
        copy=False,
        readonly=True,
    )

    # =========================================================================
    # Computes y helpers
    # =========================================================================

    def _l10n_mx_edi_get_retention_cfdi_values(self):
        """Construye el diccionario de valores para el template QWeb
        del CFDI de Retenciones v1.0.

        Returns:
            dict con las claves necesarias para el template `retentions_cfdi`.
        """
        self.ensure_one()

        # ── Certificado vigente ──────────────────────────────────────────────
        # v19: modelo certificate.certificate — _get_valid_certificate() ya no existe.
        # Se filtra directamente por el campo is_valid (Boolean computed).
        certificate = self.company_id.l10n_mx_edi_certificate_ids\
            .sudo().filtered('is_valid')[:1]
        if not certificate:
            raise UserError(_(
                'No se encontró un certificado vigente para la empresa %s.',
                self.company_id.name,
            ))

        # ── Número de serie (formato hex como requiere el SAT) ──────────────
        # v19: ('%x' % int(serial_number))[1::2]  — ver _add_certificate_cfdi_values
        certificate_number = ('%x' % int(certificate.serial_number))[1::2]

        # ── Bytes del certificado (.cer) en base64 ────────────────────────────
        # v19: certificate._get_der_certificate_bytes(formatting='base64')
        cert_b64 = certificate._get_der_certificate_bytes(formatting='base64').decode()

        # ── Fecha de expedición en horario México (UTC-6 / UTC-5 DST) ────────
        tz = timezone(MX_TZ)
        cfdi_payment_date = datetime.now(tz).strftime('%Y-%m-%dT%H:%M:%S') \
                            + self._l10n_mx_edi_get_tz_offset()

        # ── Emisor y Receptor ─────────────────────────────────────────────────
        supplier = self.company_id.partner_id
        customer = self.partner_id.commercial_partner_id

        # ── Montos ───────────────────────────────────────────────────────────
        # Para retenciones: amount_untaxed = base gravable, amount_tax = monto retenido
        # Ajusta estos valores según la lógica fiscal de tu caso de uso.
        move = self.move_id
        amount_untaxed = abs(move.amount_untaxed) if move else self.amount
        amount_tax = abs(move.amount_tax) if move else 0.0
        amount_total = abs(move.amount_total) if move else self.amount

        dict_retencion_values =  {
                                        'certificate': certificate,
                                        'certificate_number': certificate_number,
                                        'certificate_key': cert_b64,
                                        'cfdi_payment_date': cfdi_payment_date,
                                        'retention_code': self.retention_type_id.code,
                                        'supplier': supplier,
                                        'customer': customer,
                                        'year': (self.date or fields.Date.today()).year,
                                        'amount_untaxed': '%.2f' % amount_untaxed,
                                        'amount_tax': '%.2f' % amount_tax,
                                        'amount_total': '%.2f' % amount_total,
                                    }
        print ("############ dict_retencion_values: ", dict_retencion_values)
        return dict_retencion_values

    def _l10n_mx_edi_get_tz_offset(self):
        """Retorna el offset UTC para la zona horaria del SAT.
        Retorna '-06:00' o '-05:00' según el horario de verano activo.
        """
        from pytz import timezone as tz
        import datetime as dt
        mx = tz(MX_TZ)
        now_mx = dt.datetime.now(mx)
        offset_hours = int(now_mx.utcoffset().total_seconds() / 3600)
        return f'{offset_hours:+03d}:00'

    # =========================================================================
    # Acciones del usuario
    # =========================================================================

    def action_l10n_mx_edi_retention_try_send(self):
        """Genera, firma (SHA-1) y timbra el CFDI de Retenciones vía PAC."""
        self.ensure_one()

        if not self.require_retention_cfdi:
            raise UserError(_('Este pago no está marcado para generar CFDI de Retención.'))
        if not self.retention_type_id:
            raise UserError(_('Selecciona el Tipo de Retención antes de timbrar.'))
        if self.l10n_mx_edi_retention_state == 'sent':
            raise UserError(_('Este pago ya tiene un CFDI de Retención timbrado (UUID: %s).',
                              self.l10n_mx_edi_retention_uuid))

        L10nDoc = self.env['l10n_mx_edi.document']
        result = L10nDoc._retention_cfdi_try_send(self)

        if result.get('error'):
            self.write({
                'l10n_mx_edi_retention_state': 'error',
                'l10n_mx_edi_retention_error_message': result['error'],
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error al timbrar CFDI de Retención'),
                    'message': result['error'],
                    'type': 'danger',
                    'sticky': True,
                },
            }

        # Guardar XML timbrado como adjunto
        filename = f'Retencion_{self.name.replace("/", "_")}.xml'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/xml',
            'datas': base64.b64encode(result['cfdi_str'].encode('utf-8')
                                       if isinstance(result['cfdi_str'], str)
                                       else result['cfdi_str']),
        })

        self.write({
            'l10n_mx_edi_retention_state': 'sent',
            'l10n_mx_edi_retention_uuid': result.get('uuid', ''),
            'l10n_mx_edi_retention_attachment_id': attachment.id,
            'l10n_mx_edi_retention_error_message': False,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CFDI de Retención timbrado'),
                'message': _('UUID: %s', result.get('uuid', '')),
                'type': 'success',
            },
        }

    def action_l10n_mx_edi_retention_reset(self):
        """Restablece el estado para permitir un nuevo intento de timbrado."""
        self.ensure_one()
        if self.l10n_mx_edi_retention_state == 'sent':
            raise UserError(_('No se puede restablecer un CFDI de Retención ya timbrado.'))
        self.write({
            'l10n_mx_edi_retention_state': 'draft',
            'l10n_mx_edi_retention_error_message': False,
        })

    def action_download_retention_xml(self):
        """Descarga el XML del CFDI de Retenciones timbrado."""
        self.ensure_one()
        if not self.l10n_mx_edi_retention_attachment_id:
            raise UserError(_('No hay un XML de Retención disponible para descargar.'))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.l10n_mx_edi_retention_attachment_id.id}'
                   f'?download=true',
            'target': 'self',
        }

    # =========================================================================
    # Reporte: agrega datos de retención a los valores del recibo de pago
    # =========================================================================

    def _get_payment_receipt_report_values(self):
        # EXTENDS 'account' → luego EXTENDS 'l10n_mx_edi'
        values = super()._get_payment_receipt_report_values()

        if self.require_retention_cfdi and self.l10n_mx_edi_retention_attachment_id:
            try:
                xml_bytes = base64.b64decode(
                    self.l10n_mx_edi_retention_attachment_id
                        .with_context(bin_size=False).datas
                )
                retention_vals = self._l10n_mx_edi_decode_retention_xml(xml_bytes)
            except Exception as e:
                _logger.warning('Error decoding retention XML for report: %s', e)
                retention_vals = {}

            values['retention_cfdi'] = {
                'uuid': self.l10n_mx_edi_retention_uuid,
                'payment': self,
                **retention_vals,
            }

        return values

    @api.model
    def _l10n_mx_edi_decode_retention_xml(self, xml_bytes):
        """Extrae datos básicos del XML de Retenciones para el reporte."""
        from lxml import etree
        NS = {
            'ret': 'http://www.sat.gob.mx/esquemas/retencionpago/1',
            'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
        }
        try:
            root = etree.fromstring(xml_bytes)
            tfd = root.find('.//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital')
            totales = root.find('{http://www.sat.gob.mx/esquemas/retencionpago/1}Totales')
            emisor = root.find('{http://www.sat.gob.mx/esquemas/retencionpago/1}Emisor')
            receptor = root.find('{http://www.sat.gob.mx/esquemas/retencionpago/1}Receptor')

            return {
                'stamp_uuid': tfd.get('UUID') if tfd is not None else '',
                'stamp_date': tfd.get('FechaTimbrado', '').replace('T', ' ') if tfd is not None else '',
                'sat_certificate': tfd.get('NoCertificadoSAT', '') if tfd is not None else '',
                'sat_sello': tfd.get('selloSAT', '') if tfd is not None else '',
                'monto_tot_operacion': totales.get('montoTotOperacion', '') if totales is not None else '',
                'monto_tot_ret': totales.get('montoTotRet', '') if totales is not None else '',
                'monto_tot_exent': totales.get('montoTotExent', '') if totales is not None else '',
                'emisor_rfc': emisor.get('RFCEmisor', '') if emisor is not None else '',
                'emisor_name': emisor.get('NomDenRazSocE', '') if emisor is not None else '',
                'fecha_exp': root.get('FechaExp', '').replace('T', ' '),
                'num_cert': root.get('NumCert', ''),
                'sello': root.get('Sello', ''),
            }
        except Exception as e:
            _logger.warning('_l10n_mx_edi_decode_retention_xml: %s', e)
            return {}
