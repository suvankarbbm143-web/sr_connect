frappe.ui.form.on('Work Order', {

    // ==========================================
    // FORM REFRESH
    // ==========================================

    refresh(frm) {

        // Remove old button first
        frm.remove_custom_button(__('Get Latest Batch'));

        // Add Get Latest Batch button
        frm.add_custom_button(__('Get Latest Batch'), function () {

            if (!frm.doc.production_item) {

                frappe.msgprint(
                    __('Please select a Production Item first.')
                );

                return;
            }

            frappe.call({

                method: 'frappe.client.get_list',

                args: {

                    doctype: 'Work Order',

                    filters: {
                        production_item: frm.doc.production_item,
                        docstatus: ['<', 2]
                    },

                    fields: [
                        'name',
                        'custom_new_batch_id'
                    ],

                    order_by: 'creation desc',

                    limit: 50
                },

                callback: function (r) {

                    let latest_batch = '';

                    if (
                        r.message &&
                        r.message.length
                    ) {

                        for (let doc of r.message) {

                            // Current Work Order skip
                            if (
                                doc.name === frm.doc.name
                            ) {
                                continue;
                            }

                            const batch = String(
                                doc.custom_new_batch_id || ''
                            )
                                .trim()
                                .toUpperCase();

                            if (batch) {

                                latest_batch = batch;

                                break;
                            }
                        }
                    }


                    // ==================================
                    // NO PREVIOUS BATCH
                    // ==================================

                    if (!latest_batch) {

                        frappe.msgprint({

                            title: __('Latest Batch'),

                            message:
                                __('No previous batch found for this item.'),

                            indicator: 'orange'
                        });

                        return;
                    }


                    // ==================================
                    // SET PREVIOUS BATCH
                    // ==================================

                    frm.set_value(
                        'custom_previous_batch_id',
                        latest_batch
                    ).then(() => {

                        if (frm.is_dirty()) {
                            frm.save();
                        }

                    });


                    // ==================================
                    // SHOW BATCH POPUP
                    // ==================================

                    frappe.msgprint({

                        title: __('Latest Batch'),

                        message: `
                            <div style="
                                text-align:center;
                                padding:18px 10px;
                            ">

                                <div style="
                                    font-size:13px;
                                    color:#666;
                                    margin-bottom:10px;
                                ">
                                    Previous Batch No
                                </div>

                                <div style="
                                    font-size:30px;
                                    font-weight:700;
                                    color:#0d6efd;
                                    letter-spacing:1px;
                                ">
                                    ${frappe.utils.escape_html(
                                        latest_batch
                                    )}
                                </div>

                            </div>
                        `,

                        indicator: 'blue'
                    });


                    // ==================================
                    // MAKE FIELD EDITABLE
                    // ==================================

                    setTimeout(function () {

                        const field =
                            frm.fields_dict
                                .custom_previous_batch_id;

                        if (
                            field &&
                            field.$input
                        ) {

                            field.$input.prop(
                                'readonly',
                                false
                            );

                        }

                    }, 100);

                },


                // ==================================
                // ERROR
                // ==================================

                error: function (err) {

                    console.error(
                        'Get Latest Batch Error:',
                        err
                    );

                    frappe.msgprint({

                        title: __('Error'),

                        message:
                            __('Unable to get the latest batch.'),

                        indicator: 'red'
                    });

                }

            });

        });



        // ==========================================
        // QC DETAILS - CLICKABLE
        // ==========================================

        frm.remove_custom_button(__('QC Details'));

        frm.add_custom_button(__('QC Details'), function () {

            const batch = String(
                frm.doc.custom_new_batch_id ||
                frm.doc.batch_no ||
                ''
            ).trim();

            const itemName =
                frm.doc.item_name ||
                frm.doc.production_item ||
                '-';

            if (!batch) {

                frappe.msgprint({
                    title: __('QC Details'),
                    message: __('No batch number found for this Work Order.'),
                    indicator: 'orange'
                });

                return;
            }

            frappe.call({

                method: 'frappe.client.get_list',

                args: {

                    doctype: 'Quality Inspection',

                    filters: {
                        batch_no: batch,
                        docstatus: 1
                    },

                    fields: [
                        'name',
                        'custom_qc_inspection_type',
                        'inspection_type',
                        'reference_type',
                        'reference_name',
                        'quality_inspection_template',
                        'status',
                        'item_code'
                    ],

                    order_by: 'creation asc',

                    limit_page_length: 50
                },

                callback: function (r) {

                    const rows = r.message || [];

                    // ==========================================
                    // PRODUCT / APPLICATION DETECTOR
                    // ==========================================

                    function get_qc_category(x) {

                        const category = String(
                            x.custom_qc_inspection_type || ''
                        )
                            .trim()
                            .toLowerCase();

                        if (category === 'product') {
                            return 'product';
                        }

                        if (category === 'application') {
                            return 'application';
                        }

                        // OLD RECORD FALLBACK
                        const template = String(
                            x.quality_inspection_template || ''
                        )
                            .trim()
                            .toLowerCase();

                        if (template === 'bake a way (qc)') {
                            return 'product';
                        }

                        if (template === 'bake a way') {
                            return 'application';
                        }

                        return '';
                    }

                    let product = null;
                    let application = null;

                    rows.forEach(function (x) {

                        const category =
                            get_qc_category(x);

                        if (
                            category === 'product' &&
                            !product
                        ) {
                            product = x;
                        }

                        if (
                            category === 'application' &&
                            !application
                        ) {
                            application = x;
                        }
                    });


                    // ==========================================
                    // ESCAPE HTML
                    // ==========================================

                    function esc(value) {

                        if (
                            value === undefined ||
                            value === null ||
                            value === ''
                        ) {
                            return '-';
                        }

                        return frappe.utils.escape_html(
                            String(value)
                        );
                    }


                    // ==========================================
                    // CLICKABLE DOCUMENT LINK
                    // ==========================================

                    function doc_link(doctype, name) {

                        if (!name) {
                            return '-';
                        }

                        const route =
                            '/app/' +
                            doctype
                                .toLowerCase()
                                .replace(/ /g, '-') +
                            '/' +
                            encodeURIComponent(name);

                        return (
                            '<a href="' +
                            route +
                            '" ' +
                            'style="color:#0d6efd;font-weight:600;text-decoration:underline;">' +
                            esc(name) +
                            '</a>'
                        );
                    }


                    // ==========================================
                    // INSPECTION CARD
                    // ==========================================

                    function inspection_card(
                        title,
                        inspection
                    ) {

                        if (!inspection) {

                            return (
                                '<div style="' +
                                'border:1px solid #ddd;' +
                                'border-radius:8px;' +
                                'padding:15px;' +
                                'margin-bottom:12px;' +
                                '">' +

                                '<div style="' +
                                'font-size:16px;' +
                                'font-weight:700;' +
                                'margin-bottom:8px;' +
                                '">' +

                                title +

                                '</div>' +

                                '<div style="color:#888;">' +
                                '-' +
                                '</div>' +

                                '</div>'
                            );
                        }

                        let reference_html =
                            esc(
                                inspection.reference_name
                            );

                        if (
                            inspection.reference_type ===
                                'Stock Entry' &&
                            inspection.reference_name
                        ) {

                            reference_html =
                                doc_link(
                                    'Stock Entry',
                                    inspection.reference_name
                                );
                        }

                        return (
                            '<div style="' +
                            'border:1px solid #ddd;' +
                            'border-radius:8px;' +
                            'padding:15px;' +
                            'margin-bottom:12px;' +
                            '">' +

                            '<div style="' +
                            'font-size:16px;' +
                            'font-weight:700;' +
                            'margin-bottom:10px;' +
                            '">' +

                            title +

                            '</div>' +

                            '<div style="margin-bottom:6px;">' +
                            '<b>Inspection:</b> ' +

                            doc_link(
                                'Quality Inspection',
                                inspection.name
                            ) +

                            '</div>' +

                            '<div style="margin-bottom:6px;">' +
                            '<b>Status:</b> ' +
                            esc(inspection.status) +
                            '</div>' +

                            '<div style="margin-bottom:6px;">' +
                            '<b>Item:</b> ' +
                            esc(inspection.item_code) +
                            '</div>' +

                            '<div style="margin-bottom:6px;">' +
                            '<b>Reference:</b> ' +
                            reference_html +
                            '</div>' +

                            '</div>'
                        );
                    }


                    // ==========================================
                    // STOCK ENTRY
                    // ==========================================

                    let stock_entry = null;

                    if (
                        product &&
                        product.reference_type ===
                            'Stock Entry' &&
                        product.reference_name
                    ) {

                        stock_entry =
                            product.reference_name;
                    }

                    if (
                        !stock_entry &&
                        application &&
                        application.reference_type ===
                            'Stock Entry' &&
                        application.reference_name
                    ) {

                        stock_entry =
                            application.reference_name;
                    }

                    let stock_entry_html = '-';

                    if (stock_entry) {

                        stock_entry_html =
                            doc_link(
                                'Stock Entry',
                                stock_entry
                            );
                    }


                    // ==========================================
                    // POPUP
                    // ==========================================

                    const html =

                        '<div style="padding:5px;">' +

                        '<div style="' +
                        'background:#f7f7f7;' +
                        'border-radius:8px;' +
                        'padding:12px 15px;' +
                        'margin-bottom:15px;' +
                        '">' +

                        '<div style="' +
                        'font-size:13px;' +
                        'color:#777;' +
                        '">' +

                        'Batch No' +

                        '</div>' +

                        '<div style="' +
                        'font-size:22px;' +
                        'font-weight:700;' +
                        'margin-bottom:8px;' +
                        '">' +

                        esc(batch) +

                        '</div>' +

                        '<div style="' +
                        'font-size:13px;' +
                        'color:#777;' +
                        '">' +

                        'Item' +

                        '</div>' +

                        '<div style="' +
                        'font-size:16px;' +
                        'font-weight:600;' +
                        '">' +

                        esc(itemName) +

                        '</div>' +

                        '</div>' +

                        inspection_card(
                            'Product Inspection',
                            product
                        ) +

                        inspection_card(
                            'Application Inspection',
                            application
                        ) +

                        '<div style="' +
                        'border:1px solid #ddd;' +
                        'border-radius:8px;' +
                        'padding:15px;' +
                        '">' +

                        '<div style="' +
                        'font-size:16px;' +
                        'font-weight:700;' +
                        'margin-bottom:8px;' +
                        '">' +

                        'Stock Entry' +

                        '</div>' +

                        '<div style="font-size:15px;">' +

                        stock_entry_html +

                        '</div>' +

                        '</div>' +

                        '</div>';


                    frappe.msgprint({

                        title: __('QC Details'),

                        message: html,

                        wide: true

                    });

                },

                error: function (err) {

                    console.error(
                        'QC Details Error:',
                        err
                    );

                    frappe.msgprint({

                        title: __('QC Details'),

                        message:
                            __('Unable to fetch Quality Inspection details.'),

                        indicator: 'red'

                    });

                }

            });

        });



        // ==========================================
        // REFRESH হলে EXP DATE CHECK
        // ==========================================

        if (
            frm.doc.production_item &&
            frm.doc.custom_date
        ) {

            setTimeout(function () {

                calculate_exp_date(frm);

            }, 300);

        }

    },


    // ==========================================
    // PRODUCTION ITEM SELECT / CHANGE
    // ==========================================

    production_item(frm) {

        // Item remove করলে EXP clear
        if (!frm.doc.production_item) {

            frm.set_value(
                'custom_exp_date',
                ''
            );

            return;
        }


        /*
         * ERPNext-এর standard Production Item
         * event শেষ হওয়ার পরে EXP calculate করবে।
         */

        setTimeout(function () {

            calculate_exp_date(frm);

        }, 700);

    },


    // ==========================================
    // MFG DATE CHANGE
    // ==========================================

    custom_date(frm) {

        // MFG Date remove করলে EXP clear
        if (!frm.doc.custom_date) {

            frm.set_value(
                'custom_exp_date',
                ''
            );

            return;
        }


        calculate_exp_date(frm);

    },


    // ==========================================
    // PREVIOUS BATCH → UPPERCASE
    // ==========================================

    custom_previous_batch_id(frm) {

        const value = String(
            frm.doc.custom_previous_batch_id || ''
        )
            .trim();


        if (!value) {
            return;
        }


        const upper =
            value.toUpperCase();


        if (value !== upper) {

            frm.set_value(
                'custom_previous_batch_id',
                upper
            );

        }

    },


    // ==========================================
    // NEW BATCH → UPPERCASE
    // ==========================================

    custom_new_batch_id(frm) {

        const value = String(
            frm.doc.custom_new_batch_id || ''
        )
            .trim();


        if (!value) {
            return;
        }


        const upper =
            value.toUpperCase();


        if (value !== upper) {

            frm.set_value(
                'custom_new_batch_id',
                upper
            );

        }

    }

});


