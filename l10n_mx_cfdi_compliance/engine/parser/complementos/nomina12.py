# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Parser del Complemento de Nomina 1.2 (CFDI 4.0).

El parser base (`cfdi_parser`) solo levanta el flag ``has_complemento_nomina``.
Este modulo convierte el nodo ``nomina12:Nomina`` en un DTO inmutable
(``NominaDTO``) consumible por las reglas de la categoria ``nomina`` sin volver
a tocar el XML. Tolerante a campos opcionales: nunca lanza, devuelve None si no
hay nodo Nomina.

Referencia: Anexo 20 / Guia de llenado del Complemento de Nomina v1.2 (SAT).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional, List

NOMINA12_NS = "http://www.sat.gob.mx/nomina12"


def _d(value: Optional[str], default: str = "0") -> Decimal:
    try:
        return Decimal((value or default).strip())
    except (InvalidOperation, AttributeError):
        return Decimal(default)


def _date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def _int(value: Optional[str], default: int = 0) -> int:
    try:
        return int((value or "").strip())
    except (ValueError, AttributeError):
        return default


@dataclass(frozen=True)
class NominaHorasExtra:
    dias: int = 0
    tipo_horas: str = ""
    horas_extra: int = 0
    importe_pagado: Decimal = Decimal("0")


@dataclass(frozen=True)
class NominaPercepcion:
    tipo_percepcion: str = ""
    clave: str = ""
    concepto: str = ""
    importe_gravado: Decimal = Decimal("0")
    importe_exento: Decimal = Decimal("0")
    horas_extra: List[NominaHorasExtra] = field(default_factory=list)


@dataclass(frozen=True)
class NominaDeduccion:
    tipo_deduccion: str = ""
    clave: str = ""
    concepto: str = ""
    importe: Decimal = Decimal("0")


@dataclass(frozen=True)
class NominaOtroPago:
    tipo_otro_pago: str = ""
    clave: str = ""
    concepto: str = ""
    importe: Decimal = Decimal("0")
    subsidio_causado: Optional[Decimal] = None


@dataclass(frozen=True)
class NominaDTO:
    # Nodo raiz nomina12:Nomina
    version: str = "1.2"
    tipo_nomina: str = ""                       # O=Ordinaria, E=Extraordinaria
    fecha_pago: Optional[date] = None
    fecha_inicial_pago: Optional[date] = None
    fecha_final_pago: Optional[date] = None
    num_dias_pagados: Decimal = Decimal("0")
    total_percepciones: Decimal = Decimal("0")
    total_deducciones: Decimal = Decimal("0")
    total_otros_pagos: Decimal = Decimal("0")
    # Emisor (datos patronales)
    registro_patronal: str = ""
    rfc_patron_origen: str = ""
    # Receptor (datos laborales del empleado)
    curp: str = ""
    nss: str = ""
    fecha_inicio_rel_laboral: Optional[date] = None
    antiguedad: str = ""                        # atributo "Antigüedad" (periodo P..)
    tipo_contrato: str = ""
    sindicalizado: str = ""
    tipo_jornada: str = ""
    tipo_regimen: str = ""
    num_empleado: str = ""
    departamento: str = ""
    puesto: str = ""
    riesgo_puesto: str = ""
    periodicidad_pago: str = ""
    banco: str = ""
    cuenta_bancaria: str = ""
    salario_base_cot_apor: Decimal = Decimal("0")
    salario_diario_integrado: Decimal = Decimal("0")
    clave_ent_fed: str = ""
    # Totales de los sub-nodos
    total_sueldos: Decimal = Decimal("0")
    total_gravado_percepciones: Decimal = Decimal("0")
    total_exento_percepciones: Decimal = Decimal("0")
    total_otras_deducciones: Decimal = Decimal("0")
    total_impuestos_retenidos: Decimal = Decimal("0")
    # Detalle
    percepciones: List[NominaPercepcion] = field(default_factory=list)
    deducciones: List[NominaDeduccion] = field(default_factory=list)
    otros_pagos: List[NominaOtroPago] = field(default_factory=list)
    num_incapacidades: int = 0

    @property
    def neto(self) -> Decimal:
        """Neto segun el complemento: Percepciones - Deducciones + OtrosPagos.
        Debe coincidir con el Total del Comprobante."""
        return (self.total_percepciones - self.total_deducciones
                + self.total_otros_pagos)


