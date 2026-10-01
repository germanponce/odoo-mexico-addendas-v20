# -*- coding: utf-8 -*-
# Part of l10n_mx_edi_retentions.
#
# V19 + upgrade a esquema v2.0:
#   - Firmado SHA256 via certificate._sign()
#   - Atributos v2.0: RfcE, RfcR, DomicilioFiscalR, NacionalidadR, Ejercicio
#   - Dos templates QWeb: nacionales y extranjeros
#   - One2many l10n_mx_edi_retention_impuesto_ids para ImpRetenidos
#   - Checkbox is_foreign calculado por partner.country_id

import base64
import logging
from datetime import datetime

from pytz import timezone

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MX_TZ = 'America/Mexico_City'

# Catálogo de meses
MESES_SELECTION = [
    ('01', '01 - Enero'), ('02', '02 - Febrero'), ('03', '03 - Marzo'),
    ('04', '04 - Abril'), ('05', '05 - Mayo'), ('06', '06 - Junio'),
    ('07', '07 - Julio'), ('08', '08 - Agosto'), ('09', '09 - Septiembre'),
    ('10', '10 - Octubre'), ('11', '11 - Noviembre'), ('12', '12 - Diciembre'),
]


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # =========================================================================
    # Campos base del CFDI de Retenciones
    # =========================================================================

    require_retention_cfdi = fields.Boolean(
        string='Generar CFDI de Retención',
        copy=False,
        help='Al activar, genera un CFDI de Retenciones e Información de Pagos v2.0.',
    )
    retention_type_id = fields.Many2one(
        comodel_name='retention.type',
        string='Tipo de Retención (CveRetenc)',
        help='Clave del tipo de retención según catálogo SAT.',
    )
    l10n_mx_edi_ret_ext_tipo_contribuyente_id = fields.Many2one("retention.type.taxpayer", string='Tipo Contribuyente Sujeto a Retencion')

    # ── Receptor: nacional vs extranjero ─────────────────────────────────────

    l10n_mx_edi_retention_is_foreign = fields.Boolean(
        string='Receptor Extranjero',
        compute='_compute_retention_is_foreign',
        store=True,
        readonly=False,
        help='Marcado automáticamente si el país del partner no es México. '
             'Determina qué template XML se usará (Extranjero vs Nacional).',
    )

    # ── Período fiscal ────────────────────────────────────────────────────────

    l10n_mx_edi_retention_mes_ini = fields.Selection(
        selection=MESES_SELECTION,
        string='Mes Inicio',
        default='01',
        help='Mes de inicio del período fiscal de la retención (MesIni).',
    )
    l10n_mx_edi_retention_mes_fin = fields.Selection(
        selection=MESES_SELECTION,
        string='Mes Fin',
        default='12',
        help='Mes de fin del período fiscal de la retención (MesFin).',
    )
    l10n_mx_edi_retention_ejercicio = fields.Integer(
        string='Ejercicio',
        default=lambda self: datetime.now().year,
        help='Año del ejercicio fiscal (Ejercicio).',
    )

    # ── Totales del nodo Totales ──────────────────────────────────────────────

    l10n_mx_edi_retention_monto_tot_operacion = fields.Monetary(
        string='Monto Total de Operaciones',
        help='Total de las operaciones realizadas (MontoTotOperacion).',
    )
    l10n_mx_edi_retention_monto_tot_grav = fields.Monetary(
        string='Monto Total Gravado',
        help='Total del monto gravado de las operaciones (MontoTotGrav).',
    )
    l10n_mx_edi_retention_monto_tot_exent = fields.Monetary(
        string='Monto Total Exento',
        help='Total del monto exento de las operaciones (MontoTotExent).',
    )
    l10n_mx_edi_retention_monto_tot_ret = fields.Monetary(
        string='Monto Total Retenido',
        compute='_compute_monto_tot_ret',
        store=True,
        help='Suma total de los montos retenidos (MontoTotRet). '
             'Se calcula automáticamente de las líneas de impuestos.',
    )

    # ── Líneas de impuestos retenidos (ImpRetenidos) ──────────────────────────

    l10n_mx_edi_retention_impuesto_ids = fields.One2many(
        comodel_name='l10n_mx_edi.retention.impuesto',
        inverse_name='payment_id',
        string='Impuestos Retenidos',
        help='Desglose de impuestos retenidos (ImpRetenidos) del CFDI.',
    )


    # =========================================================================
    # Selector y campos de Complementos CFDI de Retenciones
    # =========================================================================

    COMPLEMENT_SELECTION = [
        ('pagosaextranjeros',        'Pagos a Extranjeros'),
        ('dividendos',               'Dividendos / Utilidades'),
        ('enajenaciondeacciones',    'Enajenación de Acciones'),
        ('fideicomisonoempresarial', 'Fideicomisos No Empresariales'),
        ('intereses',                'Intereses'),
        ('intereseshipotecarios',    'Intereses Hipotecarios'),
        ('operacionesconderivados',  'Operaciones Con Derivados'),
        ('planesderetiro',           'Planes de Retiro'),
        ('plataformastecnologicas',  'Plataformas Tecnológicas'),
        ('premios',                  'Premios'),
        ('relacionados',             'Relacionados (CFDI Relacionado)'),
        ('sectorfinanciero',         'Sector Financiero'),
        ('arrendamientoenfideicomiso', 'Arrendamiento en Fideicomiso'),
    ]
    SI_NO_SEL = [('SI', 'SI'), ('NO', 'NO')]

    l10n_mx_edi_retention_complement = fields.Selection(
        selection=COMPLEMENT_SELECTION, string='Complemento CFDI',
        help='Complemento según la actividad económica de la retención.',
    )

    # Relacionados
    l10n_mx_edi_ret_rel_tipo = fields.Selection(
        [('01', '01 - Nota de crédito'), ('04', '04 - Sustitución')],
        string='Tipo Relación',
    )
    l10n_mx_edi_ret_rel_uuid = fields.Char(string='UUID CFDI Relacionado')

    # Pagos a Extranjeros
    l10n_mx_edi_ret_ext_es_benef = fields.Selection(SI_NO_SEL, string='¿Es Beneficiario Efectivo?', default='NO')
    l10n_mx_edi_ret_ext_pais_id = fields.Many2one("res.country", string='País Residencia Fiscal', size=3, help='ISO 3166-1 alpha-2 (US, DE, FR...)')
    l10n_mx_edi_ret_ext_pais = fields.Char(string='Código Residencia Fiscal', size=3, help='ISO 3166-1 alpha-2 (US, DE, FR...)')
    l10n_mx_edi_ret_ext_descripcion = fields.Char(string='Descripción Concepto Pago')
    l10n_mx_edi_ret_ext_concepto_pago = fields.Char(string='Clave Concepto Pago')
    l10n_mx_edi_ret_ext_rfc_benef = fields.Char(string='RFC Beneficiario')
    l10n_mx_edi_ret_ext_curp_benef = fields.Char(string='CURP Beneficiario')
    l10n_mx_edi_ret_ext_nom_benef = fields.Char(string='Nombre Beneficiario')

    # Dividendos
    l10n_mx_edi_ret_div_cve_tipo = fields.Selection(
        selection=[
                    ('01', '01 - Proviene de CUFIN'),
                    ('02', '02 - No proviene de CUFIN'),
                    ('03', '03 - Reembolso o reducción de capital'),
                    ('04', '04 - Liquidación de la persona moral'),
                    ('05', '05 - CUFINRE'),
                    ('06', '06 - Proviene de CUFIN al 31 de diciembre 2013'),
                ],
        string='Tipo Dividendo (CveTipDivOUtil)',
    )
    l10n_mx_edi_ret_div_isr_mexico = fields.Monetary(string='ISR Acreditado México', currency_field='currency_id')
    l10n_mx_edi_ret_div_isr_extran = fields.Monetary(string='ISR Acreditado Extranjero', currency_field='currency_id')
    l10n_mx_edi_ret_div_tipo_soc = fields.Char(string='Tipo Sociedad', default='Sociedad Nacional')
    l10n_mx_edi_ret_div_isr_nal = fields.Monetary(string='ISR Acreditado Nacional', currency_field='currency_id')
    l10n_mx_edi_ret_div_acum_nal = fields.Monetary(string='Dividendo Acumulado Nacional', currency_field='currency_id')

    # Enajenación de Acciones
    l10n_mx_edi_ret_acc_perdida = fields.Monetary(string='Pérdida', currency_field='currency_id')
    l10n_mx_edi_ret_acc_ganancia = fields.Monetary(string='Ganancia', currency_field='currency_id')
    l10n_mx_edi_ret_acc_contrato = fields.Char(string='Contrato de Intermediación')

    # Fideicomisos No Empresariales
    l10n_mx_edi_ret_fide_prop_ing = fields.Float(string='% Proporción Ingresos', digits=(12, 4))
    l10n_mx_edi_ret_fide_part_ing = fields.Float(string='% Part. Acum. Fideicomiso Ing.', digits=(12, 4))
    l10n_mx_edi_ret_fide_entradas = fields.Monetary(string='Total Entradas Período', currency_field='currency_id')
    l10n_mx_edi_ret_fide_concepto_ing = fields.Char(string='Concepto Ingresos')
    l10n_mx_edi_ret_fide_prop_sal = fields.Float(string='% Proporción Salidas', digits=(12, 4))
    l10n_mx_edi_ret_fide_part_sal = fields.Float(string='% Part. Fideicomiso Salidas', digits=(12, 4))
    l10n_mx_edi_ret_fide_egresos = fields.Monetary(string='Total Egresos Período', currency_field='currency_id')
    l10n_mx_edi_ret_fide_concepto_sal = fields.Char(string='Concepto Egresos')
    l10n_mx_edi_ret_fide_desc_ret = fields.Char(string='Descripción Retención Fideicomiso')
    l10n_mx_edi_ret_fide_monto_ret = fields.Monetary(string='Monto Retención Fideicomiso', currency_field='currency_id')

    # Intereses
    l10n_mx_edi_ret_int_sist = fields.Selection(SI_NO_SEL, string='Sistema Financiero', default='NO')
    l10n_mx_edi_ret_int_ores = fields.Selection(SI_NO_SEL, string='Retiro/ORES', default='NO')
    l10n_mx_edi_ret_int_oper = fields.Selection(SI_NO_SEL, string='Operación Financ. Derivada', default='NO')
    l10n_mx_edi_ret_int_nominal = fields.Monetary(string='Interés Nominal', currency_field='currency_id')
    l10n_mx_edi_ret_int_real = fields.Monetary(string='Interés Real', currency_field='currency_id')
    l10n_mx_edi_ret_int_perdida = fields.Monetary(string='Pérdida', currency_field='currency_id')

    # Intereses Hipotecarios
    l10n_mx_edi_ret_hip_credito = fields.Selection(SI_NO_SEL, string='Crédito Inst. Financiera', default='SI')
    l10n_mx_edi_ret_hip_saldo = fields.Monetary(string='Saldo Insoluto', currency_field='currency_id')
    l10n_mx_edi_ret_hip_prop_deduc = fields.Monetary(string='Prop. Deducible del Crédito', currency_field='currency_id')
    l10n_mx_edi_ret_hip_int_nom = fields.Monetary(string='Int. Nominales Devengados', currency_field='currency_id')
    l10n_mx_edi_ret_hip_int_nom_pag = fields.Monetary(string='Int. Nominales Dev. y Pag.', currency_field='currency_id')
    l10n_mx_edi_ret_hip_int_real = fields.Monetary(string='Int. Real Pag. Deducible', currency_field='currency_id')
    l10n_mx_edi_ret_hip_num_contrato = fields.Char(string='Número de Contrato')

    # Operaciones Con Derivados
    l10n_mx_edi_ret_der_ganancia = fields.Monetary(string='Monto Ganancia Acumulada', currency_field='currency_id')
    l10n_mx_edi_ret_der_perdida = fields.Monetary(string='Monto Pérdida Deducible', currency_field='currency_id')

    # Planes de Retiro
    l10n_mx_edi_ret_plan_sist = fields.Selection(SI_NO_SEL, string='Sistema Financiero', default='NO')
    l10n_mx_edi_ret_plan_aport = fields.Monetary(string='Total Aportaciones Año Ant.', currency_field='currency_id')
    l10n_mx_edi_ret_plan_int = fields.Monetary(string='Int. Reales Devengados Año Ant.', currency_field='currency_id')
    l10n_mx_edi_ret_plan_retiros_per = fields.Selection(SI_NO_SEL, string='¿Hubo Retiros en Período?', default='NO')
    l10n_mx_edi_ret_plan_monto_ret_per = fields.Monetary(string='Monto Retirado en Período', currency_field='currency_id')
    l10n_mx_edi_ret_plan_excedente = fields.Monetary(string='Excedente Año Anterior', currency_field='currency_id')
    l10n_mx_edi_ret_plan_retiros = fields.Selection(SI_NO_SEL, string='¿Hubo Retiros en el Año?', default='NO')
    l10n_mx_edi_ret_plan_monto_ret = fields.Monetary(string='Monto Retirado en Año', currency_field='currency_id')
    l10n_mx_edi_ret_plan_exento = fields.Monetary(string='Monto Exento Retirado', currency_field='currency_id')
    l10n_mx_edi_ret_plan_num_ref = fields.Char(string='Número de Referencia')
    l10n_mx_edi_ret_plan_tipo_ap = fields.Char(string='Tipo Aportación/Depósito')
    l10n_mx_edi_ret_plan_monto_dep = fields.Monetary(string='Monto Depósito', currency_field='currency_id')
    l10n_mx_edi_ret_plan_rfc_fiduc = fields.Char(string='RFC Fiduciaria')

    # Plataformas Tecnológicas
    l10n_mx_edi_ret_plat_period = fields.Selection(
        [('01','01-Diario'),('02','02-Semanal'),('03','03-Quincenal'),('04','04-Mensual'),('05','05-Bimestral')],
        string='Periodicidad', default='04',
    )
    l10n_mx_edi_ret_plat_num_serv = fields.Integer(string='Número de Servicios', default=1)
    l10n_mx_edi_ret_plat_monto_sin_iva = fields.Monetary(string='Monto Total Sin IVA', currency_field='currency_id')
    l10n_mx_edi_ret_plat_iva_tras = fields.Monetary(string='Total IVA Trasladado', currency_field='currency_id')
    l10n_mx_edi_ret_plat_iva_ret = fields.Monetary(string='Total IVA Retenido', currency_field='currency_id')
    l10n_mx_edi_ret_plat_isr_ret = fields.Monetary(string='Total ISR Retenido', currency_field='currency_id')
    l10n_mx_edi_ret_plat_dif_iva = fields.Monetary(string='Dif. IVA Entregado', currency_field='currency_id')
    l10n_mx_edi_ret_plat_uso = fields.Monetary(string='Monto por Uso de Plataforma', currency_field='currency_id')
    l10n_mx_edi_ret_plat_forma_pago = fields.Char(string='Forma de Pago Servicio', default='02')
    l10n_mx_edi_ret_plat_tipo_serv = fields.Char(string='Tipo de Servicio', default='05', help='01=Hospedaje 02=Transporte personas 03=Transporte bienes 04=Venta bienes 05=Servicios 06=Intermediación')
    l10n_mx_edi_ret_plat_fecha_serv = fields.Date(string='Fecha del Servicio')
    l10n_mx_edi_ret_plat_precio = fields.Monetary(string='Precio Servicio Sin IVA', currency_field='currency_id')
    l10n_mx_edi_ret_plat_importe_iva = fields.Monetary(string='IVA del Servicio', currency_field='currency_id')
    l10n_mx_edi_ret_plat_comision = fields.Monetary(string='Importe Comisión', currency_field='currency_id')

    # Premios
    l10n_mx_edi_ret_prem_entidad = fields.Char(string='Entidad Federativa', size=2, help='01-32')
    l10n_mx_edi_ret_prem_monto = fields.Monetary(string='Monto Total Pago', currency_field='currency_id')
    l10n_mx_edi_ret_prem_grav = fields.Monetary(string='Monto Gravado', currency_field='currency_id')
    l10n_mx_edi_ret_prem_exent = fields.Monetary(string='Monto Exento', currency_field='currency_id')

    # Sector Financiero
    l10n_mx_edi_ret_sec_descrip = fields.Char(string='Descripción Fideicomiso')
    l10n_mx_edi_ret_sec_id = fields.Char(string='ID Fideicomiso')
    l10n_mx_edi_ret_sec_nom = fields.Char(string='Nombre Fideicomiso')

    # Arrendamiento en Fideicomiso
    l10n_mx_edi_ret_arren_pag_prov = fields.Monetary(string='Pago Provisional por Fiduciaria', currency_field='currency_id')
    l10n_mx_edi_ret_arren_rendim = fields.Monetary(string='Rendimiento del Fideicomiso', currency_field='currency_id')
    l10n_mx_edi_ret_arren_deduc = fields.Monetary(string='Deducción Correspondiente', currency_field='currency_id')
    l10n_mx_edi_ret_arren_tot_ret = fields.Monetary(string='Monto Total Retención', currency_field='currency_id')
    l10n_mx_edi_ret_arren_res_fis = fields.Monetary(string='Monto Res. Fiscal FIBRAS', currency_field='currency_id')
    l10n_mx_edi_ret_arren_otros = fields.Monetary(string='Monto Otros Conceptos', currency_field='currency_id')
    l10n_mx_edi_ret_arren_desc_otros = fields.Char(string='Descripción Otros Conceptos')


    # ── Estado del timbrado ───────────────────────────────────────────────────

    l10n_mx_edi_retention_pre_stamp_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='XML Pre-Timbrado',
        copy=False,
        readonly=True,
        help='Último XML generado y enviado al PAC, con o sin sello. '
             'Se sobreescribe en cada intento. Útil para depurar errores de timbrado.',
    )

    l10n_mx_edi_retention_state = fields.Selection(
        selection=[
            ('draft', 'Sin timbrar'),
            ('sent', 'Timbrado'),
            ('error', 'Error'),
        ],
        string='Estado Retención CFDI',
        default='draft',
        copy=False,
        tracking=True,
    )
    l10n_mx_edi_retention_uuid = fields.Char(
        string='Folio Fiscal Retención',
        copy=False,
        readonly=True,
    )
    l10n_mx_edi_retention_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='XML Retención',
        copy=False,
        readonly=True,
    )
    l10n_mx_edi_retention_error_message = fields.Text(
        string='Error Retención CFDI',
        copy=False,
        readonly=True,
    )

    # =========================================================================
    # Computes
    # =========================================================================

    @api.depends('partner_id', 'partner_id.country_id')
    def _compute_retention_is_foreign(self):
        for payment in self:
            country_code = payment.partner_id.country_id.code
            payment.l10n_mx_edi_retention_is_foreign = (
                bool(country_code) and country_code != 'MX'
            )

    @api.depends('l10n_mx_edi_retention_impuesto_ids.monto_ret')
    def _compute_monto_tot_ret(self):
        for payment in self:
            payment.l10n_mx_edi_retention_monto_tot_ret = sum(
                payment.l10n_mx_edi_retention_impuesto_ids.mapped('monto_ret')
            )


    @api.onchange('l10n_mx_edi_ret_ext_pais_id')
    def onchange_l10n_mx_edi_ret_ext_pais(self):
        if self.l10n_mx_edi_ret_ext_pais_id:
            # self.l10n_mx_edi_ret_ext_pais = self.l10n_mx_edi_ret_ext_pais_id.l10n_mx_edi_code if self.l10n_mx_edi_ret_ext_pais_id.l10n_mx_edi_code else ''
            self.l10n_mx_edi_ret_ext_pais = self.l10n_mx_edi_ret_ext_pais_id.code if self.l10n_mx_edi_ret_ext_pais_id.code else ''

    @api.onchange('l10n_mx_edi_ret_ext_tipo_contribuyente_id')
    def onchange_l10n_mx_edi_ret_ext_tipo_contribuyente(self):
        if self.l10n_mx_edi_ret_ext_tipo_contribuyente_id:
            l10n_mx_edi_ret_ext_concepto_pago = self.l10n_mx_edi_ret_ext_tipo_contribuyente_id.code
            #if self.l10n_mx_edi_retention_complement == 'pagosaextranjeros':
            self.l10n_mx_edi_ret_ext_concepto_pago = l10n_mx_edi_ret_ext_concepto_pago

            l10n_mx_edi_ret_ext_descripcion = self.l10n_mx_edi_ret_ext_tipo_contribuyente_id.name
            #if self.l10n_mx_edi_retention_complement == 'pagosaextranjeros':
            self.l10n_mx_edi_ret_ext_descripcion = l10n_mx_edi_ret_ext_descripcion


    # =========================================================================
    # Construcción de valores para el template QWeb v2.0
    # =========================================================================

    def _l10n_mx_edi_get_retention_cfdi_values(self):
        """Construye el diccionario de valores para los templates QWeb v2.0.

        Estructura basada en los XML de ejemplo oficiales del SAT:
          - Nacionales:  RfcE, RfcR, DomicilioFiscalR, NacionalidadR="Nacional"
          - Extranjeros: NacionalidadR="Extranjero", sin RFC

        Returns:
            dict con todas las claves necesarias para ambos templates.
        """
        self.ensure_one()

        # ── Certificado vigente (v19: filtered('is_valid')) ──────────────────
        certificate = (
            self.company_id.l10n_mx_edi_certificate_ids
            .sudo().filtered('is_valid')[:1]
        )
        if not certificate:
            raise UserError(_(
                'No se encontró un certificado vigente para %s.',
                self.company_id.name,
            ))

        # ── Función de formato de flotantes ──────────────────────────────────
        def format_float(amount, precision=2):
            if amount is None:
                return '0.00'
            return '%.*f' % (precision, amount)

        # ── Número de certificado y bytes ─────────────────────────────────────
        # v19 oficial: ('%x' % int(serial_number))[1::2]
        no_certificado = ('%x' % int(certificate.serial_number))[1::2]
        certificado = certificate._get_der_certificate_bytes(formatting='base64').decode()

        # ── Fecha de expedición (v2.0 sin offset de zona horaria) ────────────
        tz = timezone(MX_TZ)
        fecha_exp = datetime.now(tz).strftime('%Y-%m-%dT%H:%M:%S')

        # ── Emisor ────────────────────────────────────────────────────────────
        root_company = (
            self.company_id.sudo().parent_ids[::-1]
            .filtered('partner_id.vat')[:1]
            or self.company_id
        )
        supplier = root_company.partner_id.commercial_partner_id
        fiscal_regime = (
            self.company_id.l10n_mx_edi_fiscal_regime
            or root_company.l10n_mx_edi_fiscal_regime
        )

        # ── Receptor ──────────────────────────────────────────────────────────
        customer = self.partner_id.commercial_partner_id

        # ── Período ───────────────────────────────────────────────────────────
        mes_ini = self.l10n_mx_edi_retention_mes_ini or '01'
        mes_fin = self.l10n_mx_edi_retention_mes_fin or '12'
        ejercicio = str(self.l10n_mx_edi_retention_ejercicio or datetime.now().year)

        # ── Totales ───────────────────────────────────────────────────────────
        monto_tot_ret = sum(
            self.l10n_mx_edi_retention_impuesto_ids.mapped('monto_ret')
        )

        # ── Complemento: construir complement_values ─────────────────────────
        complement = self.l10n_mx_edi_retention_complement or ''
        cv = {}  # complement_values shorthand

        if complement == 'pagosaextranjeros':
            cv = {
                'es_benef':      self.l10n_mx_edi_ret_ext_es_benef or 'NO',
                'pais_resid':    self.l10n_mx_edi_ret_ext_pais or '',
                'descripcion':   self.l10n_mx_edi_ret_ext_descripcion or '',
                'concepto_pago': self.l10n_mx_edi_ret_ext_concepto_pago or '',
                'rfc_benef':     self.l10n_mx_edi_ret_ext_rfc_benef or '',
                'curp_benef':    self.l10n_mx_edi_ret_ext_curp_benef or '',
                'nom_benef':     self.l10n_mx_edi_ret_ext_nom_benef or '',
            }
        elif complement == 'dividendos':
            cv = {
                'cve_tipo':      self.l10n_mx_edi_ret_div_cve_tipo or '',
                'monto_isr_mexico': self.l10n_mx_edi_ret_div_isr_mexico,
                'monto_isr_extran': self.l10n_mx_edi_ret_div_isr_extran,
                'tipo_soc':      self.l10n_mx_edi_ret_div_tipo_soc or '',
                'monto_isr_nal': self.l10n_mx_edi_ret_div_isr_nal,
                'monto_div_acum': self.l10n_mx_edi_ret_div_acum_nal,
            }
        elif complement == 'enajenaciondeacciones':
            cv = {
                'perdida':  self.l10n_mx_edi_ret_acc_perdida,
                'ganancia': self.l10n_mx_edi_ret_acc_ganancia,
                'contrato': self.l10n_mx_edi_ret_acc_contrato or '',
            }
        elif complement == 'fideicomisonoempresarial':
            cv = {
                'prop_mont_tot_ing': self.l10n_mx_edi_ret_fide_prop_ing,
                'part_prop_ing':     self.l10n_mx_edi_ret_fide_part_ing,
                'monto_tot_entradas': self.l10n_mx_edi_ret_fide_entradas,
                'concepto_ingresos': self.l10n_mx_edi_ret_fide_concepto_ing or '',
                'prop_mont_tot_sal': self.l10n_mx_edi_ret_fide_prop_sal,
                'part_prop_sal':     self.l10n_mx_edi_ret_fide_part_sal,
                'monto_tot_egresos': self.l10n_mx_edi_ret_fide_egresos,
                'concepto_egresos':  self.l10n_mx_edi_ret_fide_concepto_sal or '',
                'desc_ret':          self.l10n_mx_edi_ret_fide_desc_ret or '',
                'monto_ret_fide':    self.l10n_mx_edi_ret_fide_monto_ret,
            }
        elif complement == 'intereses':
            cv = {
                'sist_financiero': self.l10n_mx_edi_ret_int_sist or 'NO',
                'retiro_ores':     self.l10n_mx_edi_ret_int_ores or 'NO',
                'oper_financ':     self.l10n_mx_edi_ret_int_oper or 'NO',
                'monto_nominal':   self.l10n_mx_edi_ret_int_nominal,
                'monto_real':      self.l10n_mx_edi_ret_int_real,
                'perdida':         self.l10n_mx_edi_ret_int_perdida,
            }
        elif complement == 'intereseshipotecarios':
            cv = {
                'credito_inst':    self.l10n_mx_edi_ret_hip_credito or 'SI',
                'saldo_insoluto':  self.l10n_mx_edi_ret_hip_saldo,
                'prop_deduc':      self.l10n_mx_edi_ret_hip_prop_deduc,
                'monto_int_nom':   self.l10n_mx_edi_ret_hip_int_nom,
                'monto_int_nom_pag': self.l10n_mx_edi_ret_hip_int_nom_pag,
                'monto_int_real':  self.l10n_mx_edi_ret_hip_int_real,
                'num_contrato':    self.l10n_mx_edi_ret_hip_num_contrato or '',
            }
        elif complement == 'operacionesconderivados':
            cv = {
                'monto_ganancia': self.l10n_mx_edi_ret_der_ganancia,
                'monto_perdida':  self.l10n_mx_edi_ret_der_perdida,
            }
        elif complement == 'planesderetiro':
            cv = {
                'sistema_financ':  self.l10n_mx_edi_ret_plan_sist or 'NO',
                'monto_aport':     self.l10n_mx_edi_ret_plan_aport,
                'monto_int_reales': self.l10n_mx_edi_ret_plan_int,
                'hubo_retiros_per': self.l10n_mx_edi_ret_plan_retiros_per or 'NO',
                'monto_retirado_per': self.l10n_mx_edi_ret_plan_monto_ret_per,
                'monto_excedente': self.l10n_mx_edi_ret_plan_excedente,
                'hubo_retiros':    self.l10n_mx_edi_ret_plan_retiros or 'NO',
                'monto_retirado':  self.l10n_mx_edi_ret_plan_monto_ret,
                'monto_exento':    self.l10n_mx_edi_ret_plan_exento,
                'num_referencia':  self.l10n_mx_edi_ret_plan_num_ref or '',
                'tipo_aportacion': self.l10n_mx_edi_ret_plan_tipo_ap or '',
                'monto_dep':       self.l10n_mx_edi_ret_plan_monto_dep,
                'rfc_fiduciaria':  self.l10n_mx_edi_ret_plan_rfc_fiduc or '',
            }
        elif complement == 'plataformastecnologicas':
            cv = {
                'periodicidad':    self.l10n_mx_edi_ret_plat_period or '04',
                'num_serv':        self.l10n_mx_edi_ret_plat_num_serv or 1,
                'monto_tot_sin_iva': self.l10n_mx_edi_ret_plat_monto_sin_iva,
                'total_iva_trasladado': self.l10n_mx_edi_ret_plat_iva_tras,
                'total_iva_retenido': self.l10n_mx_edi_ret_plat_iva_ret,
                'total_isr_retenido': self.l10n_mx_edi_ret_plat_isr_ret,
                'dif_iva':         self.l10n_mx_edi_ret_plat_dif_iva,
                'monto_por_uso':   self.l10n_mx_edi_ret_plat_uso,
                'forma_pago_serv': self.l10n_mx_edi_ret_plat_forma_pago or '02',
                'tipo_serv':       self.l10n_mx_edi_ret_plat_tipo_serv or '05',
                'fecha_serv':      str(self.l10n_mx_edi_ret_plat_fecha_serv or ''),
                'precio_serv_sin_iva': self.l10n_mx_edi_ret_plat_precio,
                'base_iva':        self.l10n_mx_edi_ret_plat_precio,
                'tasa_iva':        0.16,
                'importe_iva':     self.l10n_mx_edi_ret_plat_importe_iva,
                'base_comision':   self.l10n_mx_edi_ret_plat_precio,
                'importe_comision': self.l10n_mx_edi_ret_plat_comision,
            }
        elif complement == 'premios':
            cv = {
                'entidad_fed': self.l10n_mx_edi_ret_prem_entidad or '',
                'monto_tot_pago': self.l10n_mx_edi_ret_prem_monto,
                'monto_grav':    self.l10n_mx_edi_ret_prem_grav,
                'monto_exent':   self.l10n_mx_edi_ret_prem_exent,
            }
        elif complement == 'relacionados':
            cv = {
                'tipo_relacion': self.l10n_mx_edi_ret_rel_tipo or '',
                'uuid':          self.l10n_mx_edi_ret_rel_uuid or '',
            }
        elif complement == 'sectorfinanciero':
            cv = {
                'descrip_fideicom': self.l10n_mx_edi_ret_sec_descrip or '',
                'id_fideicom':      self.l10n_mx_edi_ret_sec_id or '',
                'nom_fideicom':     self.l10n_mx_edi_ret_sec_nom or '',
            }
        elif complement == 'arrendamientoenfideicomiso':
            cv = {
                'pag_prov':         self.l10n_mx_edi_ret_arren_pag_prov,
                'rendim':           self.l10n_mx_edi_ret_arren_rendim,
                'deduc':            self.l10n_mx_edi_ret_arren_deduc,
                'monto_tot_ret_arren': self.l10n_mx_edi_ret_arren_tot_ret,
                'monto_res_fis':    self.l10n_mx_edi_ret_arren_res_fis,
                'monto_otros':      self.l10n_mx_edi_ret_arren_otros,
                'desc_otros':       self.l10n_mx_edi_ret_arren_desc_otros or '',
            }

        # ── schemaLocation dinámico según complemento ──────────────────────
        COMP_NS = {
            'pagosaextranjeros':        'http://www.sat.gob.mx/esquemas/retencionpago/1/pagosaextranjeros pagosaextranjeros/pagosaextranjeros.xsd',
            'dividendos':               'http://www.sat.gob.mx/esquemas/retencionpago/1/dividendos dividendos/dividendos.xsd',
            'enajenaciondeacciones':    'http://www.sat.gob.mx/esquemas/retencionpago/1/enajenaciondeacciones enajenaciondeacciones/enajenaciondeacciones.xsd',
            'fideicomisonoempresarial': 'http://www.sat.gob.mx/esquemas/retencionpago/1/fideicomisonoempresarial fideicomisonoempresarial/fideicomisonoempresarial.xsd',
            'intereses':               'http://www.sat.gob.mx/esquemas/retencionpago/1/intereses intereses/intereses.xsd',
            'intereseshipotecarios':   'http://www.sat.gob.mx/esquemas/retencionpago/1/intereseshipotecarios intereseshipotecarios/intereseshipotecarios.xsd',
            'operacionesconderivados': 'http://www.sat.gob.mx/esquemas/retencionpago/1/operacionesconderivados operacionesconderivados/operacionesconderivados.xsd',
            'planesderetiro':          'http://www.sat.gob.mx/esquemas/retencionpago/1/planesderetiro11 planesderetiro11/planesderetiro11.xsd',
            'plataformastecnologicas': 'http://www.sat.gob.mx/esquemas/retencionpago/1/PlataformasTecnologicas10 PlataformasTecnologicas10/ServiciosPlataformasTecnologicas10.xsd',
            'premios':                 'http://www.sat.gob.mx/esquemas/retencionpago/1/premios premios/premios.xsd',
            'sectorfinanciero':        'http://www.sat.gob.mx/esquemas/retencionpago/1/sectorfinanciero sectorfinanciero/sectorfinanciero.xsd',
            'arrendamientoenfideicomiso': 'http://www.sat.gob.mx/esquemas/retencionpago/1/arrendamientoenfideicomiso arrendamientoenfideicomiso/arrendamientoenfideicomiso.xsd',
        }
        base_schema = 'http://www.sat.gob.mx/esquemas/retencionpago/2 http://www.sat.gob.mx/esquemas/retencionpago/2/retencionpagov2.xsd'
        comp_schema = COMP_NS.get(complement, '')
        schema_prefix = 'http://www.sat.gob.mx/esquemas/retencionpago/1 '
        schema_location = base_schema + (f' {schema_prefix}{comp_schema}' if comp_schema else '')

        dict_retention_cfdi_values = {
                                            # Certificado
                                            'certificate': certificate,
                                            'no_certificado': no_certificado,
                                            'certificado': certificado,
                                            # Encabezado
                                            'folio_int': self.name or self.ref or '',
                                            'fecha_exp': fecha_exp,
                                            'lugar_exp': supplier.zip or '',
                                            'cve_retenc': self.retention_type_id.code or '',
                                            'schema_location': schema_location,
                                            # Emisor
                                            'emisor_rfc': supplier.vat or '',
                                            'emisor_nombre': supplier.name or '',
                                            'emisor_regimen': fiscal_regime or '',
                                            # Receptor
                                            'is_foreign': self.l10n_mx_edi_retention_is_foreign,
                                            'receptor_nombre': customer.name or '',
                                            'receptor_rfc': customer.vat or '',
                                            'receptor_domicilio': customer.zip or '',
                                            # Período
                                            'mes_ini': mes_ini,
                                            'mes_fin': mes_fin,
                                            'ejercicio': ejercicio,
                                            # Totales
                                            'monto_tot_operacion': format_float(self.l10n_mx_edi_retention_monto_tot_operacion),
                                            'monto_tot_grav': format_float(self.l10n_mx_edi_retention_monto_tot_grav),
                                            'monto_tot_exent': format_float(self.l10n_mx_edi_retention_monto_tot_exent),
                                            'monto_tot_ret': format_float(monto_tot_ret),
                                            # ImpRetenidos
                                            'impuesto_ids': self.l10n_mx_edi_retention_impuesto_ids,
                                            'format_float': format_float,
                                            # Complemento
                                            'complement': complement,
                                            'complement_values': cv,
                                        }
        if customer.country_id.code != 'MX':
            dict_retention_cfdi_values['receptor_num_reg_id_trib'] = customer.vat
        else:
            dict_retention_cfdi_values['receptor_num_reg_id_trib'] = False

        return dict_retention_cfdi_values

    # =========================================================================
    # Acciones
    # =========================================================================

    def action_prefill_retention_from_bills(self):
        """Pre-llena los campos de retención desde las facturas de proveedor
        conciliadas con este pago (reconciled_bill_ids).

        Extrae de cada factura:
          - Las líneas de impuesto de retención (amount < 0)
          - El tipo de impuesto (ISR/IVA/IEPS) via l10n_mx_tax_type
          - La base y el monto de cada retención

        Calcula y asigna:
          - MontoTotOperacion = suma de subtotales (amount_untaxed)
          - MontoTotGrav      = suma de bases de impuestos retenidos
          - MontoTotExent     = MontoTotOperacion - MontoTotGrav
          - ImpRetenidos      = líneas agrupadas por tipo de impuesto
          - Período           = mes y año del pago
        """
        self.ensure_one()

        bills = self.reconciled_bill_ids.filtered(lambda m: m.state == 'posted')
        if not bills:
            raise UserError(_(
                'No hay facturas de proveedor confirmadas conciliadas con este pago.'
            ))

        # ── Mapeo de tipo de impuesto MX → código SAT ──────────────────────
        TAX_TYPE_TO_CODE = {'isr': '001', 'iva': '002', 'ieps': '003'}
        # c_TipoPagoRet v2.0: 03=ISR definitivo, 01=IVA definitivo, 02=IEPS definitivo
        TAX_TYPE_TO_TIPO = {'isr': '03', 'iva': '01', 'ieps': '02'}

        retention_data = {}   # {code: {'base': float, 'amount': float, 'tipo': str}}
        total_operation = 0.0
        total_grav = 0.0

        for bill in bills:
            total_operation += bill.amount_untaxed

            # Líneas de impuesto con amount < 0 = retención (withholding)
            wh_lines = bill.line_ids.filtered(
                lambda l: l.tax_line_id and l.tax_line_id.amount < 0
            )
            bill_grav = 0.0

            for line in wh_lines:
                tax = line.tax_line_id
                tax_type = getattr(tax, 'l10n_mx_tax_type', 'isr') or 'isr'
                code = TAX_TYPE_TO_CODE.get(tax_type, '001')
                tipo = TAX_TYPE_TO_TIPO.get(tax_type, '03')
                amount = abs(line.balance)
                base = abs(line.tax_base_amount)

                if code not in retention_data:
                    retention_data[code] = {'base': 0.0, 'amount': 0.0, 'tipo': tipo}
                retention_data[code]['base'] += base
                retention_data[code]['amount'] += amount
                bill_grav = max(bill_grav, base)

            total_grav += bill_grav or (bill.amount_untaxed if wh_lines else 0.0)

        if not retention_data:
            raise UserError(_(
                'Las facturas conciliadas no contienen impuestos de retención '
                '(ISR/IVA/IEPS con monto negativo). '
                'Verifica que los impuestos de retención estén configurados en las facturas.'
            ))

        total_exent = max(0.0, total_operation - total_grav)

        # Período desde la fecha del pago
        mes = str(self.date.month).zfill(2) if self.date else '01'
        year = self.date.year if self.date else fields.Date.today().year

        # Construir líneas ImpRetenidos (reemplaza las existentes)
        impuesto_commands = [(5, 0, 0)]  # borrar todas primero
        for code in sorted(retention_data):
            data = retention_data[code]
            impuesto_commands.append((0, 0, {
                'impuesto_ret': code,
                'base_ret': round(data['base'], 2),
                'monto_ret': round(data['amount'], 2),
                'tipo_pago_ret': data['tipo'],
            }))

        self.write({
            'require_retention_cfdi': True,
            'l10n_mx_edi_retention_monto_tot_operacion': round(total_operation, 2),
            'l10n_mx_edi_retention_monto_tot_grav': round(total_grav, 2),
            'l10n_mx_edi_retention_monto_tot_exent': round(total_exent, 2),
            'l10n_mx_edi_retention_mes_ini': mes,
            'l10n_mx_edi_retention_mes_fin': mes,
            'l10n_mx_edi_retention_ejercicio': year,
            'l10n_mx_edi_retention_impuesto_ids': impuesto_commands,
        })

        return {'type': 'ir.actions.act_window_close'}
        # return {
        #     'type': 'ir.actions.client',
        #     'tag': 'display_notification',
        #     'params': {
        #         'title': _('Retención pre-llenada'),
        #         'message': _(
        #             '%d factura(s) procesada(s) · %d impuesto(s) de retención.',
        #             len(bills), len(retention_data),
        #         ),
        #         'type': 'success',
        #         'sticky': False,
        #     },
        # }

    def action_l10n_mx_edi_retention_try_send(self):
        """Genera, firma (SHA-256) y timbra el CFDI de Retenciones v2.0."""
        self.ensure_one()
        if not self.require_retention_cfdi:
            raise UserError(_('Este pago no está marcado para generar CFDI de Retención.'))
        if not self.retention_type_id:
            raise UserError(_('Selecciona el Tipo de Retención (CveRetenc) antes de timbrar.'))
        if not self.l10n_mx_edi_retention_impuesto_ids:
            raise UserError(_('Agrega al menos una línea de Impuesto Retenido (ImpRetenidos).'))
        if self.l10n_mx_edi_retention_state == 'sent':
            raise UserError(_(
                'Este pago ya tiene un CFDI de Retención timbrado (UUID: %s).',
                self.l10n_mx_edi_retention_uuid,
            ))

        if self.state in ('draft', 'cancel'):
            raise UserError("No se puede timbrar un pago cancelado o en borrador.")

        result = self.env['l10n_mx_edi.document']._retention_cfdi_try_send(self)

        if result.get('error'):
            self.write({
                'l10n_mx_edi_retention_state': 'error',
                'l10n_mx_edi_retention_error_message': result['error'],
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error al timbrar CFDI de Retención'),
                    'message': result['error'],
                    'type': 'danger',
                    'sticky': True,
                },
            }

        filename = f'Retencion_{self.name.replace("/", "_")}.xml'
        cfdi_str = result['cfdi_str']
        if isinstance(cfdi_str, str):
            cfdi_bytes = cfdi_str.encode('utf-8')
        else:
            cfdi_bytes = cfdi_str

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/xml',
            'datas': base64.b64encode(cfdi_bytes),
        })

        self.write({
            'l10n_mx_edi_retention_state': 'sent',
            'l10n_mx_edi_retention_uuid': result.get('uuid', ''),
            'l10n_mx_edi_retention_attachment_id': attachment.id,
            'l10n_mx_edi_retention_error_message': False,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CFDI de Retención timbrado'),
                'message': _('UUID: %s', result.get('uuid', '')),
                'type': 'success',
            },
        }

    def action_l10n_mx_edi_retention_reset(self):
        """Restablece el estado para un nuevo intento."""
        self.ensure_one()
        if self.l10n_mx_edi_retention_state == 'sent':
            raise UserError(_('No se puede restablecer un CFDI de Retención ya timbrado.'))
        self.write({
            'l10n_mx_edi_retention_state': 'draft',
            'l10n_mx_edi_retention_error_message': False,
        })

    def action_download_pre_stamp_xml(self):
        """Descarga el XML que se envió al PAC (antes del timbrado).
        Se actualiza en cada intento — útil para depurar errores del PAC."""
        self.ensure_one()
        if not self.l10n_mx_edi_retention_pre_stamp_id:
            raise UserError(_('No hay un XML pre-timbrado disponible. '
                              'Intenta timbrar primero.'))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.l10n_mx_edi_retention_pre_stamp_id.id}?download=true',
            'target': 'self',
        }

    def action_download_retention_xml(self):
        """Descarga el XML del CFDI de Retenciones timbrado."""
        self.ensure_one()
        if not self.l10n_mx_edi_retention_attachment_id:
            raise UserError(_('No hay un XML de Retención disponible para descargar.'))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.l10n_mx_edi_retention_attachment_id.id}?download=true',
            'target': 'self',
        }

    # =========================================================================
    # Reporte
    # =========================================================================

    def _get_payment_receipt_report_values(self):
        values = super()._get_payment_receipt_report_values()
        if self.require_retention_cfdi and self.l10n_mx_edi_retention_attachment_id:
            try:
                xml_bytes = base64.b64decode(
                    self.l10n_mx_edi_retention_attachment_id
                        .with_context(bin_size=False).datas
                )
                retention_vals = self._l10n_mx_edi_decode_retention_xml(xml_bytes)
            except Exception as e:
                _logger.warning('Error decoding retention XML: %s', e)
                retention_vals = {}
            values['retention_cfdi'] = {
                'uuid': self.l10n_mx_edi_retention_uuid,
                'payment': self,
                **retention_vals,
            }
        return values

    @api.model
    def _l10n_mx_edi_decode_retention_xml(self, xml_bytes):
        """Extrae datos del XML de Retenciones v2.0 para el reporte."""
        from lxml import etree
        try:
            root = etree.fromstring(xml_bytes)
            tfd = root.find(
                './/{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital'
            )
            totales = root.find(
                '{http://www.sat.gob.mx/esquemas/retencionpago/2}Totales'
            )
            emisor = root.find(
                '{http://www.sat.gob.mx/esquemas/retencionpago/2}Emisor'
            )
            return {
                'stamp_uuid': tfd.get('UUID') if tfd is not None else '',
                'stamp_date': (tfd.get('FechaTimbrado', '') if tfd is not None else '').replace('T', ' '),
                'sat_certificate': tfd.get('NoCertificadoSAT', '') if tfd is not None else '',
                'sat_sello': tfd.get('SelloSAT', '') if tfd is not None else '',
                'monto_tot_ret': totales.get('MontoTotRet', '') if totales is not None else '',
                'monto_tot_operacion': totales.get('MontoTotOperacion', '') if totales is not None else '',
                'emisor_rfc': emisor.get('RfcE', '') if emisor is not None else '',
                'emisor_name': emisor.get('NomDenRazSocE', '') if emisor is not None else '',
                'fecha_exp': root.get('FechaExp', '').replace('T', ' '),
                'num_cert': root.get('NoCertificado', ''),
                'sello': root.get('Sello', ''),
            }
        except Exception as e:
            _logger.warning('_l10n_mx_edi_decode_retention_xml: %s', e)
            return {}
