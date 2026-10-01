from odoo import models
from odoo.exceptions import RedirectWarning


class L10nMXReportHandler(models.AbstractModel):
    _inherit = "l10n_mx.report.handler"

    def action_get_diot_txt(self, options):
        report = self.env["account.report"].browse(options["report_id"])
        partner_and_values_to_report = self._get_diot_values_per_partner(report, options)

        self.check_for_error_on_partner(list(partner_and_values_to_report))

        lines = []
        partner_wo_state = self.env["res.partner"]
        for partner, values in partner_and_values_to_report.items():
            if not any(
                values.get(x)
                for x in (
                    "paid_16",
                    "paid_16_non_cred",
                    "paid_8",
                    "paid_8_non_cred",
                    "importation_16",
                    "paid_0",
                    "exempt",
                    "withheld",
                    "refunds",
                )
            ):
                # don't report if there isn't any amount to report
                continue

            is_foreign_partner = values["third_party_code"] != "04"
            paid_8 = values.get("paid_8")
            rda_8 = values.get("paid_8_rda")
            if (paid_8 or rda_8) and (
                not partner.state_id
                or (
                    not partner._check_l10n_mx_diot_southern_border()
                    and not partner._check_l10n_mx_diot_northern_border()
                )
            ):
                partner_wo_state |= partner

            data = [""] * 54
            data[0] = values["third_party_code"]  # Supplier Type
            data[1] = values["operation_type_code"]  # Operation Type
            data[2] = values["partner_vat_number"] if not is_foreign_partner else ""  # Tax Number
            data[3] = values["partner_vat_number"] if is_foreign_partner else ""  # Tax Number for Foreigners
            data[4] = (
                "".join(self.str_format(partner.name)).encode("utf-8").strip().decode("utf-8")
                if is_foreign_partner
                else ""
            )  # Name
            data[5] = values["country_code"] if is_foreign_partner else ""  # Country
            data[6] = (
                "".join(self.str_format(values["partner_nationality"])).encode("utf-8").strip().decode("utf-8")
                if is_foreign_partner
                else ""
            )  # Nationality
            data[7] = (
                round(float(values.get("paid_8", 0))) or "" if partner._check_l10n_mx_diot_northern_border() else ""
            )  # Actos pagados RFN
            data[8] = (
                abs(round(float(values.get("paid_8_rda", 0)))) or ""
                if partner._check_l10n_mx_diot_northern_border()
                else ""
            )  # Dev, desc y bon RFN
            data[9] = (
                round(float(values.get("paid_8", 0))) or "" if partner._check_l10n_mx_diot_southern_border() else ""
            )  # Actos pagados RFS
            data[10] = (
                abs(round(float(values.get("paid_8_rda", 0)))) or ""
                if partner._check_l10n_mx_diot_southern_border()
                else ""
            )  # Dev, desc y bon RFS
            data[11] = round(float(values.get("paid_16", 0))) or ""  # Base 16%
            data[12] = abs(round(float(values.get("paid_16_rda", 0)))) or ""  # Dev, desc y bon base 16%
            data[13] = round(float(values.get("importation_16", 0))) or ""  # Importaciones tangibles 16%
            data[14] = (
                abs(round(float(values.get("importation_16_rda", 0)))) or ""
            )  # Dev, desc y bon importaciones tangibles 16%
            data[15] = ""  # Importaciones intangibles 16%
            data[16] = ""  # Dev, desc y bon importaciones intangibles 16%
            data[21] = round(float(values.get("tax_paid_16", 0))) or ""  # Monto IVA tasa del 16%
            data[23] = round(float(values.get("tax_importation_16", 0))) or ""  # Monto IVA importaciones del 16%
            data[47] = abs(round(float(values.get("withheld", 0)))) or ""  # Iva retenido
            data[49] = round(float(values.get("exempt", 0))) or ""  # Exentos
            data[50] = round(float(values.get("paid_0", 0))) or ""  # Base 0%
            data[53] = "01"  # Manifiesto

            lines.append("|".join(str(d) for d in data))

        if partner_wo_state:
            action_error = {
                "name": self.env._("Partner missing informations"),
                "type": "ir.actions.act_window",
                "res_model": "res.partner",
                "view_mode": "list",
                "views": [(False, "list"), (False, "form")],
                "domain": [("id", "in", partner_wo_state.ids)],
            }
            msg = self.env._(
                "The report cannot be generated because the following partners do not have a valid state for the 8%% "
                "(border) tax."
            )
            raise RedirectWarning(msg, action_error, self.env._("See the list of partners"))

        diot_txt_result = "\n".join(lines)
        return {
            "file_name": report.get_default_report_filename(options, "txt"),
            "file_content": diot_txt_result.encode(),
            "file_type": "txt",
        }
