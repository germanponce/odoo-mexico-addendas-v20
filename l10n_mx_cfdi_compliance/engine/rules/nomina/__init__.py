# -*- coding: utf-8 -*-
# Copyright 2026 ANFEPI - Roberto Requejo Jimenez | License OPL-1
# https://www.anfepi.com — Subscription required, redistribution prohibited.
# Reglas de cumplimiento para CFDI de Nomina (Complemento Nomina 1.2).
# Etapa 1: A (internas XML) + F (cruce contable). Las clases se auto-registran
# en CfdiRuleRegistry via el decorador @cfdi_rule al importarse.
# Etapa 2: cruces vs RRHH — empleado (B), contrato (C), recibo (D), lote (E).
# Soft-dependency + opt-in (ver _hr.py): se auto-omiten sin hr.* instalado.
from . import internas
from . import contable
from . import empleado
from . import contrato
from . import recibo
from . import lote
