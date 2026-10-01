# -*- coding: utf-8 -*-
"""
Extensión de l10n_mx_edi.document para generar y timbrar CFDI de Retenciones
e Información de Pagos v1.0 (SAT México).

Flujo:
  1. _retention_cfdi_try_send(payment)
       → _build_retention_unsigned_xml(payment)    # Genera XML con QWeb
       → _retention_cadena_original(xml_node)       # Aplica XSLT del SAT
       → _retention_sign_sha256(cadena, certificate)  # Firma SHA-1
       → _retention_sign_using_finkok(xml_str, co.) # Timbra vía PAC Finkok
"""

import base64
import logging

from lxml import etree

from odoo import _, api, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Ruta al XSLT de cadena original para Retenciones v1.0 (SAT).
# ⚠ El archivo debe obtenerse del SAT y colocarse en esta ruta dentro del módulo.
# Descarga: https://www.sat.gob.mx/cs/Satellite?blobcol=urldata&blobkey=id
#           &blobtable=MungoBlobs&blobwhere=1461173300266&ssbinary=true
CFDI_XSLT_RETENCIONES = 'l10n_mx_edi_retentions_simple/data/xslt/retenciones.xslt'

# URLs de Finkok para el servicio de Retenciones
FINKOK_RETENTIONS_TEST_URL = (
    'https://demo-facturacion.finkok.com/servicios/soap/retentions.wsdl'
)
FINKOK_RETENTIONS_PROD_URL = (
    'https://facturacion.finkok.com/servicios/soap/retentions.wsdl'
)


