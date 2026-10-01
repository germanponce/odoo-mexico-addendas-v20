# -*- coding: utf-8 -*-

import re
from odoo import models, fields, api, _
from odoo.tools.misc import ustr
from odoo.exceptions import ValidationError
from odoo.osv import osv, expression

##### Materiales Peligrosos #####
from . import materiales_peligrosos ## Clase con Codigos MP
# instance_class_hazardous = materiales_peligrosos.HazardousFCodes()
# hazardous_code = instance_class_hazardous.is_hazardous_material(str(code_result))
#################################


###### Materiales Peligrosos ######


class WaybillMaterialesPeligrosos(models.Model):
    _name = "waybill.materiales.peligrosos"
    _description = "Carta Porte - Catalogo de Materiales Peligrosos"
    _rec_name = 'code' 

    code      = fields.Char("Clave material", required=True, size=128 )
    name      = fields.Char('Descripción', size=128, required=True )
    class_div      = fields.Char('Clase o div.  ', size=128, )
    danger_sec      = fields.Char('Peligro  secundario', size=128, )
    group_env_onu = fields.Char('Grupo de emb/env ONU', size=128)
    group_env_onu_disp_esp = fields.Char('Disp. espec.', size=128)

    qty_limit = fields.Char('Cantidades limitadas', size=128)
    qty_except = fields.Char('Cantidades exceptuadas', size=128)

    ### Embalajes/envases y RIG ####
    int_emb_env = fields.Char('Inst. de  emb/env', size=128, help="Embalajes/envases y RIG")
    int_emb_env_disp_esp = fields.Char('Disp. espec.', size=128, help="Embalajes/envases y RIG")

    ### Cisternas portátiles y contenedores para graneles ####
    int_trasp = fields.Char('Inst. de transp.', size=128, help="Cisternas portátiles y contenedores para graneles")
    int_trasp_disp_esp = fields.Char('Disp. espec.', size=128, help="Cisternas portátiles y contenedores para graneles")

    # patente_id      = fields.Many2one('sat.patente', string="Patente Aduanal", required=True )
    start_date = fields.Date(string="Inicio de Vigencia", required=True, default="2021-06-01")
    end_date    = fields.Date(string="Fin de Vigencia", required=False)

    _sql_constraints = [
        ('code_unique', 'CHECK(1=1)',
         'El Código debe ser único')]


    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
            return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

        return super(WaybillMaterialesPeligrosos, self)._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)


    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for rec in self:
            if rec.name and rec.code:
                name = '[ '+rec.code+' ]' + ' ' + rec.name
                result.append((rec.id, name))
        return result

###### Tipo de Embalaje ######

class WaybillTipoEmbalaje(models.Model):
    _name = "waybill.tipo.embalaje"
    _description = "Carta Porte -  Tipos de Embalajes"
    _rec_name = 'code' 

    code      = fields.Char("Clave de designación", required=True, size=128 )
    name            = fields.Char('Descripción', size=128, required=True )
    # patente_id      = fields.Many2one('sat.patente', string="Patente Aduanal", required=True )
    start_date = fields.Date(string="Inicio de Vigencia", required=True, default="2021-06-01")
    end_date    = fields.Date(string="Fin de Vigencia", required=False)
    

    _sql_constraints = [
        ('code_unique', 'unique(code)',
         'El Código debe ser único')]
    
    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for rec in self:
            if rec.name and rec.code:
                name = '[ '+rec.code+' ]' + ' ' + rec.name
                result.append((rec.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
            return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

        return super(WaybillTipoEmbalaje, self)._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)


class AddendaProduct(models.Model):
    _inherit = 'product.template'

    @api.depends('hazardous_material','unspsc_code_id')
    def _get_info_sat_hazardous_info(self):
        for rec in self:
            hazardous_code = False
            if rec.unspsc_code_id.code:
                instance_class_hazardous = materiales_peligrosos.HazardousFCodes()
                hazardous_code = instance_class_hazardous.is_hazardous_material(str(rec.unspsc_code_id.code))
            if hazardous_code:
                rec.key_hazardous_material_sat = hazardous_code
            else:
                rec.key_hazardous_material_sat = ''

    key_hazardous_material_sat = fields.Char('Consideración SAT Clave Peligrosa', compute="_get_info_sat_hazardous_info", 
                                             help="1 Peligroso\n0 No Peligroso\n0,1 Puede ser Peligroso o No")

    hazardous_material = fields.Selection([('Sí','Sí'),('No','No')], string="Material Peligroso" )

    hazardous_key_product_id = fields.Many2one('waybill.materiales.peligrosos', 'Clave Material Peligroso')

    tipo_embalaje_id  =  fields.Many2one('waybill.tipo.embalaje', 'Tipo de Embalaje')

    @api.depends('product_variant_ids.hazardous_material')
    def _compute_hazardous_material(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.hazardous_material = template.product_variant_ids.hazardous_material
        for template in (self - unique_variants):
            template.hazardous_material = False

    def _set_hazardous_material(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.hazardous_material = self.hazardous_material


class Vehicle(models.Model):
    _inherit = 'l10n_mx_edi.vehicle'

    ambiental_transport_insurerance = fields.Char('Aseguradora Medio Ambiente')
    ambiental_transport_insurance_policy = fields.Char('No. Poliza Medio Ambiente')


class StockPicking(models.Model):
    _inherit ='stock.picking'

    l10n_mx_edi_distance = fields.Float('Distancia a Destino (KM)', copy=False, digits=(14,2))

    def _have_hazardous_code(self):
        have_hazardous_code = False
        moves = self.move_lines.filtered(lambda ml: ml.quantity_done > 0)
        for move in moves:
            if move.product_id.hazardous_material == 'Sí':
                return True
        return have_hazardous_code