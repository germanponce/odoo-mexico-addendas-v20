update pos_order set account_move=null,l10n_mx_edi_cfdi_state='', state='paid' where create_date >= '2025-02-14';

delete from l10n_mx_edi_document where id in 
(select document_id from l10n_mx_edi_pos_order_document_ids_rel);


/* Solo de un Pedido*/
update pos_order set account_move=null,l10n_mx_edi_cfdi_state='', state='paid' where id in (352347);

delete from l10n_mx_edi_document where id in 
(select document_id from l10n_mx_edi_pos_order_document_ids_rel where pos_order_id in (352347));


