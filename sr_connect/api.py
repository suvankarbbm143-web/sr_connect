import inspect

import frappe
from frappe.utils import flt


@frappe.whitelist()
def make_stock_entry(
    work_order_id=None,
    purpose=None,
    qty=None,
    target_warehouse=None,
    **kwargs
):
    from erpnext.manufacturing.doctype.work_order.work_order import (
        make_stock_entry as native_make_stock_entry
    )

    work_order_id = str(work_order_id or "").strip()
    purpose = str(purpose or "").strip()

    if not work_order_id:
        frappe.throw("Work Order is required.")

    wo = frappe.get_doc("Work Order", work_order_id)

    wo_qty = flt(wo.qty or 0)

    if wo_qty <= 0:
        frappe.throw("Work Order quantity must be greater than zero.")

    # =========================================================
    # FINAL PACKING & SHIFTING QTY
    # =========================================================
    final_qty = flt(
        frappe.db.get_value(
            "Work Order Operation",
            {
                "parent": work_order_id,
                "operation": "PACKING & SHIFTING",
            },
            "completed_qty",
        ) or 0
    )

    # Job Card fallback
    if final_qty <= 0:

        result = frappe.db.sql(
            """
            SELECT COALESCE(SUM(total_completed_qty), 0)
            FROM `tabJob Card`
            WHERE
                work_order = %s
                AND operation = 'PACKING & SHIFTING'
                AND docstatus = 1
            """,
            (work_order_id,),
        )

        if result:
            final_qty = flt(result[0][0] or 0)

    # =========================================================
    # MATERIAL CONSUMPTION
    #
    # FULL WORK ORDER QTY.
    #
    # Example:
    # WO = 1000 KG
    #
    # Raw materials remain 1000 KG BOM calculation.
    #
    # PP WOVEN BAG will later become:
    # 40 Nos -> 39 Nos
    # =========================================================
    if purpose == "Material Consumption for Manufacture":

        qty = wo_qty

    # =========================================================
    # FINISH / MANUFACTURE
    #
    # IMPORTANT:
    #
    # Native ERPNext must receive 1000.
    #
    # Packing & Shifting:
    # 975
    #
    # Process Loss:
    # 25
    #
    # Therefore:
    #
    # 975 + 25 = 1000
    #
    # This satisfies ERPNext operation validation.
    # =========================================================
    elif purpose == "Manufacture":

        if final_qty <= 0:
            frappe.throw(
                "PACKING & SHIFTING completed quantity is required before Finish."
            )

        qty = wo_qty

    else:

        qty = flt(qty or 0)

    # =========================================================
    # NATIVE FUNCTION ARGUMENTS
    # =========================================================
    signature = inspect.signature(
        native_make_stock_entry
    )

    accepted = signature.parameters

    native_args = {}

    if "work_order_id" in accepted:
        native_args["work_order_id"] = work_order_id

    if "purpose" in accepted:
        native_args["purpose"] = purpose

    if "qty" in accepted:
        native_args["qty"] = flt(qty)

    if (
        target_warehouse
        and "target_warehouse" in accepted
    ):
        native_args["target_warehouse"] = target_warehouse

    for key, value in kwargs.items():

        if key in accepted:
            native_args[key] = value

    # =========================================================
    # IMPORTANT OPERATION LOSS FIX
    #
    # ERPNext checks:
    #
    # completed_qty + process_loss_qty
    #
    # For this WO:
    #
    # completed_qty    = 975
    # process_loss_qty = 25
    # total             = 1000
    #
    # So we store the REAL process loss on the final operation.
    # =========================================================

    final_operation_name = frappe.db.get_value(
        "Work Order Operation",
        {
            "parent": work_order_id,
            "operation": "PACKING & SHIFTING",
        },
        "name",
    )

    old_process_loss_qty = None

    if (
        final_operation_name
        and final_qty > 0
        and final_qty < wo_qty
    ):

        old_process_loss_qty = flt(
            frappe.db.get_value(
                "Work Order Operation",
                final_operation_name,
                "process_loss_qty",
            ) or 0
        )

        required_loss_qty = flt(
            wo_qty - final_qty
        )

        frappe.db.set_value(
            "Work Order Operation",
            final_operation_name,
            "process_loss_qty",
            required_loss_qty,
            update_modified=False,
        )

    # =========================================================
    # CREATE NATIVE STOCK ENTRY
    # =========================================================

    stock_entry = native_make_stock_entry(
        **native_args
    )

    # =========================================================
    # MATERIAL CONSUMPTION
    #
    # ONLY PP WOVEN BAG:
    #
    # WO = 1000
    # Final = 975
    # Original Bag = 40 Nos
    #
    # 40 x 975 / 1000 = 39 Nos
    #
    # OTHER MATERIALS ARE NOT TOUCHED.
    # =========================================================

    if (
        purpose == "Material Consumption for Manufacture"
        and stock_entry
        and final_qty > 0
        and final_qty < wo_qty
    ):

        ratio = final_qty / wo_qty

        # ---------------------------------------------------------
        # CHECK WHETHER MATERIAL CONSUMPTION WAS ALREADY SUBMITTED
        # ---------------------------------------------------------
        previous_consumption = frappe.db.sql(
            """
            SELECT COUNT(*)
            FROM `tabStock Entry`
            WHERE
                work_order = %s
                AND purpose = 'Material Consumption for Manufacture'
                AND docstatus = 1
            """,
            (work_order_id,),
        )

        consumption_already_done = bool(
            previous_consumption
            and int(previous_consumption[0][0] or 0) > 0
        )

        for row in stock_entry.get("items") or []:

            item_code = str(
                row.get("item_code") or ""
            ).strip().upper()

            item_name = str(
                row.get("item_name") or ""
            ).strip().upper()

            uom = str(
                row.get("uom") or ""
            ).strip().upper()

            # ONLY PP WOVEN BAG
            if (
                "PP WOVEN BAG" not in item_code
                and
                "PP WOVEN BAG" not in item_name
            ):
                continue

            # ONLY NOS
            if uom not in (
                "NOS",
                "NO",
                "NUMBERS",
            ):
                continue

            original_qty = flt(
                row.get("qty") or 0
            )

            if original_qty <= 0:
                continue

            # -----------------------------------------------------
            # FIRST MATERIAL CONSUMPTION
            #
            # 40 bags -> 39 bags
            # -----------------------------------------------------
            if not consumption_already_done:
                row.qty = flt(
                    original_qty * ratio,
                    6
                )

            # -----------------------------------------------------
            # SECOND / LATER MATERIAL CONSUMPTION
            #
            # Native ERPNext has already calculated the remaining
            # WIP quantity. DO NOT apply 975/1000 again.
            #
            # Example:
            # 40 transferred
            # 39 consumed
            # 1 remaining
            #
            # Second consumption = 1 Nos
            # -----------------------------------------------------

            row.uom = "Nos"

    # =========================================================
    # AUTO CREATE / ASSIGN FINISHED ITEM BATCH
    #
    # Every Work Order:
    # Work Order custom_new_batch_id -> Batch
    #
    # If the batch does not exist, create it automatically
    # for the Work Order production item.
    # If it already exists for the same item, reuse it.
    # =========================================================
    if (
        purpose == "Manufacture"
        and stock_entry
        and final_qty > 0
    ):
        new_batch_id = str(
            frappe.db.get_value(
                "Work Order",
                work_order_id,
                "custom_new_batch_id",
            ) or ""
        ).strip()

        production_item = str(
            wo.production_item or ""
        ).strip()

        if new_batch_id and production_item:
            existing_batch_item = frappe.db.get_value(
                "Batch",
                new_batch_id,
                "item",
            )

            if existing_batch_item:
                if str(existing_batch_item).strip() != production_item:
                    frappe.throw(
                        "Batch {0} already belongs to item {1}, "
                        "but this Work Order production item is {2}.".format(
                            new_batch_id,
                            existing_batch_item,
                            production_item,
                        )
                    )
            else:
                batch_doc = frappe.get_doc({
                    "doctype": "Batch",
                    "batch_id": new_batch_id,
                    "item": production_item,
                })
                batch_doc.insert(ignore_permissions=True)

            # Assign the new batch ONLY to the finished item row.
            for row in stock_entry.get("items") or []:
                row_item_code = str(
                    row.get("item_code") or ""
                ).strip()

                if row_item_code == production_item:
                    row.batch_no = new_batch_id

    # =========================================================
    # FINISH
    #
    # Finished quantity = PACKING & SHIFTING quantity.
    #
    # Process loss = WO - finished.
    #
    # Batch = Work Order custom_new_batch_id.
    # =========================================================

    if (
        purpose == "Manufacture"
        and stock_entry
        and final_qty > 0
    ):

        process_loss_qty = max(
            0,
            wo_qty - final_qty
        )

        process_loss_percentage = 0

        if wo_qty > 0:

            process_loss_percentage = (
                process_loss_qty /
                wo_qty
            ) * 100

        # ---------------------------------------------
        # Keep manufacture base quantity = WO quantity
        # ---------------------------------------------
        if hasattr(
            stock_entry,
            "fg_completed_qty"
        ):

            stock_entry.fg_completed_qty = flt(
                wo_qty
            )

        # ---------------------------------------------
        # Process Loss
        # ---------------------------------------------
        if hasattr(
            stock_entry,
            "process_loss_qty"
        ):

            stock_entry.process_loss_qty = flt(
                process_loss_qty
            )

        if hasattr(
            stock_entry,
            "process_loss_percentage"
        ):

            stock_entry.process_loss_percentage = flt(
                process_loss_percentage
            )

        # ---------------------------------------------------------
        # AUTO SELECT INSPECTION REQUIREMENTS
        #
        # Finish Stock Entry must automatically select both:
        #   Application Inspection Required
        #   Production Inspection Required
        # ---------------------------------------------------------

        if hasattr(
            stock_entry,
            "custom_application_inspection_required"
        ):
            stock_entry.custom_application_inspection_required = 1

        if hasattr(
            stock_entry,
            "custom_production_inspection_required"
        ):
            stock_entry.custom_production_inspection_required = 1

        # ---------------------------------------------
        # Finished item
        # ---------------------------------------------
        production_item = str(
            wo.get("production_item") or ""
        ).strip()

        batch_no = str(
            wo.get("custom_new_batch_id") or ""
        ).strip().upper()

        for row in stock_entry.get("items") or []:

            item_code = str(
                row.get("item_code") or ""
            ).strip()

            is_finished = (
                int(
                    row.get("is_finished_item")
                    or 0
                ) == 1
            )

            if (
                is_finished
                or (
                    production_item
                    and item_code == production_item
                )
            ):

                # Finished output = 975
                row.qty = flt(
                    final_qty
                )

                row.transfer_qty = flt(
                    final_qty
                )

                if batch_no:
                    row.batch_no = batch_no

    # =========================================================
    # DO NOT RESTORE PROCESS LOSS TO ZERO.
    #
    # The 25 KG loss is REAL production loss and must remain
    # on PACKING & SHIFTING operation.
    # =========================================================

    frappe.db.commit()

    return stock_entry