def parse_nomina(complemento_node, ns) -> Optional[NominaDTO]:
    """Parsea ``nomina12:Nomina`` dentro de ``cfdi:Complemento``.

    :param complemento_node: etree node ``cfdi:Complemento`` (puede ser None).
    :param ns: dict de namespaces del parser base (incluye ``nomina12``).
    :returns: NominaDTO o None si no hay complemento de nomina.
    """
    if complemento_node is None:
        return None
    nom = complemento_node.find("nomina12:Nomina", ns)
    if nom is None:
        return None

    emisor = nom.find("nomina12:Emisor", ns)
    receptor = nom.find("nomina12:Receptor", ns)
    percep = nom.find("nomina12:Percepciones", ns)
    deduc = nom.find("nomina12:Deducciones", ns)
    otros = nom.find("nomina12:OtrosPagos", ns)
    incap = nom.find("nomina12:Incapacidades", ns)

    percepciones: List[NominaPercepcion] = []
    if percep is not None:
        for p in percep.findall("nomina12:Percepcion", ns):
            he_list = [
                NominaHorasExtra(
                    dias=_int(he.get("Dias")),
                    tipo_horas=he.get("TipoHoras", ""),
                    horas_extra=_int(he.get("HorasExtra")),
                    importe_pagado=_d(he.get("ImportePagado")),
                )
                for he in p.findall("nomina12:HorasExtra", ns)
            ]
            percepciones.append(NominaPercepcion(
                tipo_percepcion=p.get("TipoPercepcion", ""),
                clave=p.get("Clave", ""),
                concepto=p.get("Concepto", ""),
                importe_gravado=_d(p.get("ImporteGravado")),
                importe_exento=_d(p.get("ImporteExento")),
                horas_extra=he_list,
            ))

    deducciones: List[NominaDeduccion] = []
    if deduc is not None:
        for dn in deduc.findall("nomina12:Deduccion", ns):
            deducciones.append(NominaDeduccion(
                tipo_deduccion=dn.get("TipoDeduccion", ""),
                clave=dn.get("Clave", ""),
                concepto=dn.get("Concepto", ""),
                importe=_d(dn.get("Importe")),
            ))

    otros_pagos: List[NominaOtroPago] = []
    if otros is not None:
        for o in otros.findall("nomina12:OtroPago", ns):
            sub = o.find("nomina12:SubsidioAlEmpleo", ns)
            otros_pagos.append(NominaOtroPago(
                tipo_otro_pago=o.get("TipoOtroPago", ""),
                clave=o.get("Clave", ""),
                concepto=o.get("Concepto", ""),
                importe=_d(o.get("Importe")),
                subsidio_causado=_d(sub.get("SubsidioCausado")) if sub is not None else None,
            ))

    num_incap = len(incap.findall("nomina12:Incapacidad", ns)) if incap is not None else 0

    def rget(node, attr, default=""):
        return node.get(attr, default) if node is not None else default

    return NominaDTO(
        version=nom.get("Version", "1.2"),
        tipo_nomina=nom.get("TipoNomina", ""),
        fecha_pago=_date(nom.get("FechaPago")),
        fecha_inicial_pago=_date(nom.get("FechaInicialPago")),
        fecha_final_pago=_date(nom.get("FechaFinalPago")),
        num_dias_pagados=_d(nom.get("NumDiasPagados")),
        total_percepciones=_d(nom.get("TotalPercepciones")),
        total_deducciones=_d(nom.get("TotalDeducciones")),
        total_otros_pagos=_d(nom.get("TotalOtrosPagos")),
        registro_patronal=rget(emisor, "RegistroPatronal"),
        rfc_patron_origen=rget(emisor, "RfcPatronOrigen"),
        curp=rget(receptor, "Curp"),
        nss=rget(receptor, "NumSeguridadSocial"),
        fecha_inicio_rel_laboral=_date(rget(receptor, "FechaInicioRelLaboral", None)),
        antiguedad=rget(receptor, "Antigüedad"),
        tipo_contrato=rget(receptor, "TipoContrato"),
        sindicalizado=rget(receptor, "Sindicalizado"),
        tipo_jornada=rget(receptor, "TipoJornada"),
        tipo_regimen=rget(receptor, "TipoRegimen"),
        num_empleado=rget(receptor, "NumEmpleado"),
        departamento=rget(receptor, "Departamento"),
        puesto=rget(receptor, "Puesto"),
        riesgo_puesto=rget(receptor, "RiesgoPuesto"),
        periodicidad_pago=rget(receptor, "PeriodicidadPago"),
        banco=rget(receptor, "Banco"),
        cuenta_bancaria=rget(receptor, "CuentaBancaria"),
        salario_base_cot_apor=_d(rget(receptor, "SalarioBaseCotApor", "0")),
        salario_diario_integrado=_d(rget(receptor, "SalarioDiarioIntegrado", "0")),
        clave_ent_fed=rget(receptor, "ClaveEntFed"),
        total_sueldos=_d(rget(percep, "TotalSueldos", "0")),
        total_gravado_percepciones=_d(rget(percep, "TotalGravado", "0")),
        total_exento_percepciones=_d(rget(percep, "TotalExento", "0")),
        total_otras_deducciones=_d(rget(deduc, "TotalOtrasDeducciones", "0")),
        total_impuestos_retenidos=_d(rget(deduc, "TotalImpuestosRetenidos", "0")),
        percepciones=percepciones,
        deducciones=deducciones,
        otros_pagos=otros_pagos,
        num_incapacidades=num_incap,
    )
