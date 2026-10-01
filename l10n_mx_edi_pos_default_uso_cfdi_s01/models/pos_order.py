# -*- encoding: utf-8 -*-
##################################################################################################
#
#   Author: Experts SAS (www.exdoo.mx)
#   Coded by: Giovany Villarreal (giovany.villarreal@exdoo.mx)
#   License: https://blog.exdoo.mx/licencia-de-uso-de-software/
#
##################################################################################################
from odoo import api, fields, models, _, tools, SUPERUSER_ID
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"
    
    pos_simple_question = fields.Selection(
        selection=[
            ('Sin Respuesta', 'Sin Respuesta'),
            ('Por redes sociales', 'Por redes sociales'),
            ('Por recomendación', 'Por recomendación'),
            ('Por Radio', 'Por Radio'),
            ('Iba pasando y entré', 'Iba pasando y entré'),
            ('Soy cliente frecuente', 'Soy cliente frecuente'),
        ],
        string="¿Cómo te enteraste de nosotros?",)

    # Este metodo establece dentro de back-end los valores para los campos del JSON del pos order
    @api.model
    def _order_fields(self, ui_order):
        res = super(PosOrder,self)._order_fields(ui_order)
        res['pos_simple_question'] = ui_order.get('pos_simple_question') if ui_order.get('pos_simple_question',False) else False
        return res

