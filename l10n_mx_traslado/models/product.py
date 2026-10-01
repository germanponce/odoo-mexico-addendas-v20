# -*- coding: utf-8 -*-
from odoo import fields, models, api,_

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    clave_stcc = fields.Char(string='Clave STCC')
    dimensiones = fields.Char(string='Dimensiones XX/XX/XXcm')
    materialpeligroso = fields.Selection(
        selection=[('Sí', 'Si'),
                   ('No', 'No'),],
        string='Material peligroso',
    )
    embalaje = fields.Many2one('cve.tipo.embalaje', string='Embalaje')
    desc_embalaje = fields.Char(string='Descripción de embalaje')
    clavematpeligroso = fields.Many2one('cve.material.peligroso',string='Clave material peligroso')

    SectorCofepris = fields.Many2one('ccp.sector.cofepris',string='Regimen aduanero')
    IngredienteActivo = fields.Char(string='Nombre Ingrediente Activo')
    NomQuimico = fields.Char(string='Nombre Quimico')
    DenominacionGenerica  = fields.Char(string='Denominacion Generica')
    DenominacionDistintiva  = fields.Char(string='Denominacion Distintiva')
    Fabricante  = fields.Char(string='Fabricante')
    FechaCaducidad = fields.Date(string='Fecha Caducidad')
    LoteMedicamento  = fields.Char(string='Lote Medicamento')
    FormaFarmaceutica = fields.Many2one('ccp.forma.farma',string='Forma Farmaceutica')
    CondicionesEsp = fields.Many2one('ccp.condiciones.esp',string='Condiciones Especiales transp.')
    RegistroSanitario  = fields.Char(string='Registro Sanitario Folio Autorización')
    PermisoImportacion  = fields.Char(string='Permiso Importacion')
    FolioImpoVUCEM  = fields.Char(string='Folio Impo VUCEM')
    NumCAS  = fields.Char(string='Numero CAS')
    RazonSocialEmpImp  = fields.Char(string='Razon Social Emp Imp')
    NumRegSan  = fields.Char(string='Num Reg San plag COFEPRIS')
    DatosFabricante  = fields.Char(string='Datos Fabricante')
    DatosFormulador  = fields.Char(string='Datos Formulador')
    DatosMaquilador  = fields.Char(string='Datos Maquilador')
    UsoAutorizado  = fields.Char(string='Uso Autorizado')
    TipoMateria  = fields.Many2one('ccp.tipo.materia',string='Tipo Materia')
    DescripcionMateria  = fields.Char(string='Descripción Materia')
