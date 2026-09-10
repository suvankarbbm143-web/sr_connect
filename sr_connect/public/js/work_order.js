(() => {
    function install_sr_finish_qty_patch() {
        if (
            !window.erpnext ||
            !erpnext.work_order ||
            typeof erpnext.work_order.get_max_transferable_qty !== "function"
        ) {
            return false;
        }

        if (erpnext.work_order.__sr_finish_qty_patch) {
            return true;
        }

        const original_get_max =
            erpnext.work_order.get_max_transferable_qty;

        erpnext.work_order.get_max_transferable_qty = function (frm, purpose) {

            // Only change Finish / Manufacture quantity.
            // Everything else stays native ERPNext.
            if (purpose === "Manufacture") {

                const operations = frm.doc.operations || [];

                const packing_row = operations.find(
                    row =>
                        String(row.operation || "").trim().toUpperCase() ===
                        "PACKING & SHIFTING"
                );

                const final_qty = flt(
                    packing_row ? packing_row.completed_qty : 0
                );

                if (final_qty > 0) {
                    return final_qty;
                }
            }

            return original_get_max.apply(this, arguments);
        };

        erpnext.work_order.__sr_finish_qty_patch = true;

        console.log(
            "SR Connect: Finish quantity now uses PACKING & SHIFTING completed_qty"
        );

        return true;
    }

    if (!install_sr_finish_qty_patch()) {
        let tries = 0;

        const timer = setInterval(() => {
            tries++;

            if (install_sr_finish_qty_patch() || tries >= 40) {
                clearInterval(timer);
            }
        }, 250);
    }
})();
