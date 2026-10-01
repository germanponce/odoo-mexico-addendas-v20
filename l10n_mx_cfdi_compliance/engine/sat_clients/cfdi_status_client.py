# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
"""SAT CFDI status web service client.

Endpoint: https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc

The check is implemented via SOAP HTTP POST without external SOAP libs.
Returns a normalized dict {estado, codigo_estatus, es_cancelable, estatus_cancelacion}.
Network errors return {"error": "..."} and rules MUST handle the absence
of network gracefully.
"""
from __future__ import annotations

import logging
import re
from typing import Dict

from .cache import cfdi_status_cache

_logger = logging.getLogger(__name__)

SOAP_URL = (
    "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc"
)
SOAP_ACTION = "http://tempuri.org/IConsultaCFDIService/Consulta"
SOAP_TIMEOUT = 12

SOAP_ENVELOPE = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
    ' xmlns:t="http://tempuri.org/">'
    '<s:Body><t:Consulta><t:expresionImpresa><![CDATA[{expr}]]>'
    '</t:expresionImpresa></t:Consulta></s:Body></s:Envelope>'
)


def _build_expr(uuid: str, rfc_emisor: str, rfc_receptor: str, total: str) -> str:
    return (f"?re={rfc_emisor}&rr={rfc_receptor}&tt={total}&id={uuid}")


def consulta(uuid: str, rfc_emisor: str, rfc_receptor: str, total: str) -> Dict:
    cache = cfdi_status_cache()
    cache_key = f"status:{uuid}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    try:
        import requests
    except ImportError:  # pragma: no cover
        return {"error": "requests not available"}
    expr = _build_expr(uuid, rfc_emisor, rfc_receptor, total)
    body = SOAP_ENVELOPE.format(expr=expr)
    try:
        resp = requests.post(
            SOAP_URL, data=body, timeout=SOAP_TIMEOUT,
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": SOAP_ACTION,
            },
        )
        resp.raise_for_status()
        text = resp.text
        result = {
            "estado": _extract(text, "Estado"),
            "codigo_estatus": _extract(text, "CodigoEstatus"),
            "es_cancelable": _extract(text, "EsCancelable"),
            "estatus_cancelacion": _extract(text, "EstatusCancelacion"),
        }
        cache.set(cache_key, result)
        return result
    except Exception as e:
        _logger.warning("SAT status check failed for %s: %s", uuid, e)
        return {"error": str(e)}


def _extract(xml: str, tag: str) -> str:
    m = re.search(rf"<a:{tag}>([^<]*)</a:{tag}>", xml)
    return m.group(1).strip() if m else ""
