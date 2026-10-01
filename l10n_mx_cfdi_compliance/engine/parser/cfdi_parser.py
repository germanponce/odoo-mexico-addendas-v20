# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""CFDI 4.0 parser. Returns an immutable DTO suitable for the rule engine.

Security notes
--------------
The parser disables external entity resolution and network access on
the underlying ``lxml`` parser to mitigate XXE / billion-laughs attacks.
A hard limit on document size is enforced by the caller before invoking
the parser.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any

from .complementos.nomina12 import NominaDTO, parse_nomina

try:
    from lxml import etree
except ImportError:  # pragma: no cover
    etree = None

_logger = logging.getLogger(__name__)

NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
    "pago20": "http://www.sat.gob.mx/Pagos20",
    "nomina12": "http://www.sat.gob.mx/nomina12",
    "cce20": "http://www.sat.gob.mx/ComercioExterior20",
    "cartaporte31": "http://www.sat.gob.mx/CartaPorte31",
}

MAX_XML_BYTES = 10 * 1024 * 1024  # 10 MB hard ceiling


class CfdiParseError(Exception):
    """Raised when an XML cannot be parsed as a CFDI 4.0 document."""


@dataclass(frozen=True)
class CfdiConcepto:
    clave_prod_serv: str = ""
    cantidad: Decimal = Decimal("0")
    clave_unidad: str = ""
    descripcion: str = ""
    valor_unitario: Decimal = Decimal("0")
    importe: Decimal = Decimal("0")
    objeto_imp: str = ""
    descuento: Decimal = Decimal("0")
    # Numero de cuenta predial del inmueble (atributo del nodo <cfdi:CuentaPredial>).
    # Obligatorio en CFDI de arrendamiento de inmuebles (claves SAT 8013xxxx / 8014xxxx).
    cuenta_predial: str = ""


@dataclass(frozen=True)
class CfdiImpuesto:
    impuesto: str = ""           # 001 ISR, 002 IVA, 003 IEPS
    tipo_factor: str = ""
    tasa_o_cuota: Decimal = Decimal("0")
    importe: Decimal = Decimal("0")
    base: Decimal = Decimal("0")


@dataclass(frozen=True)
class CfdiDocumentDTO:
    # Identification
    uuid: str = ""
    version: str = "4.0"
    serie: str = ""
    folio: str = ""
    fecha: Optional[datetime] = None
    fecha_timbrado: Optional[datetime] = None
    sello_cfd: str = ""
    sello_sat: str = ""
    no_certificado: str = ""
    no_certificado_sat: str = ""
    rfc_prov_certif: str = ""
    # Emisor / Receptor
    rfc_emisor: str = ""
    nombre_emisor: str = ""
    regimen_fiscal_emisor: str = ""
    rfc_receptor: str = ""
    nombre_receptor: str = ""
    domicilio_fiscal_receptor: str = ""
    regimen_fiscal_receptor: str = ""
    uso_cfdi: str = ""
    residencia_fiscal: str = ""
    # Money
    subtotal: Decimal = Decimal("0")
    descuento: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    moneda: str = "MXN"
    tipo_cambio: Decimal = Decimal("1")
    # Pago
    forma_pago: str = ""
    metodo_pago: str = ""
    condiciones_pago: str = ""
    # Tipo
    tipo_comprobante: str = ""   # I, E, T, N, P
    exportacion: str = ""
    lugar_expedicion: str = ""
    # Impuestos totales
    total_impuestos_trasladados: Decimal = Decimal("0")
    total_impuestos_retenidos: Decimal = Decimal("0")
    impuestos_trasladados: List[CfdiImpuesto] = field(default_factory=list)
    impuestos_retenidos: List[CfdiImpuesto] = field(default_factory=list)
    # Conceptos
    conceptos: List[CfdiConcepto] = field(default_factory=list)
    # CFDIs relacionados
    cfdi_relacionados: List[Dict[str, Any]] = field(default_factory=list)
    # Complementos detectados (raw etree dropped; only flags + parsed sub-DTO)
    has_complemento_pagos: bool = False
    has_complemento_nomina: bool = False
    has_complemento_comercio_exterior: bool = False
    has_complemento_carta_porte: bool = False
    complementos_extra: Dict[str, Any] = field(default_factory=dict)
    # Complemento de Nomina 1.2 parseado (None si el CFDI no es de nomina)
    nomina: Optional[NominaDTO] = None
    # Hash (SHA-256 of original bytes)
    xml_hash: str = ""


