# CFDI 4.0 - Envío de XML Manual (Odoo 18)

## Descripción

Migración del módulo de envío manual de XML CFDI a Odoo 18, adaptado a la nueva estructura `l10n_mx_edi.document`.

## Características Principales

- ✅ **XML Personalizado**: Permite adjuntar un archivo XML personalizado que se enviará directamente al PAC
- ✅ **Sin Generación QWeb**: Cuando se usa XML personalizado, omite la generación automática del CFDI
- ✅ **Validación XML**: Valida la estructura del XML antes del envío
- ✅ **Compatibilidad Odoo 18**: Adaptado a la nueva arquitectura l10n_mx_edi.document
- ✅ **Interfaz Mejorada**: Vistas y botones intuitivos para gestionar XML personalizado

## Instalación

1. Coloca el módulo en tu directorio de addons
2. Actualiza la lista de módulos
3. Instala el módulo `l10n_mx_edi_force_send_xml`

## Dependencias

- `account`
- `l10n_mx_edi` (Odoo Enterprise)

## Uso

### Adjuntar XML Personalizado

1. Ve a una factura que requiera CFDI
2. Haz clic en el botón "Adjuntar XML" en el área de botones
3. Marca "Usar XML Personalizado"
4. Sube tu archivo XML
5. Valida el XML (opcional pero recomendado)
6. Guarda los cambios

### Enviar CFDI con XML Personalizado

1. Una vez adjuntado el XML personalizado, aparecerá un botón "XML Personalizado"
2. Haz clic en este botón para enviar el CFDI usando tu XML
3. El sistema validará y enviará el archivo directamente al PAC

### Gestión de Documentos CFDI

- Los documentos con XML personalizado aparecen marcados en las vistas
- Puedes validar el XML en cualquier momento
- Mantiene historial de todos los intentos de envío

## Cambios Principales vs Versión Anterior

### Arquitectura
- ✅ Migrado de `account.edi.document` a `l10n_mx_edi.document`
- ✅ Uso del nuevo método `_send_api()` de Odoo 18
- ✅ Compatibilidad con el nuevo flujo de timbrado

### Funcionalidades Nuevas
- ✅ Validación automática de XML al subir archivo
- ✅ Indicadores visuales en vistas de lista y kanban
- ✅ Filtros de búsqueda para facturas con XML personalizado
- ✅ Mejores mensajes de error y notificaciones

### Mejoras de UX
- ✅ Botones más intuitivos en la vista de factura
- ✅ Wizard dedicado para adjuntar XML
- ✅ Alertas informativas sobre el estado del XML

## Estructura del Código

```
l10n_mx_edi_force_send_xml/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── l10n_mx_edi_document.py  # Lógica principal
│   └── account_move.py          # Extensión de facturas
├── views/
│   ├── l10n_mx_edi_document_views.xml  # Vistas de documentos
│   └── account_move_views.xml          # Vistas de facturas
└── security/
    └── ir.model.access.csv      # Permisos
```

## Flujo Técnico

1. **Subida de XML**: El usuario adjunta un archivo XML en el documento CFDI
2. **Validación**: El sistema valida que sea XML válido con estructura CFDI
3. **Activación**: Se marca el flag `use_custom_xml`
4. **Envío**: Al enviar CFDI, se detecta el XML personalizado
5. **Procesamiento**: Se omite la generación QWeb y se usa el XML adjunto
6. **Firma**: Se firma el XML con el certificado de la empresa
7. **PAC**: Se envía directamente al PAC para timbrado
8. **Resultado**: Se almacena el XML timbrado como adjunto

## Validaciones

- ✅ XML bien formado
- ✅ Estructura CFDI básica
- ✅ Presencia de nodos obligatorios
- ✅ Compatibilidad con certificado

## Logs y Debugging

El módulo incluye logging detallado para facilitar el debugging:

```python
_logger.info("=== Procesando XML personalizado ===")
_logger.info("XML personalizado decodificado, tamaño: %s bytes", len(xml_content))
_logger.info("Enviando XML personalizado al PAC: %s", pac_name)
```

## Soporte y Mantenimiento

**Autor**: German Ponce Dominguez  
**Email**: german.poncce@outlook.com  
**Website**: http://poncesoft.blogspot.com

## Licencia

LGPL-3

## Changelog

### v18.0.1.0.0
- ✅ Migración inicial a Odoo 18
- ✅ Adaptación a l10n_mx_edi.document
- ✅ Nuevas validaciones y controles
- ✅ Mejora de interfaz de usuario