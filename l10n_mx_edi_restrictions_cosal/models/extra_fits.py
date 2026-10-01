# -*- coding: utf-8 -*-
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


from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

#### Gestión Zona Horaria ####

from datetime import datetime
from pytz import timezone
import pytz
import time

import logging
_logger = logging.getLogger(__name__)

format_date = "%Y-%m-%d"


class AccountMove(models.Model):
    _inherit ='account.move'

    # def action_post(self):
    #     for rec in self:
    #         if rec.move_type == 'out_invoice':
    #             if rec.invoice_general_public and rec.partner_id.name == 'PUBLICO EN GENERAL':
    #                 if rec.l10n_mx_edi_payment_method_id and rec.l10n_mx_edi_payment_method_id.code == '99':
    #                     raise UserError("No se puede utilizar la Forma de Pago 'Por definir' cuando facturamos a publico en general.")
    #                 # if rec.l10n_mx_edi_payment_policy == 'PPD':
    #                 #     raise UserError("No se puede utilizar el metodo de Pago PPD cuando facturamos a publico en general.")

    #     res = super(AccountMove, self).action_post()
    #     return res


    def action_prepost(self):
        for rec in self:
            if rec.move_type == 'out_invoice':
                # Si la factura cliente es PUE que forma de pago no deje poner Por definir y que seleccionen cualquiera del resto de opciones y 
                # si la factura cliente es PPD que solo deje seleccionar Por Definir. 

                # invoice_date = datetime.today()
                # invoice_date_due = datetime.today()
                # payment_term_lines_count = 0
                # if rec.invoice_date:
                #     invoice_date = rec.invoice_date
                # if rec.invoice_payment_term_id.line_ids:
                #     payment_term_lines_count  = len(rec.invoice_payment_term_id.line_ids)
                # if rec.invoice_date_due:
                #     invoice_date_due = rec.invoice_date_due
                l10n_mx_edi_payment_policy = rec.l10n_mx_edi_payment_policy
                if not rec.invoice_date:
                    rec.invoice_date = fields.Date.context_today(rec)
                if rec.is_invoice(include_receipts=True) \
                and rec.invoice_date_due \
                and rec.invoice_date:

                    # By default PUE means immediate payment and then, no need to send the payments to
                    # the SAT except if you explicitely send them.
                    l10n_mx_edi_payment_policy = 'PUE'

                    # In CFDI 3.3 - rule 2.7.1.43 which establish that
                    # invoice payment term should be PPD as soon as the due date
                    # is after the last day of  the month (the month of the invoice date).
                    if (
                        rec.move_type == 'out_invoice'
                        and (
                            rec.invoice_date_due.month > rec.invoice_date.month
                            or rec.invoice_date_due.year > rec.invoice_date.year
                            or len(rec.invoice_payment_term_id.line_ids) > 1
                        )
                    ):
                        l10n_mx_edi_payment_policy = 'PPD'
                if l10n_mx_edi_payment_policy == 'PUE' and rec.l10n_mx_edi_payment_method_id.code  == '99':
                    raise UserError("En facturas PUE no es posible utilizar la forma de Pago por Definir.")
                if l10n_mx_edi_payment_policy == 'PPD' and rec.l10n_mx_edi_payment_method_id.code  != '99':
                    raise UserError("En facturas PPD solo podemos utilizar la forma de Pago por Definir.") 

        res = super(AccountMove, self).action_prepost()
        return res