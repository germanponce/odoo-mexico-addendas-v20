/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * Compliance Panel Widget.
 * Suscribe al canal `l10n_mx_cfdi_compliance/validated` de bus.bus
 * para refrescar el panel del CFDI cuando termina el pipeline.
 */
export class CompliancePanel extends Component {
    static template = "l10n_mx_cfdi_compliance.CompliancePanel";
    static props = {
        record: Object,
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.bus = useService("bus_service");
        this.notification = useService("notification");
        this.state = useState({
            score: this.props.record.data.compliance_score || 0,
            status: this.props.record.data.compliance_state || "pending",
        });
        onWillStart(() => {
            this.bus.addChannel("l10n_mx_cfdi_compliance/validated");
            this.bus.addEventListener("notification", (ev) => this._onBus(ev));
        });
    }

    _onBus(ev) {
        const notifs = ev.detail || [];
        for (const n of notifs) {
            if (n.type !== "l10n_mx_cfdi_compliance/validated") continue;
            const payload = n.payload || {};
            if (payload.cfdi_id === this.props.record.resId) {
                this.state.score = payload.score;
                this.state.status = payload.state;
                this.notification.add(
                    `CFDI ${payload.uuid || ""}: ${payload.state} (${payload.score}/100)`,
                    { type: payload.state === "passed" ? "success" : "warning" },
                );
            }
        }
    }

    get badgeClass() {
        const map = {
            passed: "badge text-bg-success",
            authorized: "badge text-bg-success",
            warning: "badge text-bg-warning",
            authorization_required: "badge text-bg-info",
            blocked: "badge text-bg-danger",
            rejected: "badge text-bg-danger",
            error: "badge text-bg-dark",
            pending: "badge text-bg-secondary",
            validating: "badge text-bg-secondary",
        };
        return map[this.state.status] || "badge text-bg-secondary";
    }
}

registry.category("view_widgets").add("cfdi_compliance_panel", {
    component: CompliancePanel,
});
