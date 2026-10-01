# CFDI Compliance Engine MX

**Motor de Compliance Fiscal Preventivo para CFDIs de Proveedores - México**

- **Autor:** ANFEPI - Roberto Requejo Jiménez
- **Website:** https://www.anfepi.com
- **Licencia:** OPL-1 (ver `LICENSE`)
- **Versión:** 19.0.1.0.25+
- **Compatibilidad:** Odoo 15, 16, 17, 18, 19 (Enterprise / Community + l10n_mx)

## ¿Qué hace?

Valida CFDIs de proveedores en el momento exacto en que el XML es adjuntado
a Odoo, **antes** de que entre a la contabilidad o a compras. No espera a la
contabilización, no usa cron jobs, no requiere acción del usuario para
disparar la validación.

## Escenarios cubiertos

1. Factura de proveedor directa desde contabilidad
2. Factura de proveedor desde Orden de Compra
3. XML importado manualmente vía wizard
4. Drag & drop de XML en chatter
5. Integración con Documents/OCR
6. Importación masiva (wizard incluido)

## Características clave

- Motor de reglas pluggable (Strategy + Registry).
- Perfiles de compliance configurables por compañía.
- 4 severidades: INFO / WARNING / ERROR / AUTHORIZATION REQUIRED.
- Soporte completo de **Régimen de Coordinados** (Art. 72-73 LISR).
- Multi-company estricto.
- Bitácora de auditoría inmutable con hash chain SHA-256.
- Panel de compliance OWL en tiempo real.
- API estable para reglas custom de terceros.
- **Cola persistente nativa** del pipeline (`l10n_mx.cfdi.pipeline.job`)
  para procesamiento async resiliente sin dependencias externas.

## Cola persistente (Pipeline Queue)

Al adjuntar un XML CFDI a Odoo, el pipeline de validación se ejecuta
**asíncrono** vía cola persistente — no bloquea el upload del usuario.
El cron `CFDI Compliance: process pipeline job queue` corre cada
minuto y procesa lotes de hasta 20 jobs en paralelo seguro
(`FOR UPDATE SKIP LOCKED`).

**Beneficios vs. threading clásico:**

- **Sobrevive restart de workers** — los jobs viven en DB.
- **Retry automático con backoff** — 30s, 5min, 30min (3 intentos max).
- **Visibilidad UI completa** — menú `CFDI Compliance → Pipeline Queue`
  con badges colores (pendiente / ejecutándose / completado / fallido).
- **Concurrencia segura** entre múltiples workers/crones.
- **Botones manuales** — `Procesar ahora` (skip cron) / `Reintentar`
  (re-encolar failed).
- **Cero dependencias externas** — no requiere queue_job de OCA.

**Configuración:** parámetro de sistema
`l10n_mx_cfdi_compliance.queue_batch_size` (default 20) controla
cuántos jobs procesa por ciclo.

## Instalación

1. Copiar el módulo a `addons_path`.
2. Actualizar lista de aplicaciones.
3. Instalar **CFDI Compliance Engine MX (ANFEPI)**.
4. Configurar perfil por compañía en Ajustes > Compañías > CFDI Compliance.

## Licencia

**Odoo Proprietary License v1.0 (OPL-1)**

Software propietario. Requiere suscripción activa para uso comercial.
Redistribución, modificación y descompilación prohibidas sin autorización
escrita. Ver archivo `LICENSE` para términos completos.

## Contacto

- **Ventas / Información comercial:** info@anfepi.com
- **Soporte técnico (clientes con suscripción):** soporte@anfepi.com
- **Teléfono / WhatsApp:** +52 999 520 0611
- **Sitio web:** https://www.anfepi.com
- **Repositorio:** https://github.com/anfepi-gh/anfepi-mx-modules
