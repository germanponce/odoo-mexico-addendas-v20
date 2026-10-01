MX Reports DIOT (2025)
----------------------

This module extends the DIOT (Declaración Informativa de Operaciones con Terceros) report functionality in Odoo for
Mexican taxpayers. It adds new fields for the 2025 version and ensures the `.txt` file complies with the SAT
requirements for DIOT submissions. This includes handling special cases for border zones (8% tax), identifying
supplier types (national, foreign, global), and validating partner data (RFC, state, etc.).

Currently Supported DIOT 2025 Columns
-------------------------------------

Below is the list of columns from the SAT's official DIOT 2025 structure that this module currently supports.
Note that certain columns are not yet implemented or may not be relevant for most use cases. We plan to add more
columns based on user feedback and evolving requirements.

- **1. Tipo de tercero**
- **2. Tipo de operación**
- **3. Registro Federal de Contribuyentes**
- **4. Número de identificación fiscal (Extranjero)**
- **5. Nombre del extranjero**
- **6. País o jurisdicción de residencia fiscal**
- **7. Especificar lugar de jurisdicción fiscal**
- **8. Valor total actos/actividades pagadas - Región Fronteriza Norte**
- **9. Devol./desc./bonif. - Región Fronteriza Norte**
- **10. Valor total actos/actividades pagadas - Región Fronteriza Sur**
- **11. Devol./desc./bonif. - Región Fronteriza Sur**
- **12. Valor total actos/actividades pagadas - Tasa 16%**
- **13. Devol./desc./bonif. - Tasa 16%**
- **14. Valor total actos/actividades pagadas - Importación bienes tangibles (16%)**
- **15. Devol./desc./bonif. - Importación bienes tangibles (16%)**
- **22. Valor total actos/actividades pagadas - Monto de IVA Tasa 16%**
- **24. Valor total actos/actividades pagadas Importación bienes tangibles (16%)- Monto de IVA Tasa 16% Importación**
- **31. IVA no acreditable - Actividades no objeto - Región Fronteriza Norte**
- **35. IVA no acreditable - Actividades no objeto - Región Fronteriza Sur**
- **36. IVA no acreditable - Proporción - Tasa 16%**
- **37. IVA no acreditable - No cumple requisitos - Tasa 16%**
- **39. IVA no acreditable - Actividades no objeto - Tasa 16%**
- **48. IVA retenido por el contribuyente**
- **50. Actos/actividades exentos (por los que no se pagará IVA)**
- **51. Demás actos/actividades pagados a la tasa 0%**
- **52. Actos/actividades no objeto del IVA en territorio nacional**
- **53. Actos/actividades no objeto del IVA por no contar con establecimiento en territorio nacional**
- **54. Manifiesto de efectos fiscales (01=Sí)**

.. note::
   The numbering above corresponds to the official DIOT 2025 guide from the SAT. Our module may omit
   or rearrange certain columns if they are not yet implemented or not required in most scenarios.
   We plan to support additional columns and scenarios over time, based on user feedback and updates
   to SAT requirements.

Usage
-----

1. **Configure your partners** with the appropriate tax information, including:

   - RFC (Registro Federal de Contribuyentes).
   - Address (especially the state if they apply to border regions).
   - Type of operation and type of third party (national, foreign, global).

2. **Set up the correct tax rates**:

   - For 8% or 16% (including import taxes at 16%), ensure you assign the proper tax tags in the tax configuration,
     particularly for the "Distribution for Refunds" section. The label should include the `"RDA"` suffix,
     for example: `+DIOT: 16% RDA`.
   - This step ensures Odoo correctly identifies refunds or partial credits when generating the DIOT report.

   .. image:: l10n_mx_reports_diot/static/description/tax_configuration_example.png
      :alt: Tax Configuration Example
      :width: 600pt

   - For taxes reporting the tax amount:
     You must add the corresponding tag for tax distribution using the format `+/-DIOT % TAX`. For example:
     `+DIOT: 16% TAX` (this applies to both invoices and credit notes).

   .. image:: l10n_mx_reports_diot/static/description/diot_tax_amount.png
      :alt: Tax Configuration Example
      :width: 600pt

3. **Regenerate tax tags if you already have existing data**:

   - Install the `account_update_tax_tags`_ module:
   - Access **Accounting > Configuration > Settings** and run the **Update tax tags on existing Journal Entries**
     for the period(s) you need to report. This will update existing cash basis entries
     with the correct tags.

   .. image:: l10n_mx_reports_diot/static/description/regenerate_cash_basis_tags.png
      :alt: Update tax tags on existing Journal Entries
      :width: 600pt

4. **Generate the DIOT file**:

   - From the **Accounting** menu (or the corresponding DIOT menu), generate the `.txt` file in UTF-8 encoding
     following SAT requirements.

   .. image:: l10n_mx_reports_diot/static/description/diot_generation.png
      :alt: Diot Generation
      :width: 600pt

5. **Validate or upload** the `.txt` file:
   - Use the SAT's DIOT tool or portal to ensure your operations are correctly reported before final submission.

.. _account_update_tax_tags: https://github.com/odoo/odoo/tree/17.0/addons/account_update_tax_tags

Notes
-----

- For border zones with 8% tax, a warning is displayed if the partner's state (address) is not correctly set.
- The updated structure for the DIOT 2025 requires careful assignment of tax tags (including the RDA suffix for refunds)
  to match the SAT's new reporting fields.


Credits
-------

**Contributors**

* Luis Torres <luis_t@vauxoo.com> (Planner/Developer)

Maintainer
----------

This module is maintained by **Vauxoo**.

A Latin American company that provides training, coaching, development, and implementation of enterprise management systems.
It bases its entire operational strategy on the use of Open Source Software, focusing primarily on Odoo.

.. image:: https://s3.amazonaws.com/s3.vauxoo.com/description_logo.png
   :alt: Company Logo
   :width: 600px
