# Rename: l10n_mx_xml_masive_download -> l10n_mx_xml_massive_download (.48.0)

Incluye TODO .47.7 (fix IVA cross-empresa + boton Deshacer) + rename. Modelos/TABLAS
NO cambian: CERO migracion de datos de negocio. Solo metadatos del modulo.

## DESPLIEGUE 2 PASOS OBLIGATORIO (para BD con el modulo ya instalado)
### Paso 1 - Pre-paso SQL (con codigo VIEJO corriendo):
  BEGIN;
  UPDATE ir_module_module            SET name=  'l10n_mx_xml_massive_download' WHERE name=  'l10n_mx_xml_masive_download';
  UPDATE ir_model_data               SET module='l10n_mx_xml_massive_download' WHERE module='l10n_mx_xml_masive_download';
  UPDATE ir_module_module_dependency SET name=  'l10n_mx_xml_massive_download' WHERE name=  'l10n_mx_xml_masive_download';
  COMMIT;
### Paso 2 - Desplegar codigo renombrado + upgrade:
  odoo-bin -u l10n_mx_xml_massive_download,l10n_mx_cfdi_compliance --stop-after-init
