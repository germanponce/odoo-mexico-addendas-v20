# -*- coding: utf-8 -*-

# Part of Probuse Consulting Service Pvt Ltd. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import base64

import logging
_logger = logging.getLogger(__name__)


class AccountEdiDocument(models.Model):
    _inherit = 'account.edi.document'
    _sql_constraints = [
        (
            'unique_edi_document_by_move_by_format',
             'CHECK(1=1)',
            'Only one edi document by move by format',
        ),
    ]


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    l10n_mx_edi_force_generate_cfdi = fields.Boolean(string='Generate CFDI')

    def action_l10n_mx_edi_force_generate_cfdi(self):
        res = super(AccountBankStatementLine, self).action_l10n_mx_edi_force_generate_cfdi()
        attachment_obj = self.env['ir.attachment'].sudo()
        for rec in self:
            if rec.move_id:
                if rec.move_id.l10n_mx_edi_cfdi_uuid:
                    report_from_action = self.env.ref('l10n_mx_edi.action_report_payment_receipt')
                    ### Este metodo retorna el PDF en B64 ###
                    result, format = report_from_action._render_qweb_pdf([rec.id])
                    # # TODO in trunk, change return format to binary to match message_post expected format
                    result = base64.b64encode(result)
                    
                    move = rec.move_id

                    fname_payment = ""
                    fname = move.company_id.partner_id.vat + '_' + \
                            (move.name and move.name.replace('/','_').replace(' ','') or '')
                    fname_payment = fname

                    attachment_pdf_name = fname_payment+'.pdf'

                    data_attach_pdf = {
                                'name'        : attachment_pdf_name,
                                'datas'       : result,
                                'store_fname' : attachment_pdf_name,
                                'description' : 'Archivo PDF Pago: %s' % self.name ,
                                'res_model'   : 'account.move',
                                'res_id'      : move.id,
                                'type'        : 'binary',
                            }

                    attachment_pdf = attachment_obj.with_context({}).create(data_attach_pdf)

                    attachment_ids = attachment_obj.search([('res_model','=','account.move'),('res_id','=',move.id),('name','ilike','.xml')])
                    if attachment_ids:
                        attachment_xml = attachment_ids[-1]
                        attachment_xml.name = fname_payment+'.xml'

                        #### Envio del XML ####
                        partner_mail = move.partner_id.email or False
                        user_mail = self.env.user.email or False
                        company_id = move.company_id.id
                        address_id = move.partner_id.address_get(['invoice'])['invoice']
                        partner_invoice_address = address_id
                        
                        # adjuntos = attachment_obj.search([('res_model', '=', 'account.payment'), 
                        #                                   ('res_id', '=', payment.id)])
                        # q = True
                        # attachments = []
                        # for attach in adjuntos:
                        #     if q and attach.name.endswith('.xml'):
                        #         attachments.append(attach.id)
                        #         break

                        attachments = []
                        if attachment_xml:
                            attachments.append(attachment_xml.id)
                        mail_compose_message_pool = self.env['mail.compose.message']

                        template_id = self.env.ref('l10n_mx_edi_payment_send_by_mail.email_template_stamement_line_from_invoice_cfdi', False)

                        if template_id:
                            ctx = dict(
                                default_model='account.move',
                                default_res_id=move.id,
                                default_use_template=bool(template_id),
                                default_template_id=template_id.id,
                                default_composition_mode='comment',
                            )
                            ## CHERMAN 
                            # context2 = dict(self._context)
                            # if 'default_journal_id' in context2:
                            #     del context2['default_journal_id']
                            # if 'default_type' in context2:
                            #     del context2['default_type']
                            # if 'search_default_dashboard' in context2:
                            #     del context2['search_default_dashboard']

                            xres = mail_compose_message_pool.with_context(force_onchange=True)._onchange_template_id(template_id=template_id.id, 
                                                                                                         composition_mode=None,
                                                                                                         model='account.move', 
                                                                                                         res_id=move.id)
                            xres['value'].update({'attachment_ids' : [(6, 0, [attachment_xml.id, attachment_pdf.id])]})

                            ### Renombrando los Adjuntos ###
                            for attach in attachment_obj.browse(attachments):
                                if attach.name.endswith('.pdf'):
                                    attach.name = fname_payment+'.pdf'
                            message = mail_compose_message_pool.with_context(ctx).create(xres['value'])
                            _logger.info('Antes de  enviar XML y PDF por mail al cliente - Pago: %s', fname_payment)
                            xx = message.action_send_mail()
                            _logger.info('Despues de  enviar XML y PDF por mail al cliente - Pago: %s', fname_payment)
                            move.send_auto_email = True

