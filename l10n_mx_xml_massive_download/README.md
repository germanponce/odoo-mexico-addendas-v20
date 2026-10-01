# l10n_mx_xml_massive_download

Modulo Odoo para descarga masiva y vinculacion automatica de XMLs del SAT (Mexico).

## Versiones soportadas

Funcionalidad equivalente en las 5 ramas. Una sola fuente de verdad por version.

| Branch | Ultima version | Fresh install validado | Cliente productivo |
|--------|---|---|---|
| [15.0](https://github.com/anfepi-gh/anfepi-mx-modules/tree/15.0) | 15.0.46.39+ | OK | Mitzu |
| [16.0](https://github.com/anfepi-gh/anfepi-mx-modules/tree/16.0) | 16.0.46.39+ | OK | -- |
| [17.0](https://github.com/anfepi-gh/anfepi-mx-modules/tree/17.0) | 17.0.46.40+ | OK | Cosal, Bekook |
| [18.0](https://github.com/anfepi-gh/anfepi-mx-modules/tree/18.0) | 18.0.46.40+ | OK | MIDO |
| [19.0](https://github.com/anfepi-gh/anfepi-mx-modules/tree/19.0) | 19.0.46.53+ | OK | ANFEPI, Vencedor |

## Prerequisitos

### Modulos Odoo requeridos (hard dependencies)

| Modulo | Por que | Si no esta |
|---|---|---|
| `base`, `mail`, `account` | Core Odoo | El modulo no carga |
| `l10n_mx_edi` | Localizacion fiscal Mexico (CFDI) | El modulo no carga |
| `hr_payroll` | Campo `payslip_id` para vincular CFDIs tipo N (Nomina) | El modulo no carga |

**Despachos sin nomina:** instalar `hr_payroll` vacio (es ligero y gratuito). Alternativa futura: bridge module `l10n_mx_xml_massive_download_payroll`.

### Modulos opcionales (soft dependencies)

| Modulo | Que activa |
|---|---|
| `sale` | Busqueda de Sales Orders como documento origen de facturas cliente |
| `purchase` | Busqueda de Purchase Orders como documento origen de facturas proveedor |
| `account_reports` (v15-v18) | Reportes contables integrados (Enterprise) |

Si `sale`/`purchase` no estan instalados, el modulo carga sin errores y omite la busqueda de SO/PO (caso despachos contables). Verificacion runtime con `self.env.get('sale.order')`.

### Dependencias Python externas

- `pdf417gen` - generacion de codigos PDF417 (CBB)

```bash
pip install pdf417gen
```

### Backend xmlsat.anfepi.com

El modulo se conecta a `xmlsat.anfepi.com` para autenticar/descargar XMLs. Cada cliente requiere su **api_key** registrada vinculada a su RFC via VAT match en `res.company`. Sin api_key registrada el modulo retorna 402 al intentar fetch.

## Instalacion

```bash
odoo-bin --stop-after-init -d <database> \
  -i l10n_mx_edi,hr_payroll,l10n_mx_xml_massive_download \
  --without-demo=all
```

O via UI: Apps -> Update Apps List -> buscar "XML Massive Download" -> Instalar.

## Configuracion multi-empresa

### Caso single-tenant (Cosal, Vencedor)

1 res.company controladora + N RFCs internos (fabricas, coordinadas).

- Todos los lotes viven bajo la company controladora.
- Campo `Contribuyente` (RFC) varia por lote, `Empresa` siempre la misma.
- No requiere configuracion especial.

### Caso multi-tenant (ANFEPI, despachos)

N res.companies independientes, una por cliente.

- Cada res.company debe tener su `vat` poblado via `res_partner.vat`.
- `lote.company_id` se auto-resuelve por VAT match (computed-stored) y se valida con `_check_vat_company_consistency`.
- Lotes se crean automaticamente bajo la company correcta del RFC, sin importar que company tenga activa el usuario.

```sql
-- Verificar que cada company tiene VAT seteado
SELECT c.id, c.name, p.vat
  FROM res_company c JOIN res_partner p ON c.partner_id = p.id;

-- Detectar mismatch (deben ser 0 filas):
SELECT lote.id, lote.vat, lc.name FROM account_edi_api_download lote
  JOIN res_company lc ON lote.company_id = lc.id
  JOIN res_partner lcp ON lc.partner_id = lcp.id
  JOIN res_partner cp ON UPPER(cp.vat) = UPPER(lote.vat)
  JOIN res_company c ON c.partner_id = cp.id
 WHERE lote.vat IS NOT NULL AND c.id != lote.company_id;
```

## Funcionalidades clave

### Descarga SAT
- Descarga masiva por lote (rango de fechas configurable).
- Cron auto-sync programable (default cada 2 min).
- Manejo de listas blancas/negras (Art. 69B).
- Re-intento automatico con backoff.

### Vinculacion automatica
- Boton inteligente "XML SAT" en factura visible cuando hay XML SAT vinculado.
- `xml_imported_id` es computed-stored basado en reverse `xml.invoice_id` - se popula en TODOS los flujos (wizard de descarga, matching por UUID, vinculacion manual, REPs).
- Backfill SQL en post-migrate para historicos sin vincular.

### Verificacion SAT
- Estado "Verificado" cruzado contra `ConsultaCFDIService` del SAT.
- Deteccion de duplicados (cancelaciones + reemisiones).
- Conciliacion SAT vs Odoo (reporte profesional).

### Reportes de Complementos de Pago (Clientes + Proveedores)

2 reportes especializados ubicados en **Contabilidad > XML SAT** debajo
de "Reporte de Conciliacion". Validan que toda factura PPD con pago
tenga su correspondiente Complemento de Pago (REP) y que coincida entre
Odoo y SAT.

**Implementacion:** SQL VIEW (no tabla real) — siempre live, se
reconstruye en cada solicitud sin cron de refresh. Permite filtros
nativos, agrupacion, export CSV/XLSX.

**Validaciones cubiertas (9):**
1. Factura en Odoo
2. Factura en SAT
3. Complemento en Odoo
4. Complemento en SAT
5. UUID factura coincide entre Odoo y SAT
6. UUID complemento coincide entre Odoo y SAT
7. Importe pagado coincide (tolerancia 0.01 MXN)
8. Saldo insoluto visible
9. Estados (Odoo + SAT factura + SAT complemento) + complementos cancelados

**Semaforo Resultado:**
- 🟢 Verde — todo coincide
- 🟡 Amarillo — diferencia ≤ 0.01 MXN o cancelado en ambos sistemas
- 🔴 Rojo — falta complemento, UUID distinto, diferencia > 0.01 MXN,
  pago sin REP, o cancelado solo en uno de los lados

**Filtros default:** ultimos 90 dias (configurable via search).
Filtros rapidos: Solo rojos, Solo amarillos, Solo verdes, Con diferencias.
Agrupacion: Resultado, Cliente/Proveedor, Estado SAT, Empresa.

**Click navegacion:** las columnas Factura y Complemento son Many2one
directos al `account.move` / `account.payment` — click abre el record.

**Deteccion PPD multipath** (importante para bases historicas):
1. `payment_method = 'PPD'` (nuestro campo, solo se popula desde wizard SAT)
2. `l10n_mx_edi_payment_method_id.code = '99'` (Por definir = PPD tipico)
3. Heuristica: `invoice_date_due > invoice_date` (vencimiento posterior)

**Performance:** migration `19.0.46.49` (y equivalente por rama) crea
4 indices auxiliares:
- `idx_am_ppd_out` — account_move filtros PPD
- `idx_aedxs_doctype_payment` — XML SAT por document_type='P'
- `idx_aedxs_invoice_cfditype` — XML SAT por invoice_id+cfdi_type
- `idx_am_stored_uuid` — account_move por UPPER(stored_sat_uuid)

## Tests

```bash
odoo-bin --stop-after-init -d <database> \
  -u l10n_mx_xml_massive_download \
  --test-tags l10n_mx_xml_massive_download
```

Tests cubren:
- Computed `xml_imported_id` en todos los flujos de vinculacion.
- Resolucion de `lote.company_id` por VAT match (multi-tenant).
- Constraint `_check_vat_company_consistency`.

## Limitaciones conocidas v15/v16

- `<list>` tag no soportado en views (usar `<tree>`).
- Expresiones Python en `invisible="..."` no soportadas (usar `attrs="{'invisible': [...]}"`).
- `l10n_mx_edi_cfdi_sat_state` no existe en `account.payment` - REP view omite columna derecha.
- `post_init_hook` recibe `(cr, registry)` (compatibilizado en codigo).

## Workflow de deploy seguro

1. Trabajar en branch local
2. **Fresh install en Docker desktop v15-v19** (zero error)
3. Push a `anfepi-gh/anfepi-mx-modules`
4. Cliente: pull / odoo.sh rebuild -> migration post-migrate auto-corre

**Vencedor productivo:** requiere autorizacion explicita del equipo de Sistemas antes de tocar. Siempre pruebas primero.

## Licencia

OPL-1 (Odoo Proprietary License v1.0). Subscription required.

---

ANFEPI - soporte@anfepi.com - +52 999 520 0611