class L10nMxEdiDocument(models.Model):
    _inherit = 'l10n_mx_edi.document'

    # =========================================================================
    # Punto de entrada principal
    # =========================================================================

    @api.model
    def _retention_cfdi_try_send(self, payment):
        """Genera, firma y timbra el CFDI de Retenciones para el pago dado.

        Args:
            payment (account.payment): El pago con require_retention_cfdi=True.

        Returns:
            dict:
                - {'cfdi_str': str, 'uuid': str}  → éxito
                - {'error': str}                   → fallo
        """
        try:
            cfdi_values = payment._l10n_mx_edi_get_retention_cfdi_values()
        except UserError as e:
            return {'error': str(e)}

        # 1. Generar el XML sin sellar con QWeb
        try:
            unsigned_xml_bytes = self._build_retention_unsigned_xml(cfdi_values)
        except Exception as e:
            _logger.exception('Error generating retention XML')
            return {'error': _('Error generando el XML de Retención: %s', str(e))}

        # 2. Calcular cadena original y sellar con SHA-1
        print ("######### unsigned_xml_bytes: ", unsigned_xml_bytes)
        try:
            xml_node = etree.fromstring(unsigned_xml_bytes)
            print ("######### xml_node: ", xml_node)
            cadena = self._retention_cadena_original(xml_node)
            print ("######### cadena: ", cadena)
            if not cadena:
                return {'error': _('No se pudo calcular la cadena original del CFDI de Retención.')}

            sello = self._retention_sign_sha256(cadena, cfdi_values['certificate'])
            xml_node.attrib['Sello'] = sello
        except Exception as e:
            _logger.exception('Error signing retention cadena')
            return {'error': _('Error al sellar el CFDI de Retención: %s', str(e))}

        # 3. Serializar y timbrar vía PAC
        sealed_xml_str = etree.tostring(
            xml_node, pretty_print=True, xml_declaration=True, encoding='UTF-8',
        ).decode('utf-8')

        result = self._retention_sign_via_pac(sealed_xml_str, payment.company_id)
        return result

    # =========================================================================
    # Generación del XML sin timbrar
    # =========================================================================

    @api.model
    def _build_retention_unsigned_xml(self, cfdi_values):
        """Renderiza el template QWeb retentions_cfdi con los valores dados.

        Returns:
            bytes: XML sin sellar.
        """
        # v19: los templates QWeb se renderizan via ir.qweb._render(xml_id, values).
        # env.ref(...) devuelve ir.ui.view que NO tiene ._render(); ese método
        # vive en ir.qweb. El XML ID usa el nombre real del módulo instalado.
        cfdi_str = self.env['ir.qweb']._render(
            'l10n_mx_edi_retentions_simple.retentions_cfdi', cfdi_values
        )
        # cfdi_str puede ser bytes o str según versión de Odoo
        if isinstance(cfdi_str, str):
            cfdi_str = cfdi_str.encode('utf-8')

        # Sanear y validar como XML válido
        try:
            etree.fromstring(cfdi_str)
        except etree.XMLSyntaxError as e:
            _logger.error('Generated XML is not valid: %s\n%s', e, cfdi_str[:2000])
            raise
        return cfdi_str

    # =========================================================================
    # Cadena original (XSLT del SAT)
    # =========================================================================

    @api.model
    def _retention_cadena_original(self, xml_node):
        """Aplica el XSLT del SAT para obtener la cadena original.

        Args:
            xml_node: lxml.etree._Element — nodo raíz del CFDI de Retención.

        Returns:
            str: cadena original, o vacío si el XSLT no está disponible.

        Note:
            Si el archivo XSLT no está disponible, se usa una cadena vacía
            (útil en entorno de pruebas). En producción, el XSLT es obligatorio.
        """
        try:
            xslt_file = tools.file_open(CFDI_XSLT_RETENCIONES)
            cadena_root = etree.parse(xslt_file)
            transform = etree.XSLT(cadena_root)
            cadena = str(transform(xml_node))
            _logger.debug('Retention cadena original: %s', cadena[:120])
            return cadena
        except FileNotFoundError:
            _logger.warning(
                'XSLT de Retenciones no encontrado en %s. '
                'Descárgalo de sat.gob.mx y colócalo en la ruta indicada.',
                CFDI_XSLT_RETENCIONES,
            )
            # En test con PAC de prueba el sello no se valida → cadena vacía
            return ''
        except Exception as e:
            _logger.exception('Error applying retentions XSLT: %s', e)
            return ''

    # =========================================================================
    # Firma SHA-1 (requerida por esquema Retenciones v1.0 del SAT)
    # =========================================================================

    @api.model
    def _retention_sign_sha256(self, cadena, certificate):
        """Firma la cadena original con SHA-1 usando la llave privada del certificado.

        El esquema retenciones v1.0 del SAT requiere SHA-1 (no SHA-256).
        El esquema v2.0 usa SHA-256; si migras a v2.0, usa hashes.SHA256().

        En v19, la estructura del certificado es certificate.certificate (no l10n_mx_edi.certificate):
          - certificate.private_key_id  → objeto certificate.key
          - certificate.private_key_id.pem_key   → bytes PEM del key en base64
          - certificate.private_key_id.password  → contraseña del key

        Ver _get_unencrypted_private_key_pem en l10n_mx_edi_document.py oficial v19.

        Args:
            cadena (str): Cadena original generada por el XSLT.
            certificate (certificate.certificate): Certificado vigente.

        Returns:
            str: Sello en base64.
        """
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding as asym_padding

        # v19: acceso a la llave privada via private_key_id
        key_obj = certificate.private_key_id
        if not key_obj:
            raise UserError(_(
                'El certificado no tiene una llave privada asociada. '
                'Verifica la configuración del certificado.'
            ))

        key_pem_bytes = base64.b64decode(key_obj.pem_key)
        password = key_obj.password.encode() if key_obj.password else None
        private_key = serialization.load_pem_private_key(key_pem_bytes, password=password)

        cadena_bytes = cadena.encode('utf-8')
        signature = private_key.sign(
            cadena_bytes,
            asym_padding.PKCS1v15(),
            hashes.SHA256(),  # ← Obligatorio para Retenciones v1.0 del SAT
        )
        return base64.b64encode(signature).decode('utf-8')

    # =========================================================================
    # Timbrado vía PAC — Finkok, Solucion Factible y Smart Web
    # Dispatcher principal + implementación por PAC
    # =========================================================================

    @api.model
    def _retention_sign_via_pac(self, xml_str, company):
        """Dispatcher: selecciona el PAC configurado en la empresa y firma
        el CFDI de Retenciones usando su endpoint específico.

        Reutiliza los métodos de credenciales del modelo oficial l10n_mx_edi.document
        (_get_finkok_credentials, _get_solfact_credentials, _get_sw_credentials)
        para no duplicar configuración.

        Args:
            xml_str (str | bytes): XML sellado listo para timbrar.
            company (res.company): Compañía con configuración PAC.

        Returns:
            dict: {'cfdi_str': ..., 'uuid': ...} o {'error': ...}
        """
        # Obtener la empresa raíz (misma lógica que _get_company_cfdi_values oficial)
        root_company = (
            company.sudo().parent_ids[::-1].filtered('partner_id.vat')[:1]
            or company
        )
        pac_name = root_company.l10n_mx_edi_pac
        if not pac_name:
            return {'error': _('No hay PAC configurado en la empresa %s.', company.name)}

        # Credenciales base via métodos del modelo oficial
        credential_method = {
            'finkok':  self._get_finkok_credentials,
            'solfact': self._get_solfact_credentials,
            'sw':      self._get_sw_credentials,
        }.get(pac_name)

        if not credential_method:
            return {'error': _(
                'El PAC "%s" no está soportado para retenciones. '
                'PACs disponibles: finkok, solfact, sw.', pac_name
            )}

        credentials = credential_method(root_company)
        if credentials.get('errors'):
            return {'error': '\n'.join(credentials['errors'])}

        # Para Finkok, retenciones usa un WSDL diferente al de facturas
        if pac_name == 'finkok':
            credentials['sign_url'] = (
                FINKOK_RETENTIONS_TEST_URL
                if root_company.l10n_mx_edi_pac_test_env
                else FINKOK_RETENTIONS_PROD_URL
            )

        # Asegurar que xml_str es str para SOAP / bytes para REST
        if isinstance(xml_str, bytes):
            xml_str_decoded = xml_str.decode('utf-8')
            xml_bytes = xml_str
        else:
            xml_str_decoded = xml_str
            xml_bytes = xml_str.encode('utf-8')

        sign_method = {
            'finkok':  self._retention_sign_finkok,
            'solfact': self._retention_sign_solfact,
            'sw':      self._retention_sign_sw,
        }[pac_name]

        _logger.info(
            'Sending retention CFDI via %s (test=%s)',
            pac_name, root_company.l10n_mx_edi_pac_test_env,
        )
        return sign_method(xml_str_decoded, xml_bytes, credentials)

    # ── Finkok ───────────────────────────────────────────────────────────────

    @api.model
    def _retention_sign_finkok(self, xml_str, xml_bytes, credentials):
        """Timbra el CFDI de Retenciones en Finkok usando su WSDL exclusivo
        de retenciones (distinto al WSDL de facturas).

        WSDL Test: https://demo-facturacion.finkok.com/servicios/soap/retentions.wsdl
        WSDL Prod: https://facturacion.finkok.com/servicios/soap/retentions.wsdl
        Método   : sign(username, password, retencion)
        """
        from odoo.tools.zeep import Client, Transport

        try:
            client = Client(
                credentials['sign_url'],
                transport=Transport(timeout=20, operation_timeout=20),
            )
            response = client.service.sign(
                username=credentials['username'],
                password=credentials['password'],
                retencion=xml_str,
            )
        except Exception as e:
            _logger.exception('Finkok retentions SOAP error')
            return {'error': _('Error de comunicación con Finkok: %s', str(e))}

        errors = []
        if hasattr(response, 'Incidencias') and response.Incidencias:
            try:
                for inc in response.Incidencias.Incidencia:
                    errors.append(str(getattr(inc, 'MensajeIncidencia', inc)))
            except Exception:
                errors.append(str(response.Incidencias))
        if errors:
            return {'error': '\n'.join(errors)}

        signed_xml = getattr(response, 'Documento', None)
        if not signed_xml:
            return {'error': _('Finkok no devolvió el documento timbrado.')}

        return {'cfdi_str': signed_xml, 'uuid': self._retention_extract_uuid(signed_xml)}

    # ── Solucion Factible ────────────────────────────────────────────────────

    @api.model
    def _retention_sign_solfact(self, xml_str, xml_bytes, credentials):
        """Timbra el CFDI de Retenciones en Solucion Factible.

        SF usa el mismo endpoint timbrar() para facturas y retenciones;
        el PAC detecta el tipo de documento por el namespace del XML.

        WSDL Test: https://testing.solucionfactible.com/ws/services/Timbrado?wsdl
        WSDL Prod: https://solucionfactible.com/ws/services/Timbrado?wsdl
        Método   : timbrar(username, password, cfdi, return_xml)
        """
        from odoo.tools.zeep import Client, Transport

        try:
            client = Client(
                credentials['url'],
                transport=Transport(timeout=20),
            )
            response = client.service.timbrar(
                credentials['username'],
                credentials['password'],
                xml_bytes,   # acepta bytes
                False,
            )
        except Exception as e:
            _logger.exception('Solucion Factible retentions error')
            return {'error': _('Error de comunicación con Solucion Factible: %s', str(e))}

        if response.status != 200:
            msg = getattr(response, 'mensaje', str(response.status))
            return {'error': f'[{response.status}] {msg}'}

        result = response.resultados[0] if response.resultados else response
        signed_xml = getattr(result, 'cfdiTimbrado', None)
        if signed_xml:
            return {'cfdi_str': signed_xml, 'uuid': self._retention_extract_uuid(signed_xml)}

        code = getattr(result, 'status', '') or ''
        msg = getattr(result, 'mensaje', '') or ''
        return {'error': f'[{code}] {msg}' if (code or msg) else _('Sin respuesta de Solucion Factible.')}

    # ── Smart Web (SW) ────────────────────────────────────────────────────────

    @api.model
    def _retention_sign_sw(self, xml_str, xml_bytes, credentials):
        """Timbra el CFDI de Retenciones en Smart Web (SW) vía REST/b64.

        SW detecta automáticamente el tipo de documento (factura o retención)
        por el namespace del XML, usando el mismo endpoint de timbrado.

        Endpoint Test: https://services.test.sw.com.mx/cfdi33/stamp/v3/b64
        Endpoint Prod: https://services.sw.com.mx/cfdi33/stamp/v3/b64
        """
        import base64
        import random
        import string
        import requests
        from json.decoder import JSONDecodeError

        cfdi_b64 = base64.encodebytes(xml_bytes).decode('UTF-8')
        boundary = ''.join(random.choices(string.ascii_letters + string.digits, k=30))
        payload = (
            f'--{boundary}\r\n'
            'Content-Type: text/xml\r\n'
            'Content-Transfer-Encoding: binary\r\n'
            'Content-Disposition: form-data; name="xml"; filename="xml"\r\n'
            f'\r\n{cfdi_b64}\r\n'
            f'--{boundary}--\r\n'
        ).replace('\n', '\r\n').encode('UTF-8')

        headers = {
            'Authorization': f"bearer {credentials['token']}",
            'Content-Type': f'multipart/form-data; boundary="{boundary}"',
        }

        try:
            response = requests.post(
                credentials['sign_url'],
                data=payload,
                headers=headers,
                verify=True,
                timeout=(20, 120),
            )
            response_json = response.json()
        except (requests.exceptions.RequestException, JSONDecodeError) as e:
            _logger.exception('SW retentions REST error')
            return {'error': _('Error de comunicación con Smart Web: %s', str(e))}

        # SW devuelve el CFDI en base64 dentro de data.cfdi
        try:
            signed_b64 = response_json['data']['cfdi']
            signed_xml = base64.decodebytes(signed_b64.encode('UTF-8'))
            return {'cfdi_str': signed_xml, 'uuid': self._retention_extract_uuid(signed_xml)}
        except (KeyError, TypeError):
            pass

        # Código 307 = documento ya firmado previamente
        if response_json.get('message', '').startswith('307'):
            signed_xml = base64.decodebytes(
                response_json['messageDetail'].encode('UTF-8')
            )
            return {'cfdi_str': signed_xml, 'uuid': self._retention_extract_uuid(signed_xml)}

        code = response_json.get('message', '')
        msg = response_json.get('messageDetail', '')
        return {'error': f'[{code}] {msg}' if (code or msg) else str(response_json)}

    # =========================================================================
    # Utilidades
    # =========================================================================

    @api.model
    def _retention_extract_uuid(self, signed_xml_str):
        """Extrae el UUID del TimbreFiscalDigital del XML timbrado."""
        try:
            if isinstance(signed_xml_str, str):
                signed_xml_str = signed_xml_str.encode('utf-8')
            root = etree.fromstring(signed_xml_str)
            tfd = root.find(
                './/{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital'
            )
            return tfd.get('UUID', '') if tfd is not None else ''
        except Exception as e:
            _logger.warning('Could not extract UUID from retention XML: %s', e)
            return ''
