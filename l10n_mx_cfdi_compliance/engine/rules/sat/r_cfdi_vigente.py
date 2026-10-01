# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
from ...base_rule import BaseCfdiRule, RuleResult, cfdi_rule, CATEGORY_SAT, SEVERITY_ERROR
from ...sat_clients import cfdi_status_client


@cfdi_rule
class RuleCfdiVigente(BaseCfdiRule):
    code = "SAT_030_CFDI_VIGENTE"
    name = "CFDI vigente segun SAT"
    description = ("Verifica que el CFDI no este cancelado. Primero busca cache local "
                   "en account.edi.downloaded.xml.sat (poblado por el cron diario "
                   "'Actualizacion automatica de estado sat'). Si no hay cache local, "
                   "consulta el web service del SAT.")
    category = CATEGORY_SAT
    requires_internet = True
    default_severity = SEVERITY_ERROR
    sat_reference = "Servicio Consulta CFDI SAT"

    def execute(self, ctx):
        cfdi = ctx.cfdi
        # OPTIMIZACION: si ya tenemos el sat_state determinado por el cron
        # 'cron_fetch_sat_status' (en l10n_mx_xml_massive_download), usar ese valor
        # cacheado en lugar de consultar SOAP. Evita 100-300ms de latencia por XML.
        # Usamos SQL directo para NO disparar computes/searches que puedan recursionar
        # durante la pipeline.
        cached_state = self._get_cached_sat_state_sql(ctx, cfdi.uuid)
        if cached_state:
            return self._result_from_state(cached_state, source='cache_xml_sat')

        # Fallback: consultar SOAP al SAT
        result = cfdi_status_client.consulta(
            cfdi.uuid, cfdi.rfc_emisor, cfdi.rfc_receptor, str(cfdi.total),
        )
        if result.get("error"):
            return RuleResult(
                True,  # degrade gracefully
                f"No se pudo consultar SAT (offline?): {result['error']}",
                details=result, score_impact=0,
            )
        estado = (result.get("estado") or "").lower()
        return self._result_from_state(estado, source='sat_soap', details=result)

    def _get_cached_sat_state_sql(self, ctx, uuid):
        """Lookup directo via SQL para evitar disparar ORM computes/searches
        que pueden causar recursion infinita dentro de la pipeline.

        Acepta estados definitivos del cron 'cron_fetch_sat_status':
        - 'vigente': el SAT confirmo que esta vigente
        - 'cancelado': el SAT confirmo que esta cancelado
        - 'no encontrado': el SAT respondio que no existe (info valida tambien)

        Solo cae al SOAP cuando el estado es vacio o 'sin definir' (cron no
        determino nada todavia).
        """
        if not uuid or not ctx.env:
            return None
        try:
            ctx.env.cr.execute(
                "SELECT sat_state FROM account_edi_downloaded_xml_sat WHERE name = %s LIMIT 1",
                (uuid,),
            )
            row = ctx.env.cr.fetchone()
        except Exception:
            return None
        if not row or not row[0]:
            return None
        state = (row[0] or '').lower()
        # Aceptar como cache cualquier estado determinado (vigente/cancelado/no encontrado).
        # 'Sin Definir' significa que el cron no pudo o no llego — caer a SOAP.
        if state in ('vigente', 'cancelado', 'no encontrado'):
            return state
        return None

    def _result_from_state(self, estado, source='unknown', details=None):
        """Construye el RuleResult desde un estado string normalizado."""
        details = details or {}
        details.setdefault('source', source)
        details.setdefault('estado', estado)
        if estado == "cancelado":
            return RuleResult(
                False, f"CFDI CANCELADO segun SAT ({source})",
                details=details, score_impact=-100,
            )
        if estado == "no encontrado":
            return RuleResult(
                False, f"CFDI NO ENCONTRADO en SAT ({source})",
                details=details, score_impact=-20,
            )
        if estado != "vigente":
            return RuleResult(
                False, f"CFDI con estado SAT: {estado or 'desconocido'} ({source})",
                details=details, score_impact=-30,
            )
        return RuleResult(True, f"CFDI vigente ({source})", details=details, score_impact=10)
