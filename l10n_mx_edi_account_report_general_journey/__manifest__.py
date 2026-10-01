# -*- encoding: utf-8 -*-
# Coded by German Ponce Dominguez 
#     ▬▬▬▬▬.◙.▬▬▬▬▬  
#       ▂▄▄▓▄▄▂  
#    ◢◤█▀▀████▄▄▄▄▄▄ ◢◤  
#    █▄ █ █▄ ███▀▀▀▀▀▀▀ ╬  
#    ◥ █████ ◤  
#     ══╩══╩═  
#       ╬═╬  
#       ╬═╬ Dream big and start with something small!!!  
#       ╬═╬  
#       ╬═╬ You can do it!  
#       ╬═╬   Let's go...
#    ☻/ ╬═╬   
#   /▌  ╬═╬   
#   / \
# Cherman Seingalt - german.ponce@outlook.com

{
    'name': 'Reporte Diario General',
    'summary': """Reportes Contables MX""",
    'description': """
Reportes Contables comunmente usados en Mexico
==============================================

Este modulo esta enfocado cuando se maneja multicompany y permite consolidar cuentas de las sucursales hacia la empresa central

        Diversos informes segun los requerimientos de Mexico, basados en 13 periodos al año 
        (12 meses naturales y Periodo Inicial), 
        donde el periodo 0 es de apertura/cierre.
        Los informes son:
       - Balanza Mensual de Comprobacion
       - Auxiliar de cuentas (desde la Balanza de comprobacion)
       - Auxiliar de cuentas
       - Configurador de Reportes Personalizados
       - Generador de Reportes Personalizados

    NOTAS IMPORTANTES:
    - Estos reportes funcionan tomando en cuenta lo siguiente:
        + Deben usarse 13 periodos por cada periodo Fiscal.
        + El nombre de los periodos es importante, de manera que deben tener orden alfabetico, por ejemplo:
        
        * 01/2012
        * 02/2012
        * 03/2012
        * 04/2012
        * 05/2012
        * 06/2012
        * 07/2012
        * 08/2012
        * 09/2012
        * 10/2012
        * 11/2012
        * 12/2012
        * 13/2012   => Marcado como periodo de cierre
    """,
    "author" : "German Ponce Dominguez",
    "website" : "https://www.fixdoo.mx",
    'category': 'Account',
    "version"   : "20.0.1.0",
    'depends':
        [
            "account",
            "l10n_mx_edi_account_tree",
            "l10n_mx_edi_period_and_fiscalyear"
        ],
    'data': [
        "security/ir.model.access.csv",
        "views/account_mx_general_ledger_view.xml",        
        "report/report_general_ledger.xml",
    ],
    'license': 'Other proprietary',
}