class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'


    def _post_payment_edi(self, payments):
        # EXTENDS l10n_mx_edi - rename attachment
        edi_result = super(AccountEdiFormat, self)._post_payment_edi(payments)
        attachment_obj = self.env['ir.attachment']
        for move in payments:
            attachment_xml = edi_result[move].get('attachment', False)
            success_xml = edi_result[move].get('success', False)
            
            fname_payment = ""
            fname = move.company_id.partner_id.vat + '_' + \
                    (move.name and move.name.replace('/','_').replace(' ','') or '')
            fname_payment = fname

            xedi_to_drop = False
            if attachment_xml and success_xml:
                attachment_xml.name = fname_payment+'.xml'
                edi_obj = self.env['account.edi.document']
                edi_cfdi33 = self.env['account.edi.format'].search([('code','=','cfdi_3_3')], limit=1)
                xedi = edi_obj.create({'name' : fname_payment+'.xml',
                                                               'state' : 'sent',
                                                               'edi_format_name' : edi_cfdi33.name,
                                                               'edi_format_id' : edi_cfdi33.id,
                                                               'attachment_id' : attachment_xml.id,
                                                               'move_id'    : move.id
                                                              })
                xedi_to_drop = xedi
            if move.payment_id:
                payment = move.payment_id
                if payment.partner_id.custom_allow_send_mail or payment.partner_id.parent_id.custom_allow_send_mail:
                    partner_mail = payment.partner_id.email or False
                    user_mail = self.env.user.email or False
                    company_id = payment.company_id.id
                    address_id = payment.partner_id.address_get(['invoice'])['invoice']
                    partner_invoice_address = address_id
                    
                    # adjuntos = attachment_obj.search([('res_model', '=', 'account.payment'), 
                    #                                   ('res_id', '=', payment.id)])
                    # q = True
                    # attachments = []
                    # for attach in adjuntos:
                    #     if q and attach.name.endswith('.xml'):
                    #         attachments.append(attach.id)
                    #         break

                    attachments = []
                    if attachment_xml:
                        attachments.append(attachment_xml.id)
                    mail_compose_message_pool = self.env['mail.compose.message']

                    template_id = self.env.ref('account.mail_template_data_payment_receipt', False)

                    if template_id:
                        ctx = dict(
                            default_model='account.payment',
                            default_res_id=payment.id,
                            default_use_template=bool(template_id),
                            default_template_id=template_id.id,
                            default_composition_mode='comment',
                        )
                        ## CHERMAN 
                        # context2 = dict(self._context)
                        # if 'default_journal_id' in context2:
                        #     del context2['default_journal_id']
                        # if 'default_type' in context2:
                        #     del context2['default_type']
                        # if 'search_default_dashboard' in context2:
                        #     del context2['search_default_dashboard']

                        xres = mail_compose_message_pool.with_context(force_onchange=True)._onchange_template_id(template_id=template_id.id, 
                                                                                                     composition_mode=None,
                                                                                                     model='account.payment', 
                                                                                                     res_id=payment.id)
                        try:
                            try:
                                attachments.append(xres['value']['attachment_ids'][0][2][0])
                            except:
                                mail_attachments = (xres['value']['attachment_ids'])
                                for mail_atch in mail_attachments:
                                    if mail_atch[0] == 4:
                                        # attachments.append(mail_atch[1])
                                        attach_br = self.env['ir.attachment'].browse(mail_atch[1])
                                        if attach_br.name != fname_payment+'.pdf':
                                            attach_br.write({'name': fname_payment+'.pdf'})
                                        attachments.append(mail_atch[1])
                        except:
                            _logger.error('No se genero el PDF del CFDI, no se enviara al cliente. - Pago: %s', fname_payment)
                        xres['value'].update({'attachment_ids' : [(6, 0, attachments)]})

                        ### Renombrando los Adjuntos ###
                        for attach in attachment_obj.browse(attachments):
                            if attach.name.endswith('.pdf'):
                                attach.name = fname_payment+'.pdf'
                        message = mail_compose_message_pool.with_context(ctx).create(xres['value'])
                        _logger.info('Antes de  enviar XML y PDF por mail al cliente - Pago: %s', fname_payment)
                        xx = message.action_send_mail()
                        _logger.info('Despues de  enviar XML y PDF por mail al cliente - Pago: %s', fname_payment)
                        payment.send_auto_email = True
                        if xedi_to_drop:
                            xedi_to_drop.unlink()
                # else:
                #     if move.cfdi_custom_date:

                #         cfdi_payment_datetime = move._get_date_time_xml_tz()
                #         res['cfdi_payment_date'] = cfdi_payment_datetime

                #         issued_address = move._get_l10n_mx_edi_issued_address()
                #         tz = move._l10n_mx_edi_get_cfdi_partner_timezone(issued_address)
                #         tz_force = self.env['ir.config_parameter'].sudo().get_param('l10n_mx_edi_tz_%s' % move.journal_id.id, default=None)
                #         if tz_force:
                #             tz = timezone(tz_force)

                #         cfdi_date = str(fields.Datetime.to_string(datetime.now(tz)))
                #         cfdi_date = str(cfdi_date)[0:19].replace(' ','T') if cfdi_date else ''
                #         if cfdi_date:
                #             res['cfdi_date'] = cfdi_date

        return edi_result

# class AccountMove(models.Model):
#     _inherit = "account.move"

#     def _update_payments_edi_documents(self):
#         res = super()._update_payments_edi_documents()
#         for payment in self:
#             # if payment.l10n_mx_edi_cfdi_uuid:
#         return res

class AccountMove(models.Model):
    _inherit = "account.move"
    
    send_auto_email = fields.Boolean('Correo Enviado')


class AccountPayment(models.Model):
    _inherit = "account.payment"
    
    send_auto_email = fields.Boolean('Correo Enviado')

    def action_cancel(self):
        res = super(AccountPayment, self).action_cancel()
        for payment in self:
            payment.send_auto_email = False
        return res

    # def write(self, vals):
    #     ret = super(AccountPayment, self).write(vals)
    #     return ret

    # def action_post(self):
    #     res = super(AccountPayment, self).action_post()
    #     if self.partner_type == 'customer' and self.partner_id.parent_id.custom_allow_send_mail or self.partner_id.custom_allow_send_mail:
    #         template = self.env.ref('account.mail_template_data_payment_receipt', False)
    #         template.send_mail(self.id)
    #     return res