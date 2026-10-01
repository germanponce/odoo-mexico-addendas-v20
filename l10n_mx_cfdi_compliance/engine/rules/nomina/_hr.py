# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
"""Helpers de matching XML-Nomina <-> modelos de RRHH de Odoo (Etapa 2, B-E).

Dependencia SOFT: el modulo NO agrega ``hr`` a ``depends``. Las reglas B-E:
- se AUTO-OMITEN si los modelos hr.* no estan instalados (``env.get`` -> None);
- son OPT-IN (``default_enabled = False``): solo aplican a clientes que calculan
  la nomina en Odoo. En clientes que solo descargan los XML del SAT, los cruces
  no aplican y no deben generar ruido (las internas A si corren).

El empleado se casa por AUTODETECCION de campos (RFC/CURP/NSS/NumEmpleado) para
tolerar distintos modulos de nomina MX, con override por profile via el param
``employee_match_field``. Los resultados se cachean en ``ctx.scratchpad`` para
no repetir busquedas entre reglas del mismo run.
"""
from __future__ import annotations

from decimal import Decimal

from ._base import BaseNominaRule

# Campos candidatos por dato, en orden de preferencia. Se usa el primero que
# exista en el modelo (``_fields``). Cubre el hr estandar + nombres comunes MX.
_RFC_FIELDS = ("l10n_mx_rfc", "rfc", "identification_id")
_CURP_FIELDS = ("l10n_mx_curp", "curp", "identification_id")
_NSS_FIELDS = ("l10n_mx_nss", "nss", "imss", "ssnid")
_NUM_FIELDS = ("registration_number", "barcode", "employee_number", "numero_empleado")
_SBC_FIELDS = ("l10n_mx_sbc", "sbc", "salario_base_cotizacion", "salario_base_cot")
_SDI_FIELDS = ("l10n_mx_sdi", "sdi", "salario_diario_integrado")
_NET_FIELDS = ("net_wage", "net", "l10n_mx_net", "total_neto")


def hr(ctx, model):
    """``env.get`` del modelo hr.* (None si el modulo no esta instalado)."""
    return ctx.env.get(model)


def _norm(value):
    return (value or "").strip().upper()


def _first_field(model, candidates):
    """Primer nombre de campo de ``candidates`` que exista en el modelo."""
    fields = model._fields
    for f in candidates:
        if f in fields:
            return f
    return None


def field_value(record, candidates):
    """(nombre_campo, valor) del primer campo existente con valor; si no, (None, None)."""
    if not record:
        return (None, None)
    for f in candidates:
        if f in record._fields:
            return (f, record[f])
    return (None, None)


def profile_param(ctx, key, default=None):
    """Busca un parametro ``key`` en cualquier rule_config del profile."""
    for c in ctx.profile.rule_config_ids:
        if c.params and key in c.params:
            return c.params[key]
    return default


# ───────────────────────────── matching ─────────────────────────────
def find_employee(ctx):
    """hr.employee que casa con el receptor del CFDI de nomina (o recordset vacio).

    Cache en ``ctx.scratchpad['nom_employee']``. Devuelve None si hr no instalado.
    """
    cache = ctx.scratchpad
    if "nom_employee" in cache:
        return cache["nom_employee"]

    Emp = hr(ctx, "hr.employee")
    result = Emp  # recordset vacio si instalado; None si no
    if Emp is not None:
        Emp = Emp.sudo().with_context(active_test=False)
        result = Emp.browse()  # vacio
        nomina = ctx.cfdi.nomina
        rfc = _norm(ctx.cfdi_record.rfc_receptor)
        curp = _norm(getattr(nomina, "curp", ""))
        nss = (getattr(nomina, "nss", "") or "").strip()
        num = (getattr(nomina, "num_empleado", "") or "").strip()

        attempts = []
        forced = profile_param(ctx, "employee_match_field")
        if forced and forced in Emp._fields and rfc:
            attempts.append((forced, rfc))
        for value, cands in ((rfc, _RFC_FIELDS), (curp, _CURP_FIELDS),
                             (nss, _NSS_FIELDS), (num, _NUM_FIELDS)):
            if not value:
                continue
            f = _first_field(Emp, cands)
            if f:
                attempts.append((f, value))

        seen = set()
        for fname, value in attempts:
            if (fname, value) in seen:
                continue
            seen.add((fname, value))
            recs = Emp.search([(fname, "=ilike", value)], limit=2)
            if len(recs) == 1:
                result = recs
                break
            if recs and not result:
                result = recs[:1]  # ambiguo: tomar el primero, no bloquear
    cache["nom_employee"] = result
    return result


