# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
import hashlib
import re

from odoo import api, fields, models  # type: ignore

_SHA512_HEX_RE = re.compile(r'^[0-9a-f]{128}$')

class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_mx_xml_download_api_key = fields.Char(string='API Key')
    l10n_mx_xml_download_automatic_contact_creation = fields.Boolean(string='Creación automática de contactos', default=False)
    l10n_mx_xml_download_ieps_in_base = fields.Boolean(
        string='IEPS forma parte de la base (gasto)',
        default=False,
        help='Si está activo, al crear la factura proveedor desde el XML los IEPS '
             'TRASLADADOS se SUMAN al precio unitario de cada línea (forman parte del '
             'gasto deducible) y se eliminan del listado de impuestos de la línea. El IVA '
             'permanece igual al del XML. Util cuando la empresa NO es causante de IEPS '
             'pero compra bienes con IEPS (gasolina, bebidas, tabaco), ya que el IEPS no '
             'es acreditable y debe formar parte del costo. El IEPS Retenido no se toca.'
    )

    @api.model
    def _l10n_mx_hash_api_key(self, vals):
        """Normaliza la API key del servicio xmlsat: si viene CRUDA la hashea a
        SHA-512; si ya es un hash SHA-512 (128 hex) la deja igual (en minusculas).
        Evita el doble-hash que rompe con 402 y permite que el usuario pegue la
        llave cruda en la UI sin romper el pipeline (que espera el hash)."""
        key = vals.get('l10n_mx_xml_download_api_key')
        if not key:
            return vals
        key = key.strip()
        vals = dict(vals)
        if _SHA512_HEX_RE.match(key.lower()):
            vals['l10n_mx_xml_download_api_key'] = key.lower()
        else:
            vals['l10n_mx_xml_download_api_key'] = hashlib.sha512(
                key.encode('utf-8')).hexdigest()
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._l10n_mx_hash_api_key(v) for v in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if 'l10n_mx_xml_download_api_key' in vals:
            vals = self._l10n_mx_hash_api_key(vals)
        return super().write(vals)

    def action_open_upload_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Upload Fiel',
            'res_model': 'upload.fiel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_id': self.id,
            },
        }
