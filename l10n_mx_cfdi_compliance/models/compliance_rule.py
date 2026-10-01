# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


SEVERITY_SELECTION = [
    ("info", "Info"),
    ("warning", "Warning"),
    ("error", "Error / Bloqueante"),
    ("authorization", "Requiere Autorizacion"),
]

CATEGORY_SELECTION = [
    ("sat", "SAT / Estructural"),
    ("accounting", "Contable"),
    ("deductibility", "Deducibilidad"),
    ("specific", "Especifica por Giro"),
    ("antifraud", "Anti-Fraude"),
    ("coordinados", "Regimen Coordinados"),
    ("nomina", "Nomina"),
]


class ComplianceRule(models.Model):
    """Catalogo de reglas. Sincronizado desde el registry Python al
    instalar/actualizar el modulo (ver ``post_init_hook`` y datos)."""
    _name = "l10n_mx.compliance.rule"
    _description = "Catalogo de Reglas CFDI"
    _order = "category, code"

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    category = fields.Selection(CATEGORY_SELECTION, required=True, default="sat")
    technical_class = fields.Char(
        readonly=True,
        help="FQN de la clase Python que implementa la regla.",
    )
    requires_internet = fields.Boolean()
    sat_reference = fields.Char()
    default_severity = fields.Selection(
        SEVERITY_SELECTION, required=True, default="warning",
    )
    default_weight = fields.Integer(default=10)
    default_enabled = fields.Boolean(
        default=True,
        help="Si es False, la regla se asigna DESHABILITADA a los profiles "
             "(opt-in). Ej.: cruces que solo aplican si el cliente procesa el "
             "flujo en Odoo (nomina contable cuando el XML viene de descarga SAT).",
    )
    short_circuit_on_fail = fields.Boolean()
    avg_execution_ms = fields.Integer(readonly=True)
    is_active_in_registry = fields.Boolean(
        default=True,
        help="False si la regla existe en BD pero ya no en el registry Python "
             "(ej. modulo addon desinstalado).",
    )

    _code_uniq = models.Constraint(
        "UNIQUE(code)",
        "El codigo de regla debe ser unico.",
    )

    def _register_hook(self):
        """DESHABILITADO: corria _sync_from_registry() en cada arranque del worker
        pero con BD llena (~3K+ cfdi_documents) causa RecursionError en computes
        relacionados (campos related que loopean en startup antes del registry
        completo).

        El sync de reglas se mantiene via post_init_hook (al instalar) y se debe
        invocar manualmente al actualizar el modulo:

            env['l10n_mx.compliance.rule']._sync_from_registry()

        Alternativa segura para automatizarlo en upgrades: agregar la llamada al
        post_init_hook del __init__.py del modulo (corre solo en install, no en
        upgrade — limitacion conocida de Odoo)."""
        return super()._register_hook()

    @api.model
    def _sync_from_registry(self):
        """Synchronize Python registry into the DB catalog. Idempotent.
        Tambien hace auto-assign de reglas nuevas a TODOS los profiles
        existentes con defaults (enabled, severity y weight de la regla).
        """
        from ..engine.base_rule import CfdiRuleRegistry
        registry_codes = set()
        new_rule_ids = []
        for cls in CfdiRuleRegistry.all():
            registry_codes.add(cls.code)
            existing = self.search([("code", "=", cls.code)], limit=1)
            vals = {
                "code": cls.code,
                "name": cls.name or cls.code,
                "description": cls.description or "",
                "category": cls.category,
                "technical_class": f"{cls.__module__}.{cls.__name__}",
                "requires_internet": cls.requires_internet,
                "sat_reference": cls.sat_reference or "",
                "default_severity": cls.default_severity,
                "default_weight": cls.default_weight,
                "default_enabled": getattr(cls, "default_enabled", True),
                "short_circuit_on_fail": cls.short_circuit_on_fail,
                "is_active_in_registry": True,
            }
            if existing:
                # .51: escribir SOLO los campos que realmente cambiaron. El write
                # incondicional reescribia name/code/category de TODAS las reglas en
                # cada upgrade; como compliance.result.rule_name/rule_code/rule_category
                # son related store=True sobre rule_id.*, eso marcaba esos campos en
                # TODOS los resultados (Cosal: 21K+ docs, 380K+ resultados) para
                # recompute. El flush masivo final de _load_module_terms entraba en
                # re-entrancia (recompute del related dispara fetch de la fuente que
                # vuelve a flushear/recomputar el related pendiente) -> RecursionError
                # y "Failed to load registry". Escribir solo el delta = idempotencia
                # real: en un upgrade sin cambios de catalogo no se marca nada.
                changed = {}
                for k, v in vals.items():
                    cur = existing[k]
                    # tratar False (NULL) y '' como equivalentes en campos de texto
                    if isinstance(v, str) and not v and not cur:
                        continue
                    if cur != v:
                        changed[k] = v
                if changed:
                    existing.write(changed)
            else:
                rec = self.create(vals)
                new_rule_ids.append(rec.id)

        # Mark orphans (rules in DB no longer in registry) as inactive
        orphans = self.search([("code", "not in", list(registry_codes))])
        if orphans:
            orphans.write({"is_active_in_registry": False})

        # Auto-assign nuevas reglas a profiles existentes con defaults.
        # Tambien cubre reglas viejas a las que les falta config en algun profile
        # (caso comun: profiles creados antes de agregar la regla).
        assigned = self._ensure_all_rules_in_all_profiles()

        _logger.info(
            "CFDI rule catalog sync: %s reglas, %s nuevas, %s orphans, %s rule_config creados",
            len(registry_codes), len(new_rule_ids), len(orphans), assigned,
        )
        return True

    @api.model
    def _ensure_all_rules_in_all_profiles(self):
        """Garantiza que cada regla activa en registry tenga config en cada profile.
        Crea las que faltan con defaults. Idempotente. Devuelve cuantas creo."""
        Profile = self.env["l10n_mx.compliance.profile"]
        RuleCfg = self.env["l10n_mx.compliance.rule.config"]
        all_profiles = Profile.search([])
        if not all_profiles:
            return 0
        active_rules = self.search([("is_active_in_registry", "=", True)])
        if not active_rules:
            return 0

        # Pre-cargar existencia de cfgs en una sola query
        existing_pairs = set()
        existing_cfgs = RuleCfg.search([
            ("profile_id", "in", all_profiles.ids),
            ("rule_id", "in", active_rules.ids),
        ])
        for cfg in existing_cfgs:
            existing_pairs.add((cfg.profile_id.id, cfg.rule_id.id))

        # Calcular sequence base por profile (max existente + 10)
        max_seq_by_profile = {}
        for cfg in existing_cfgs:
            pid = cfg.profile_id.id
            max_seq_by_profile[pid] = max(max_seq_by_profile.get(pid, 0), cfg.sequence or 0)

        to_create = []
        for profile in all_profiles:
            for rule in active_rules:
                key = (profile.id, rule.id)
                if key in existing_pairs:
                    continue
                max_seq_by_profile[profile.id] = max_seq_by_profile.get(profile.id, 0) + 10
                to_create.append({
                    "profile_id": profile.id,
                    "rule_id": rule.id,
                    "enabled": rule.default_enabled,
                    "severity": rule.default_severity,
                    "weight": rule.default_weight,
                    "sequence": max_seq_by_profile[profile.id],
                })

        if to_create:
            RuleCfg.create(to_create)
            _logger.info("Auto-assigned %s rule_config entries to existing profiles", len(to_create))
        return len(to_create)
