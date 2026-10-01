/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

// Herencia --
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";


patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos_simple_question = false;
    },
      
    captureChange () {
                this.pos_simple_question = document.getElementsByName("pos_simple_question")[0].value;
                this.currentOrder.pos_simple_question = this.pos_simple_question;
    },

});
