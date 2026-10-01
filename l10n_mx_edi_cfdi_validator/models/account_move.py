# -*- coding: utf-8 -*-
import logging
from lxml import etree

import requests
import xmltodict

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Selección reutilizada en todos los campos de resultado de validación
VAL_RESULT = [
    ('ok', 'Correcto'),
    ('error', 'Error'),
    ('omitido', 'No configurado'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    # =========================================================================
    # CAMPOS DE DATOS CFDI
    # Populados automáticamente desde el XML al importar (override de
    # _l10n_mx_edi_import_cfdi_invoice) y manualmente con el botón
    # "Releer XML".  Son campos almacenados regulares (no computed).
    # =========================================================================

    # ── Cabecera ──────────────────────────────────────────────────────────────
    l10n_mx_cfdi_version = fields.Char(
        string='Versión CFDI',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_tipo_comprobante = fields.Char(
        string='Tipo Comprobante',
        readonly=True, copy=False,
    )

    # ── Emisor ────────────────────────────────────────────────────────────────
    l10n_mx_cfdi_emisor_rfc = fields.Char(
        string='RFC Emisor',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_emisor_nombre = fields.Char(
        string='Nombre Emisor',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_emisor_regimen = fields.Char(
        string='Régimen Fiscal Emisor',
        readonly=True, copy=False,
    )

    # ── Receptor ──────────────────────────────────────────────────────────────
    l10n_mx_cfdi_receptor_rfc = fields.Char(
        string='RFC Receptor',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_receptor_nombre = fields.Char(
        string='Nombre Receptor',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_receptor_domicilio = fields.Char(
        string='Domicilio Fiscal Receptor',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_receptor_regimen = fields.Char(
        string='Régimen Fiscal Receptor',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_uso = fields.Char(
        string='Uso de CFDI',
        readonly=True, copy=False,
    )

    # ── Información Adicional ─────────────────────────────────────────────────
    l10n_mx_cfdi_metodo_pago = fields.Char(
        string='Método de Pago',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_forma_pago = fields.Char(
        string='Forma de Pago',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_lugar_expedicion = fields.Char(
        string='Lugar de Expedición',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_moneda_xml = fields.Char(
        string='Moneda XML',
        readonly=True, copy=False,
    )
    l10n_mx_cfdi_subtotal_xml = fields.Float(
        string='Subtotal XML',
        readonly=True, copy=False,
        digits=(16, 2),
    )
    l10n_mx_cfdi_total_xml = fields.Float(
        string='Total XML',
        readonly=True, copy=False,
        digits=(16, 2),
    )

    # ── Impuestos (One2many) ───────────────────────────────────────────────────
    l10n_mx_cfdi_tax_line_ids = fields.One2many(
        comodel_name='mx.cfdi.tax.line',
        inverse_name='move_id',
        string='Impuestos CFDI',
        readonly=True, copy=False,
    )

    # =========================================================================
    # CAMPOS DE RESULTADO DE VALIDACIÓN
    # Non-stored computed: se recalculan en cada lectura usando los datos
    # de los campos anteriores + la configuración de la empresa.
    # Esto garantiza que siempre reflejen la configuración vigente.
    # =========================================================================

    l10n_mx_cfdi_res_version = fields.Selection(
        VAL_RESULT, string='Versión 4.0',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_rfc_receptor = fields.Selection(
        VAL_RESULT, string='RFC Receptor',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_rs_receptor = fields.Selection(
        VAL_RESULT, string='Razón Social Receptor',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_cp_receptor = fields.Selection(
        VAL_RESULT, string='CP Receptor',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_tipo_comprobante = fields.Selection(
        VAL_RESULT, string='Tipo Comprobante',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_moneda = fields.Selection(
        VAL_RESULT, string='Moneda',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_uuid_duplicado = fields.Selection(
        VAL_RESULT, string='UUID Duplicado',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_rfc_emisor = fields.Selection(
        VAL_RESULT, string='RFC Emisor',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_rs_emisor = fields.Selection(
        VAL_RESULT, string='Razón Social Emisor',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_regimen_emisor = fields.Selection(
        VAL_RESULT, string='Régimen Fiscal Emisor',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_cp_emisor = fields.Selection(
        VAL_RESULT, string='CP Emisor',
        compute='_compute_mx_cfdi_validations',
    )
    l10n_mx_cfdi_res_sat_status = fields.Selection(
        VAL_RESULT, string='Estatus SAT',
        compute='_compute_mx_cfdi_validations',
    )
    # Contador de errores para badge en la pestaña
    l10n_mx_cfdi_error_count = fields.Integer(
        string='Errores de validación',
        compute='_compute_mx_cfdi_validations',
    )

    l10n_mx_cfdi_res_total = fields.Selection(
        VAL_RESULT, string='Total XML',
        compute='_compute_mx_cfdi_validations',
    )

    # Validaciones Status SAT
    l10n_mx_cfdi_sat_result = fields.Selection([
        ('valid', 'Vigente'),
        ('cancelled', 'Cancelado'),
        ('not_found', 'No encontrado'),
        ('error', 'Error consulta'),
        ('omitido', 'Omitido'),
    ], string='Resultado SAT', readonly=True, copy=False)

    l10n_mx_cfdi_sat_message = fields.Text(
        string='Detalle SAT',
        readonly=True,
        copy=False,
    )

    # =========================================================================
    # COMPUTE — VALIDACIONES
    # =========================================================================

    @api.depends(
        'l10n_mx_cfdi_version',
        'l10n_mx_cfdi_tipo_comprobante',
        'l10n_mx_cfdi_emisor_rfc',
        'l10n_mx_cfdi_emisor_nombre',
        'l10n_mx_cfdi_emisor_regimen',
        'l10n_mx_cfdi_lugar_expedicion',
        'l10n_mx_cfdi_receptor_rfc',
        'l10n_mx_cfdi_receptor_nombre',
        'l10n_mx_cfdi_receptor_domicilio',
        'l10n_mx_cfdi_moneda_xml',
        'l10n_mx_edi_cfdi_sat_state',
        'l10n_mx_edi_cfdi_uuid',
        'l10n_mx_cfdi_total_xml',
        'move_type',
        'company_id',
        'partner_id',
    )
    def _compute_mx_cfdi_validations(self):
        """
        Calcula el resultado de cada validación habilitada en la empresa.
        Valores posibles: 'ok' | 'error' | 'omitido'
        'omitido' significa que la validación no está activada O no hay XML.
        """
        for move in self:
            company = move.company_id
            # Proxy rápido: si no hay RFC del emisor, el XML no ha sido leído
            no_xml = not move.l10n_mx_cfdi_emisor_rfc
            errors = 0

            # ── Helper inline ────────────────────────────────────────────────
            def sanitize(name):
                if not name:
                    return ''
                try:
                    return self.env['l10n_mx_edi.document']._cfdi_sanitize_to_legal_name(name)
                except Exception:
                    return (name or '').strip().upper()

            # ── Versión ──────────────────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_version:
                move.l10n_mx_cfdi_res_version = 'omitido'
            else:
                ok = (move.l10n_mx_cfdi_version or '') == '4.0'
                move.l10n_mx_cfdi_res_version = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── RFC Receptor ─────────────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_rfc_receptor:
                move.l10n_mx_cfdi_res_rfc_receptor = 'omitido'
            else:
                c_rfc = (company.partner_id.vat or '').strip().upper()
                x_rfc = (move.l10n_mx_cfdi_receptor_rfc or '').strip().upper()
                ok = bool(c_rfc) and c_rfc == x_rfc
                move.l10n_mx_cfdi_res_rfc_receptor = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── Razón Social Receptor ────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_rs_receptor:
                move.l10n_mx_cfdi_res_rs_receptor = 'omitido'
            else:
                c_name = sanitize(company.name)
                x_name = sanitize(move.l10n_mx_cfdi_receptor_nombre)
                ok = bool(c_name) and c_name == x_name
                move.l10n_mx_cfdi_res_rs_receptor = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── CP Receptor ──────────────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_cp_receptor:
                move.l10n_mx_cfdi_res_cp_receptor = 'omitido'
            else:
                c_zip = (company.partner_id.zip or '').strip()
                x_cp = (move.l10n_mx_cfdi_receptor_domicilio or '').strip()
                ok = bool(c_zip) and c_zip == x_cp
                move.l10n_mx_cfdi_res_cp_receptor = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── Tipo Comprobante ─────────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_tipo_comprobante:
                move.l10n_mx_cfdi_res_tipo_comprobante = 'omitido'
            else:
                expected = 'I' if move.move_type == 'in_invoice' else 'E'
                ok = (move.l10n_mx_cfdi_tipo_comprobante or '') == expected
                move.l10n_mx_cfdi_res_tipo_comprobante = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── Moneda ───────────────────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_moneda:
                move.l10n_mx_cfdi_res_moneda = 'omitido'
            else:
                ok = (move.l10n_mx_cfdi_moneda_xml or '').upper() in ('MXN', 'USD')
                move.l10n_mx_cfdi_res_moneda = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── UUID Duplicado ───────────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_uuid_duplicado \
                    or not move.l10n_mx_edi_cfdi_uuid:
                move.l10n_mx_cfdi_res_uuid_duplicado = 'omitido'
            else:
                dup = self.search_count([
                    ('l10n_mx_edi_cfdi_uuid', '=', move.l10n_mx_edi_cfdi_uuid),
                    ('id', '!=', move.id),
                    ('move_type', 'in', ('in_invoice', 'in_refund')),
                    ('state', '!=', 'cancel'),
                ])
                ok = dup == 0
                move.l10n_mx_cfdi_res_uuid_duplicado = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── RFC Emisor ───────────────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_rfc_emisor:
                move.l10n_mx_cfdi_res_rfc_emisor = 'omitido'
            else:
                p_rfc = (move.partner_id.commercial_partner_id.vat or '').strip().upper()
                x_rfc = (move.l10n_mx_cfdi_emisor_rfc or '').strip().upper()
                ok = bool(p_rfc) and p_rfc == x_rfc
                move.l10n_mx_cfdi_res_rfc_emisor = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── Razón Social Emisor ──────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_rs_emisor:
                move.l10n_mx_cfdi_res_rs_emisor = 'omitido'
            else:
                p_name = sanitize(move.partner_id.commercial_partner_id.name)
                x_name = sanitize(move.l10n_mx_cfdi_emisor_nombre)
                ok = bool(p_name) and p_name == x_name
                move.l10n_mx_cfdi_res_rs_emisor = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── Régimen Fiscal Emisor ────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_regimen_emisor:
                move.l10n_mx_cfdi_res_regimen_emisor = 'omitido'
            else:
                partner = move.partner_id.commercial_partner_id
                p_reg = (getattr(partner, 'l10n_mx_edi_fiscal_regime', '') or '').strip()
                x_reg = (move.l10n_mx_cfdi_emisor_regimen or '').strip()
                ok = bool(p_reg) and p_reg == x_reg
                move.l10n_mx_cfdi_res_regimen_emisor = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── CP Emisor (LugarExpedición) ──────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_cp_emisor:
                move.l10n_mx_cfdi_res_cp_emisor = 'omitido'
            else:
                p_zip = (move.partner_id.commercial_partner_id.zip or '').strip()
                x_lugar = (move.l10n_mx_cfdi_lugar_expedicion or '').strip()
                ok = bool(p_zip) and p_zip == x_lugar
                move.l10n_mx_cfdi_res_cp_emisor = 'ok' if ok else 'error'
                if not ok:
                    errors += 1

            # ── Estatus SAT ──────────────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_sat_status:
                move.l10n_mx_cfdi_res_sat_status = 'omitido'
            else:
                sat = move.l10n_mx_cfdi_sat_result
                if not sat or sat == 'error':
                    # move.l10n_mx_cfdi_res_sat_status = 'omitido'
                    move.l10n_mx_cfdi_res_sat_status = 'omitido'
                    errors += 1
                elif sat == 'valid':
                    move.l10n_mx_cfdi_res_sat_status = 'ok'
                else:  # cancelled | not_found
                    move.l10n_mx_cfdi_res_sat_status = 'error'
                    errors += 1

            # ── MONTO XML ──────────────────────────────────────────────────
            if no_xml or not company.l10n_mx_cfdi_val_sat_amount:
                move.l10n_mx_cfdi_res_total = 'omitido'
            else:
                tolerance = 0.1
                if move.amount_total:
                    up_tolerance = move.amount_total + 0.1
                    down_tolerance = move.amount_total - 0.1
                    if move.l10n_mx_cfdi_total_xml:
                        if move.l10n_mx_cfdi_total_xml > up_tolerance or move.l10n_mx_cfdi_total_xml < down_tolerance:
                            move.l10n_mx_cfdi_res_total = 'omitido'
                        else:
                           move.l10n_mx_cfdi_res_total = 'error'
                           errors += 1 
                    else:
                        move.l10n_mx_cfdi_res_total = 'error'
                        errors += 1
                else:
                    move.l10n_mx_cfdi_res_total = 'omitido'

            move.l10n_mx_cfdi_error_count = errors

    # =========================================================================
    # LECTURA Y POBLACIÓN DEL XML
    # =========================================================================

    def _l10n_mx_edi_import_cfdi_invoice(self, invoice, file_data, new=False):
        """
        Override del método estándar de importación de CFDI.
        Después del flujo base, si el documento es de proveedor,
        poblamos automáticamente la pestaña CFDI.
        """
        result = super()._l10n_mx_edi_import_cfdi_invoice(invoice, file_data, new=new)
        if result and invoice.move_type in ('in_invoice', 'in_refund'):
            xml_tree = file_data.get('xml_tree')
            if xml_tree is not None:
                invoice._mx_cfdi_populate_all(tree=xml_tree)
        return result

    def action_mx_cfdi_reread_xml(self):
        """
        Botón "Releer XML" de la pestaña CFDI.
        Re-lee el XML adjunto y actualiza todos los campos de la pestaña.
        """
        self.ensure_one()
        if not self.l10n_mx_edi_cfdi_attachment_id:
            raise UserError(_('No hay un archivo XML CFDI adjunto al documento.'))
        self._mx_cfdi_populate_all()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('XML releído'),
                'message': _('Los datos del CFDI han sido actualizados correctamente.'),
                'sticky': False,
                'type': 'success',
            },
        }

    def _mx_cfdi_populate_all(self, tree=None):
        """
        Lee el CFDI XML (del árbol ya parseado o del adjunto)
        y actualiza todos los campos de datos + líneas de impuestos.

        :param tree: lxml.etree._Element (opcional, ya parseado)
        """
        self.ensure_one()

        # ── Obtener el árbol XML ─────────────────────────────────────────────
        if tree is None:
            if not self.l10n_mx_edi_cfdi_attachment_id:
                return
            try:
                raw = self.l10n_mx_edi_cfdi_attachment_id.with_context(bin_size=False).raw
                if not raw:
                    return
                tree = etree.fromstring(raw)
            except Exception as exc:
                _logger.warning(
                    'l10n_mx_edi_cfdi_validator: error al parsear XML en move %s: %s',
                    self.id, exc,
                )
                return

        # ── Helper: obtener atributo de un nodo (namespace-agnostic) ─────────
        def ga(node, attr):
            return node.get(attr) if node is not None else False

        # ── Localizar nodos relevantes ───────────────────────────────────────
        emisor = tree.find('.//{*}Emisor')
        receptor = tree.find('.//{*}Receptor')

        # ── Escribir campos escalares ─────────────────────────────────────────
        vals = {
            'l10n_mx_cfdi_version': tree.get('Version') or False,
            'l10n_mx_cfdi_tipo_comprobante': tree.get('TipoDeComprobante') or False,
            # Emisor
            'l10n_mx_cfdi_emisor_rfc': ga(emisor, 'Rfc'),
            'l10n_mx_cfdi_emisor_nombre': ga(emisor, 'Nombre'),
            'l10n_mx_cfdi_emisor_regimen': ga(emisor, 'RegimenFiscal'),
            # Receptor
            'l10n_mx_cfdi_receptor_rfc': ga(receptor, 'Rfc'),
            'l10n_mx_cfdi_receptor_nombre': ga(receptor, 'Nombre'),
            'l10n_mx_cfdi_receptor_domicilio': ga(receptor, 'DomicilioFiscalReceptor'),
            'l10n_mx_cfdi_receptor_regimen': ga(receptor, 'RegimenFiscalReceptor'),
            'l10n_mx_cfdi_uso': ga(receptor, 'UsoCFDI'),
            # Info adicional
            'l10n_mx_cfdi_metodo_pago': tree.get('MetodoPago') or False,
            'l10n_mx_cfdi_forma_pago': tree.get('FormaPago') or False,
            'l10n_mx_cfdi_lugar_expedicion': tree.get('LugarExpedicion') or False,
            'l10n_mx_cfdi_moneda_xml': tree.get('Moneda') or False,
            'l10n_mx_cfdi_total_xml': float(tree.get('Total') or 0),
            'l10n_mx_cfdi_subtotal_xml': float(tree.get('SubTotal') or 0),
        }

        # ── Líneas de impuestos ───────────────────────────────────────────────
        self._mx_cfdi_populate_tax_lines(tree)

        # ── UUID ─────────────────────────────────────────────
        timbre = tree.find('.//{*}TimbreFiscalDigital')
        uuid = timbre.get('UUID') if timbre is not None else False
        # print ("################ uuid: ", uuid)
        if uuid:
            sat_result, sat_msg = self._mx_cfdi_check_sat(
                uuid=uuid,
                rfc_emisor=vals.get('l10n_mx_cfdi_emisor_rfc'),
                rfc_receptor=vals.get('l10n_mx_cfdi_receptor_rfc'),
                total=vals.get('l10n_mx_cfdi_total_xml'),
            )
            # print ("########## sat_result: ", sat_result)
            # print ("########## sat_msg: ", sat_msg)
            vals.update({
                'l10n_mx_cfdi_sat_result': sat_result,
                'l10n_mx_cfdi_sat_message': str(sat_msg),
            })
        ### Guardamos el Resultado
        self.write(vals)

    def _mx_cfdi_populate_tax_lines(self, tree):
        """
        Elimina las líneas de impuesto CFDI existentes y las recrea
        leyendo el nodo global <cfdi:Impuestos> (hijo directo de Comprobante).
        Solo procesa los impuestos globales, no los de cada Concepto.
        """
        self.ensure_one()
        # Borrar líneas previas
        self.l10n_mx_cfdi_tax_line_ids.unlink()

        # Encontrar <Impuestos> como hijo directo de la raíz
        global_imp = None
        for child in tree:
            tag_local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag_local == 'Impuestos':
                global_imp = child
                break

        if global_imp is None:
            return

        lines = []

        # Traslados globales
        for section in global_imp:
            sec_local = section.tag.split('}')[-1] if '}' in section.tag else section.tag
            tipo = 'traslado' if sec_local == 'Traslados' else (
                'retencion' if sec_local == 'Retenciones' else None
            )
            if tipo is None:
                continue
            for node in section:
                try:
                    importe = float(node.get('Importe') or 0)
                except (ValueError, TypeError):
                    importe = 0.0
                lines.append({
                    'move_id': self.id,
                    'tipo': tipo,
                    'codigo': node.get('Impuesto') or False,
                    'tipo_factor': node.get('TipoFactor') or False,
                    'tasa_o_cuota': node.get('TasaOCuota') or False,
                    'importe': importe,
                })

        if lines:
            self.env['mx.cfdi.tax.line'].create(lines)


    def _mx_cfdi_check_sat(self, uuid, rfc_emisor, rfc_receptor, total):
        self.ensure_one()

        url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl'
        headers = {
            'Content-type': 'text/xml;charset="utf-8"',
            'Accept': 'text/xml',
            'SOAPAction': 'http://tempuri.org/IConsultaCFDIService/Consulta'
        }

        body = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
            <soapenv:Header/>
            <soapenv:Body>
                <tem:Consulta>
                    <tem:expresionImpresa><![CDATA[?re={rfc_emisor}&rr={rfc_receptor}&tt={total}&id={uuid}]]></tem:expresionImpresa>
                </tem:Consulta>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        try:
            response = requests.post(url=url, headers=headers, data=body, timeout=5)

            if response.status_code != 200:
                return 'error', f'HTTP {response.status_code}'

            data = xmltodict.parse(response.text)
            result = data['s:Envelope']['s:Body']['ConsultaResponse']['ConsultaResult']

            estado = result.get('a:Estado', '').lower()

            if estado == 'vigente':
                return 'valid', result
            elif estado == 'cancelado':
                return 'cancelled', result
            else:
                return 'not_found', result

        except Exception as e:
            _logger.warning('Error SAT consulta CFDI: %s', str(e))
            return 'error', str(e)

    # =========================================================================
    # BLOQUEO EN CONFIRMAR
    # =========================================================================

    def action_mx_cfdi_check_sat(self):
        for rec in self:
            if not rec.l10n_mx_edi_cfdi_uuid:
                continue

            result, msg = rec._mx_cfdi_check_sat(
                uuid=rec.l10n_mx_edi_cfdi_uuid,
                rfc_emisor=rec.l10n_mx_cfdi_emisor_rfc,
                rfc_receptor=rec.l10n_mx_cfdi_receptor_rfc,
                total=rec.l10n_mx_cfdi_total_xml,
            )

            rec.write({
                'l10n_mx_cfdi_sat_result': result,
                'l10n_mx_cfdi_sat_message': str(msg),
            })

    def action_post(self):
        """
        Override de action_post para verificar validaciones CFDI antes de
        registrar una factura de proveedor con XML adjunto.
        """
        for move in self:
            if (
                move.move_type in ('in_invoice', 'in_refund')
                and move.l10n_mx_cfdi_emisor_rfc  # hay datos XML leídos
            ):
                if move.l10n_mx_cfdi_sat_result in (
                                                    'not_found',
                                                    'error',
                                                    'omitido'
                                                    ):
                    move.action_mx_cfdi_check_sat()
                move._mx_cfdi_check_validations_on_post()

        return super().action_post()

    def _mx_cfdi_check_validations_on_post(self):
        """
        Evalúa cada validación activa en la empresa. Si alguna tiene
        resultado 'error', lanza UserError e impide la confirmación.
        """
        company = self.company_id

        # Mapa: (campo_config_empresa, campo_resultado_factura, etiqueta)
        checks = [
            ('l10n_mx_cfdi_val_version',
             'l10n_mx_cfdi_res_version',
             _('Versión CFDI 4.0')),
            ('l10n_mx_cfdi_val_rfc_receptor',
             'l10n_mx_cfdi_res_rfc_receptor',
             _('RFC Receptor')),
            ('l10n_mx_cfdi_val_rs_receptor',
             'l10n_mx_cfdi_res_rs_receptor',
             _('Razón Social Receptor')),
            ('l10n_mx_cfdi_val_cp_receptor',
             'l10n_mx_cfdi_res_cp_receptor',
             _('CP Receptor')),
            ('l10n_mx_cfdi_val_tipo_comprobante',
             'l10n_mx_cfdi_res_tipo_comprobante',
             _('Tipo de Comprobante')),
            ('l10n_mx_cfdi_val_moneda',
             'l10n_mx_cfdi_res_moneda',
             _('Moneda')),
            ('l10n_mx_cfdi_val_uuid_duplicado',
             'l10n_mx_cfdi_res_uuid_duplicado',
             _('UUID / Folio Fiscal duplicado')),
            ('l10n_mx_cfdi_val_rfc_emisor',
             'l10n_mx_cfdi_res_rfc_emisor',
             _('RFC Emisor')),
            ('l10n_mx_cfdi_val_rs_emisor',
             'l10n_mx_cfdi_res_rs_emisor',
             _('Razón Social Emisor')),
            ('l10n_mx_cfdi_val_regimen_emisor',
             'l10n_mx_cfdi_res_regimen_emisor',
             _('Régimen Fiscal Emisor')),
            ('l10n_mx_cfdi_val_cp_emisor',
             'l10n_mx_cfdi_res_cp_emisor',
             _('CP Emisor')),
            ('l10n_mx_cfdi_val_sat_amount',
             'l10n_mx_cfdi_res_total',
             _('Monto XML')),
            ('l10n_mx_cfdi_val_sat_status',
             'l10n_mx_cfdi_res_sat_status',
             _('Estatus SAT')),
        ]

        errors = []
        for config_field, result_field, label in checks:
            if getattr(company, config_field) and getattr(self, result_field) == 'error':
                errors.append(f'  • {label}')

        if errors:
            raise UserError(
                _(
                    'No se puede confirmar la factura %(name)s.\n'
                    'Las siguientes validaciones CFDI han fallado:\n\n%(errors)s\n\n'
                    'Revise la pestaña CFDI para más detalles.',
                    name=self.name,
                    errors='\n'.join(errors),
                )
            )
