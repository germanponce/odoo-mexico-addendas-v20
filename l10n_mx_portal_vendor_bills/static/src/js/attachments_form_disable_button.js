odoo.define('l10n_mx_portal_vendor_bills.attachments_form_disable_button', function (require) {
"use strict";

console.log("########### CARGANDO >>>>>>>>>> ");

require('web.dom_ready');
var core = require('web.core');
var ajax = require('web.ajax');
var publicWidget = require('web.public.widget');

publicWidget.registry.upload_attachments_bill = publicWidget.Widget.extend({
    selector: '#o_website_form_portal_vendor_upload_files',
    events: {
        'click #o_website_form_portal_vendor_upload_files': 'DisableButtonOnClick',
    },
    DisableButtonOnClick: function (ev) {
        console.log("Estamos desactivando el boton ..................");
        ev.preventDefault();
        var $target = $(ev.target);
        $target.prop('disabled', true);
     },
});

return publicWidget.registry.upload_attachments_bill;


/*publicWidget.registry.upload_attachments_bill = publicWidget.Widget.extend({
    selector: '.btn_upload_attachments',
    events: {
        'click #o_website_form_portal_vendor_upload_files': 'DisableButtonOnClick',
    },
     DisableButtonOnClick: function (ev) {
        console.log("Estamos desactivando el boton ..................");
        ev.preventDefault();
        var $target = $(ev.target);
        $target.prop('disabled', true);
     },
});
return publicWidget.registry.upload_attachments_bill

*/
/*$('.o_website_form_portal_vendor_upload_files').on('click', function (event) {
    event.preventDefault();
    console.log("Le dieron click >>>>>>>>>>>> ");
    var $target = $(event.target);
    console.log("SE ESTA EJECUTANDO >>>>>>>>>>> ");
    $target.prop('disabled', true);
});*/

});

