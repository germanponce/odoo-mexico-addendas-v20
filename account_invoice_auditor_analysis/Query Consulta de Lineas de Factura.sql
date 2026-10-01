WITH invoice_lines AS (
    SELECT
        ai.id AS factura_id,
        ai.name AS numero_factura,
        ai.invoice_date AS fecha_factura,
        ai.move_type AS tipo_documento,
        CASE 
            WHEN ai.move_type = 'out_invoice' THEN 
                '1'
            ELSE '2' 
        END AS tipo_operacion,
        acj.name AS diario,
        ai.amount_total AS total_factura,
        rp.name AS nombre_partner,
        rp.vat AS rfc_partner,
        rp.ref AS nombre_comercial,
        bc.name AS nombre_branch,
        pph.name AS plan_hotel,
        rp.city_operation_work as ciudad_donde_opera,
        psg.name as grupo,
        CASE 
            WHEN rp.is_driver = True THEN 
                'Sí'
            ELSE '' 
        END AS es_chofer,
        CASE 
            WHEN rp.is_salesman_manager = True THEN 
                'Sí'
            ELSE '' 
        END AS es_ejecutivo_ventas,
        CASE 
            WHEN rp.is_salesman_collection = True THEN 
                'Sí'
            ELSE '' 
        END AS es_ejecutivo_cobranza,
        pfb.name AS unidad_financiera,
        pchc.name AS canal,
        pschc.name AS subcanal,
        pcsg.name AS segmento_de_consumo,
        ail.id AS factura_linea_id,
        ail.name AS descripcion_producto,
        COALESCE(pt.name->>'es_MX', pt.name->>'es_ES', pt.name->>'en_US') AS nombre_producto,
        pt.default_code AS referencia_interna_producto,
        pp.barcode AS codigo_barras_producto,
        pc.complete_name AS nombre_categoria_producto,
        ail.quantity AS cantidad_producto,
        ail.price_unit AS precio_unitario,
        ail.x_studio_unitario_sin_impuestos AS precio_unitario_sin_impuestos,
        ail.price_subtotal AS subtotal,
        ARRAY_TO_STRING(ARRAY_AGG(DISTINCT at.name), ', ') AS impuestos_en_linea,
        ai.invoice_origin AS origen_factura,
        SUM(CASE 
            WHEN at.name LIKE '%IVA%' THEN 
               ail.price_subtotal
            ELSE 0 
        END) AS base_sin_impuestos,
        SUM(CASE 
            WHEN at.name LIKE '%IVA%' THEN 
              ail.price_subtotal * (at.amount / 100.0)
            ELSE 0 
        END) AS monto_iva,
        SUM(CASE 
            WHEN at.name LIKE '%IEPS%' THEN 
                ail.price_subtotal * (at.amount / 100.0)
            ELSE 0 
        END) AS monto_ieps,

        SUM(CASE 
            WHEN at.name LIKE '%IVA%' THEN 
              at.amount
            ELSE 0 
        END) AS porcentaje_iva,
        SUM(CASE 
            WHEN at.name LIKE '%IEPS%' THEN 
                at.amount
            ELSE 0 
        END) AS porcentaje_ieps,
        ail.price_total AS monto_total,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM sale_order_line_invoice_rel solir
                WHERE solir.invoice_line_id = ail.id
            ) THEN 'Orden de Venta (SO)'
            WHEN EXISTS (
                SELECT 1 FROM pos_order po
                WHERE po.account_move = ai.id
            ) THEN 'Punto de Venta (POS)'
            ELSE ''
        END AS tipo_venta
    FROM 
        account_move_line ail
    JOIN 
        account_move ai ON ail.move_id = ai.id
    JOIN 
        res_partner rp ON ai.partner_id = rp.id
    LEFT JOIN
        partner_plan_hotel pph on pph.id = rp.plan_hotel_id
    LEFT JOIN
        partner_segment_group psg on psg.id = rp.partner_group_id

    LEFT JOIN
        partner_financial_branch pfb on pfb.id = rp.financial_branch_id
    LEFT JOIN
        partner_channel_comercial pchc on pchc.id = rp.comercial_channel_id
    LEFT JOIN
        partner_subchannel_comercial pschc on pschc.id = rp.comercial_subchannel_id
    LEFT JOIN
        partner_consumption_segment pcsg on psg.id = rp.consumption_segment_id

    JOIN 
        account_journal acj ON acj.id = ai.journal_id
    JOIN 
        product_product pp ON ail.product_id = pp.id
    JOIN 
        product_template pt ON pp.product_tmpl_id = pt.id
    LEFT JOIN 
        res_branch bc ON rp.branch_id = bc.id
    LEFT JOIN 
        product_category pc ON pt.categ_id = pc.id
    LEFT JOIN 
        account_move_line_account_tax_rel amltr ON ail.id = amltr.account_move_line_id
    LEFT JOIN 
        account_tax at ON amltr.account_tax_id = at.id
    WHERE 
        ai.move_type IN ('out_invoice', 'out_refund')  -- Filtrar facturas de venta y reembolsos
        AND ai.state = 'posted'
        AND ail.display_type = 'product' -- Filtrar solo líneas de producto
        AND acj.type = 'sale'
        AND acj.report_invoice_line_access = True
    GROUP BY 
        ai.id, ail.id, rp.name, rp.vat, rp.ref, ai.invoice_date, ai.name,
        pt.default_code, pt.name, ail.name, pp.barcode, ail.price_unit, ail.x_studio_unitario_sin_impuestos,
        ail.quantity, 
        bc.name, pc.complete_name, ai.move_type, acj.name, pph.name, rp.city_operation_work,
        psg.name, rp.is_driver, rp.is_salesman_manager, rp.is_salesman_collection,
        ai.invoice_origin,
        pfb.name, pchc.name, pschc.name, pcsg.name
    ORDER BY ail.id desc
)
SELECT 
        factura_id,
        numero_factura,
        fecha_factura,
        tipo_documento,
        tipo_operacion,
        diario,
        total_factura,
        nombre_partner,
        rfc_partner,
        nombre_comercial,
        nombre_branch,
        plan_hotel,
        ciudad_donde_opera,
        grupo,
        es_chofer,
        es_ejecutivo_ventas,
        es_ejecutivo_cobranza,
        unidad_financiera,
        canal,
        subcanal,
        segmento_de_consumo,
        factura_linea_id,
        descripcion_producto,
        nombre_producto,
        referencia_interna_producto,
        codigo_barras_producto,
        nombre_categoria_producto,
        cantidad_producto,
        precio_unitario,
        precio_unitario_sin_impuestos,
        subtotal,
        impuestos_en_linea,
        base_sin_impuestos,
        monto_iva,
        monto_ieps,
        porcentaje_iva,
        porcentaje_ieps,
        monto_total,
        origen_factura,
        tipo_venta
FROM 
    invoice_lines;
