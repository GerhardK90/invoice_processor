frappe.ui.form.on('Invoice Processor Settings', {
    refresh: function(frm) {
        // Add a button to test the API key
        frm.add_custom_button(__('Test API Key'), function() {
            frm.trigger('test_api_key');
        });
    },

    test_api_key: function(frm) {
        if (!frm.doc.openai_api_key) {
            frappe.msgprint(__('Please enter an API key first'));
            return;
        }

        frappe.call({
            method: 'invoice_processor.invoice_processor.doctype.invoice_processor_settings.invoice_processor_settings.test_api_key',
            args: {
                api_key: frm.doc.openai_api_key
            },
            callback: function(r) {
                if (r.message) {
                    frappe.msgprint(__('API Key is valid'));
                } else {
                    frappe.msgprint(__('API Key is invalid'));
                }
            }
        });
    },

    validate: function(frm) {
        if (!frm.doc.openai_api_key) {
            frappe.throw(__('API Key is required'));
        }
    }
}); 