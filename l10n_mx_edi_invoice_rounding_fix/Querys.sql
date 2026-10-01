update pos_order set account_move=null,l10n_mx_edi_cfdi_state='' where create_date >= '2024-07-21';

delete from l10n_mx_edi_document where id in 
(select document_id from l10n_mx_edi_pos_order_document_ids_rel);