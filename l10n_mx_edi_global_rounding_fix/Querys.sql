update pos_order set account_move=null,l10n_mx_edi_cfdi_state='' where create_date >= '2024-07-21';

delete from l10n_mx_edi_document where id in 
(select document_id from l10n_mx_edi_pos_order_document_ids_rel);


/* Corrige los errores de metodos de formas de pago */
update pos_order set payment_tpv_id=pos_payment_method.l10n_mx_edi_payment_method_id from pos_payment_method join pos_payment on pos_payment_method.id=pos_payment.payment_method_id where pos_payment.pos_order_id = pos_order.id
and pos_order.create_date between '2024-06-01' and '2025-01-01';