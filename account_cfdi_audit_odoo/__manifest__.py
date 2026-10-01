# -*- encoding: utf-8 -*-

{
    "name"      : "Auditoría de Facturas vs. SAT",
    "version"   : "1.0",
    "depends"   : ["account_accountant",
                   #"l10n_mx_einvoice",
                   #"asti_eaccounting_mx_base",
                  ],
    "author"    : "German Ponce",
    "website"   : "https://poncesoft.blogspot.com",
    "license"   : "Other proprietary",
    "category"  : "Accounting",
    "description" : """
Auditoría de Facturas vs. SAT
=============================

Este módulo le permite hacer una revisión de los registros de Facturas 
tanto de Clientes como de Proveedores cotejando que el CFDI se encuentre 
Vigente (para los registros cuyo estado sea "Es Factura"), y revisando
que los Cancelados se encuentren efectivamente Cancelados en el SAT.

El modulo funciona de la siguiente manera:
1. Descargará todos los CFDIs del periodo actual (proceso que se
   corre por la noche o bajo demanda con un wizard).
2. Las guardara en una tabla para una búsqueda mas rápida
3. Recorrerá TODAS las facturas de Clientes y Proveedores del periodo, 
   y si tiene archivo XML adjunto, lo leerá, y cotejará los datos 
   contra el punto 2.
4. Al final se podrá revisar:
   - Facturas vigentes vs. Canceladas
   - Facturas sin registro en sistema y/o duplicadas
   - Facturas inválidas o apócrifas
   - Montos de facturas diferentes (monto total +/- 1.0)

    """,
    
    "demo": [],
    "test": [],
    "data": [
        "security/ir.model.access.csv",
        "view/account_cfdi_view.xml",
    ],
    "application": False,
    "installable": True,
}