def find_contract(ctx, emp):
    """Contrato del empleado que cubre el periodo del XML (o recordset vacio/None)."""
    cache = ctx.scratchpad
    if "nom_contract" in cache:
        return cache["nom_contract"]
    Contract = hr(ctx, "hr.contract")
    result = Contract
    if Contract is not None:
        Contract = Contract.sudo()
        result = Contract.browse()
        if emp:
            nomina = ctx.cfdi.nomina
            ini, fin = nomina.fecha_inicial_pago, nomina.fecha_final_pago
            # Dominio: empleado + (date_start <= fin Y (date_end vacio O >= ini)).
            # Odoo arma el AND implicito entre leafs; el OR se declara explicito.
            dom = [("employee_id", "=", emp.id)]
            if ini and fin:
                dom += [("date_start", "<=", fin),
                        "|", ("date_end", "=", False), ("date_end", ">=", ini)]
            recs = Contract.search(dom + [("state", "in", ("open", "close"))],
                                   order="date_start desc", limit=1)
            if not recs:
                recs = Contract.search(dom, order="date_start desc", limit=1)
            if not recs and "contract_id" in emp._fields and emp.contract_id:
                recs = emp.contract_id
            result = recs or Contract.browse()
    cache["nom_contract"] = result
    return result


def find_payslip(ctx, emp):
    """hr.payslip del empleado cuyo periodo solapa el del XML (o recordset vacio/None)."""
    cache = ctx.scratchpad
    if "nom_payslip" in cache:
        return cache["nom_payslip"]
    Slip = hr(ctx, "hr.payslip")
    result = Slip
    if Slip is not None:
        Slip = Slip.sudo()
        result = Slip.browse()
        if emp:
            nomina = ctx.cfdi.nomina
            ini, fin = nomina.fecha_inicial_pago, nomina.fecha_final_pago
            dom = [("employee_id", "=", emp.id)]
            if ini and fin:
                dom += [("date_from", "<=", fin), ("date_to", ">=", ini)]
            recs = Slip.search(dom + [("state", "in", ("done", "paid"))],
                               order="date_to desc", limit=1)
            if not recs:
                recs = Slip.search(dom, order="date_to desc", limit=1)
            result = recs or Slip.browse()
    cache["nom_payslip"] = result
    return result


def find_run(payslip):
    """Lote (hr.payslip.run) del recibo, si el campo existe."""
    if payslip and "payslip_run_id" in payslip._fields:
        return payslip.payslip_run_id
    return None


def payslip_net(payslip):
    """Neto del recibo: campo directo (net_wage/net/...) o suma de lineas NET."""
    if not payslip:
        return None
    f, val = field_value(payslip, _NET_FIELDS)
    if f is not None and val:
        return Decimal(str(val))
    # Fallback: linea(s) con code/category NET.
    if "line_ids" in payslip._fields:
        total = Decimal("0")
        found = False
        for ln in payslip.line_ids:
            code = (getattr(ln, "code", "") or "").upper()
            if code in ("NET", "NETO"):
                total += Decimal(str(ln.total or 0))
                found = True
        if found:
            return total
    return None


# ───────────────────────────── bases ─────────────────────────────
class _NominaHrEmpleado(BaseNominaRule):
    """Base B/C/D/E: corre si hay nomina + hr.employee instalado (haya o no match).

    OPT-IN: solo clientes que calculan nomina en Odoo. Sin hr -> se auto-omite.
    """
    default_enabled = False

    def applies(self, ctx) -> bool:
        return super().applies(ctx) and hr(ctx, "hr.employee") is not None


class _NominaConEmpleado(_NominaHrEmpleado):
    """Ademas exige que el empleado se haya encontrado (no doble-marca su ausencia)."""

    def applies(self, ctx) -> bool:
        return super().applies(ctx) and bool(find_employee(ctx))


class _NominaConContrato(_NominaConEmpleado):
    """Ademas exige contrato encontrado."""

    def applies(self, ctx) -> bool:
        return super().applies(ctx) and bool(find_contract(ctx, find_employee(ctx)))


class _NominaConRecibo(_NominaConEmpleado):
    """Ademas exige recibo (hr.payslip) encontrado."""

    def applies(self, ctx) -> bool:
        return super().applies(ctx) and bool(find_payslip(ctx, find_employee(ctx)))
