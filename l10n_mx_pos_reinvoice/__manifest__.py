# -*- coding: utf-8 -*-
# Copyright 2026 Asesores y Soluciones ANFEPI | License OPL-1
# https://www.anfepi.com
# SUSCRIPTION REQUIRED — REDISTRIBUTION PROHIBITED — DECOMPILATION PROHIBITED
# See LICENSE file for full Odoo Proprietary License v1.0 terms.

{
    'name': 'Refacturación de tickets incluidos en Factura Global (México)',
    "version"   : "20.0.1.0",
    'category': 'Accounting/Localizations/EDI',
    'author': 'ANFEPI: Roberto Requejo Jiménez',
    'maintainer': 'Asesores y Soluciones ANFEPI',
    'website': 'https://www.anfepi.com',
    'support': 'soporte@anfepi.com',
    'contact_url': 'https://www.anfepi.com',
    'live_test_url': 'https://www.anfepi.com',
    # Contacto comercial: info@anfepi.com  |  Soporte tecnico: soporte@anfepi.com
    # Telefono/WhatsApp: +52 999 520 0611  |  Web: https://www.anfepi.com
    'summary': 'Botón Refacturar en la orden del POS: nota de crédito a la Global '
               'y factura nominativa al cliente, en un solo paso',
    'description': """
Refacturación de tickets incluidos en Factura Global
=====================================================

Cuando un ticket del punto de venta ya salió en una Factura Global y el cliente
pide después su factura nominativa, este módulo lo resuelve con un botón en la
propia orden del punto de venta.

Qué hace el botón
-----------------
1. Localiza SOLA la Factura Global que incluyó el ticket. El usuario no captura
   ningún folio fiscal: el módulo lo lee del propio CFDI.
2. Emite la factura nominativa al cliente, con exactamente las mismas líneas,
   cantidades y precios del ticket.
3. Emite la nota de crédito a Público en General, relacionada 01| a esa Factura
   Global, heredando su forma de pago del XML original.
4. Aplica la nota de crédito a la factura nominativa, y deja el saldo a nombre
   del cliente real aunque el XML de la nota siga siendo a Público en General.

Garantías contables
-------------------
* La pareja factura + nota de crédito netea a CERO en todas las cuentas, de modo
  que no se duplica el ingreso ni se altera el costo de ventas ya registrado en
  el asiento de cierre de la sesión del punto de venta.
* Ante el SAT, el ingreso del ticket queda declarado una sola vez: la nota de
  crédito relacionada 01| cancela el importe que ya iba dentro de la Global.
* Antes de timbrar, el módulo verifica que la nota sea espejo exacto de la
  factura (mismas líneas y mismo total). Si no lo es, aborta.
* Exige que la sesión del punto de venta esté cerrada. Con la sesión abierta,
  Odoo omitiría la venta de un ticket ya facturado al construir el asiento de
  cierre, y el ingreso se perdería.

Seguridad
---------
El botón sólo lo ven los usuarios del grupo "Refacturar tickets incluidos en
Factura Global". Se timbran dos CFDI ante el SAT, así que conviene otorgarlo
sólo a quien deba hacer esta operación.

Compatibilidad
--------------
Usa exclusivamente mecanismos nativos de Odoo y de la localización mexicana.
No depende de módulos de terceros.
    """,
    'depends': ['point_of_sale', 'l10n_mx_edi', 'l10n_mx_edi_pos'],
    'data': [
        'security/pos_reinvoice_groups.xml',
        'security/ir.model.access.csv',
        'wizards/pos_reinvoice_wizard_views.xml',
        'views/pos_order_views.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
