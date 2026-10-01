# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)

class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    tipo_documento_id = fields.Many2one(
        'ccp.tipo.documento',
        string='Tipo de documento aduanero',
        help="Tipo de documento: 01 Pedimento, 02 Autorización temporal, etc."
    )
    pedimento = fields.Char(
        string='No. Pedimento',
        help="Número de pedimento con formato: AA  BB  CCCC  DDDDDDD"
    )
    fecha_pedimento = fields.Date(string='Fecha pedimento')
    aduana_pedimento = fields.Char(string='Aduana')
    id_doc_aduanero = fields.Text(string='Identificador documento aduanero')
    rfc_import = fields.Text(string='RFC de importador')


    @api.onchange('l10n_mx_edi_customs_number')
    def onchange_l10n_mx_edi_customs_number(self):
        if self.l10n_mx_edi_customs_number:
            self.pedimento = self.l10n_mx_edi_customs_number
            tipo_doc_pedimento = self.env['ccp.tipo.documento'].search([('clave', '=', '01')], limit=1)
            if not self.tipo_documento_id:
                self.tipo_documento_id = tipo_doc_pedimento.id

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_customs_info_for_product(self, product_id):
        """
        Devuelve TODOS los pedimentos relacionados con un producto en este picking.

        Retorna lista de dicts:
        [
            {
                'pedimento': str,
                'fecha_pedimento': date,
                'aduana_pedimento': str,
                'id_doc_aduanero': str,
                'rfc_import': str,
            }
        ]
        """

        results = []
        seen = set()

        # ─────────────────────────────────────────────
        # 1. Landed Costs (PRIORIDAD ALTA)
        # ─────────────────────────────────────────────
        landed_costs = self.env['stock.landed.cost'].search([
            ('picking_ids', 'in', self.ids),
            # ('state', '=', 'done'),
        ])

        tipo_doc_pedimento = self.env['ccp.tipo.documento'].search([('clave', '=', '01')], limit=1)

        for lc in landed_costs:

            tipo_documento_id = lc.tipo_documento_id.id if lc.tipo_documento_id else tipo_doc_pedimento.id
            pedimento = lc.pedimento if lc.pedimento else lc.l10n_mx_edi_customs_number
            fecha_pedimento = lc.fecha_pedimento
            aduana_pedimento = lc.aduana_pedimento
            id_doc_aduanero = lc.id_doc_aduanero
            rfc_import = lc.rfc_import

            results.append({
                'pedimento': pedimento,
                'fecha_pedimento': fecha_pedimento,
                'aduana_pedimento': aduana_pedimento or '',
                'id_doc_aduanero': id_doc_aduanero or '',
                'rfc_import': rfc_import or '',
                'tipo_documento_id': tipo_documento_id,
            })


        return results

    ########## Metodos que Agrega Relleno (Padding) ###########

    def add_padding_char(self, padding_number, cadena, caracter, position_add):
        while(len(cadena)<padding_number):
            if position_add == 'left':
                cadena = caracter+cadena
            else:
                cadena = cadena+caracter
        return cadena

    def _get_ubicaciones_line_ids(self, ):
        results = []
        seen = set()


        padding_id = self.add_padding_char(6,"1",'0','left')
        idorigen = 'OR'+padding_id

        xorigin = { 
                    'tipoubicacion':'Origen',
                    'contacto': self.env.company.partner_id.id,
                    'fecha': fields.Datetime.now(),
                    'idubicacion': idorigen
                }
        results.append((0,0,xorigin))

        i=1
        for picking in self:

            padding_id = self.add_padding_char(6,str(i),'0','left')
            iddestino = 'DE'+padding_id
            i+=1
            xdestiny = {
                            'tipoubicacion':'Destino',
                            'contacto': picking.partner_id.id if picking.partner_id else False,
                            'fecha': picking.date_deadline if picking.date_deadline else fields.Datetime.now(),
                            'idubicacion': iddestino
                        }

            results.append((0,0,xdestiny))


        return results

    def create_cfdi_traslado(self):
        """
        Crea un CFDI de traslado a partir del/los picking(s) seleccionados.

        Mejoras respecto a la versión original:
        - Agrega los campos de pedimento directamente en cada línea del traslado
          (tipo_documento_id, pedimento, fecha_pedimento, aduana_pedimento) pre-llenados
          desde costes en destino / facturas de compra.
        - Soporta pickings en estado 'assigned' (reservado) y 'done' (hecho).
        """
        line_vals = []
        is_product = False
        cfdi_traslado_obj = self.env['cfdi.traslado']
        origin = ''

        # Tipo de documento por defecto (01 = Pedimento)
        tipo_doc_pedimento = self.env['ccp.tipo.documento'].search([('clave', '=', '01')], limit=1)

        for data in self:
            states_ok = ('assigned', 'done')
            if data.state not in states_ok:
                continue

            if not data.move_ids_without_package:
                raise UserError(_('Debe tener productos en las líneas.'))

            for line in data.move_ids_without_package:
                qty = line.quantity if data.state == 'done' else line.product_uom_qty
                if qty <= 0:
                    continue

                # ── Buscar pedimento para este producto ──
                customs_info = self._get_customs_info_for_product(line.product_id.id)

                # ── Acumular o agregar línea ──
                aduanera_line_ids = []
                found = False
                for l in line_vals:
                    if l.get('product_id') == line.product_id.id:
                        found = True
                        l['quantity'] = l['quantity'] + qty
                        l['pesoenkg'] = l['pesoenkg'] + (line.product_id.weight * qty)
                        # Si ya tiene pedimento dejarlo; si no, agregar el encontrado
                        if customs_info:
                            if not l.get('pedimento') and customs_info.get('pedimento'):
                                l['pedimento'] = customs_info['pedimento']
                                l['fecha_pedimento'] = customs_info['fecha_pedimento']
                                l['aduana_pedimento'] = customs_info['aduana_pedimento']
                                l['tipo_documento_id'] = customs_info['tipo_documento_id']
                                l['id_doc_aduanero'] = customs_info['id_doc_aduanero']
                                l['rfc_import'] = customs_info['rfc_import']

                        break

                if not found:
                    line_vals_dict = {
                                            'product_id': line.product_id.id,
                                            'name': line.product_id.partner_ref,
                                            'price_unit': line.product_id.lst_price,
                                            'pesoenkg': line.product_id.weight * qty,
                                            'quantity': qty,                        
                                        }
                    if customs_info:
                        for custinfo in customs_info:
                            xline = {
                                        'tipo_documento_id': custinfo.get('tipo_documento_id', False),
                                        'pedimento': custinfo.get('pedimento', ''),
                                        'id_doc_aduanero': custinfo.get('id_doc_aduanero', ''),
                                        'rfc_import': custinfo.get('rfc_import', ''),
                                        'fecha_pedimento': custinfo.get('fecha_pedimento', ''),
                                        'aduana_pedimento': custinfo.get('aduana_pedimento', ''),
                                    }
                            aduanera_line_ids.append((0,0,xline))
                        if aduanera_line_ids:
                            line_vals_dict.update({
                                                      'aduanera_line_ids': aduanera_line_ids,
                                                  })
                        line_vals_dict.update({
                                                    # ── Pedimento pre-llenado ──
                                                    'tipo_documento_id': customs_info[-1].get('tipo_documento_id',False),
                                                    'pedimento': customs_info[-1].get('pedimento', ''),
                                                    'fecha_pedimento': customs_info[-1].get('fecha_pedimento'),
                                                    'aduana_pedimento': customs_info[-1].get('aduana_pedimento', ''),
                                                    'id_doc_aduanero' : customs_info[-1].get('id_doc_aduanero',''),
                                                    'rfc_import' : customs_info[-1].get('rfc_import',''),
                                              })
                    line_vals.append(line_vals_dict)
                    

            origin += data.name + ' '
        if not line_vals:
            raise UserError(_('Solo se pueden crear un CFDI de traslado si el documento está reservado o hecho.'))

        val = {
            'partner_id': self.company_id.partner_id.id,
            'source_document': origin.strip(),
            'invoice_date': datetime.today(),
            'currency_id': self.company_id.currency_id.id,
            'factura_line_ids': [(0, 0, i) for i in line_vals],
            'company_id': self.company_id.id,
            'journal_id': self.env['account.journal'].search(
                [('type', '=', 'sale'), ('company_id', '=', self.company_id.id)], limit=1
            ).id,
        }

        ubicaciones_line_ids = self._get_ubicaciones_line_ids()
        val['ubicaciones_line_ids'] = ubicaciones_line_ids

        cfdi_id = cfdi_traslado_obj.create(val)

        # Abrir el traslado recién creado
        return {
            'type': 'ir.actions.act_window',
            'name': _('CFDI Traslado'),
            'res_model': 'cfdi.traslado',
            'res_id': cfdi_id.id,
            'view_mode': 'form',
            'target': 'current',
        }