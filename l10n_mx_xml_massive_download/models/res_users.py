# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    # =========================================================================
    # PERMISOS DE VISIBILIDAD POR TIPO DE CFDI
    # Permite restringir, por usuario, qué tipos de CFDI puede ver al consultar
    # los XMLs descargados del SAT. Útil para contadores externos que NO deben
    # ver nóminas (información sensible: sueldos, percepciones, deducciones).
    # =========================================================================
    can_see_cfdi_ingreso = fields.Boolean(
        string='Ver Facturas de Ingreso (I)',
        default=True,
        help='Permite ver XMLs de tipo Ingreso (Facturas de cliente)',
    )
    can_see_cfdi_egreso = fields.Boolean(
        string='Ver Notas de Crédito (E)',
        default=True,
        help='Permite ver XMLs de tipo Egreso (Notas de crédito)',
    )
    can_see_cfdi_pago = fields.Boolean(
        string='Ver Complementos de Pago (P)',
        default=True,
        help='Permite ver XMLs de tipo Pago (Complementos de pago)',
    )
    can_see_cfdi_nomina = fields.Boolean(
        string='Ver Nóminas (N)',
        default=False,
        help='Permite ver XMLs de tipo Nómina. Información sensible: sueldos, '
             'percepciones y deducciones. Desactivado por defecto.',
    )
    can_see_cfdi_traslado = fields.Boolean(
        string='Ver Traslados / Carta Porte (T)',
        default=True,
        help='Permite ver XMLs de tipo Traslado (Guías de traslado / Carta Porte)',
    )

    has_xml_sat_access = fields.Boolean(
        string='Tiene acceso XML SAT',
        compute='_compute_has_xml_sat_access',
        help='True si el usuario pertenece al grupo "Acceso a Descarga XML del SAT".',
    )

    @api.depends('group_ids')
    def _compute_has_xml_sat_access(self):
        xml_sat_group = self.env.ref(
            'l10n_mx_xml_massive_download.group_l10n_mx_xml_sat_user',
            raise_if_not_found=False,
        )
        for user in self:
            user.has_xml_sat_access = bool(xml_sat_group) and (xml_sat_group in user.group_ids)

    def get_allowed_cfdi_types(self):
        """Lista de tipos de CFDI permitidos para self (asumido un solo usuario)."""
        self.ensure_one()
        allowed = []
        if self.can_see_cfdi_ingreso:
            allowed.append('I')
        if self.can_see_cfdi_egreso:
            allowed.append('E')
        if self.can_see_cfdi_pago:
            allowed.append('P')
        if self.can_see_cfdi_nomina:
            allowed.append('N')
        if self.can_see_cfdi_traslado:
            allowed.append('T')
        return allowed
