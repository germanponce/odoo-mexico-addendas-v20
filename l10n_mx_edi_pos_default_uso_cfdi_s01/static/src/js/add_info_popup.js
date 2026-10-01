/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

// Herencia EDI POS --
import { AddInfoPopup } from '@l10n_mx_edi_pos/app/add_info_popup/add_info_popup';
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";

patch(AddInfoPopup.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        const order = this.props.order;
        const partner = order.get_partner()
        // when opening the popup for the first time, both variables are undefined !
        this.state = useState({
            l10n_mx_edi_usage: partner?.l10n_mx_edi_usage || order.l10n_mx_edi_usage || 'S01',
            l10n_mx_edi_cfdi_to_public: !!order.l10n_mx_edi_cfdi_to_public,
        });
    }


});

