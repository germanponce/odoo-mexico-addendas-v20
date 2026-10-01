# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
from odoo import models, fields, api # type: ignore

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_mx_xml_download_api_key = fields.Char(
        related='company_id.l10n_mx_xml_download_api_key', 
        string='API Key', 
        readonly=False,
        )
    l10n_mx_xml_download_automatic_contact_creation = fields.Boolean(
        related='company_id.l10n_mx_xml_download_automatic_contact_creation',
        string='Creacion automatica de contactos',
        readonly=False,
        )
    l10n_mx_xml_download_ieps_in_base = fields.Boolean(
        related='company_id.l10n_mx_xml_download_ieps_in_base',
        string='IEPS en la base',
        readonly=False,
    )