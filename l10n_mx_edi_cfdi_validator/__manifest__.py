# -*- coding: utf-8 -*-
{
    'name': 'MX CFDI — Validador Facturas Proveedor',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'summary': 'Pestaña CFDI con lectura de XML y validaciones SAT en facturas de proveedor',
    'description': """
        Agrega en Odoo 19:

        * Pestaña **CFDI** en facturas y notas de crédito de proveedor
          (in_invoice / in_refund) con todos los datos del XML:
          UUID, Emisor, Receptor, Información Adicional e Impuestos.

        * **Lectura automática del XML** al adjuntar el CFDI a través
          del flujo estándar de l10n_mx_edi.  Botón "Releer XML" para
          actualización manual.

        * **Validaciones SAT configurables** por empresa en
          Contabilidad → Configuración. Cada validación puede
          activarse o desactivarse independientemente.

        * **Bloqueo en Confirmar**: si una validación activa falla,
          el sistema impide registrar la factura hasta corregirla.
    """,
    'author': 'German Ponce Dominguez',
    'depends': [
                  'l10n_mx_edi',
                  'l10n_mx_edi_extended', 
                  'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
