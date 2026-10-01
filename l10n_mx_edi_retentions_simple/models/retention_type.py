# -*- coding: utf-8 -*-

from odoo import fields, models


class RetentionType(models.Model):
    """Catálogo de tipos de retención del SAT.
    Usado en el nodo CveRetenc del CFDI de Retenciones v1.0.
    Ver catálogo en: http://www.sat.gob.mx/esquemas/retencionpago/1/catRetenciones.xsd
    """
    _name = 'retention.type'
    _description = 'Retention CFDI Type'
    _rec_name = 'name'
    _order = 'code'

    code = fields.Char(
        string='Code',
        required=True,
        help='Clave de retención según catálogo del SAT (p.ej. 14 = Dividendos).',
    )
    name = fields.Char(
        string='Name',
        required=True,
        help='Descripción del tipo de retención.',
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Ya existe un tipo de retención con ese código.'),
    ]
