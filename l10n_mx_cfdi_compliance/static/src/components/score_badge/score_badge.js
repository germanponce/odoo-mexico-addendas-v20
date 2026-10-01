/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

export class ScoreBadge extends Component {
    static template = "l10n_mx_cfdi_compliance.ScoreBadge";
    static props = { ...Component.props, value: { type: Number, optional: true } };

    get cssClass() {
        const v = this.props.value || 0;
        if (v >= 80) return "badge text-bg-success";
        if (v >= 60) return "badge text-bg-warning";
        return "badge text-bg-danger";
    }
}

registry.category("fields").add("cfdi_score_badge", { component: ScoreBadge });