def _decimal(value: Optional[str], default: str = "0") -> Decimal:
    try:
        return Decimal((value or default).strip())
    except (InvalidOperation, AttributeError):
        return Decimal(default)


def _dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None


def _safe_parser():
    if etree is None:
        raise CfdiParseError("lxml no esta instalado en el entorno Python")
    return etree.XMLParser(
        resolve_entities=False, no_network=True,
        huge_tree=False, recover=False, remove_comments=True,
    )


def parse_cfdi(xml_bytes: bytes) -> CfdiDocumentDTO:
    """Parse raw XML bytes into a :class:`CfdiDocumentDTO`."""
    if not xml_bytes:
        raise CfdiParseError("XML vacio")
    if len(xml_bytes) > MAX_XML_BYTES:
        raise CfdiParseError(f"XML excede el limite de {MAX_XML_BYTES} bytes")

    xml_hash = hashlib.sha256(xml_bytes).hexdigest()
    try:
        root = etree.fromstring(xml_bytes, parser=_safe_parser())
    except etree.XMLSyntaxError as e:
        raise CfdiParseError(f"XML malformado: {e}") from e

    if not root.tag.endswith("}Comprobante"):
        raise CfdiParseError(f"Raiz inesperada: {root.tag}")

    # Emisor / Receptor
    emisor = root.find("cfdi:Emisor", NS)
    receptor = root.find("cfdi:Receptor", NS)
    if emisor is None or receptor is None:
        raise CfdiParseError("Faltan nodos Emisor o Receptor")

    # Timbre Fiscal Digital
    tfd_node = root.find(".//tfd:TimbreFiscalDigital", NS)
    uuid = tfd_node.get("UUID", "") if tfd_node is not None else ""
    if not uuid:
        raise CfdiParseError("CFDI sin UUID (sin Timbre Fiscal Digital)")

    # Conceptos
    conceptos: List[CfdiConcepto] = []
    for c in root.findall("cfdi:Conceptos/cfdi:Concepto", NS):
        cp_node = c.find("cfdi:CuentaPredial", NS)
        cuenta_predial_num = cp_node.get("Numero", "") if cp_node is not None else ""
        conceptos.append(CfdiConcepto(
            clave_prod_serv=c.get("ClaveProdServ", ""),
            cantidad=_decimal(c.get("Cantidad")),
            clave_unidad=c.get("ClaveUnidad", ""),
            descripcion=c.get("Descripcion", ""),
            valor_unitario=_decimal(c.get("ValorUnitario")),
            importe=_decimal(c.get("Importe")),
            objeto_imp=c.get("ObjetoImp", ""),
            descuento=_decimal(c.get("Descuento")),
            cuenta_predial=cuenta_predial_num,
        ))

    # Impuestos totales
    impuestos_node = root.find("cfdi:Impuestos", NS)
    trasladados: List[CfdiImpuesto] = []
    retenidos: List[CfdiImpuesto] = []
    total_t = Decimal("0")
    total_r = Decimal("0")
    if impuestos_node is not None:
        total_t = _decimal(impuestos_node.get("TotalImpuestosTrasladados"))
        total_r = _decimal(impuestos_node.get("TotalImpuestosRetenidos"))
        for t in impuestos_node.findall("cfdi:Traslados/cfdi:Traslado", NS):
            trasladados.append(CfdiImpuesto(
                impuesto=t.get("Impuesto", ""),
                tipo_factor=t.get("TipoFactor", ""),
                tasa_o_cuota=_decimal(t.get("TasaOCuota")),
                importe=_decimal(t.get("Importe")),
                base=_decimal(t.get("Base")),
            ))
        for r in impuestos_node.findall("cfdi:Retenciones/cfdi:Retencion", NS):
            retenidos.append(CfdiImpuesto(
                impuesto=r.get("Impuesto", ""),
                importe=_decimal(r.get("Importe")),
            ))

    # CFDI relacionados
    relacionados = []
    for grp in root.findall("cfdi:CfdiRelacionados", NS):
        tipo = grp.get("TipoRelacion", "")
        for rel in grp.findall("cfdi:CfdiRelacionado", NS):
            relacionados.append({"tipo_relacion": tipo, "uuid": rel.get("UUID", "")})

    # Complementos: flags only (sub-DTOs lazily parsed by complementos package)
    complemento = root.find("cfdi:Complemento", NS)
    has_pagos = has_nomina = has_cce = has_cp = False
    extra = {}
    if complemento is not None:
        has_pagos = complemento.find("pago20:Pagos", NS) is not None
        has_nomina = complemento.find("nomina12:Nomina", NS) is not None
        has_cce = complemento.find("cce20:ComercioExterior", NS) is not None
        has_cp = complemento.find("cartaporte31:CartaPorte", NS) is not None

    # Complemento de Nomina 1.2: se parsea a sub-DTO para las reglas categoria nomina.
    nomina_dto = parse_nomina(complemento, NS) if has_nomina else None

    return CfdiDocumentDTO(
        uuid=uuid,
        version=root.get("Version", "4.0"),
        serie=root.get("Serie", ""),
        folio=root.get("Folio", ""),
        fecha=_dt(root.get("Fecha")),
        fecha_timbrado=_dt(tfd_node.get("FechaTimbrado") if tfd_node is not None else None),
        sello_cfd=root.get("Sello", ""),
        sello_sat=tfd_node.get("SelloSAT", "") if tfd_node is not None else "",
        no_certificado=root.get("NoCertificado", ""),
        no_certificado_sat=tfd_node.get("NoCertificadoSAT", "") if tfd_node is not None else "",
        rfc_prov_certif=tfd_node.get("RfcProvCertif", "") if tfd_node is not None else "",
        rfc_emisor=(emisor.get("Rfc") or "").upper(),
        nombre_emisor=emisor.get("Nombre", ""),
        regimen_fiscal_emisor=emisor.get("RegimenFiscal", ""),
        rfc_receptor=(receptor.get("Rfc") or "").upper(),
        nombre_receptor=receptor.get("Nombre", ""),
        domicilio_fiscal_receptor=receptor.get("DomicilioFiscalReceptor", ""),
        regimen_fiscal_receptor=receptor.get("RegimenFiscalReceptor", ""),
        uso_cfdi=receptor.get("UsoCFDI", ""),
        residencia_fiscal=receptor.get("ResidenciaFiscal", ""),
        subtotal=_decimal(root.get("SubTotal")),
        descuento=_decimal(root.get("Descuento")),
        total=_decimal(root.get("Total")),
        moneda=root.get("Moneda", "MXN"),
        tipo_cambio=_decimal(root.get("TipoCambio"), default="1"),
        forma_pago=root.get("FormaPago", ""),
        metodo_pago=root.get("MetodoPago", ""),
        condiciones_pago=root.get("CondicionesDePago", ""),
        tipo_comprobante=root.get("TipoDeComprobante", ""),
        exportacion=root.get("Exportacion", ""),
        lugar_expedicion=root.get("LugarExpedicion", ""),
        total_impuestos_trasladados=total_t,
        total_impuestos_retenidos=total_r,
        impuestos_trasladados=trasladados,
        impuestos_retenidos=retenidos,
        conceptos=conceptos,
        cfdi_relacionados=relacionados,
        has_complemento_pagos=has_pagos,
        has_complemento_nomina=has_nomina,
        has_complemento_comercio_exterior=has_cce,
        has_complemento_carta_porte=has_cp,
        complementos_extra=extra,
        nomina=nomina_dto,
        xml_hash=xml_hash,
    )


def is_cfdi_xml(xml_bytes: bytes) -> bool:
    """Cheap pre-check used by ir.attachment hook."""
    if not xml_bytes or len(xml_bytes) > MAX_XML_BYTES:
        return False
    head = xml_bytes[:2048].lower()
    return b"cfdi:comprobante" in head or b"<comprobante" in head and b"sat.gob.mx/cfd" in head
