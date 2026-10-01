WITH sat_results AS (
    SELECT 
        COUNT(*) as total_facturas,
        COALESCE(SUM(subtotal), 0) as importe_sin_iva,
        COALESCE(COUNT(CASE WHEN sat_estado = 'vigente' THEN 1 ELSE NULL END), 0) as facturas_vigentes_auditor,
        COALESCE(SUM(CASE WHEN sat_estado = 'vigente' THEN subtotal ELSE 0 END), 0) as importe_vigente_auditor,
        COALESCE(COUNT(CASE WHEN sat_estado = 'cancelado' THEN 1 ELSE NULL END), 0) as facturas_canceladas_auditor,
        COALESCE(SUM(CASE WHEN sat_estado = 'cancelado' THEN subtotal ELSE 0 END), 0) as importe_cancelado_auditor
    
    FROM 
        account_cfdi acfdi
    JOIN 
        res_company rc ON rc.id = acfdi.company_id
    JOIN 
        res_partner rp_acfdi ON rc.partner_id = rp_acfdi.id
    WHERE 
        acfdi.tipo_cfdi IN ('INGRESO', 'I')  -- Filtrar Registros de Ingreso
        AND acfdi.rfc_emisor = rp_acfdi.vat
        AND (acfdi.fecha_emision AT TIME ZONE 'UTC-5') BETWEEN '2022-01-01'::date AND '2024-08-31'::date
),
odoo_results AS (
    SELECT 
        COUNT(*) as total_facturas,
        COALESCE(SUM(amount_untaxed), 0) as importe_sin_iva,
        COALESCE(COUNT(CASE WHEN state = 'posted' THEN 1 ELSE NULL END), 0) as facturas_vigentes_odoo,
        COALESCE(SUM(CASE WHEN state = 'posted' THEN amount_untaxed ELSE 0 END), 0) as importe_vigente_odoo,
        COALESCE(COUNT(CASE WHEN state = 'cancel' THEN 1 ELSE NULL END), 0) as facturas_canceladas_odoo,
        COALESCE(SUM(CASE WHEN state = 'cancel' THEN amount_untaxed ELSE 0 END), 0) as importe_cancelado_odoo
    
    FROM 
        account_move
    WHERE 
        move_type = 'out_invoice'
        AND (invoice_date AT TIME ZONE 'UTC-5') BETWEEN '2022-01-01'::date AND '2024-08-31'::date
)

SELECT 
    'SAT' as descripcion,
    sat_results.total_facturas,
    sat_results.importe_sin_iva,
    sat_results.facturas_vigentes_auditor as facturas_vigentes,
    sat_results.importe_vigente_auditor as importe_vigente,
    sat_results.facturas_canceladas_auditor as facturas_canceladas,
    sat_results.importe_cancelado_auditor as importe_cancelado
FROM sat_results

UNION ALL

SELECT 
    'Odoo' as descripcion,
    odoo_results.total_facturas,
    odoo_results.importe_sin_iva,
    odoo_results.facturas_vigentes_odoo as facturas_vigentes,
    odoo_results.importe_vigente_odoo as importe_vigente,
    odoo_results.facturas_canceladas_odoo as facturas_canceladas,
    odoo_results.importe_cancelado_odoo as importe_cancelado
FROM odoo_results

UNION ALL

SELECT 
    'Diferencia' as descripcion,
    sat_results.total_facturas - odoo_results.total_facturas as total_facturas,
    sat_results.importe_sin_iva - odoo_results.importe_sin_iva as importe_sin_iva,
    sat_results.facturas_vigentes_auditor - odoo_results.facturas_vigentes_odoo as facturas_vigentes,
    sat_results.importe_vigente_auditor - odoo_results.importe_vigente_odoo as importe_vigente,
    sat_results.facturas_canceladas_auditor - odoo_results.facturas_canceladas_odoo as facturas_canceladas,
    sat_results.importe_cancelado_auditor - odoo_results.importe_cancelado_odoo as importe_cancelado
FROM sat_results, odoo_results;