// ==================================================
// EXP DATE CALCULATION FUNCTION
// ==================================================

function calculate_exp_date(frm) {

    // ==========================================
    // ITEM / MFG DATE না থাকলে EXP CLEAR
    // ==========================================

    if (
        !frm.doc.production_item ||
        !frm.doc.custom_date
    ) {

        frm.set_value(
            'custom_exp_date',
            ''
        );

        return;
    }


    // ==========================================
    // GET SHELF LIFE FROM ITEM
    // ==========================================

    frappe.db.get_value(

        'Item',

        frm.doc.production_item,

        'custom_shelf_life_months'

    ).then(function (r) {

        let months = 0;


        if (
            r &&
            r.message &&
            r.message.custom_shelf_life_months !== undefined &&
            r.message.custom_shelf_life_months !== null
        ) {

            months = parseInt(
                r.message.custom_shelf_life_months
            );

        }


        // ==========================================
        // SHELF LIFE নেই
        // ==========================================

        if (
            isNaN(months) ||
            months <= 0
        ) {

            // আগের Item-এর EXP clear করবে
            frm.set_value(
                'custom_exp_date',
                ''
            );

            return;
        }


        // ==========================================
        // CALCULATE EXP DATE
        // ==========================================

        const exp_date =
            frappe.datetime.add_months(

                frm.doc.custom_date,

                months

            );


        // ==========================================
        // SET EXP DATE
        // ==========================================

        frm.set_value(
            'custom_exp_date',
            exp_date
        );

    });

}