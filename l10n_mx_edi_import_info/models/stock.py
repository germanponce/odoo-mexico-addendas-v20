# -*- encoding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit ='product.template'

    import_info_required = fields.Boolean('Pedimento Obligatorio', help='Indica que el pedimento sera obligatorio en las recepciones.', )

class stock_quant_package(models.Model):
    _inherit = "stock.quant.package"

    import_id = fields.Many2one('import.info', string='Pedimento Aduanal', required=False,
            help="Información de Importación (Pedimento aduanal), necesaria para Facturación Electrónica.")
    

class stock_production_lot(models.Model):
    _inherit = "stock.lot"

    import_id = fields.Many2one('import.info', string='Pedimento Aduanal', required=False,
            help="Información de Importación (Pedimento aduanal), necesaria para Facturación Electrónica.")

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    import_id = fields.Many2one('import.info', string='Pedimento Aduanal', required=False,
            help="Información de Importación (Pedimento aduanal), necesaria para Facturación Electrónica.")

    import_info_required = fields.Boolean('Pedimento Obligatorio', help='Indica que el pedimento sera obligatorio en las recepciones.', )

    # @api.onchange('import_id','lot_id')
    # def onchange_import_id(self):
    #     if self.lot_id and self.import_id:


    @api.model
    def create(self, vals):
        res = super(StockMoveLine, self).create(vals)
        if res.product_id.import_info_required and res.move_id:
            if res.move_id.picking_id and res.move_id.picking_id.picking_type_code == 'incoming':
                res.import_info_required = True
        return res

    def write(self, vals):
        updat_info_lot_serie = False
        if 'import_id' in vals and vals['import_id']:
            updat_info_lot_serie = True
        res = super(StockMoveLine, self).write(vals)
        for rec in self:
            if rec.lot_id and rec.import_id:
                rec.lot_id.import_id = rec.import_id.id
        return res


class StockMove(models.Model):
    _inherit = "stock.move"
    
    facturado = fields.Boolean(string='Facturado')
    
    import_id = fields.Many2one('import.info', string='Pedimento Aduanal', required=False,
            help="Información de Importación (Pedimento aduanal), necesaria para Facturación Electrónica.")
    
    import_info_required = fields.Boolean('Pedimento Obligatorio', help='Indica que el pedimento sera obligatorio en las recepciones.', )

    @api.onchange('import_id')
    def onchange_import_id(self):
        if self.move_line_nosuggest_ids and self.import_id:
            for line in self.move_line_nosuggest_ids:
                line.import_id = self.import_id.id

    @api.model
    def create(self, vals):
        res = super(StockMove, self).create(vals)
        if res.product_id.import_info_required:
            if res.picking_id and res.picking_id.picking_type_code == 'incoming':
                res.import_info_required = True
        return res


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit ='stock.picking'


    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        for rec in self:
            if rec.picking_type_code == 'incoming':
                for line in rec.move_line_ids:
                    import_id = line.import_id.id if line.import_id else False
                    if line.product_id.tracking != 'none':
                        if not import_id:
                            if line.move_id and line.move_id.import_id:
                                import_id = line.move_id.import_id.id
                        if rec.group_id and rec.group_id.sale_id:
                            _logger.info("\n############# Es una devolución >>>>>>>>>>>> ")
                        else:
                            if line.product_id.import_info_required and not import_id:
                                raise UserError("El producto %s requiere un pedimento de entrada de forma obligatoria." % line.product_id.name)
                            if line.lot_id and import_id:
                                line.lot_id.import_id = import_id

        return res
