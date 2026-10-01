# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Catalogos SAT del Complemento de Nomina 1.2 (subconjuntos de codigos validos).

Fuente: catalogos c_* publicados por el SAT para Nomina 1.2. Se mantienen como
constantes editables: si el SAT agrega un codigo, basta actualizarlo aqui (la
regla de catalogos es severidad Medium/warning, asi que un codigo nuevo nunca
bloquea, solo advierte "verificar catalogo").
"""
from __future__ import annotations

C_TIPO_NOMINA = frozenset({"O", "E"})

C_TIPO_CONTRATO = frozenset({
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "99",
})

C_TIPO_JORNADA = frozenset({
    "01", "02", "03", "04", "05", "06", "07", "08", "99",
})

C_TIPO_REGIMEN = frozenset({
    "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "99",
})

C_RIESGO_PUESTO = frozenset({"1", "2", "3", "4", "5", "99"})

C_TIPO_PERCEPCION = frozenset({
    "001", "002", "003", "004", "005", "006", "009", "010", "011", "012",
    "013", "014", "015", "019", "020", "021", "022", "023", "024", "025",
    "026", "027", "028", "029", "030", "031", "032", "033", "034", "035",
    "036", "037", "038", "039", "044", "045", "046", "047", "048", "049",
    "050",
})

C_TIPO_DEDUCCION = frozenset({
    "001", "002", "003", "004", "005", "006", "007", "008", "009", "010",
    "011", "012", "013", "014", "015", "016", "017", "018", "019", "020",
    "021", "022", "023",
})

C_TIPO_OTRO_PAGO = frozenset({
    "001", "002", "003", "004", "005", "999",
})

C_TIPO_HORAS = frozenset({"01", "02", "03"})  # 01 Dobles, 02 Triples, 03 Simples

# Mapa nombre-catalogo -> conjunto, usado por la regla NOM_015.
CATALOGOS = {
    "TipoNomina": C_TIPO_NOMINA,
    "TipoContrato": C_TIPO_CONTRATO,
    "TipoJornada": C_TIPO_JORNADA,
    "TipoRegimen": C_TIPO_REGIMEN,
    "RiesgoPuesto": C_RIESGO_PUESTO,
    "TipoPercepcion": C_TIPO_PERCEPCION,
    "TipoDeduccion": C_TIPO_DEDUCCION,
    "TipoOtroPago": C_TIPO_OTRO_PAGO,
    "TipoHoras": C_TIPO_HORAS,
}


def is_valid(catalogo: str, code: str) -> bool:
    """True si ``code`` pertenece al catalogo (o el catalogo no esta cargado)."""
    valid = CATALOGOS.get(catalogo)
    if valid is None:
        return True
    return (code or "") in valid
