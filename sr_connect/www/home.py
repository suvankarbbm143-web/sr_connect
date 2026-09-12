import frappe
from frappe.utils import now_datetime, flt, get_datetime, time_diff_in_seconds


# =========================================================
# PAGE CONTEXT
# =========================================================



SR_STOCK_V2_PREFIX = "SR Connect Stock Entry V2"

@frappe.whitelist()


@frappe.whitelist()
def sr_stock_entry_submit_v3(
    work_order_id,
    materials
):

    if not _sr_stock_v2_has_access():
        frappe.throw(
            "You do not have Stock Entry access."
        )

    import json

    work_order_id = str(
        work_order_id or ""
    ).strip()

    if isinstance(
        materials,
        str
    ):

        try:
            materials = json.loads(
                materials
            )
        except Exception:
            frappe.throw(
                "Invalid material data."
            )

    if not isinstance(
        materials,
        list
    ):

        frappe.throw(
            "Invalid material data."
        )

    if not work_order_id:

        frappe.throw(
            "Work Order is required."
        )

    if not frappe.db.exists(
        "Work Order",
        work_order_id
    ):

        frappe.throw(
            "Work Order not found."
        )

    wo = frappe.get_doc(
        "Work Order",
        work_order_id
    )

    previous = frappe.get_all(
        "Stock Entry",
        filters={
            "work_order":
                work_order_id,

            "docstatus":
                1,

            "stock_entry_type":
                "Material Transfer for Manufacture",

            "remarks":
                [
                    "like",
                    SR_STOCK_V2_PREFIX
                    + "%"
                ],
        },
        pluck="name",
        limit_page_length=1,
    )

    if previous:

        frappe.throw(
            "Stock Entry has already been given for this batch."
        )

    required = {}

    for row in (
        wo.get("required_items")
        or []
    ):

        code = str(
            getattr(
                row,
                "item_code",
                ""
            )
            or ""
        ).strip()

        if code:
            required[code] = row

    se = frappe.new_doc(
        "Stock Entry"
    )

    se.stock_entry_type = (
        "Material Transfer for Manufacture"
    )

    se.purpose = (
        "Material Transfer for Manufacture"
    )

    se.work_order = (
        wo.name
    )

    se.company = (
        wo.company
    )

    se.remarks = (
        SR_STOCK_V2_PREFIX
        + " | Work Order: "
        + str(wo.name)
        + " | Batch: "
        + _sr_stock_v2_batch(wo)
    )

    added = set()

    for data in materials:

        item_code = str(
            data.get(
                "item_code"
            )
            or ""
        ).strip()

        batch_no = str(
            data.get(
                "batch_no"
            )
            or ""
        ).strip()

        if not item_code:
            continue

        if item_code in added:
            frappe.throw(
                "Duplicate material: "
                + item_code
            )

        if item_code not in required:

            frappe.throw(
                item_code
                + " is not required by "
                + work_order_id
            )

        row = required[
            item_code
        ]

        required_qty = flt(
            getattr(
                row,
                "required_qty",
                0
            )
            or 0
        )

        transferred_qty = flt(
            getattr(
                row,
                "transferred_qty",
                0
            )
            or 0
        )

        remaining_qty = max(
            0,
            required_qty
            - transferred_qty
        )

        if remaining_qty <= 0:
            continue

        source = str(
            getattr(
                row,
                "source_warehouse",
                ""
            )
            or ""
        ).strip()

        if not source:

            frappe.throw(
                "Source Warehouse missing for "
                + item_code
            )

        has_batch_no = int(
            frappe.db.get_value(
                "Item",
                item_code,
                "has_batch_no"
            )
            or 0
        )

        if has_batch_no:

            if not batch_no:

                frappe.throw(
                    "Select a Batch for "
                    + item_code
                )

            available = flt(
                frappe.db.sql(
                    """
                    SELECT
                        SUM(
                            actual_qty
                        )
                    FROM `tabStock Ledger Entry`
                    WHERE
                        item_code=%s
                        AND warehouse=%s
                        AND batch_no=%s
                        AND is_cancelled=0
                    """,
                    (
                        item_code,
                        source,
                        batch_no,
                    ),
                )[0][0]
                or 0
            )

            if available < remaining_qty:

                frappe.throw(
                    "Stock not enough for "
                    + item_code
                    + ". Required: "
                    + str(remaining_qty)
                    + ", Batch "
                    + batch_no
                    + " available: "
                    + str(available)
                )

        else:

            available = flt(
                frappe.db.get_value(
                    "Bin",
                    {
                        "item_code":
                            item_code,
                        "warehouse":
                            source,
                    },
                    "actual_qty"
                )
                or 0
            )

            if available < remaining_qty:

                frappe.throw(
                    "Stock not enough for "
                    + item_code
                    + ". Required: "
                    + str(remaining_qty)
                    + ", Available: "
                    + str(available)
                )

        if not wo.wip_warehouse:

            frappe.throw(
                "WIP warehouse is missing."
            )

        child = se.append(
            "items",
            {}
        )

        child.item_code = (
            item_code
        )

        # Quantity is deliberately NOT
        # received from browser.
        # ERPNext required remaining qty
        # is always used.
        child.qty = (
            remaining_qty
        )

        child.uom = (
            getattr(
                row,
                "stock_uom",
                ""
            )
            or ""
        )

        child.s_warehouse = (
            source
        )

        child.t_warehouse = (
            wo.wip_warehouse
        )

        if has_batch_no:

            child.batch_no = (
                batch_no
            )

        added.add(
            item_code
        )

    if not se.items:

        frappe.throw(
            "No valid materials selected."
        )

    try:
        se.insert(
            ignore_permissions=True
        )

        se.submit()

        frappe.db.commit()

    except Exception:
        frappe.db.rollback()
        frappe.log_error(
            frappe.get_traceback(),
            "SR STOCK ENTRY V3 SUBMIT ERROR"
        )
        raise

    return {

        "success":
            True,

        "name":
            str(
                se.name
            ),

        "work_order":
            str(
                wo.name
            ),

        "batch_no":
            _sr_stock_v2_batch(
                wo
            ),

        "message":
            "✓ Stock Entry submitted successfully.",
    }


# =========================================================
# CREATE WORK ORDER
# =========================================================

def get_context(context):
    context.no_cache = 1

    user = frappe.session.user
    if user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    try:
        user_doc = frappe.get_doc("User", user)
        context.user_name = user_doc.full_name or user_doc.first_name or user
        context.user_initial = (context.user_name[0] if context.user_name else "U").upper()
        context.user_image = user_doc.user_image or ""
    except Exception:
        context.user_name = user
        context.user_initial = "U"
        context.user_image = ""

    context.csrf_token = frappe.sessions.get_csrf_token()
    return context


# =========================================================
# HELPERS
# =========================================================

def _is_guest():
    return frappe.session.user == "Guest"


def _assigned_job_card_names():
    if _is_guest():
        return []

    rows = frappe.get_all(
        "ToDo",
        filters={
            "allocated_to": frappe.session.user,
            "reference_type": "Job Card",
            "status": ["in", ["Open", "Closed"]],
        },
        fields=["reference_name", "creation", "assigned_by", "owner"],
        order_by="creation asc",
        limit_page_length=500,
    )

    result = []
    for row in rows:
        name = row.reference_name
        if name and frappe.db.exists("Job Card", name) and name not in result:
            result.append(name)
    return result


def _operation_idx(work_order, operation):
    if not work_order or not operation:
        return 999999

    target = (operation or "").strip().upper()

    try:
        rows = frappe.db.sql(
            """
            SELECT operation, idx
            FROM `tabWork Order Operation`
            WHERE parent=%s
            ORDER BY idx ASC
            """,
            (work_order,),
            as_dict=True,
        )

        for row in rows:
            if (row.operation or "").strip().upper() == target:
                return int(row.idx or 999999)
    except Exception:
        pass

    fallback = {
        "RM WEIGING": 1,
        "RM  WEIGING": 1,
        "RAW MATERIAL POURING": 2,
        "MIXING": 3,
        "PACKING & SHIFTING": 4,
    }
    return fallback.get(target, 999999)


def _is_final_operation(operation):
    return (operation or "").strip().upper() == "PACKING & SHIFTING"


def _find_batch_field(doctype):
    """
    Finds a Batch No / Batch Number field without assuming a specific
    custom fieldname. This prevents SQL errors when the field is custom.
    """
    try:
        meta = frappe.get_meta(doctype)

        preferred = [
            "batch_no",
            "batch_number",
            "custom_batch_no",
            "custom_batch_number",
        ]

        for fieldname in preferred:
            if meta.has_field(fieldname):
                return fieldname

        for df in meta.fields:
            fieldname_raw = (df.fieldname or "").strip()
            fieldname = fieldname_raw.lower()
            label = (df.label or "").strip().lower()

            if fieldname in preferred:
                return fieldname_raw

            # Also support arbitrary custom fields like custom_batch_no,
            # batch_number_1, production_batch, etc.
            if "batch" in fieldname or "batch" in label:
                return fieldname_raw

        return None
    except Exception:
        return None


def _get_batch_no(job_card, work_order_doc=None):
    """
    SR Connect Batch No.

    ALWAYS use Work Order -> custom_new_batch_id.
    NEVER use custom_previous_batch_id.
    """

    if work_order_doc:
        try:
            value = work_order_doc.get("custom_new_batch_id")
            if value not in (None, ""):
                return str(value).strip()
        except Exception:
            pass

    return ""


def _elapsed_seconds(jc):
    """
    Cumulative timer:
    - closed logs are permanently counted
    - an open log counts up to now
    - pause/resume therefore never resets the timer
    """
    total = 0.0

    for row in jc.get("time_logs") or []:
        if not row.from_time:
            continue

        try:
            start = get_datetime(row.from_time)
            end = get_datetime(row.to_time) if row.to_time else now_datetime()
            seconds = time_diff_in_seconds(end, start)
            if seconds and seconds > 0:
                total += float(seconds)
        except Exception:
            continue

    return int(max(0, total))


def _closed_elapsed_seconds(jc):
    total = 0.0

    for row in jc.get("time_logs") or []:
        if not row.from_time or not row.to_time:
            continue

        try:
            seconds = time_diff_in_seconds(
                get_datetime(row.to_time),
                get_datetime(row.from_time),
            )
            if seconds and seconds > 0:
                total += float(seconds)
        except Exception:
            continue

    return int(max(0, total))


def _get_ordered_job_cards(work_order):
    if not work_order:
        return []

    rows = frappe.db.sql(
        """
        SELECT
            name,
            operation,
            status,
            docstatus,
            creation,
            for_quantity,
            total_completed_qty
        FROM `tabJob Card`
        WHERE work_order=%s
        ORDER BY creation ASC
        """,
        (work_order,),
        as_dict=True,
    )

    for row in rows:
        row["operation_idx"] = _operation_idx(work_order, row.operation)

    rows.sort(
        key=lambda x: (
            x.get("operation_idx") or 999999,
            str(x.get("creation") or ""),
        )
    )
    return rows




# =========================================================
# ITEM SHELF LIFE / EXPIRY CONFIG
# =========================================================
# Put expiry duration here in DAYS.
# Key can be Item Code or Item Name.
# Example: 365 = 1 year.
SR_ITEM_EXPIRY_DAYS = {
    "Baking Powder 1 Kg": 365,
    # "YOUR ITEM CODE": 730,
}


def _sr_expiry_days(item_code="", item_name=""):
    code = str(item_code or "").strip()
    name = str(item_name or "").strip()

    if code in SR_ITEM_EXPIRY_DAYS:
        return int(SR_ITEM_EXPIRY_DAYS[code])

    if name in SR_ITEM_EXPIRY_DAYS:
        return int(SR_ITEM_EXPIRY_DAYS[name])

    return 0


def _sr_mfg_expiry(wo=None, fallback_date=None, item_code="", item_name=""):
    mfg = None

    if wo:
        mfg = getattr(wo, "creation", None)

    if not mfg:
        mfg = fallback_date

    if not mfg:
        return "", "", 0

    mfg_text = str(mfg)[:10]
    days = _sr_expiry_days(item_code, item_name)

    if not days:
        return mfg_text, "", 0

    try:
        from datetime import datetime, timedelta

        mfg_date = datetime.strptime(
            mfg_text,
            "%Y-%m-%d",
        ).date()

        expiry_date = mfg_date + timedelta(days=days)

        return (
            mfg_date.isoformat(),
            expiry_date.isoformat(),
            days,
        )
    except Exception:
        return mfg_text, "", days


def _work_order_data(wo):
    """Return a frontend-safe Work Order summary including operations and BOM."""
    if not wo:
        return {
            "name": "",
            "production_item": "",
            "item_name": "",
            "qty": 0,
            "produced_qty": 0,
            "status": "",
            "batch_no": "",
            "operations": [],
            "bom_items": [],
        }

    batch_no = _get_batch_no(None, wo)

    # Previous Batch belongs to this SAME Work Order.
    previous_batch_no = str(
        wo.get("custom_previous_batch_id") or ""
    ).strip().upper()


    operations = []
    for row in wo.get("operations") or []:
        operations.append({
            "idx": int(getattr(row, "idx", 0) or 0),
            "operation": str(getattr(row, "operation", "") or ""),
            "workstation": str(getattr(row, "workstation", "") or ""),
            "time_in_mins": flt(
                getattr(row, "time_in_mins", 0)
                or getattr(row, "time_in_mins", 0)
                or 0
            ),
        })
    operations.sort(key=lambda x: (x["idx"] or 999999, x["operation"]))

    bom_items = []
    for row in wo.get("required_items") or []:
        item_code = str(getattr(row, "item_code", "") or "")
        item_name = str(getattr(row, "item_name", "") or item_code)
        required_qty = flt(getattr(row, "required_qty", 0) or 0)
        transferred_qty = flt(getattr(row, "transferred_qty", 0) or 0)
        bom_items.append({
            "item_code": item_code,
            "item_name": item_name,
            "required_qty": required_qty,
            "transferred_qty": transferred_qty,
            "uom": str(getattr(row, "stock_uom", "") or ""),
            "warehouse": str(getattr(row, "source_warehouse", "") or ""),
        })

    return {
        "name": str(wo.name or ""),
        "production_item": str(getattr(wo, "production_item", "") or ""),
        "item_name": str(getattr(wo, "item_name", "") or getattr(wo, "production_item", "") or ""),
        "qty": flt(getattr(wo, "qty", 0) or 0),
        "produced_qty": flt(getattr(wo, "produced_qty", 0) or 0),
        "status": str(getattr(wo, "status", "") or "Not Started"),
        "batch_no": batch_no,
        "previous_batch_no": previous_batch_no,
        "operations": operations,
        "bom_items": bom_items,
    }

def _job_card_data(name):
    jc = frappe.get_doc("Job Card", name)

    wo = None
    if jc.work_order:
        try:
            # Load the complete Work Order document so a custom Batch No field
            # is available even when its fieldname is not standard.
            wo = frappe.get_doc("Work Order", jc.work_order)
        except Exception:
            wo = frappe.db.get_value(
                "Work Order",
                jc.work_order,
                [
                    "name",
                    "production_item",
                    "item_name",
                    "qty",
                    "produced_qty",
                    "status",
                ],
                as_dict=True,
            )

    item_code = (
        (wo or {}).get("production_item")
        or getattr(jc, "production_item", None)
        or ""
    )

    item_name = (
        (wo or {}).get("item_name")
        or item_code
        or ""
    )

    qty = flt(
        getattr(jc, "for_quantity", 0)
        or (wo or {}).get("qty", 0)
    )

    completed_qty = flt(getattr(jc, "total_completed_qty", 0))

    running = False
    running_from = ""

    for row in jc.get("time_logs") or []:
        if row.from_time and not row.to_time:
            running = True
            running_from = str(row.from_time)
            break

    ordered = _get_ordered_job_cards(jc.work_order)

    current_index = next(
        (i for i, row in enumerate(ordered) if row.name == jc.name),
        None,
    )

    job_no = current_index + 1 if current_index is not None else 1

    previous_job = None
    if current_index is not None and current_index > 0:
        previous_job = ordered[current_index - 1]

    blocked = False
    block_message = ""

    # Next operation can start only after previous Job Card is submitted.
    if previous_job and int(previous_job.docstatus or 0) != 1:
        blocked = True
        previous_no = (
            ordered[current_index - 1].get("operation_idx")
            or current_index
        )
        block_message = (
            "Job No-" + str(previous_no)
            + " (" + str(previous_job.operation or "Job") + ") "
            + "must be submitted first."
        )

    batch_no = _get_batch_no(jc, wo)

    custom_date = ""
    try:
        if wo:
            custom_date = str(getattr(wo, "custom_date", "") or "")[:10]
    except Exception:
        custom_date = ""
    custom_exp_date = ""
    try:
        if wo and custom_date:
            item_code_for_shelf = (
                getattr(wo, "production_item", None)
                or getattr(wo, "item_code", None)
                or getattr(jc, "item_code", None)
                or ""
            )

            shelf_life_months = frappe.db.get_value(
                "Item",
                item_code_for_shelf,
                "custom_shelf_life_months",
            )

            if shelf_life_months:
                from frappe.utils import getdate, add_months

                custom_exp_date = str(
                    add_months(
                        getdate(custom_date),
                        int(float(shelf_life_months)),
                    )
                )[:10]
    except Exception:
        custom_exp_date = ""

    # -----------------------------------------------------
    # Operation planned time from Work Order Operation
    # -----------------------------------------------------
    operation_time_in_mins = 0.0

    try:
        if wo and jc.operation:
            target_operation = str(jc.operation or "").strip().upper()

            for op in wo.get("operations") or []:
                op_name = str(
                    getattr(op, "operation", "")
                    or ""
                ).strip().upper()

                if op_name == target_operation:
                    operation_time_in_mins = flt(
                        getattr(op, "time_in_mins", 0)
                        or 0
                    )
                    break
    except Exception:
        operation_time_in_mins = 0.0

    elapsed = _elapsed_seconds(jc)
    closed_elapsed = _closed_elapsed_seconds(jc)

    # Last closed time-log = actual Job Card completion time.
    completed_on = None

    try:
        for tl in reversed(jc.get("time_logs") or []):
            if tl.to_time:
                completed_on = str(tl.to_time)
                break
    except Exception:
        completed_on = None

    return {
        "name": jc.name,
        "job_card_no": jc.name,
        "creation": str(jc.creation or ""),
        "modified": str(jc.modified or ""),
        "work_order": jc.work_order or "",
        "custom_exp_date": custom_exp_date,
        "custom_date": custom_date,
        "operation": (jc.operation or "").strip(),
        "status": jc.status or "Open",
        "docstatus": int(jc.docstatus or 0),
        "qty": qty,
        "completed_qty": completed_qty,
        "produced_qty": completed_qty,
        "item_code": item_code,
        "production_item": item_code,
        "item_name": item_name,
        "batch_no": batch_no,
        "running": 1 if running else 0,
        "running_from": running_from,
        "elapsed_seconds": elapsed,
        "closed_elapsed_seconds": closed_elapsed,
        "completed_on": completed_on,
        "operation_time_in_mins": operation_time_in_mins,
        "job_no": job_no,
        "is_final": 1 if _is_final_operation(jc.operation) else 0,
        "blocked": blocked,
        "block_message": block_message,
        "work_order_info": _work_order_data(wo),
        "bom_items": _work_order_data(wo).get("bom_items", []),
        "work_order_operations": _work_order_data(wo).get("operations", []),
    }


def _close_assigned_todos(job_card_name):
    try:
        todos = frappe.get_all(
            "ToDo",
            filters={
                "reference_type": "Job Card",
                "reference_name": job_card_name,
                "allocated_to": frappe.session.user,
                "status": "Open",
            },
            pluck="name",
        )

        for todo_name in todos:
            frappe.db.set_value(
                "ToDo",
                todo_name,
                "status",
                "Closed",
                update_modified=False,
            )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "SR Connect Close Job ToDo Error",
        )


# =========================================================
# LIST API
# =========================================================



# =========================================================
# SR CONNECT - UNIVERSAL ERPNext ROLE PERMISSION
# =========================================================

@frappe.whitelist()
def get_sr_role_permissions():
    """
    Return native ERPNext permissions for the CURRENT logged-in user.

    No employee/user/role is hard-coded.
    ERPNext Role Permission Manager remains the source of truth.
    """
    if _is_guest():
        frappe.throw("Please login")

    doctypes = [
        "Work Order",
        "Job Card",
        "Stock Entry",
        "Quality Inspection",
        "Item",
        "BOM",
        "Batch",
        "Warehouse",
        "Employee",
        "User",
    ]

    permission_types = [
        "read",
        "write",
        "create",
        "delete",
        "submit",
        "cancel",
        "amend",
        "report",
        "import",
        "export",
        "print",
        "email",
        "share",
        "select",
    ]

    result = {}

    for doctype in doctypes:
        result[doctype] = {}

        for ptype in permission_types:
            try:
                result[doctype][ptype] = bool(
                    frappe.has_permission(
                        doctype,
                        ptype=ptype,
                        user=frappe.session.user,
                    )
                )
            except Exception:
                result[doctype][ptype] = False

    return result


@frappe.whitelist()
def check_sr_permission(doctype, ptype="read"):
    """
    Server-side permission check for SR Connect actions.
    """
    if _is_guest():
        frappe.throw("Please login")

    doctype = str(doctype or "").strip()
    ptype = str(ptype or "read").strip().lower()

    allowed_types = {
        "read",
        "write",
        "create",
        "delete",
        "submit",
        "cancel",
        "amend",
        "report",
        "import",
        "export",
        "print",
        "email",
        "share",
        "select",
    }

    if not doctype:
        frappe.throw("DocType is required.")

    if ptype not in allowed_types:
        frappe.throw("Invalid permission type.")

    return {
        "doctype": doctype,
        "permission": ptype,
        "allowed": bool(
            frappe.has_permission(
                doctype,
                ptype=ptype,
                user=frappe.session.user,
            )
        ),
    }


@frappe.whitelist()
def get_user_assigned_orders(doctype="Job Card"):
    if _is_guest():
        return []

    try:
        if doctype == "Job Card":
            names = _assigned_job_card_names()
            result = []

            for name in names:
                if not frappe.db.exists("Job Card", name):
                    continue

                try:
                    info = _job_card_data(name)

                    # UI has ONLY two categories:
                    # Completed = submitted OR explicitly completed.
                    # In Process = all other assigned, not-yet-submitted jobs
                    # that have actually been started at least once OR are Open
                    # after a pause.
                    is_completed = (
                        int(info["docstatus"]) == 1
                        or info["status"] == "Completed"
                    )

                    if is_completed:
                        category = "Completed"
                    else:
                        # Do not expose any third status in the UI.
                        category = "In Process"

                    info["category"] = category
                    info["is_running"] = 1 if info["running"] else 0
                    todo = frappe.db.get_value(
                        "ToDo",
                        {
                            "allocated_to": frappe.session.user,
                            "reference_type": "Job Card",
                            "reference_name": name,
                            "status": ["in", ["Open", "Closed"]],
                        },
                        ["assigned_by", "owner"],
                        as_dict=True,
                    ) or {}
                    info["assigned_by"] = (
                        todo.get("assigned_by")
                        or todo.get("owner")
                        or ""
                    )
                    result.append(info)
                except Exception:
                    frappe.log_error(
                        frappe.get_traceback(),
                        "SR Connect Job Card Read Error",
                    )

            result.sort(
                key=lambda x: (
                    x.get("work_order") or "",
                    x.get("job_no") or 999999,
                )
            )
            return result

        # =====================================================
        # WORK ORDER
        #
        # Show ALL Work Orders, not only Work Orders connected
        # to currently assigned Job Cards.
        #
        # Batch No comes from:
        # Work Order.custom_new_batch_id
        # =====================================================

        if doctype == "Work Order":

            rows = frappe.get_all(
                "Work Order",
                fields=[
                    "name",
                    "production_item",
                    "item_name",
                    "qty",
                    "produced_qty",
                    "status",
                    "creation",
                    "modified",
                    "docstatus",
                    "custom_new_batch_id",
                    "custom_date",
                    "custom_exp_date",
                ],
                order_by="creation desc",
                limit_page_length=500,
            )

            result = []

            # Any submitted Stock Entry linked to a Work Order
            # means material transfer has started.
            stock_work_orders = set(
                frappe.get_all(
                    "Stock Entry",
                    filters={
                        "docstatus": 1,
                        "work_order": ["is", "set"],
                    },
                    pluck="work_order",
                    limit_page_length=5000,
                )
            )

            for row in rows:

                wo_status = str(
                    row.status or "Not Started"
                )

                if (
                    row.name in stock_work_orders
                    and wo_status == "Not Started"
                ):
                    wo_status = "In Process"

                result.append({
                    "name": str(
                        row.name or ""
                    ),

                    "production_item": str(
                        row.production_item or ""
                    ),

                    "item_name": str(
                        row.item_name
                        or row.production_item
                        or ""
                    ),

                    "qty": flt(
                        row.qty or 0
                    ),

                    "custom_date": str(
                        row.custom_date or ""
                    )[:10],

                    "custom_exp_date": str(
                        row.custom_exp_date or ""
                    )[:10],

                    "produced_qty": flt(
                        row.produced_qty or 0
                    ),

                    "status": wo_status,

                    "docstatus": int(
                        row.docstatus or 0
                    ),

                    "creation": str(
                        row.creation or ""
                    ),

                    "modified": str(
                        row.modified or ""
                    ),

                    "batch_no": str(
                        row.custom_new_batch_id
                        or ""
                    ).strip(),

                })

            return result

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "SR Connect Orders API Error",
        )

    # ========================================================
    # STOCK ENTRY
    # ========================================================

    if doctype == "Stock Entry":

        rows = frappe.get_all(
            "Stock Entry",
            fields=[
                "name",
                "stock_entry_type",
                "purpose",
                "posting_date",
                "from_warehouse",
                "to_warehouse",
                "work_order",
                "docstatus",
            ],
            order_by="posting_date desc, creation desc",
            limit_page_length=100,
        )

        return [
            {
                "name":
                    str(row.name or ""),

                "stock_entry_type":
                    str(
                        row.stock_entry_type
                        or ""
                    ),

                "purpose":
                    str(
                        row.purpose
                        or ""
                    ),

                "posting_date":
                    str(
                        row.posting_date
                        or ""
                    ),

                "from_warehouse":
                    str(
                        row.from_warehouse
                        or ""
                    ),

                "to_warehouse":
                    str(
                        row.to_warehouse
                        or ""
                    ),

                "work_order":
                    str(
                        row.work_order
                        or ""
                    ),

                "docstatus":
                    int(
                        row.docstatus
                        or 0
                    ),
            }
            for row in rows
        ]

        return []


# =========================================================
# WORK ORDER DETAIL
# =========================================================

@frappe.whitelist()
def get_assignment_notifications(since=None):
    """Return Job Card assignments created after the supplied timestamp.

    This powers SR Connect browser/PWA notifications. It deliberately reads
    ToDo assignments so the notification is tied to the same assignment
    mechanism that controls the employee's Job Card list.
    """
    if _is_guest():
        return []

    since_dt = None
    if since:
        try:
            since_dt = get_datetime(since)
        except Exception:
            since_dt = None

    filters = {
        "allocated_to": frappe.session.user,
        "reference_type": "Job Card",
        "status": ["in", ["Open", "Closed"]],
    }
    if since_dt:
        filters["creation"] = [">", since_dt]

    rows = frappe.get_all(
        "ToDo",
        filters=filters,
        fields=["name", "reference_name", "description", "creation", "assigned_by", "owner"],
        order_by="creation asc",
        limit_page_length=50,
    )

    result = []
    for row in rows:
        job_card = row.reference_name
        if not job_card or not frappe.db.exists("Job Card", job_card):
            continue

        try:
            info = _job_card_data(job_card)
        except Exception:
            continue

        result.append({
            "todo": row.name,
            "job_card": job_card,
            "job_no": info.get("job_no") or 1,
            "work_order": info.get("work_order") or "",
            "operation": info.get("operation") or "",
            "item_name": info.get("item_name") or "",
            "batch_no": info.get("batch_no") or "",
            "created_at": str(row.creation),
            "assigned_by": row.assigned_by or row.owner or "",
        })

    return result


@frappe.whitelist()
def get_work_order(work_order_id):
    if _is_guest():
        frappe.throw("Please login")

    if not frappe.db.exists(
        "Work Order",
        work_order_id,
    ):
        frappe.throw(
            "Work Order not found: "
            + str(work_order_id)
        )

    wo = frappe.get_doc(
        "Work Order",
        work_order_id,
    )

    info = _work_order_data(wo)

    job_cards = _get_ordered_job_cards(
        work_order_id
    )

    info["job_cards"] = []

    for row in job_cards:

        todo = frappe.get_all(
            "ToDo",
            filters={
                "reference_type": "Job Card",
                "reference_name": row.name,
                "status": "Open",
            },
            fields=[
                "allocated_to",
            ],
            order_by="creation desc",
            limit_page_length=1,
        )

        assigned_to = (
            str(todo[0].allocated_to or "")
            if todo
            else ""
        )

        assigned_employee = ""

        if assigned_to:
            assigned_employee = str(
                frappe.db.get_value(
                    "Employee",
                    {
                        "user_id": assigned_to,
                    },
                    "employee_name",
                )
                or assigned_to
            )

        info["job_cards"].append({
            "name": row.name,
            "operation": row.operation or "",
            "status": row.status or "",
            "docstatus": int(
                row.docstatus or 0
            ),
            "total_completed_qty": flt(
                row.total_completed_qty or 0
            ),
            "for_quantity": flt(
                row.for_quantity or 0
            ),
            "assigned_to": assigned_to,
            "assigned_employee": assigned_employee,
        })

    stock_entries = frappe.get_all(
        "Stock Entry",
        filters={
            "work_order": work_order_id,
        },
        fields=[
            "name",
            "stock_entry_type",
            "purpose",
            "posting_date",
            "docstatus",
            "from_warehouse",
            "to_warehouse",
        ],
        order_by="posting_date desc, creation desc",
    )

    info["stock_entries"] = [
        {
            "name": row.name,
            "stock_entry_type": row.stock_entry_type or "",
            "purpose": row.purpose or "",
            "posting_date": str(
                row.posting_date or ""
            ),
            "docstatus": int(
                row.docstatus or 0
            ),
            "from_warehouse": row.from_warehouse or "",
            "to_warehouse": row.to_warehouse or "",
        }
        for row in stock_entries
    ]

    info["stock_given"] = any(
        int(row.docstatus or 0) == 1
        for row in stock_entries
    )

    # Keep ERPNext Work Order status authoritative.
    # Stock Entry submit already changes Not Started -> In Process.
    # Do not override Completed/Stopped/Closed here.

    return info

# =========================================================
# JOB CARD DETAIL
# =========================================================

@frappe.whitelist()
def get_job_card(job_card_id):
    if _is_guest():
        frappe.throw("Please login")

    if job_card_id not in _assigned_job_card_names():
        frappe.throw("This Job Card is not assigned to you")

    return _job_card_data(job_card_id)


# =========================================================
# START
# =========================================================

@frappe.whitelist()
def start_job(job_card_id):
    if _is_guest():
        frappe.throw("Please login")

    if job_card_id not in _assigned_job_card_names():
        frappe.throw("This Job Card is not assigned to you")

    jc = frappe.get_doc("Job Card", job_card_id)

    if jc.docstatus == 1:
        frappe.throw("Job Card is already submitted.")

    info = _job_card_data(job_card_id)

    if info["blocked"]:
        frappe.throw(info["block_message"])

    for row in jc.get("time_logs") or []:
        if row.from_time and not row.to_time:
            return {
                "success": True,
                "status": "Work In Progress",
                "message": "Job already running",
            }

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user},
        "name",
    )

    log = {
        "from_time": now_datetime(),
        "completed_qty": 0,
    }

    if employee:
        log["employee"] = employee

    jc.append("time_logs", log)
    jc.status = "Work In Progress"
    jc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "success": True,
        "status": "Work In Progress",
        "message": "Job Started",
    }


# =========================================================
# PUSH / PAUSE
# =========================================================

@frappe.whitelist()
def pause_job(job_card_id):
    if _is_guest():
        frappe.throw("Please login")

    if job_card_id not in _assigned_job_card_names():
        frappe.throw("This Job Card is not assigned to you")

    jc = frappe.get_doc("Job Card", job_card_id)

    if jc.docstatus == 1:
        frappe.throw("Job Card is already submitted.")

    found = False

    for row in reversed(jc.get("time_logs") or []):
        if row.from_time and not row.to_time:
            row.to_time = now_datetime()
            found = True
            break

    if found:
        # IMPORTANT: keep Open here so the cumulative timer remains visible.
        # It will appear under "In Process" in the UI.
        jc.status = "Open"
        jc.save(ignore_permissions=True)
        frappe.db.commit()

    info = _job_card_data(job_card_id)

    return {
        "success": True,
        "status": jc.status,
        "elapsed_seconds": info["elapsed_seconds"],
        "message": "Timer Paused",
    }


# =========================================================
# COMPLETE
# =========================================================


@frappe.whitelist()
def sr_make_material_consumption_stock_entry(work_order_id, qty):
    from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

    work_order_id = str(work_order_id or "").strip()

    if not work_order_id:
        frappe.throw("Work Order is required.")

    wo = frappe.get_doc("Work Order", work_order_id)

    wo_qty = flt(wo.qty or 0)

    # =========================================================
    # MATERIAL CONSUMPTION QUANTITY
    # =========================================================
    #
    # Always use actual PACKING & SHIFTING completed quantity.
    #
    # Example:
    # Work Order = 1000
    # Packing & Shifting = 975
    # Material Consumption = 975
    # =========================================================

    final_completed_qty = flt(
        frappe.db.get_value(
            "Work Order Operation",
            {
                "parent": work_order_id,
                "operation": "PACKING & SHIFTING",
            },
            "completed_qty",
        ) or 0
    )

    # Fallback to submitted final Job Card
    if final_completed_qty <= 0:

        result = frappe.db.sql(
            """
            SELECT
                COALESCE(SUM(total_completed_qty), 0)
            FROM `tabJob Card`
            WHERE
                work_order = %s
                AND operation = 'PACKING & SHIFTING'
                AND docstatus = 1
            """,
            (work_order_id,),
        )

        if result:
            final_completed_qty = flt(result[0][0] or 0)

    if final_completed_qty > 0:
        consumption_qty = final_completed_qty
    else:
        consumption_qty = flt(qty)

    if consumption_qty <= 0:
        frappe.throw(
            "PACKING & SHIFTING completed quantity is required "
            "before Material Consumption."
        )

    if wo_qty > 0 and consumption_qty > wo_qty:
        consumption_qty = wo_qty

    # =========================================================
    # NATIVE ERPNext MATERIAL CONSUMPTION
    # =========================================================
    #
    # IMPORTANT:
    # Do NOT force Work Order finished-product batch here.
    #
    # Material Consumption must contain the BOM/raw-material
    # rows generated by native ERPNext.
    #
    # Finished-product batch belongs to the final Material
    # Receipt / Manufacture entry, not this consumption entry.
    # =========================================================

    se = make_stock_entry(
        work_order_id=work_order_id,
        purpose="Material Consumption for Manufacture",
        qty=consumption_qty,
    )

    return se

@frappe.whitelist()
def update_work_order_batch(work_order_id, batch_no):
    if not frappe.has_permission(
        "Work Order",
        ptype="write",
        user=frappe.session.user,
    ):
        frappe.throw(
            "You do not have Write permission for Work Order."
        )

    work_order_id = str(work_order_id or "").strip()
    batch_no = str(batch_no or "").strip().upper()

    if not work_order_id:
        frappe.throw("Work Order is required.")

    if not batch_no:
        frappe.throw("Batch No is required.")

    wo = frappe.get_doc("Work Order", work_order_id)

    status = str(wo.status or "Not Started").strip()

    if status in (
        "In Process",
        "Completed",
        "Stopped",
        "Closed",
    ):
        frappe.throw(
            "Batch No cannot be changed after Work Order has started."
        )

    # ---------------------------------------------------------
    # IMPORTANT:
    # Previous Batch MUST come from the previous Work Order
    # of the same Production Item.
    #
    # Do NOT use current Work Order old batch here.
    # Example:
    # Previous WO = B244B
    # Current WO old = B244D
    # Current WO new = B244C
    #
    # Result:
    # previous_batch_id = B244B
    # batch_no          = B244C
    # ---------------------------------------------------------

    previous_batch = ""

    production_item = str(
        wo.get("production_item") or ""
    ).strip()

    if production_item:
        previous_rows = frappe.db.get_all(
            "Work Order",
            filters={
                "production_item": production_item,
                "name": ["!=", work_order_id],
                "docstatus": ["<", 2],
            },
            fields=[
                "name",
                "custom_new_batch_id",
                "creation",
            ],
            order_by="creation desc",
            limit=50,
        )

        for row in previous_rows:
            candidate = str(
                row.get("custom_new_batch_id") or ""
            ).strip().upper()

            if candidate:
                previous_batch = candidate
                break

    # ---------------------------------------------------------
    # If no older Work Order batch exists, retain an already
    # stored previous batch if available.
    # ---------------------------------------------------------

    if not previous_batch:
        previous_batch = str(
            wo.get("custom_previous_batch_id") or ""
        ).strip().upper()

    # ---------------------------------------------------------
    # Save previous Work Order batch
    # ---------------------------------------------------------

    if frappe.db.has_column(
        "Work Order",
        "custom_previous_batch_id"
    ):
        frappe.db.set_value(
            "Work Order",
            work_order_id,
            "custom_previous_batch_id",
            previous_batch,
            update_modified=False,
        )

    # ---------------------------------------------------------
    # Save NEW batch to SAME Work Order
    # ---------------------------------------------------------

    frappe.db.set_value(
        "Work Order",
        work_order_id,
        "custom_new_batch_id",
        batch_no,
        update_modified=True,
    )

    frappe.db.commit()

    return {
        "success": True,
        "work_order_id": work_order_id,
        "previous_batch_id": previous_batch,
        "batch_no": batch_no,
        "new_batch_id": batch_no,
        "status": status,
    }


@frappe.whitelist()
def complete_job(job_card_id, completed_qty=None):
    if _is_guest():
        frappe.throw("Please login")

    if job_card_id not in _assigned_job_card_names():
        frappe.throw("This Job Card is not assigned to you")

    jc = frappe.get_doc("Job Card", job_card_id)

    if jc.docstatus == 1:
        frappe.throw("Job Card is already submitted.")

    info = _job_card_data(job_card_id)

    if info["blocked"]:
        frappe.throw(info["block_message"])

    # Every Job Card must receive an actual completed quantity.
    # Intermediate operations are no longer forced to zero.
    if completed_qty in (None, ""):
        frappe.throw(
            "Enter Completed Quantity for "
            + str(jc.operation or "this Job Card")
            + "."
        )

    qty = flt(completed_qty)

    if qty <= 0:
        frappe.throw(
            "Completed Quantity must be greater than 0."
        )

    work_order_qty = flt(
        frappe.db.get_value(
            "Work Order",
            jc.work_order,
            "qty",
        ) or 0
    )

    if work_order_qty and qty > work_order_qty:
        frappe.throw(
            "Completed Quantity cannot be greater than "
            "Work Order quantity "
            + str(work_order_qty)
            + "."
        )

    # Do not allow a Job Card to complete above its assigned quantity.
    job_card_qty = flt(jc.for_quantity or 0)

    if job_card_qty and qty > job_card_qty:
        frappe.throw(
            "Completed Quantity cannot be greater than "
            "Job Card quantity "
            + str(job_card_qty)
            + "."
        )

    # If user clicks Complete after Push/Pause, there is no open log.
    # In that case, do NOT reset the timer. The previous closed logs
    # remain the cumulative time.
    found = False

    for row in reversed(jc.get("time_logs") or []):
        if row.from_time and not row.to_time:
            row.to_time = now_datetime()
            row.completed_qty = qty
            found = True
            break

    # ---------------------------------------------------------
    # IMPORTANT:
    # Complete must not run ERPNext's normal Job Card validation.
    # In particular, ERPNext can compare the final operation quantity
    # with the previous operation quantity.
    #
    # We therefore update the time-log child row and the parent fields
    # directly in DB. The actual final quantity is still written to the
    # Work Order only during Submit.
    # ---------------------------------------------------------

    if found:
        for row in reversed(jc.get("time_logs") or []):
            if row.from_time and row.to_time:
                values = {
                    "to_time": row.to_time,
                    "completed_qty": qty,
                }

                try:
                    frappe.db.set_value(
                        row.doctype,
                        row.name,
                        values,
                        update_modified=False,
                    )
                except Exception:
                    # Fallback for unusual child-table metadata.
                    pass

                break

    # Every completed Job Card keeps its actual completed quantity.
    # Intermediate operations must not be forced back to zero.
    parent_qty = qty

    frappe.db.set_value(
        "Job Card",
        jc.name,
        {
            "status": "Completed",
            "total_completed_qty": parent_qty,
        },
        update_modified=True,
    )

    frappe.db.commit()

    updated = _job_card_data(job_card_id)

    return {
        "success": True,
        "status": "Completed",
        "completed_qty": qty,
        "elapsed_seconds": updated["elapsed_seconds"],
        "is_final": info["is_final"],
        "message": "Job Card Completed. Submit Job Card.",
    }


# =========================================================
# SAVE
# =========================================================

@frappe.whitelist()
def save_job(job_card_id, completed_qty=None):
    if _is_guest():
        frappe.throw("Please login")

    if job_card_id not in _assigned_job_card_names():
        frappe.throw("This Job Card is not assigned to you")

    jc = frappe.get_doc("Job Card", job_card_id)

    if jc.docstatus == 1:
        frappe.throw("Job Card is already submitted.")

    info = _job_card_data(job_card_id)

    if info["status"] != "Completed":
        frappe.throw("Complete Job Card first.")

    if info["is_final"]:
        if completed_qty in (None, ""):
            qty = flt(jc.total_completed_qty or 0)
        else:
            qty = flt(completed_qty)

        if qty <= 0:
            frappe.throw("Enter a valid Completed Quantity.")

        work_order_qty = flt(
            frappe.db.get_value(
                "Work Order",
                jc.work_order,
                "qty",
            ) or 0
        )

        if work_order_qty and qty > work_order_qty:
            frappe.throw(
                "Completed Quantity cannot be greater than "
                "Work Order quantity "
                + str(work_order_qty)
                + "."
            )

        for row in reversed(jc.get("time_logs") or []):
            if row.to_time:
                try:
                    frappe.db.set_value(
                        row.doctype,
                        row.name,
                        "completed_qty",
                        qty,
                        update_modified=False,
                    )
                except Exception:
                    pass
                break
    else:
        qty = 0

    frappe.db.set_value(
        "Job Card",
        jc.name,
        "total_completed_qty",
        qty,
        update_modified=True,
    )

    frappe.db.commit()

    updated = _job_card_data(job_card_id)

    return {
        "success": True,
        "status": jc.status,
        "docstatus": int(jc.docstatus or 0),
        "name": jc.name,
        "completed_qty": flt(jc.total_completed_qty or 0),
        "elapsed_seconds": updated["elapsed_seconds"],
        "message": "Job Card saved successfully.",
    }


# =========================================================
# CUSTOM SUBMIT
# =========================================================

@frappe.whitelist()
def submit_job_card(job_card_id, completed_qty=None):
    if _is_guest():
        frappe.throw("Please login")

    if job_card_id not in _assigned_job_card_names():
        frappe.throw("This Job Card is not assigned to you")

    jc = frappe.get_doc("Job Card", job_card_id)

    if jc.docstatus == 1:
        return {
            "success": True,
            "status": "Submitted",
            "docstatus": 1,
            "name": jc.name,
            "completed_qty": flt(jc.total_completed_qty or 0),
            "message": "Job Card is already submitted",
        }

    info = _job_card_data(job_card_id)

    if info["blocked"]:
        frappe.throw(info["block_message"])

    if jc.status != "Completed":
        frappe.throw("Complete Job Card first.")

    # Final quantity comes from the user's Packing & Shifting entry.
    if info["is_final"]:
        if completed_qty not in (None, ""):
            qty = flt(completed_qty)

            if qty <= 0:
                frappe.throw("Enter a valid Completed Quantity.")

            work_order_qty = flt(
                frappe.db.get_value(
                    "Work Order",
                    jc.work_order,
                    "qty",
                ) or 0
            )

            if work_order_qty and qty > work_order_qty:
                frappe.throw(
                    "Completed Quantity cannot be greater than "
                    "Work Order quantity "
                    + str(work_order_qty)
                    + "."
                )

            # IMPORTANT: do NOT call jc.save() here.
            # ERPNext Job Card save/validate can reject the final operation
            # quantity when it is larger than a previous operation.
            # We intentionally bypass that validation for SR Connect.
            # Use a direct SQL UPDATE here so no Job Card controller
            # validation/on_update path can re-run the previous-operation
            # quantity check during SR Connect submission.
            frappe.db.sql(
                "UPDATE `tabJob Card` SET total_completed_qty=%s, modified=NOW() WHERE name=%s",
                (qty, jc.name),
            )

            for row in reversed(jc.get("time_logs") or []):
                if row.to_time:
                    try:
                        frappe.db.set_value(
                            row.doctype,
                            row.name,
                            "completed_qty",
                            qty,
                            update_modified=False,
                        )
                    except Exception:
                        pass
                    break

            # Keep the in-memory value in sync for the response below.
            jc.total_completed_qty = qty

    # =====================================================
    # VERY IMPORTANT:
    #
    # DO NOT call jc.submit().
    #
    # ERPNext's normal Job Card submit validates:
    # final operation completed_qty <= previous operation qty.
    #
    # SR Connect intentionally allows the final Packing &
    # Shifting quantity to be the actual packed quantity.
    # Therefore we mark docstatus directly.
    # =====================================================

    final_qty = flt(jc.total_completed_qty or 0)

    if final_qty <= 0:
        frappe.throw(
            "Completed Quantity is required before submitting Job Card."
        )

    # =====================================================
    # INTERMEDIATE OPERATIONS:
    # Use ERPNext's native Job Card submit flow.
    #
    # This is important because native submit updates the
    # linked Work Order Operation.completed_qty and all
    # related manufacturing data.
    # =====================================================
    if not info["is_final"]:

        jc.submit()

        # Refresh from database so the response and later
        # logic use the actual submitted value.
        jc = frappe.get_doc(
            "Job Card",
            job_card_id,
        )

        final_qty = flt(
            jc.total_completed_qty or 0
        )

    else:

        # =================================================
        # FINAL PACKING & SHIFTING:
        # Keep the existing SR Connect special flow.
        #
        # Native submit is intentionally bypassed here so
        # the actual final packed quantity (for example 975)
        # can remain independent of the previous operation.
        # =================================================
        frappe.db.sql(
            """
            UPDATE `tabJob Card`
            SET total_completed_qty=%s, docstatus=1, modified=NOW()
            WHERE name=%s
            """,
            (final_qty, jc.name),
        )

        jc.docstatus = 1

    # =====================================================
    # WORK ORDER OPERATION SYNC
    # =====================================================
    # Keep the linked operation explicitly synchronized.
    # For intermediate operations native jc.submit() already
    # performs this update; this remains as a safe final sync.
    if getattr(jc, "operation_id", None):
        frappe.db.set_value(
            "Work Order Operation",
            jc.operation_id,
            {
                "completed_qty": final_qty,
                "status": "Completed",
            },
            update_modified=False,
        )

    frappe.db.commit()

    # =====================================================
    # FINAL PACKING QUANTITY -> WORK ORDER
    # =====================================================

    if info["is_final"] and final_qty > 0 and jc.work_order:
        frappe.db.sql(
            "UPDATE `tabWork Order` SET produced_qty=%s, modified=NOW() WHERE name=%s",
            (final_qty, jc.work_order),
        )

        frappe.db.commit()

    _close_assigned_todos(jc.name)
    frappe.db.commit()

    return {
        "success": True,
        "status": "Submitted",
        "docstatus": 1,
        "name": jc.name,
        "completed_qty": final_qty,
        "message": "Job Card submitted successfully.",
    }


# =========================================================
# COMPATIBILITY API
# =========================================================

@frappe.whitelist()
def submit_job(job_card_id, completed_qty=None):
    return submit_job_card(job_card_id, completed_qty)


@frappe.whitelist()
def toggle_job_card(job_card_id, action="start"):
    if action == "start":
        return start_job(job_card_id)

    if action in ("stop", "complete"):
        return complete_job(job_card_id)

    if action == "pause":
        return pause_job(job_card_id)

    return {
        "success": False,
        "error": "Invalid action",
    }



# =========================================================
# SR CONNECT WORK ORDER / ERPNext INTEGRATION
# =========================================================

@frappe.whitelist()
def get_manufacturing_items():
    """Return ERPNext Items that have an active submitted BOM."""
    if _is_guest():
        frappe.throw("Please login")

    rows = frappe.db.sql(
        """
        SELECT
            i.name,
            i.item_name,
            i.stock_uom,
            i.has_batch_no
        FROM `tabItem` i
        INNER JOIN `tabBOM` b
            ON b.item = i.name
           AND b.docstatus = 1
           AND b.is_active = 1
        WHERE
            i.disabled = 0
            AND i.is_stock_item = 1
        GROUP BY
            i.name,
            i.item_name,
            i.stock_uom,
            i.has_batch_no
        ORDER BY i.item_name, i.name
        """,
        as_dict=True,
    )

    return {
        "items": [
            {
                "name": str(r.name or ""),
                "item_name": str(r.item_name or r.name or ""),
                "stock_uom": str(r.stock_uom or ""),
                "has_batch_no": int(r.has_batch_no or 0),
            }
            for r in rows
        ]
    }


@frappe.whitelist()
def get_work_order_create_data(production_item):
    """Return active submitted BOMs for the selected item."""

    if _is_guest():
        frappe.throw("Please login")

    production_item = str(
        production_item or ""
    ).strip()

    if not production_item:
        return {
            "items": []
        }

    if not frappe.db.exists(
        "Item",
        production_item
    ):
        frappe.throw(
            "Item not found: " +
            production_item
        )

    # Keep this compatible with the ERPNext version
    # installed on this site.  Do NOT request
    # fields that may not exist in the BOM DocType.
    shelf_life_months = int(
        flt(
            frappe.db.get_value(
                "Item",
                production_item,
                "custom_shelf_life_months",
            ) or 0
        )
    )

    rows = frappe.get_all(
        "BOM",
        filters={
            "item": production_item,
            "docstatus": 1,
            "is_active": 1,
        },
        fields=[
            "name",
            "is_default",
            "quantity",
        ],
        order_by="is_default desc, creation desc",
        limit_page_length=100,
    )

    return {
        "items": [
            {
                "name": str(
                    row.name or ""
                ),
                "is_default": int(
                    row.is_default or 0
                ),
                "quantity": flt(
                    row.quantity or 1
                ),
            }
            for row in rows
        ],
        "custom_shelf_life_months": shelf_life_months,
    }


@frappe.whitelist()
def preview_work_order_materials(production_item, bom_no, qty):
    """
    Let ERPNext calculate required_items.
    No browser-side BOM calculation.
    """
    if _is_guest():
        frappe.throw("Please login")

    qty = flt(qty)

    if qty <= 0:
        return {
            "success": False,
            "items": [],
            "message": "Enter a valid quantity.",
        }

    if not production_item:
        frappe.throw("Production Item is required")

    if not bom_no:
        frappe.throw("BOM is required")

    company = (
        frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value(
            "Global Defaults",
            "default_company",
        )
    )

    wo = frappe.new_doc("Work Order")

    wo.production_item = production_item
    wo.bom_no = bom_no
    wo.qty = qty
    wo.company = company

    # ERPNext itself supplies operations and required raw materials.
    try:
        wo.set_work_order_operations()
    except Exception:
        pass

    try:
        wo.set_required_items()
    except Exception:
        # Fallback: use ERPNext's BOM calculation directly.
        from erpnext.manufacturing.doctype.bom.bom import get_bom_items

        bom_items = get_bom_items(
            bom_no,
            wo.use_multi_level_bom,
            qty=qty,
        )

        for row in bom_items:
            wo.append(
                "required_items",
                {
                    "item_code": row.item_code,
                    "item_name": row.item_name,
                    "required_qty": flt(row.qty),
                    "stock_uom": row.stock_uom,
                    "uom": row.get("uom"),
                    "source_warehouse": row.get("source_warehouse"),
                    "operation": row.get("operation"),
                },
            )

    return {
        "success": True,
        "production_item": production_item,
        "bom_no": bom_no,
        "qty": qty,
        "items": [
            {
                "item_code": str(row.item_code or ""),
                "item_name": str(row.item_name or row.item_code or ""),
                "required_qty": flt(row.required_qty or 0),
                "uom": str(
                    row.get("uom")
                    or row.get("stock_uom")
                    or ""
                ),
                "stock_uom": str(row.get("stock_uom") or ""),
                "warehouse": str(
                    row.get("source_warehouse")
                    or ""
                ),
                "operation": str(
                    row.get("operation")
                    or ""
                ),
            }
            for row in wo.get("required_items") or []
        ],
    }


@frappe.whitelist()
def get_latest_work_order_batch(production_item):
    """
    Return the latest New Batch Id created on a Work Order
    for the selected production item.

    IMPORTANT:
    This does NOT read the old Batch master list.
    It reads Work Order.custom_new_batch_id directly.
    """

    if _is_guest():
        frappe.throw("Please login")

    production_item = str(
        production_item or ""
    ).strip()

    if not production_item:
        return {
            "batch_no": "",
            "batch": None,
        }

    if not frappe.db.exists(
        "Item",
        production_item
    ):
        frappe.throw(
            "Item not found: " +
            production_item
        )

    row = frappe.db.sql(
        """
        SELECT
            name,
            production_item,
            custom_new_batch_id,
            qty,
            produced_qty,
            creation
        FROM `tabWork Order`
        WHERE
            production_item = %s
            AND IFNULL(
                custom_new_batch_id,
                ''
            ) != ''
        ORDER BY creation DESC
        LIMIT 1
        """,
        (production_item,),
        as_dict=True,
    )

    if not row:
        return {
            "batch_no": "",
            "batch": None,
        }

    latest = row[0]

    return {
        "batch_no": str(
            latest.get(
                "custom_new_batch_id"
            )
            or ""
        ).strip(),

        "batch": {
            "work_order": str(
                latest.get("name")
                or ""
            ),

            "batch_no": str(
                latest.get(
                    "custom_new_batch_id"
                )
                or ""
            ).strip(),

            "item": str(
                latest.get(
                    "production_item"
                )
                or ""
            ),

            "batch_qty": flt(
                latest.get("qty")
                or 0
            ),

            "produced_qty": flt(
                latest.get(
                    "produced_qty"
                )
                or 0
            ),

            "creation": str(
                latest.get(
                    "creation"
                )
                or ""
            ),
        },
    }


def get_latest_work_order_batch(production_item):
    if _is_guest():
        frappe.throw("Please login")

    if not production_item:
        return {
            "success": True,
            "batch_no": "",
        }

    batch = frappe.get_all(
        "Batch",
        filters={
            "item": production_item,
            "disabled": 0,
        },
        fields=[
            "name",
            "batch_id",
            "item",
            "item_name",
            "manufacturing_date",
            "batch_qty",
            "produced_qty",
        ],
        order_by="creation desc",
        limit_page_length=1,
    )

    if not batch:
        return {
            "success": True,
            "batch_no": "",
            "batch": None,
        }

    row = batch[0]

    return {
        "success": True,
        "batch_no": str(row.name or row.batch_id or ""),
        "batch": {
            "name": str(row.name or ""),
            "batch_id": str(row.batch_id or row.name or ""),
            "item": str(row.item or ""),
            "item_name": str(row.item_name or ""),
            "manufacturing_date": str(
                row.manufacturing_date or ""
            ),
            "batch_qty": flt(row.batch_qty or 0),
            "produced_qty": flt(row.produced_qty or 0),
        },
    }



@frappe.whitelist()
def get_latest_work_order_new_batch(production_item):
    """
    Return the New Batch Id from the latest Work Order
    for the selected production item.

    IMPORTANT:
    This reads ONLY:
        tabWork Order.custom_new_batch_id

    It does NOT read the Batch master.
    Draft and Submitted Work Orders are both considered.
    """

    if _is_guest():
        frappe.throw("Please login")

    production_item = str(
        production_item or ""
    ).strip()

    if not production_item:
        return {
            "success": True,
            "batch_no": "",
            "work_order": "",
        }

    row = frappe.db.sql(
        """
        SELECT
            name,
            production_item,
            custom_new_batch_id,
            qty,
            produced_qty,
            status,
            docstatus,
            creation,
            modified
        FROM `tabWork Order`
        WHERE
            production_item = %s
            AND TRIM(
                IFNULL(
                    custom_new_batch_id,
                    ''
                )
            ) != ''
        ORDER BY
            creation DESC,
            modified DESC
        LIMIT 1
        """,
        (production_item,),
        as_dict=True,
    )

    if not row:
        return {
            "success": True,
            "batch_no": "",
            "work_order": "",
        }

    latest = row[0]

    batch_no = str(
        latest.get(
            "custom_new_batch_id"
        )
        or ""
    ).strip()

    return {
        "success": True,

        "batch_no":
            batch_no,

        "work_order":
            str(
                latest.get("name")
                or ""
            ),

        "production_item":
            str(
                latest.get(
                    "production_item"
                )
                or ""
            ),

        "qty":
            flt(
                latest.get("qty")
                or 0
            ),

        "produced_qty":
            flt(
                latest.get(
                    "produced_qty"
                )
                or 0
            ),

        "status":
            str(
                latest.get("status")
                or ""
            ),

        "docstatus":
            int(
                latest.get("docstatus")
                or 0
            ),

        "creation":
            str(
                latest.get("creation")
                or ""
            ),
    }



# =========================================================
# SR CONNECT - COPY BOM OPERATIONS TO WORK ORDER
# =========================================================

def _sr_populate_work_order_operations(wo):
    """
    Copy the submitted BOM operations into the Work Order
    operations child table.

    This is intentionally based on the actual BOM, so the
    Work Order has the same operations as ERPNext Web.
    """

    bom_no = str(
        getattr(wo, "bom_no", None) or ""
    ).strip()

    if not bom_no:
        return

    if not frappe.db.exists(
        "BOM",
        bom_no
    ):
        frappe.throw(
            "BOM not found: " + bom_no
        )

    bom = frappe.get_doc(
        "BOM",
        bom_no
    )

    if int(bom.docstatus or 0) != 1:
        frappe.throw(
            "BOM must be submitted: " + bom_no
        )

    if int(bom.is_active or 0) != 1:
        frappe.throw(
            "BOM is not active: " + bom_no
        )

    # Do not duplicate operations.
    if wo.get("operations"):
        return

    for row in (
        bom.get("operations") or []
    ):

        operation = str(
            row.operation or ""
        ).strip()

        if not operation:
            continue

        values = {
            "operation": operation,
            "workstation": str(
                row.workstation or ""
            ).strip(),
        }

        # Copy optional fields only when available.
        if getattr(row, "time_in_mins", None) is not None:
            values["time_in_mins"] = flt(
                row.time_in_mins or 0
            )

        if getattr(row, "batch_size", None) is not None:
            values["batch_size"] = flt(
                row.batch_size or 0
            )

        if getattr(row, "sequence_id", None) is not None:
            values["sequence_id"] = row.sequence_id

        if getattr(row, "description", None):
            values["description"] = row.description

        wo.append(
            "operations",
            values
        )


# =========================================================
# SR CONNECT - CREATE JOB CARDS FROM WORK ORDER OPERATIONS
# =========================================================

def _sr_ensure_job_cards_for_work_order(wo):

    existing = frappe.get_all(
        "Job Card",
        filters={
            "work_order": wo.name,
        },
        fields=[
            "name",
            "operation",
            "status",
            "docstatus",
            "for_quantity",
        ],
        order_by="creation asc",
    )

    if existing:
        return existing

    operations = list(
        wo.get("operations") or []
    )

    if not operations:
        return []

    for op in operations:

        operation = str(
            op.operation or ""
        ).strip()

        if not operation:
            continue

        # Safety: don't create duplicates.
        if frappe.db.exists(
            "Job Card",
            {
                "work_order": wo.name,
                "operation": operation,
            }
        ):
            continue

        values = {
            "doctype": "Job Card",
            "work_order": wo.name,
            "operation": operation,
            "for_quantity": flt(
                wo.qty or 0
            ),
        }

        workstation = str(
            op.workstation or ""
        ).strip()

        if workstation:
            values["workstation"] = workstation

        jc = frappe.get_doc(
            values
        )

        jc.insert(
            ignore_permissions=True
        )

    frappe.db.commit()

    return frappe.get_all(
        "Job Card",
        filters={
            "work_order": wo.name,
        },
        fields=[
            "name",
            "operation",
            "status",
            "docstatus",
            "for_quantity",
        ],
        order_by="creation asc",
    )


@frappe.whitelist()
def get_item_shelf_life(production_item):
    production_item = str(production_item or "").strip()

    if not production_item:
        return {
            "custom_shelf_life_months": 0
        }

    months = frappe.db.get_value(
        "Item",
        production_item,
        "custom_shelf_life_months",
    ) or 0

    return {
        "custom_shelf_life_months": int(flt(months))
    }


@frappe.whitelist()
def create_work_order_from_sr(
    production_item,
    bom_no,
    qty,
    labour_qty=None,
    posting_date=None,
    new_batch_no=None,
    submit=0,
    batch_no=None,
    work_order_id=None,
):

    if _is_guest():
        frappe.throw("Please login")

    production_item = str(
        production_item or ""
    ).strip()

    bom_no = str(
        bom_no or ""
    ).strip()

    qty = flt(qty)

    labour_qty = flt(
        labour_qty or 0
    )

    new_batch_no = str(
        new_batch_no or batch_no or ""
    ).strip()

    submit = int(
        flt(submit or 0)
    )

    # -----------------------------------------------------
    # MFG / EXP / SHELF LIFE
    # MFG = selected Work Order date
    # EXP = MFG + Item Master custom_shelf_life_months
    # -----------------------------------------------------
    mfg_date = str(posting_date or "").strip()[:10]
    shelf_life_months = 0
    calculated_exp_date = ""

    if production_item:
        shelf_life_months = int(
            flt(
                frappe.db.get_value(
                    "Item",
                    production_item,
                    "custom_shelf_life_months",
                ) or 0
            )
        )

    if mfg_date and shelf_life_months > 0:
        from frappe.utils import getdate, add_months

        calculated_exp_date = str(
            add_months(
                getdate(mfg_date),
                shelf_life_months,
            )
        )[:10]

    # -----------------------------------------------------
    # Validate
    # -----------------------------------------------------

    if not production_item:
        frappe.throw(
            "Item to Manufacture is required"
        )

    if not bom_no:
        frappe.throw(
            "BOM is required"
        )

    if qty <= 0:
        frappe.throw(
            "Qty to Manufacture must be greater than zero"
        )

    if labour_qty <= 0:
        frappe.throw(
            "Labour Qty is required"
        )

    if not new_batch_no:
        frappe.throw(
            "New Batch No is required"
        )

    # -----------------------------------------------------
    # IMPORTANT:
    # SAVE = create Draft
    # SUBMIT = submit the SAME Draft
    # -----------------------------------------------------

    if work_order_id:

        if not frappe.db.exists(
            "Work Order",
            work_order_id
        ):
            frappe.throw(
                "Work Order not found: "
                + str(work_order_id)
            )

        wo = frappe.get_doc(
            "Work Order",
            work_order_id
        )

        if int(wo.docstatus or 0) == 1:
            return {
                "success": True,
                "name": wo.name,
                "docstatus": 1,
                "work_order": _work_order_data(wo),
            }

    else:

        wo = frappe.new_doc(
            "Work Order"
        )

        wo.production_item = (
            production_item
        )

        wo.bom_no = bom_no

        # -------------------------------------------------
        # IMPORTANT:
        # Copy BOM operations into Work Order.
        # This fixes WO.operations == [].
        # -------------------------------------------------

        wo.qty = qty

        wo.company = (
            frappe.defaults.get_user_default(
                "Company"
            )
            or frappe.db.get_single_value(
                "Global Defaults",
                "default_company",
            )
        )

        if posting_date:
            wo.planned_start_date = (
                str(posting_date)
                + " 00:00:00"
            )

        # ERPNext custom fields visible in
        # Customize Form.

        # -------------------------------------------------
        # USE ERPNext NATIVE BOM -> WORK ORDER CALCULATION
        # -------------------------------------------------
        #
        # This populates:
        #   - Work Order Operations
        #   - Required Items
        #
        # exactly through ERPNext's own Work Order logic.
        # -------------------------------------------------

        if not wo.get("operations"):
            wo.set_work_order_operations()

        if not wo.get("required_items"):
            wo.set_required_items()

        wo.custom_labour = int(
            labour_qty
        )

        wo.custom_new_batch_id = (
            new_batch_no
        )

        # MFG / EXP / SHELF LIFE
        if mfg_date:
            wo.custom_date = mfg_date

        if calculated_exp_date:
            wo.custom_exp_date = calculated_exp_date

        # -------------------------------------------------
        # INSERT = Draft Work Order
        # ERPNext calculates Operations /
        # Required Items from BOM.
        # -------------------------------------------------

        wo.insert(
            ignore_permissions=True
        )

    # -----------------------------------------------------
    # Existing draft: make sure the required custom
    # fields are still present.
    # -----------------------------------------------------

    if not getattr(
        wo,
        "custom_labour",
        None
    ):
        wo.custom_labour = int(
            labour_qty
        )

    if not getattr(
        wo,
        "custom_new_batch_id",
        None
    ):
        wo.custom_new_batch_id = (
            new_batch_no
        )

    # Keep selected MFG date and calculated EXP on Draft too.
    if mfg_date:
        wo.custom_date = mfg_date

    if calculated_exp_date:
        wo.custom_exp_date = calculated_exp_date

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    if not submit:

        wo.save(
            ignore_permissions=True
        )

        frappe.db.commit()

        fresh = frappe.get_doc(
            "Work Order",
            wo.name
        )

        return {
            "success": True,
            "name": fresh.name,
            "docstatus": int(
                fresh.docstatus or 0
            ),
            "status": str(
                fresh.status or "Not Started"
            ),
            "custom_date": str(
                getattr(fresh, "custom_date", "") or ""
            )[:10],
            "custom_exp_date": str(
                getattr(fresh, "custom_exp_date", "") or ""
            )[:10],
            "shelf_life_months": int(
                flt(shelf_life_months or 0)
            ),
            "production_item": str(
                fresh.production_item or ""
            ),
            "item_name": str(
                fresh.item_name
                or fresh.production_item
                or ""
            ),
            "bom_no": str(
                fresh.bom_no or ""
            ),
            "qty": flt(
                fresh.qty or 0
            ),
            "labour_qty": flt(
                getattr(
                    fresh,
                    "custom_labour",
                    0
                ) or 0
            ),
            "batch_no": str(
                getattr(
                    fresh,
                    "custom_new_batch_id",
                    ""
                ) or ""
            ),
            "work_order": _work_order_data(
                fresh
            ),
            "message":
                "Work Order saved as Draft.",
        }

    # -----------------------------------------------------
    # SUBMIT SAME WORK ORDER
    # -----------------------------------------------------

    if int(wo.docstatus or 0) != 1:

        wo.submit()

    # -----------------------------------------------------
    # IMPORTANT:
    #
    # ERPNext Work Order.submit() already runs its native
    # create_job_card() lifecycle for the Work Order
    # operations.
    #
    # DO NOT call make_job_card() again here.
    # -----------------------------------------------------

    frappe.db.commit()

    fresh = frappe.get_doc(
        "Work Order",
        wo.name
    )

    return {
        "success": True,
        "name": fresh.name,
        "docstatus": int(
            fresh.docstatus or 0
        ),
        "status": str(
            fresh.status or ""
        ),
        "production_item": str(
            fresh.production_item or ""
        ),
        "item_name": str(
            fresh.item_name
            or fresh.production_item
            or ""
        ),
        "bom_no": str(
            fresh.bom_no or ""
        ),
        "qty": flt(
            fresh.qty or 0
        ),
        "labour_qty": flt(
            getattr(
                fresh,
                "custom_labour",
                0
            ) or 0
        ),
        "batch_no": str(
            getattr(
                fresh,
                "custom_new_batch_id",
                ""
            ) or ""
        ),
        "work_order": _work_order_data(
            fresh
        ),
        "message":
            "Work Order submitted successfully.",
    }



@frappe.whitelist()
def get_work_order_job_cards(work_order_id):

    if _is_guest():
        frappe.throw("Please login")

    work_order_id = str(
        work_order_id or ""
    ).strip()

    if not work_order_id:
        frappe.throw(
            "Work Order is required"
        )

    if not frappe.db.exists(
        "Work Order",
        work_order_id
    ):
        frappe.throw(
            "Work Order not found: " +
            work_order_id
        )

    rows = frappe.get_all(
        "Job Card",
        filters={
            "work_order": work_order_id,
        },
        fields=[
            "name",
            "operation",
            "status",
            "docstatus",
            "for_quantity",
            "total_completed_qty",
            "creation",
        ],
        order_by="creation asc",
        limit_page_length=500,
    )

    result = []

    for row in rows:

        todo = frappe.get_all(
            "ToDo",
            filters={
                "reference_type": "Job Card",
                "reference_name": row.name,
                "status": "Open",
            },
            fields=[
                "allocated_to",
            ],
            order_by="creation desc",
            limit_page_length=1,
        )

        assigned_to = (
            todo[0].allocated_to
            if todo
            else ""
        )

        result.append({
            "name": str(
                row.name or ""
            ),

            "operation": str(
                row.operation or ""
            ),

            "status": str(
                row.status or "Open"
            ),

            "docstatus": int(
                row.docstatus or 0
            ),

            "for_quantity": flt(
                row.for_quantity or 0
            ),

            "total_completed_qty": flt(
                row.total_completed_qty or 0
            ),

            "assigned_to": str(
                assigned_to or ""
            ),
        })

    return {
        "work_order":
            work_order_id,

        "job_cards":
            result,
    }


@frappe.whitelist()
def get_work_order_stock_status(work_order_id):
    if _is_guest():
        frappe.throw("Please login")

    rows = frappe.get_all(
        "Stock Entry",
        filters={
            "work_order": work_order_id,
            "docstatus": 1,
        },
        fields=[
            "name",
            "stock_entry_type",
            "purpose",
            "posting_date",
            "from_warehouse",
            "to_warehouse",
        ],
        order_by="posting_date desc, creation desc",
    )

    return {
        "entries": [
            {
                "name": str(r.name or ""),
                "stock_entry_type": str(
                    r.stock_entry_type or ""
                ),
                "purpose": str(r.purpose or ""),
                "posting_date": str(
                    r.posting_date or ""
                ),
                "from_warehouse": str(
                    r.from_warehouse or ""
                ),
                "to_warehouse": str(
                    r.to_warehouse or ""
                ),
                "submitted": True,
            }
            for r in rows
        ]
    }



# =========================================================
# SR CONNECT - CREATE STOCK ENTRY FROM WORK ORDER
# =========================================================

@frappe.whitelist()
def _sr_stock_v2_batch(wo):

    value = str(
        getattr(
            wo,
            "custom_new_batch_id",
            ""
        )
        or ""
    ).strip()

    if value:
        return value

    return str(
        wo.name or ""
    )


def _sr_stock_v2_done_work_orders():

    # IMPORTANT:
    # Any submitted Stock Entry already linked to a Work Order
    # means that the Work Order has received stock activity.
    #
    # This intentionally includes EXISTING ERPNext Stock Entries,
    # not only entries created by the new SR Connect workflow.
    #
    # This fixes the mismatch where the real web list shows
    # fewer Not Started WOs than the new SR workflow.

    rows = frappe.get_all(
        "Stock Entry",
        filters={
            "docstatus": 1,
            "work_order": ["is", "set"],
        },
        fields=[
            "work_order",
            "name",
            "stock_entry_type",
        ],
        limit_page_length=5000,
    )

    return {
        str(row.work_order)
        for row in rows
        if row.work_order
    }


def _sr_stock_v2_has_access():

    if _is_guest():
        return False

    roles = set(
        frappe.get_roles(
            frappe.session.user
        )
    )

    return bool(
        {
            "System Manager",
            "Stock User",
            "Stock Manager",
            "Manufacturing Manager",
            "Production Manager",
        }
        & roles
    )


@frappe.whitelist()
def sr_stock_entry_groups_v2():

    if not _sr_stock_v2_has_access():
        frappe.throw(
            "You do not have Stock Entry access."
        )

    done = (
        _sr_stock_v2_done_work_orders()
    )

    rows = frappe.get_all(
        "Work Order",
        filters={
            "docstatus": 1,
        },
        fields=[
            "name",
            "production_item",
            "bom_no",
            "qty",
            "custom_new_batch_id",
            "status",
        ],
        order_by="creation desc",
        limit_page_length=1000,
    )

    item_cache = {}
    groups = {}

    for wo in rows:

        item_code = str(
            wo.production_item or ""
        ).strip()

        if not item_code:
            continue

        if item_code not in item_cache:

            item_cache[item_code] = (
                frappe.db.get_value(
                    "Item",
                    item_code,
                    "item_name",
                )
                or item_code
            )

        item_name = str(
            item_cache[item_code]
        )

        bom_no = str(
            wo.bom_no or ""
        ).strip()

        group_key = (
            item_code
            + "||"
            + bom_no
        )

        if group_key not in groups:

            groups[group_key] = {
                "group_key":
                    group_key,

                "production_item":
                    item_code,

                "item_name":
                    item_name,

                "bom_no":
                    bom_no,

                "not_started":
                    [],

                "in_progress":
                    [],
            }

        # Submitted Stock Entry means material was transferred,
        # but a Completed Work Order must never appear in In Progress.
        wo_status = str(
            wo.status or "Not Started"
        ).strip()

        is_completed = (
            wo_status == "Completed"
        )

        is_done = (
            str(wo.name) in done
            and not is_completed
        )

        # Completed production is not shown in either
        # Not Started or In Progress tab.
        if is_completed:
            continue

        batch = {

            "work_order":
                str(wo.name),

            "batch_no":
                _sr_stock_v2_batch(wo),

            "production_item":
                item_code,

            "item_name":
                item_name,

            "bom_no":
                bom_no,

            "qty":
                flt(wo.qty or 0),

            "status":
                (
                    "In Process"
                    if is_done
                    else "Not Started"
                ),
        }

        if is_done:

            groups[group_key][
                "in_progress"
            ].append(
                batch
            )

        else:

            groups[group_key][
                "not_started"
            ].append(
                batch
            )

    not_started = []
    in_progress = []

    for group in groups.values():

        if group["not_started"]:

            not_started.append({
                "group_key":
                    group["group_key"],

                "production_item":
                    group["production_item"],

                "item_name":
                    group["item_name"],

                "bom_no":
                    group["bom_no"],

                "batch_count":
                    len(
                        group["not_started"]
                    ),

                "batches":
                    group["not_started"],
            })

        if group["in_progress"]:

            in_progress.append({
                "group_key":
                    group["group_key"],

                "production_item":
                    group["production_item"],

                "item_name":
                    group["item_name"],

                "bom_no":
                    group["bom_no"],

                "batch_count":
                    len(
                        group["in_progress"]
                    ),

                "batches":
                    group["in_progress"],
            })

    return {
        "success":
            True,

        "not_started":
            not_started,

        "in_progress":
            in_progress,
    }


@frappe.whitelist()
def _sr_v3_batch_bundle_stock(
    item_code,
    warehouse,
):

    item_code = str(
        item_code or ""
    ).strip()

    warehouse = str(
        warehouse or ""
    ).strip()

    if not item_code or not warehouse:
        return {}

    rows = frappe.db.sql(
        """
        SELECT
            sabb.name AS bundle_name,
            sabb.total_qty,
            sbe.batch_no,
            sbe.qty,
            sbe.warehouse,
            sbe.is_outward,
            sabb.is_cancelled
        FROM `tabSerial and Batch Bundle` sabb
        INNER JOIN `tabSerial and Batch Entry` sbe
            ON sbe.parent = sabb.name
        WHERE
            sabb.item_code=%s
            AND sabb.warehouse=%s
            AND COALESCE(
                sabb.is_cancelled,
                0
            )=0
            AND COALESCE(
                sbe.batch_no,
                ''
            ) != ''
        ORDER BY
            sabb.posting_datetime ASC,
            sabb.creation ASC,
            sbe.idx ASC
        """,
        (
            item_code,
            warehouse,
        ),
        as_dict=True,
    )

    balances = {}

    for row in rows:

        batch_no = str(
            row.batch_no or ""
        ).strip()

        if not batch_no:
            continue

        qty = abs(
            flt(row.qty or 0)
        )

        if qty <= 0:
            continue

        if int(
            row.is_outward or 0
        ):
            qty = -qty

        balances[batch_no] = (
            balances.get(
                batch_no,
                0
            )
            + qty
        )

    return {
        batch_no: flt(qty)
        for batch_no, qty
        in balances.items()
        if flt(qty) > 0
    }


@frappe.whitelist()
def sr_stock_item_options_v3(
    item_code
):

    if not _sr_stock_v2_has_access():
        frappe.throw(
            "You do not have Stock Entry access."
        )

    item_code = str(
        item_code or ""
    ).strip()

    if not item_code:
        frappe.throw(
            "Item is required."
        )

    items = frappe.get_all(
        "Item",
        filters={
            "disabled": 0,
            "is_stock_item": 1,
        },
        fields=[
            "name",
            "item_name",
            "item_group",
            "stock_uom",
            "has_batch_no",
        ],
        order_by="item_name asc",
        limit_page_length=500,
    )

    return {
        "success": True,
        "current_item": item_code,
        "items": items,
    }



# SR_V3_STOCK_ENTRY_HISTORY_API_V1

@frappe.whitelist()
def sr_stock_entry_history_v3(work_order_id):

    if not _sr_stock_v2_has_access():
        frappe.throw(
            "You do not have Stock Entry access."
        )

    work_order_id = str(
        work_order_id or ""
    ).strip()

    if not work_order_id:
        frappe.throw(
            "Work Order is required."
        )

    if not frappe.db.exists(
        "Work Order",
        work_order_id
    ):
        frappe.throw(
            "Work Order not found."
        )

    entries = frappe.get_all(
        "Stock Entry",
        filters={
            "work_order": work_order_id,
            "docstatus": 1,
        },
        fields=[
            "name",
            "posting_date",
            "posting_time",
            "purpose",
            "stock_entry_type",
            "from_warehouse",
            "to_warehouse",
            "creation",
        ],
        order_by="posting_date desc, posting_time desc, creation desc",
        limit_page_length=100,
    )

    result = []

    for entry in entries:

        children = frappe.get_all(
            "Stock Entry Detail",
            filters={
                "parent": entry.name,
                "parenttype": "Stock Entry",
            },
            fields=[
                "item_code",
                "item_name",
                "qty",
                "uom",
                "s_warehouse",
                "t_warehouse",
                "batch_no",
                "basic_amount",
                "stock_uom",
            ],
            order_by="idx asc",
            limit_page_length=500,
        )

        for child in children:

            result.append({
                "stock_entry":
                    entry.name,

                "posting_date":
                    str(
                        entry.posting_date or ""
                    ),

                "posting_time":
                    str(
                        entry.posting_time or ""
                    ),

                "purpose":
                    str(
                        entry.purpose or
                        entry.stock_entry_type or
                        ""
                    ),

                "item_code":
                    str(
                        child.item_code or ""
                    ),

                "item_name":
                    str(
                        child.item_name or
                        child.item_code or
                        ""
                    ),

                "qty":
                    flt(
                        child.qty or 0
                    ),

                "uom":
                    str(
                        child.stock_uom or
                        child.uom or
                        ""
                    ),

                "source_warehouse":
                    str(
                        child.s_warehouse or
                        entry.from_warehouse or
                        ""
                    ),

                "target_warehouse":
                    str(
                        child.t_warehouse or
                        entry.to_warehouse or
                        ""
                    ),

                "batch_no":
                    str(
                        child.batch_no or ""
                    ),
            })

    return {
        "success": True,
        "work_order": work_order_id,
        "entries": result,
    }


@frappe.whitelist()
def sr_stock_entry_detail_v3(
    work_order_id,
    item_overrides=None
):

    if not _sr_stock_v2_has_access():
        frappe.throw(
            "You do not have Stock Entry access."
        )

    work_order_id = str(
        work_order_id or ""
    ).strip()

    if not work_order_id:
        frappe.throw(
            "Work Order is required."
        )

    if not frappe.db.exists(
        "Work Order",
        work_order_id
    ):
        frappe.throw(
            "Work Order not found."
        )

    if isinstance(
        item_overrides,
        str
    ):

        try:
            item_overrides = frappe.parse_json(
                item_overrides
            )
        except Exception:
            item_overrides = {}

    if not isinstance(
        item_overrides,
        dict
    ):
        item_overrides = {}

    wo = frappe.get_doc(
        "Work Order",
        work_order_id
    )

    materials = []

    for row in (
        wo.get("required_items")
        or []
    ):

        item_code = str(
            getattr(
                row,
                "item_code",
                ""
            )
            or ""
        ).strip()

        if not item_code:
            continue

        original_item_code = item_code

        override_item = str(
            item_overrides.get(
                original_item_code,
                ""
            )
            or ""
        ).strip()

        if override_item:
            item_code = override_item

        required_qty = flt(
            getattr(
                row,
                "required_qty",
                0
            )
            or 0
        )

        # -------------------------------------------------
        # IMPORTANT:
        # Do NOT trust required_items.transferred_qty here.
        # That value can remain stale after a submitted
        # Material Transfer.
        #
        # ERPNext submitted Stock Entries linked to this
        # Work Order are the source of truth.
        # -------------------------------------------------
        transferred_result = frappe.db.sql(
            """
            SELECT
                COALESCE(
                    SUM(
                        sed.qty
                    ),
                    0
                ) AS transferred_qty
            FROM `tabStock Entry` se
            INNER JOIN `tabStock Entry Detail` sed
                ON sed.parent = se.name
            WHERE
                se.docstatus = 1
                AND COALESCE(
                    se.work_order,
                    ''
                ) = %s
                AND sed.item_code = %s
                AND COALESCE(
                    sed.s_warehouse,
                    ''
                ) != ''
            """,
            (
                work_order_id,
                item_code,
            ),
            as_dict=True,
        )

        transferred_qty = flt(
            transferred_result[0].get(
                "transferred_qty",
                0
            )
            if transferred_result
            else 0
        )

        remaining_qty = max(
            0,
            required_qty
            - transferred_qty
        )

        if remaining_qty <= 0:
            continue

        item_name = (
            frappe.db.get_value(
                "Item",
                item_code,
                "item_name"
            )
            or item_code
        )

        stock_uom = str(
            getattr(
                row,
                "stock_uom",
                ""
            )
            or ""
        )

        source_warehouse = str(
            getattr(
                row,
                "source_warehouse",
                ""
            )
            or ""
        ).strip()

        has_batch_no = int(
            frappe.db.get_value(
                "Item",
                item_code,
                "has_batch_no"
            )
            or 0
        )

        batches = []
        total_available = 0
        warehouse_options = []

        # Show every active leaf warehouse.
        # Stock quantity is item-specific.
        # The BOM/Work Order source warehouse remains
        # the default selected value on the frontend.

        # -------------------------------------------------
        # IMPORTANT:
        # warehouse_options must belong to THIS material.
        # Re-create it immediately before warehouse query.
        # This also fixes the previous NameError caused by
        # wrong indentation/scope.
        # -------------------------------------------------
        warehouse_options = []

        wh_rows = frappe.db.sql(
            """
            SELECT
                w.name AS warehouse,
                COALESCE(
                    b.actual_qty,
                    0
                ) AS actual_qty
            FROM `tabWarehouse` w
            LEFT JOIN `tabBin` b
                ON b.warehouse = w.name
                AND b.item_code = %s
            WHERE
                COALESCE(
                    w.disabled,
                    0
                ) = 0
                AND COALESCE(
                    w.is_group,
                    0
                ) = 0
            ORDER BY
                w.name
            """,
            (
                item_code,
            ),
            as_dict=True,
        )

        for wh in wh_rows:

            wh_name = str(
                wh.warehouse or ""
            ).strip()

            if not wh_name:
                continue

            wh_qty = flt(
                wh.actual_qty or 0
            )

            wh_batches = {}

            if has_batch_no:

                wh_batches = _sr_v3_batch_bundle_stock(
                    item_code,
                    wh_name,
                )

            warehouse_options.append({
                "warehouse":
                    wh_name,

                "available_qty":
                    wh_qty,

                "batches": [
                    {
                        "batch_no":
                            str(
                                batch_name or ""
                            ).strip(),

                        "available_qty":
                            flt(
                                batch_qty or 0
                            ),
                    }

                    for batch_name, batch_qty
                    in sorted(
                        wh_batches.items()
                    )

                    if flt(
                        batch_qty or 0
                    ) > 0
                ],
            })

        if (
            item_code != original_item_code
        ):

            preferred_found = False

            for wh_option in warehouse_options:

                if (
                    str(
                        wh_option.get(
                            "warehouse",
                            ""
                        )
                    ).strip()
                    ==
                    source_warehouse
                    and flt(
                        wh_option.get(
                            "available_qty",
                            0
                        )
                        or 0
                    ) > 0
                ):

                    preferred_found = True

                    break

            if not preferred_found:

                for wh_option in warehouse_options:

                    if flt(
                        wh_option.get(
                            "available_qty",
                            0
                        )
                        or 0
                    ) > 0:

                        source_warehouse = str(
                            wh_option.get(
                                "warehouse",
                                ""
                            )
                            or ""
                        ).strip()

                        break


        # =====================================================
        # SOURCE WAREHOUSE ONLY STOCK
        #
        # IMPORTANT:
        # AVAILABLE must NEVER be calculated by adding stock
        # from WIP/other warehouses.
        #
        # Source warehouse = Stores - SP
        # Therefore AVAILABLE = Stores - SP Bin.actual_qty
        # =====================================================

        source_bin_qty = flt(
            frappe.db.get_value(
                "Bin",
                {
                    "item_code":
                        item_code,
                    "warehouse":
                        source_warehouse,
                },
                "actual_qty"
            )
            or 0
        )

        if has_batch_no and source_warehouse:

            bundle_stock = _sr_v3_batch_bundle_stock(
                item_code,
                source_warehouse,
            )

            for batch_name, qty in sorted(
                bundle_stock.items()
            ):

                qty = flt(
                    qty or 0
                )

                if qty <= 0:
                    continue

                batches.append({
                    "batch_no":
                        str(
                            batch_name or ""
                        ).strip(),

                    "available_qty":
                        qty,
                })

            # -------------------------------------------------
            # IMPORTANT:
            # Do NOT sum batch quantities here.
            #
            # The authoritative total warehouse stock is
            # the Bin.actual_qty of the selected source
            # warehouse only.
            # -------------------------------------------------

            total_available = source_bin_qty

        else:

            total_available = source_bin_qty

        materials.append({

            "item_code":
                item_code,

            "original_item_code":
                original_item_code,

            "item_name":
                str(
                    item_name
                ),

            "stock_uom":
                stock_uom,

            "required_qty":
                required_qty,

            "transferred_qty":
                transferred_qty,

            "remaining_qty":
                remaining_qty,

            "source_warehouse":
                source_warehouse,

            "warehouse_options":
                warehouse_options,

            "target_warehouse":
                str(
                    wo.wip_warehouse
                    or ""
                ),

            "has_batch_no":
                has_batch_no,

            "available_qty":
                total_available,

            "stock_available":
                bool(
                    total_available
                    >= remaining_qty
                ),

            "batches":
                batches,
        })

    return {

        "success":
            True,

        "work_order":
            str(
                wo.name
            ),

        "batch_no":
            _sr_stock_v2_batch(
                wo
            ),

        "production_item":
            str(
                wo.production_item
                or ""
            ),

        "item_name":
            str(
                frappe.db.get_value(
                    "Item",
                    wo.production_item,
                    "item_name"
                )
                or wo.production_item
                or ""
            ),

        "bom_no":
            str(
                wo.bom_no
                or ""
            ),

        "qty":
            flt(
                wo.qty
                or 0
            ),

        "target_warehouse":
            str(
                wo.wip_warehouse
                or ""
            ),

        "materials":
            materials,
    }



@frappe.whitelist()
def create_stock_entry_from_work_order(
    work_order_id,
    items,
):

    if _is_guest():
        frappe.throw("Please login")

    import json

    if isinstance(items, str):

        try:
            items = json.loads(items)
        except Exception:
            frappe.throw("Invalid material data.")

    if not isinstance(items, list) or not items:
        frappe.throw("Select at least one material.")

    frappe.log_error(
        title="SR V3 RAW SUBMIT ITEMS",
        message=(
            "WORK ORDER: "
            + str(work_order_id)
            + "\n\nITEMS RECEIVED:\n"
            + json.dumps(
                items,
                indent=2,
                default=str,
            )
        ),
    )

    if not frappe.db.exists(
        "Work Order",
        work_order_id,
    ):
        frappe.throw(
            "Work Order not found: " +
            str(work_order_id)
        )

    wo = frappe.get_doc(
        "Work Order",
        work_order_id,
    )

    # -----------------------------------------------------
    # Employee access:
    # assigned Job Card -> same Work Order
    # Managers can access all submitted WOs.
    # -----------------------------------------------------

    roles = set(
        frappe.get_roles(
            frappe.session.user
        )
    )

    manager_access = bool(
        {
            "System Manager",
            "Manufacturing Manager",
            "Production Manager",
        } & roles
    )

    if not manager_access:

        allowed = frappe.db.sql(
            """
            SELECT jc.name
            FROM `tabJob Card` jc
            INNER JOIN `tabToDo` td
                ON td.reference_type='Job Card'
               AND td.reference_name=jc.name
            WHERE td.allocated_to=%s
              AND td.status='Open'
              AND jc.work_order=%s
            LIMIT 1
            """,
            (
                frappe.session.user,
                work_order_id,
            ),
            as_dict=True,
        )

        if not allowed:
            frappe.throw(
                "You do not have access to this Work Order."
            )

    requested = {}

    for data in items:

        item_code = str(
            data.get("item_code") or ""
        ).strip()

        original_item_code = str(
            data.get("original_item_code")
            or item_code
            or ""
        ).strip()

        qty = flt(
            data.get("qty") or 0
        )

        batch_no = str(
            data.get("batch_no") or ""
        ).strip()

        source_warehouse = str(
            data.get("source_warehouse") or ""
        ).strip()

        if not item_code or qty <= 0:
            continue

        requested_key = (
            original_item_code,
            item_code
        )

        requested[requested_key] = {
            "qty": qty,
            "batch_no": batch_no,
            "source_warehouse": source_warehouse,
            "original_item_code": original_item_code,
        }

    if not requested:
        frappe.throw(
            "Enter quantity for at least one material."
        )

    real_rows = {}

    for row in (
        wo.get("required_items") or []
    ):

        code = str(
            row.item_code or ""
        ).strip()

        if code:
            real_rows[code] = row

    se = frappe.new_doc(
        "Stock Entry"
    )

    se.stock_entry_type = (
        "Material Transfer for Manufacture"
    )

    se.purpose = (
        "Material Transfer for Manufacture"
    )

    se.use_serial_batch_fields = 1

    se.work_order = (
        wo.name
    )

    se.company = (
        wo.company
    )

    # -------------------------------------------------
    # ERPNext native manufacturing transfer metadata.
    # These are required so that submitting this
    # Material Transfer for Manufacture updates the
    # linked Work Order's transferred quantities/status.
    # -------------------------------------------------
    se.from_bom = 1

    se.bom_no = (
        wo.bom_no
        or ""
    )

    se.fg_completed_qty = flt(
        wo.qty
        or 0
    )

    if not wo.wip_warehouse:
        frappe.throw(
            "Work In Progress warehouse is not set on the Work Order."
        )

    for requested_key, data in requested.items():

        original_item_code = str(
            data.get("original_item_code") or ""
        ).strip()

        item_code = str(
            requested_key[1] or ""
        ).strip()

        # FIX: batch and warehouse MUST belong to this material row.
        # Never reuse values left over from another requested item.
        batch_no = str(
            data.get("batch_no") or ""
        ).strip()

        source_warehouse = str(
            data.get("source_warehouse") or ""
        ).strip()

        if original_item_code not in real_rows:
            frappe.throw(
                original_item_code +
                " is not required by this Work Order."
            )

        row = real_rows[original_item_code]

        # -------------------------------------------------
        # Alternative Item support:
        # The BOM/Work Order material is the original item.
        # The selected item may be another active stock item
        # from the same Item Group.
        # -------------------------------------------------
        if item_code != original_item_code:

            original_group = str(
                frappe.db.get_value(
                    "Item",
                    original_item_code,
                    "item_group"
                ) or ""
            ).strip()

            selected_group = str(
                frappe.db.get_value(
                    "Item",
                    item_code,
                    "item_group"
                ) or ""
            ).strip()

            selected_is_stock = int(
                frappe.db.get_value(
                    "Item",
                    item_code,
                    "is_stock_item"
                ) or 0
            )

            selected_disabled = int(
                frappe.db.get_value(
                    "Item",
                    item_code,
                    "disabled"
                ) or 0
            )

            if not selected_group:
                frappe.throw(
                    item_code +
                    " is not a valid Item."
                )

            if selected_group != original_group:
                frappe.throw(
                    item_code +
                    " is not an allowed alternative for " +
                    original_item_code +
                    "."
                )

            if not selected_is_stock:
                frappe.throw(
                    item_code +
                    " is not a Stock Item."
                )

            if selected_disabled:
                frappe.throw(
                    item_code +
                    " is disabled."
                )

        required_qty = flt(
            row.required_qty or 0
        )

        transferred_qty = flt(
            row.transferred_qty or 0
        )

        remaining_qty = max(
            0,
            required_qty -
            transferred_qty
        )

        qty = flt(
            data["qty"]
        )

        if qty > remaining_qty:

            frappe.throw(
                "Transfer Qty for "
                + item_code
                + " cannot exceed remaining Qty "
                + str(remaining_qty)
                + "."
            )

        source = str(
            data.get(
                "source_warehouse"
            )
            or getattr(
                row,
                "source_warehouse",
                "",
            )
            or ""
        ).strip()

        if not source:
            frappe.throw(
                "Source Warehouse missing for "
                + item_code
            )

        child = se.append(
            "items",
            {},
        )

        child.item_code = (
            item_code
        )

        child.qty = qty

        child.uom = (
            getattr(
                frappe.get_doc(
                    "Item",
                    item_code
                ),
                "stock_uom",
                "",
            )
            or getattr(
                row,
                "stock_uom",
                "",
            )
            or ""
        )

        child.s_warehouse = source

        child.use_serial_batch_fields = 1

        if (
            batch_no
            and int(
                frappe.db.get_value(
                    "Item",
                    item_code,
                    "has_batch_no"
                )
                or 0
            )
        ):
            child.batch_no = batch_no

        child.t_warehouse = (
            wo.wip_warehouse
        )

        child.t_warehouse = (
            wo.wip_warehouse
        )

        item_has_batch_no = int(
            frappe.db.get_value(
                "Item",
                item_code,
                "has_batch_no"
            ) or 0
        )

        if item_has_batch_no:

            child.batch_no = (
                batch_no
            )

        frappe.logger().warning(
            "SR V3 STOCK DEBUG | "
            "WO=%s | ORIGINAL=%s | ITEM=%s | BATCH=%s | SOURCE=%s | QTY=%s",
            wo.name,
            original_item_code,
            item_code,
            batch_no,
            source,
            qty,
        )

    if not se.items:

        frappe.throw(
            "No valid materials selected."
        )

    se.insert(
        ignore_permissions=True
    )

    se.submit()

    # Automatically move the linked Work Order to In Process
    # after the Stock Entry is successfully submitted.
    if se.docstatus == 1 and wo.name:
        frappe.db.set_value(
            "Work Order",
            wo.name,
            "status",
            "In Process",
            update_modified=True,
        )

    frappe.db.commit()

    return {

        "success":
            True,

        "name":
            str(
                se.name
            ),

        "work_order":
            str(
                wo.name
            ),

        "batch_no":
            _sr_stock_v2_batch(
                wo
            ),

        "message":
            "✓ Stock Entry submitted successfully.",
    }


# =========================================================
# CREATE WORK ORDER
# =========================================================

@frappe.whitelist()
def get_latest_batch_for_item(item_code):
    """Return latest batch for the selected manufactured item."""

    if _is_guest():
        frappe.throw("Please login")

    if not item_code:
        return {
            "batch_no": "",
        }

    batch = frappe.db.get_value(
        "Batch",
        {
            "item": item_code,
            "disabled": 0,
        },
        "name",
        order_by="creation desc",
    )

    return {
        "batch_no": batch or "",
    }


@frappe.whitelist()
def create_quick_work_order(
    production_item,
    qty,
    bom_no=None,
    labour_qty=None,
    planned_start_date=None,
    batch_no=None,
):
    if not frappe.has_permission(
        "Work Order",
        ptype="create",
        user=frappe.session.user,
    ):
        frappe.throw(
            "You do not have Create permission for Work Order."
        )

    if not frappe.has_permission(
        "Work Order",
        ptype="create",
        user=frappe.session.user,
    ):
        frappe.throw(
            "You do not have Create permission for Work Order."
        )

    """
    Create Work Order using ERPNext's own BOM calculation.

    SR Connect does NOT calculate raw materials.
    ERPNext Work Order remains the source of truth.
    """

    try:
        if _is_guest():
            frappe.throw("Please login")

        production_item = str(production_item or "").strip()

        if not production_item:
            frappe.throw("Item to Manufacture is required")

        qty = flt(qty)

        if qty <= 0:
            frappe.throw("Qty to Manufacture must be greater than zero")

        wo = frappe.new_doc("Work Order")

        wo.production_item = production_item
        wo.qty = qty

        # ERPNext Work Order has mandatory Labour field.
        labour_qty = flt(
            labour_qty or 0
        )

        if labour_qty <= 0:
            frappe.throw(
                "Labour Qty must be greater than zero"
            )

        wo.custom_labour = int(
            labour_qty
        )

        if bom_no:
            wo.bom_no = str(bom_no).strip()

        if planned_start_date:
            wo.planned_start_date = planned_start_date

        if batch_no:
            try:
                wo.custom_new_batch_id = str(batch_no).strip()
            except Exception:
                pass

        # Labour Qty is SR Connect data.
        # Do NOT write it into ERPNext Work Order.
        # It will be stored separately by SR Connect.

        wo.company = (
            frappe.defaults.get_user_default("Company")
            or frappe.db.get_single_value(
                "Global Defaults",
                "default_company",
            )
        )

        # Let ERPNext populate operations and required_items.
        wo.insert(ignore_permissions=True)

        # Save again after ERPNext's own Work Order calculations.
        wo.save(ignore_permissions=True)

        frappe.db.commit()

        fresh = frappe.get_doc(
            "Work Order",
            wo.name
        )

        return {
            "success": True,
            "name": fresh.name,
            "work_order": _work_order_data(fresh),
        }

    except Exception as e:
        frappe.db.rollback()

        frappe.log_error(
            frappe.get_traceback(),
            "SR Connect Create Work Order Error",
        )

        return {
            "success": False,
            "error": str(e),
        }

# =========================================================
# SR CONNECT - WORK ORDER JOB CARD ASSIGNMENT
# =========================================================

@frappe.whitelist()
def get_work_order_employees(work_order_id=None):

    if _is_guest():
        frappe.throw("Please login")

    employees = frappe.get_all(
        "Employee",
        filters={
            "status": "Active",
        },
        fields=[
            "name",
            "employee_name",
            "user_id",
        ],
        order_by="employee_name asc, name asc",
        limit_page_length=500,
    )

    return {
        "employees": [
            {
                "name": str(row.name or ""),
                "employee_name": str(
                    row.employee_name
                    or row.name
                    or ""
                ),
                "user_id": str(
                    row.user_id
                    or ""
                ),
            }
            for row in employees
        ]
    }


@frappe.whitelist()
def assign_work_order_job_card(
    job_card_id,
    employee,
):

    if _is_guest():
        frappe.throw("Please login")

    job_card_id = str(
        job_card_id or ""
    ).strip()

    employee = str(
        employee or ""
    ).strip()

    if not job_card_id:
        frappe.throw(
            "Job Card is required"
        )

    if not employee:
        frappe.throw(
            "Employee is required"
        )

    if not frappe.db.exists(
        "Job Card",
        job_card_id
    ):
        frappe.throw(
            "Job Card not found: "
            + job_card_id
        )

    if not frappe.db.exists(
        "Employee",
        employee
    ):
        frappe.throw(
            "Employee not found: "
            + employee
        )

    jc = frappe.get_doc(
        "Job Card",
        job_card_id
    )

    # Prefer the employee's linked system user.
    user_id = frappe.db.get_value(
        "Employee",
        employee,
        "user_id",
    )

    if not user_id:
        frappe.throw(
            "Selected Employee has no User ID linked."
        )

    # Avoid duplicate open assignment.
    existing = frappe.get_all(
        "ToDo",
        filters={
            "allocated_to": user_id,
            "reference_type": "Job Card",
            "reference_name": job_card_id,
            "status": "Open",
        },
        fields=["name"],
        limit_page_length=1,
    )

    if not existing:

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": user_id,
            "reference_type": "Job Card",
            "reference_name": job_card_id,
            "description": (
                "SR Connect Job Card Assignment: "
                + job_card_id
                + " / "
                + str(jc.operation or "")
            ),
            "status": "Open",
        })

        todo.insert(
            ignore_permissions=True
        )

    frappe.db.commit()

    return {
        "success": True,
        "job_card": job_card_id,
        "employee": employee,
        "user_id": user_id,
        "message":
            "Job Card assigned successfully.",
    }



# =========================================================
# SR CONNECT - ENSURE WORK ORDER JOB CARDS
# =========================================================

@frappe.whitelist()
def ensure_work_order_job_cards(work_order_id):

    if _is_guest():
        frappe.throw("Please login")

    work_order_id = str(
        work_order_id or ""
    ).strip()

    if not work_order_id:
        frappe.throw(
            "Work Order is required"
        )

    wo = frappe.get_doc(
        "Work Order",
        work_order_id
    )

    # Existing Job Cards
    existing = frappe.get_all(
        "Job Card",
        filters={
            "work_order": work_order_id,
        },
        fields=[
            "name",
            "operation",
            "status",
            "docstatus",
            "for_quantity",
        ],
        order_by="creation asc",
    )

    if existing:
        return {
            "success": True,
            "job_cards": [
                {
                    "name": row.name,
                    "operation": row.operation or "",
                    "status": row.status or "Open",
                    "docstatus": int(
                        row.docstatus or 0
                    ),
                    "for_quantity": flt(
                        row.for_quantity or 0
                    ),
                }
                for row in existing
            ],
        }

    # -----------------------------------------------------
    # No Job Cards found.
    # Generate one Job Card for each Work Order Operation.
    # -----------------------------------------------------

    operations = []

    try:
        operations = list(
            wo.get("operations") or []
        )
    except Exception:
        operations = []

    if not operations:
        frappe.throw(
            "No Work Order Operations found for "
            + work_order_id
        )

    created = []

    for op in operations:

        operation_name = str(
            op.operation or ""
        ).strip()

        if not operation_name:
            continue

        workstation = str(
            op.workstation or ""
        ).strip()

        # Do not create duplicate operation Job Cards.
        duplicate = frappe.db.exists(
            "Job Card",
            {
                "work_order": work_order_id,
                "operation": operation_name,
            },
        )

        if duplicate:
            continue

        jc = frappe.new_doc(
            "Job Card"
        )

        jc.work_order = (
            work_order_id
        )

        jc.operation = (
            operation_name
        )

        jc.for_quantity = flt(
            wo.qty or 0
        )

        if workstation:
            try:
                jc.workstation = (
                    workstation
                )
            except Exception:
                pass

        # Let ERPNext set defaults where available.
        try:
            jc.insert(
                ignore_permissions=True
            )
        except Exception as e:

            frappe.log_error(
                frappe.get_traceback(),
                "SR Connect Job Card Generation Error",
            )

            frappe.throw(
                "Could not create Job Card for "
                + operation_name
                + ": "
                + str(e)
            )

        created.append(jc)

    frappe.db.commit()

    rows = frappe.get_all(
        "Job Card",
        filters={
            "work_order": work_order_id,
        },
        fields=[
            "name",
            "operation",
            "status",
            "docstatus",
            "for_quantity",
        ],
        order_by="creation asc",
    )

    return {
        "success": True,
        "created": len(created),
        "job_cards": [
            {
                "name": row.name,
                "operation": row.operation or "",
                "status": row.status or "Open",
                "docstatus": int(
                    row.docstatus or 0
                ),
                "for_quantity": flt(
                    row.for_quantity or 0
                ),
            }
            for row in rows
        ],
    }



# =========================================================
# SR CONNECT - BULK JOB CARD ASSIGNMENT
# =========================================================

@frappe.whitelist()
def assign_work_order_job_cards(
    job_cards,
    employee,
):

    if _is_guest():
        frappe.throw("Please login")

    employee = str(
        employee or ""
    ).strip()

    if not employee:
        frappe.throw(
            "Employee is required."
        )

    if not frappe.db.exists(
        "Employee",
        employee
    ):
        frappe.throw(
            "Employee not found: " + employee
        )

    user_id = frappe.db.get_value(
        "Employee",
        employee,
        "user_id"
    )

    if not user_id:
        frappe.throw(
            "Selected Employee has no User ID linked."
        )

    import json

    if isinstance(
        job_cards,
        str
    ):

        try:

            job_cards = json.loads(
                job_cards
            )

        except Exception:

            job_cards = [
                x.strip()
                for x in str(
                    job_cards
                ).split(",")
                if x.strip()
            ]

    if not isinstance(
        job_cards,
        list
    ):
        job_cards = [
            job_cards
        ]

    job_cards = [
        str(x).strip()
        for x in job_cards
        if str(x).strip()
    ]

    if not job_cards:
        frappe.throw(
            "Select at least one Job Card."
        )

    assigned = []
    already_assigned = []

    for job_card_id in job_cards:

        if not frappe.db.exists(
            "Job Card",
            job_card_id
        ):
            continue

        existing = frappe.get_all(
            "ToDo",
            filters={
                "allocated_to": user_id,
                "reference_type": "Job Card",
                "reference_name": job_card_id,
                "status": "Open",
            },
            fields=[
                "name"
            ],
            limit_page_length=1,
        )

        if existing:

            already_assigned.append(
                job_card_id
            )

            continue

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": user_id,
            "reference_type": "Job Card",
            "reference_name": job_card_id,
            "description":
                "SR Connect Job Card Assignment",
            "status": "Open",
        })

        todo.insert(
            ignore_permissions=True
        )

        assigned.append(
            job_card_id
        )

    frappe.db.commit()

    return {
        "success": True,
        "employee": employee,
        "user_id": user_id,
        "assigned": assigned,
        "already_assigned":
            already_assigned,
        "count":
            len(assigned),
        "message":
            str(len(assigned))
            + " Job Card(s) assigned successfully.",
    }




@frappe.whitelist()
def sr_stock_entry_submit_v3_draft(stock_entry_name):
    """
    Submit an already-created V3 bulk Draft Stock Entry.
    SAVE and SUBMIT are intentionally separate operations.
    """
    if not _sr_stock_v2_has_access():
        frappe.throw("You do not have Stock Entry access.")

    stock_entry_name = str(
        stock_entry_name or ""
    ).strip()

    if not stock_entry_name:
        frappe.throw("Stock Entry is required.")

    if not frappe.db.exists(
        "Stock Entry",
        stock_entry_name
    ):
        frappe.throw("Stock Entry not found.")

    se = frappe.get_doc(
        "Stock Entry",
        stock_entry_name
    )

    if int(se.docstatus or 0) == 1:
        return {
            "success": True,
            "name": se.name,
            "status": "Submitted",
        }

    if int(se.docstatus or 0) == 2:
        frappe.throw("Stock Entry is cancelled.")

    if not se.items:
        frappe.throw("Stock Entry has no materials.")

    se.submit()
    frappe.db.commit()

    return {
        "success": True,
        "name": se.name,
        "status": "Submitted",
    }


@frappe.whitelist()
def sr_stock_entry_submit_v3_bulk(batches):
    if not _sr_stock_v2_has_access():
        frappe.throw("You do not have Stock Entry access.")

    import json
    if isinstance(batches, str):
        try:
            batches = json.loads(batches)
        except Exception:
            frappe.throw("Invalid batch data.")

    if not isinstance(batches, list) or not batches:
        frappe.throw("No batches provided.")

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer for Manufacture"
    se.purpose = "Material Transfer for Manufacture"

    included_labels = []
    skipped = []
    company = None

    for batch_entry in batches:
        work_order_id = str(batch_entry.get("work_order_id") or "").strip()
        materials = batch_entry.get("materials") or []

        if not work_order_id or not frappe.db.exists("Work Order", work_order_id):
            skipped.append({"work_order_id": work_order_id, "reason": "Work Order not found."})
            continue

        wo = frappe.get_doc("Work Order", work_order_id)

        previous = frappe.get_all(
            "Stock Entry",
            filters={
                "work_order": work_order_id,
                "docstatus": 1,
                "stock_entry_type": "Material Transfer for Manufacture",
                "remarks": ["like", SR_STOCK_V2_PREFIX + "%"],
            },
            pluck="name",
            limit_page_length=1,
        )
        if previous:
            skipped.append({"work_order_id": work_order_id, "reason": "Stock already given."})
            continue

        if not wo.wip_warehouse:
            skipped.append({"work_order_id": work_order_id, "reason": "WIP warehouse missing."})
            continue

        required = {}
        for row in (wo.get("required_items") or []):
            code = str(getattr(row, "item_code", "") or "").strip()
            if code:
                required[code] = row

        batch_added_any = False
        batch_label = _sr_stock_v2_batch(wo) or work_order_id
        batch_failed = False

        for data in materials:
            item_code = str(data.get("item_code") or "").strip()
            batch_no = str(data.get("batch_no") or "").strip()
            if not item_code or item_code not in required:
                continue

            row = required[item_code]
            required_qty = flt(getattr(row, "required_qty", 0) or 0)
            transferred_qty = flt(getattr(row, "transferred_qty", 0) or 0)
            remaining_qty = max(0, required_qty - transferred_qty)
            if remaining_qty <= 0:
                continue

            source = str(getattr(row, "source_warehouse", "") or "").strip()
            if not source:
                skipped.append({"work_order_id": work_order_id, "reason": "Source Warehouse missing for " + item_code})
                batch_failed = True
                break

            has_batch_no = int(frappe.db.get_value("Item", item_code, "has_batch_no") or 0)

            if has_batch_no:
                if not batch_no:
                    skipped.append({"work_order_id": work_order_id, "reason": "Batch missing for " + item_code})
                    batch_failed = True
                    break
                available = flt(
                    frappe.db.sql(
                        """
                        SELECT SUM(actual_qty)
                        FROM `tabStock Ledger Entry`
                        WHERE item_code=%s AND warehouse=%s AND batch_no=%s AND is_cancelled=0
                        """,
                        (item_code, source, batch_no),
                    )[0][0] or 0
                )
                if available < remaining_qty:
                    total_warehouse_qty = flt(
                        frappe.db.get_value(
                            "Bin",
                            {"item_code": item_code, "warehouse": source},
                            "actual_qty",
                        )
                        or 0
                    )
                    if total_warehouse_qty >= remaining_qty:
                        available = total_warehouse_qty
            else:
                available = flt(
                    frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": source}, "actual_qty") or 0
                )

            if available < remaining_qty:
                skipped.append({"work_order_id": work_order_id, "reason": "Stock not enough for " + item_code})
                batch_failed = True
                break

            child = se.append("items", {})
            child.item_code = item_code
            child.qty = remaining_qty
            child.uom = getattr(row, "stock_uom", "") or ""
            child.s_warehouse = source
            child.t_warehouse = wo.wip_warehouse
            if has_batch_no:
                child.batch_no = batch_no

            batch_added_any = True
            company = company or wo.company

        if batch_added_any and not batch_failed:
            included_labels.append(batch_label)
        elif not batch_failed and not batch_added_any:
            skipped.append({"work_order_id": work_order_id, "reason": "No pending materials."})

    if not se.items:
        reasons = "; ".join(
            [str(s.get("work_order_id")) + ": " + str(s.get("reason")) for s in skipped]
        )
        frappe.throw(
            "No valid materials could be transferred. Details: " + (reasons or "no reason captured")
        )

    se.company = company
    se.remarks = SR_STOCK_V2_PREFIX + " | Batches: " + ", ".join(included_labels)

    try:
        se.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "SR STOCK ENTRY V3 BULK SUBMIT ERROR")
        raise

    return {
        "success": True,
        "name": str(se.name),
        "included": included_labels,
        "skipped": skipped,
    }

# =========================================================
# STOCK BALANCE
# Category -> Item -> Opening / Closing / Balance
# =========================================================

# =========================================================
# STOCK BALANCE - TALLY STYLE
#
# Category is warehouse based:
#
# Raw Material       -> Stores - SP
# Packing Material   -> PM WAREHOUSE - SP
# Finished Goods     -> Finished Goods - SP
# Work In Progress   -> Work In Progress - SP
#
# Stock values come from Stock Ledger Entry for that
# specific warehouse.
# =========================================================

_SR_STOCK_BALANCE_WAREHOUSES = {
    "Raw Material": "Stores - SP",
    "Packing Material": "PM WAREHOUSE - SP",
    "Finished Goods": "Finished Goods - SP",
    "Work In Progress": "Work In Progress - SP",
}


@frappe.whitelist()
def get_stock_balance_items(category):
    category = str(
        category or ""
    ).strip()

    warehouse = _SR_STOCK_BALANCE_WAREHOUSES.get(
        category
    )

    if not warehouse:
        frappe.throw(
            "Invalid Stock Balance category."
        )

    rows = frappe.db.sql(
        """
        SELECT
            i.name,
            i.item_name
        FROM `tabItem` i
        INNER JOIN `tabBin` b
            ON b.item_code = i.name
        WHERE
            i.disabled = 0
            AND i.is_stock_item = 1
            AND b.warehouse = %s
            AND COALESCE(b.actual_qty, 0) != 0
        ORDER BY
            i.item_name ASC,
            i.name ASC
        """,
        (warehouse,),
        as_dict=True,
    )

    return {
        "warehouse": warehouse,
        "items": [
            {
                "name": str(
                    row.name or ""
                ),
                "item_name": str(
                    row.item_name
                    or row.name
                    or ""
                ),
            }
            for row in rows
        ],
    }


def _sr_stock_balance_item(item_code):
    item_code = str(
        item_code or ""
    ).strip()

    if not item_code:
        frappe.throw(
            "Item is required."
        )

    item = frappe.db.get_value(
        "Item",
        item_code,
        [
            "item_name",
            "stock_uom",
            "is_stock_item",
        ],
        as_dict=True,
    )

    if not item:
        frappe.throw(
            "Item not found: " + item_code
        )

    if not int(
        item.is_stock_item or 0
    ):
        frappe.throw(
            "This is not a Stock Item."
        )

    return item


def _sr_stock_balance_get_category(
    item_code
):
    rows = frappe.db.sql(
        """
        SELECT
            w.name
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w
            ON w.name = b.warehouse
        WHERE
            b.item_code = %s
            AND COALESCE(
                b.actual_qty,
                0
            ) != 0
        ORDER BY
            ABS(b.actual_qty) DESC
        """,
        (item_code,),
        as_dict=True,
    )

    warehouses = {
        str(r.name or "").strip()
        for r in rows
    }

    for category, warehouse in (
        _SR_STOCK_BALANCE_WAREHOUSES.items()
    ):
        if warehouse in warehouses:
            return category, warehouse

    return None, None


@frappe.whitelist()
def get_stock_balance_months(item_code, category=None):
    item_code = str(
        item_code or ""
    ).strip()

    category = str(
        category or ""
    ).strip()

    item = _sr_stock_balance_item(
        item_code
    )

    # Category is authoritative. Never infer the warehouse
    # from the item's current Bin stock.
    warehouse = _SR_STOCK_BALANCE_WAREHOUSES.get(
        category
    )

    if not warehouse:
        return {
            "item_code": item_code,
            "item_name": str(
                item.item_name or item_code
            ),
            "stock_uom": str(
                item.stock_uom or ""
            ),
            "warehouse": "",
            "months": [],
        }

    rows = frappe.db.sql(
        """
        SELECT
            DATE_FORMAT(
                posting_date,
                '%%Y-%%m'
            ) AS month_key,
            MAX(posting_date) AS last_date
        FROM `tabStock Ledger Entry`
        WHERE
            item_code = %s
            AND warehouse = %s
            AND is_cancelled = 0
        GROUP BY
            DATE_FORMAT(
                posting_date,
                '%%Y-%%m'
            )
        ORDER BY
            month_key DESC
        """,
        (
            item_code,
            warehouse,
        ),
        as_dict=True,
    )

    months = []

    for row in rows:

        month_key = str(
            row.month_key or ""
        ).strip()

        if not month_key:
            continue

        closing = frappe.db.sql(
            """
            SELECT
                COALESCE(
                    qty_after_transaction,
                    0
                ) AS qty
            FROM `tabStock Ledger Entry`
            WHERE
                item_code = %s
                AND warehouse = %s
                AND posting_date <= %s
                AND is_cancelled = 0
            ORDER BY
                posting_date DESC,
                posting_time DESC,
                creation DESC,
                name DESC
            LIMIT 1
            """,
            (
                item_code,
                warehouse,
                row.last_date,
            ),
            as_dict=True,
        )

        balance = flt(
            closing[0].get("qty", 0)
            if closing
            else 0
        )

        try:
            import datetime

            dt = datetime.datetime.strptime(
                month_key,
                "%Y-%m"
            )

            label = dt.strftime(
                "%B %Y"
            )

        except Exception:
            label = month_key

        months.append({
            "month": month_key,
            "label": label,
            "balance": balance,
        })

    return {
        "item_code": item_code,
        "item_name": str(
            item.item_name or item_code
        ),
        "stock_uom": str(
            item.stock_uom or ""
        ),
        "warehouse": warehouse,
        "category": category or "",
        "months": months,
    }



@frappe.whitelist()
def get_stock_balance_batches(item_code, month, category=None):
    item_code = str(item_code or "").strip()
    month = str(month or "").strip()
    category = str(category or "").strip()

    if not item_code or not month:
        return []

    warehouse = _SR_STOCK_BALANCE_WAREHOUSES.get(category)

    if not warehouse:
        return []

    from_date = month + "-01"

    month_end = frappe.db.sql(
        """
        SELECT LAST_DAY(%s)
        """,
        (from_date,),
    )[0][0]

    stock_uom = (
        frappe.db.get_value(
            "Item",
            item_code,
            "stock_uom",
        )
        or ""
    )

    float_precision = int(
        frappe.db.get_default("float_precision") or 3
    )

    # Use ERPNext's own Batch Wise Balance History logic.
    from erpnext.stock.report.batch_wise_balance_history.batch_wise_balance_history import (
        get_item_warehouse_batch_map,
    )

    filters = frappe._dict({
        "from_date": from_date,
        "to_date": str(month_end),
        "item_code": item_code,
        "warehouse": warehouse,
        "warehouse_type": "",
        "batch_no": "",
        "company": "",
    })

    iwb_map = get_item_warehouse_batch_map(
        filters,
        float_precision,
    )

    batch_map = (
        iwb_map
        .get(item_code, {})
        .get(warehouse, {})
    )

    out = []

    for batch_no, qty_dict in sorted(batch_map.items()):
        batch_no = str(batch_no or "").strip()

        if not batch_no:
            continue

        balance_qty = flt(
            qty_dict.bal_qty or 0,
            float_precision,
        )

        if abs(balance_qty) <= 0.000001:
            continue

        batch = frappe.db.get_value(
            "Batch",
            batch_no,
            ["expiry_date"],
            as_dict=True,
        ) or {}

        expiry = batch.get("expiry_date")
        status = "safe"

        if expiry:
            today = frappe.utils.getdate(
                frappe.utils.nowdate()
            )
            exp = frappe.utils.getdate(expiry)
            days = (exp - today).days

            if days < 0:
                status = "expired"
            elif days <= 30:
                status = "near"

        out.append({
            "batch_no": batch_no,
            "qty": balance_qty,
            "balance": balance_qty,
            "status": status,
            "stock_uom": stock_uom,
        })

    return out


@frappe.whitelist()
def get_stock_balance_dates(item_code, month, category=None):
    """
    Tally-style Stock Balance date/transaction view.

    IMPORTANT:
    - Category decides the exact warehouse.
    - Every Stock Ledger Entry remains a separate row.
    - Same date can therefore have multiple rows.
    - Running balance is calculated transaction-by-transaction.
    """

    item_code = str(item_code or "").strip()
    month = str(month or "").strip()
    category = str(category or "").strip()

    if not item_code or not month:
        return []

    warehouse = _SR_STOCK_BALANCE_WAREHOUSES.get(category)

    if not warehouse:
        # Never guess Raw Material/WIP from current Bin.
        return []

    rows = frappe.db.sql(
        """
        SELECT
            sle.name,
            sle.posting_date,
            sle.posting_time,
            sle.actual_qty,
            sle.qty_after_transaction,
            sle.stock_uom,
            sle.voucher_type,
            sle.voucher_no
        FROM `tabStock Ledger Entry` sle
        WHERE sle.item_code = %s
          AND sle.warehouse = %s
          AND sle.is_cancelled = 0
          AND DATE_FORMAT(sle.posting_date, '%%Y-%%m') = %s
        ORDER BY
            sle.posting_date ASC,
            sle.posting_time ASC,
            sle.creation ASC,
            sle.name ASC
        """,
        (
            item_code,
            warehouse,
            month,
        ),
        as_dict=True,
    )

    if not rows:
        return []

    # Opening balance = all ledger movement before this month.
    opening = frappe.db.sql(
        """
        SELECT COALESCE(SUM(actual_qty), 0)
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s
          AND warehouse = %s
          AND is_cancelled = 0
          AND posting_date < %s
        """,
        (
            item_code,
            warehouse,
            month + "-01",
        ),
    )[0][0] or 0

    balance = flt(opening)
    out = []

    for row in rows:
        movement = flt(row.actual_qty or 0)

        # ERPNext authoritative running stock.
        erp_balance = flt(
            row.qty_after_transaction
            if row.qty_after_transaction is not None
            else balance + movement
        )

        out.append({
            "date": str(row.posting_date),
            "item_name": frappe.db.get_value(
                "Item",
                item_code,
                "item_name",
            ) or item_code,
            "item_code": item_code,
            "unit": (
                frappe.db.get_value(
                    "Item",
                    item_code,
                    "stock_uom",
                )
                or row.stock_uom
                or ""
            ),
            "stock_uom": (
                frappe.db.get_value(
                    "Item",
                    item_code,
                    "stock_uom",
                )
                or row.stock_uom
                or ""
            ),
            "opening_stock": flt(
                erp_balance - movement
            ),
            "closing_stock": flt(
                erp_balance
            ),
            "balance": flt(
                erp_balance
            ),
            "movement": movement,
            "voucher_type": row.voucher_type or "",
            "voucher_no": row.voucher_no or "",
            "posting_time": str(row.posting_time or ""),
            "stock_ledger_entry": row.name,
        })

        balance = erp_balance

    return {
        "rows": out
    }


@frappe.whitelist()
def get_stock_balance_transaction_detail(stock_ledger_entry):
    """
    Exact production usage information for one Stock Ledger Entry.

    Uses:
    SLE -> Stock Entry -> Work Order -> Production Item
    and actual Stock Entry / Batch data.
    """

    stock_ledger_entry = str(
        stock_ledger_entry or ""
    ).strip()

    if not stock_ledger_entry:
        return {}

    sle = frappe.db.get_value(
        "Stock Ledger Entry",
        stock_ledger_entry,
        [
            "name",
            "posting_date",
            "posting_time",
            "item_code",
            "actual_qty",
            "warehouse",
            "voucher_type",
            "voucher_no",
        ],
        as_dict=True,
    )

    if not sle:
        return {}

    result = {
        "stock_ledger_entry": sle.name,
        "date": str(sle.posting_date or ""),
        "posting_time": str(sle.posting_time or ""),
        "raw_material": sle.item_code or "",
        "raw_material_name": (
            frappe.db.get_value(
                "Item",
                sle.item_code,
                "item_name",
            )
            or sle.item_code
            or ""
        ),
        "issued_qty": abs(flt(sle.actual_qty or 0)),
        "movement": flt(sle.actual_qty or 0),
        "warehouse": sle.warehouse or "",
        "stock_entry": sle.voucher_no or "",
        "purpose": "",
        "work_order": "",
        "work_order_qty": 0,
        "work_order_status": "",
        "production_qty": 0,
        "process_loss_qty": 0,
        "finished_product": "",
        "finished_product_name": "",
        "finished_product_batch_no": "",
        "raw_material_batch_no": "",
        "raw_material_mfg_date": "",
        "raw_material_exp_date": "",
        "expiry_status": "",
        "expiry_days": None,
    }

    if (
        sle.voucher_type != "Stock Entry"
        or not sle.voucher_no
    ):
        return result

    se = frappe.db.get_value(
        "Stock Entry",
        sle.voucher_no,
        [
            "name",
            "work_order",
            "fg_completed_qty",
            "purpose",
        ],
        as_dict=True,
    )

    if not se:
        return result

    result["purpose"] = se.purpose or ""

    work_order = str(
        se.work_order or ""
    ).strip()

    result["work_order"] = work_order

    # -----------------------------------------------------
    # RAW MATERIAL BATCH FROM THE ACTUAL STOCK ENTRY
    # -----------------------------------------------------

    raw_rows = frappe.db.sql(
        """
        SELECT
            sed.batch_no,
            sed.qty,
            sed.s_warehouse,
            sed.t_warehouse
        FROM `tabStock Entry Detail` sed
        WHERE sed.parent = %s
          AND sed.parenttype = 'Stock Entry'
          AND sed.item_code = %s
          AND (
                sed.s_warehouse = %s
                OR sed.t_warehouse = %s
              )
        ORDER BY sed.idx ASC
        """,
        (
            sle.voucher_no,
            sle.item_code,
            sle.warehouse,
            sle.warehouse,
        ),
        as_dict=True,
    )

    if raw_rows:

        raw_detail = next(
            (
                row
                for row in raw_rows
                if str(row.batch_no or "").strip()
            ),
            raw_rows[0],
        )

        raw_batch = str(
            raw_detail.batch_no or ""
        ).strip()

        result["raw_material_batch_no"] = raw_batch

        if raw_detail.qty is not None:
            result["issued_qty"] = abs(
                flt(raw_detail.qty or 0)
            )

        # -------------------------------------------------
        # BATCH MASTER: MFG + EXP
        # -------------------------------------------------

        if raw_batch:

            batch = frappe.db.get_value(
                "Batch",
                raw_batch,
                [
                    "batch_id",
                    "manufacturing_date",
                    "expiry_date",
                    "item",
                ],
                as_dict=True,
            )

            if batch:

                result["raw_material_mfg_date"] = str(
                    batch.manufacturing_date or ""
                )

                result["raw_material_exp_date"] = str(
                    batch.expiry_date or ""
                )

                if batch.expiry_date:

                    from frappe.utils import (
                        getdate,
                        today,
                        date_diff,
                    )

                    days_left = date_diff(
                        getdate(batch.expiry_date),
                        getdate(today()),
                    )

                    result["expiry_days"] = days_left

                    if days_left < 0:
                        result["expiry_status"] = "Expired"
                    elif days_left <= 30:
                        result["expiry_status"] = (
                            "Near Expiry — 30 Days"
                        )
                    else:
                        result["expiry_status"] = "Safe"

    # -----------------------------------------------------
    # WORK ORDER
    # -----------------------------------------------------

    if not work_order:
        return result

    wo = frappe.db.get_value(
        "Work Order",
        work_order,
        [
            "production_item",
            "qty",
            "produced_qty",
            "process_loss_qty",
            "status",
            "docstatus",
        ],
        as_dict=True,
    )

    if not wo:
        return result

    result["work_order_qty"] = flt(
        wo.qty or 0
    )

    result["work_order_status"] = (
        wo.status or ""
    )

    production_item = str(
        wo.production_item or ""
    ).strip()

    result["finished_product"] = production_item

    result["finished_product_name"] = (
        frappe.db.get_value(
            "Item",
            production_item,
            "item_name",
        )
        or production_item
        or ""
    )

    # -----------------------------------------------------
    # PRODUCTION QTY + PROCESS LOSS
    #
    # Completed:
    #   produced_qty / process_loss_qty
    #
    # Not completed:
    #   original WO qty
    # -----------------------------------------------------

    completed = (
        int(wo.docstatus or 0) == 1
        and str(wo.status or "").strip().lower()
        in {
            "completed",
            "closed",
        }
    )

    if completed:

        result["production_qty"] = flt(
            wo.produced_qty or 0
        )

        result["process_loss_qty"] = flt(
            wo.process_loss_qty or 0
        )

    else:

        result["production_qty"] = flt(
            wo.qty or 0
        )

        result["process_loss_qty"] = 0

    # -----------------------------------------------------
    # FINISHED PRODUCT BATCH
    #
    # First try the same Stock Entry.
    # Then find the latest submitted Manufacture entry
    # for the same Work Order and production item.
    # -----------------------------------------------------

    if production_item:

        same_entry_batch = frappe.db.sql(
            """
            SELECT
                sed.batch_no
            FROM `tabStock Entry Detail` sed
            WHERE sed.parent = %s
              AND sed.parenttype = 'Stock Entry'
              AND sed.item_code = %s
              AND IFNULL(sed.batch_no, '') != ''
            ORDER BY sed.idx ASC
            LIMIT 1
            """,
            (
                sle.voucher_no,
                production_item,
            ),
            as_dict=True,
        )

        if same_entry_batch:
            result["finished_product_batch_no"] = str(
                same_entry_batch[0].batch_no or ""
            ).strip()

        if not result["finished_product_batch_no"]:

            fg_batch = frappe.db.sql(
                """
                SELECT
                    sed.batch_no
                FROM `tabStock Entry` se
                INNER JOIN `tabStock Entry Detail` sed
                    ON sed.parent = se.name
                   AND sed.parenttype = 'Stock Entry'
                WHERE se.docstatus = 1
                  AND se.work_order = %s
                  AND se.purpose = 'Manufacture'
                  AND sed.item_code = %s
                  AND IFNULL(sed.batch_no, '') != ''
                ORDER BY
                    se.posting_date DESC,
                    se.posting_time DESC,
                    se.creation DESC,
                    sed.idx ASC
                LIMIT 1
                """,
                (
                    work_order,
                    production_item,
                ),
                as_dict=True,
            )

            if fg_batch:
                result["finished_product_batch_no"] = str(
                    fg_batch[0].batch_no or ""
                ).strip()

    return result


@frappe.whitelist()
def sr_stock_alert_save(item, alert_limit, employee=None, active=1):
    item=str(item or "").strip()
    employee=str(employee or "").strip()

    if not item:
        frappe.throw("Item is required")

    if not frappe.db.exists("Item",item):
        frappe.throw("Invalid Item")

    if employee and not frappe.db.exists("Employee",employee):
        frappe.throw("Invalid Employee")

    doctype="SR Stock Alert Setting"
    name=frappe.db.get_value(doctype,{"item":item},"name")

    if name:
        doc=frappe.get_doc(doctype,name)
    else:
        doc=frappe.new_doc(doctype)
        doc.item=item

    doc.alert_limit=float(alert_limit or 0)
    doc.employee=employee
    doc.active=1 if str(active) in ("1","true","True") else 0
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok":True,"name":doc.name}


@frappe.whitelist()
def sr_stock_alert_get(item=None):
    if not item:
        return {"setting":None}

    doc=frappe.db.get_value(
        "SR Stock Alert Setting",
        {"item":item},
        ["name","item","alert_limit","employee","active"],
        as_dict=True
    )

    current_stock=frappe.db.sql(
        """
        SELECT COALESCE(SUM(actual_qty),0)
        FROM `tabBin`
        WHERE item_code=%s
        """,
        (item,)
    )[0][0] or 0

    stock_uom=frappe.db.get_value("Item",item,"stock_uom") or ""

    if not doc:
        return {
            "setting": {
                "current_stock":current_stock,
                "stock_uom":stock_uom
            }
        }

    doc.current_stock=current_stock
    doc.stock_uom=stock_uom

    return {"setting":doc}


@frappe.whitelist()
def sr_stock_alert_test(item):
    item=str(item or "").strip()

    if not item:
        frappe.throw("Item is required")

    setting=frappe.db.get_value(
        "SR Stock Alert Setting",
        {"item":item},
        ["employee"],
        as_dict=True
    )

    if not setting or not setting.employee:
        frappe.throw("Employee is required")

    chat_id=frappe.db.get_value(
        "Employee",
        setting.employee,
        "custom_telegram_chat_id"
    )

    if not chat_id:
        frappe.throw("Telegram Chat ID is not set for the selected Employee")

    bot_token=frappe.db.get_single_value(
        "SR Telegram Settings",
        "telegram_bot_token"
    )

    if not bot_token:
        frappe.throw("Telegram Bot Token is not configured")

    stock=frappe.db.sql(
        """
        SELECT COALESCE(SUM(actual_qty),0)
        FROM `tabBin`
        WHERE item_code=%s
        """,
        (item,)
    )[0][0] or 0

    uom=frappe.db.get_value("Item",item,"stock_uom") or ""

    message=(
        "🔔 STOCK ALERT TEST\n\n"
        f"Item: {item}\n"
        f"Current Stock: {float(stock):g} {uom}\n"
        "This is a test notification from SR Connect."
    )

    import requests
    response=requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id":chat_id,"text":message},
        timeout=15
    )

    data=response.json()

    if not data.get("ok"):
        frappe.throw(
            "Telegram error: "
            + str(data.get("description") or "Unknown error")
        )

    return {"ok":True}


@frappe.whitelist()
def sr_stock_alert_items():
    return frappe.get_all(
        "Item",
        fields=["name", "item_name", "stock_uom"],
        order_by="name asc",
        limit_page_length=0
    )


@frappe.whitelist()
def sr_stock_alert_employees():
    return frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_name"],
        order_by="employee_name asc",
        limit_page_length=0
    )


@frappe.whitelist()
def sr_save_telegram_config(telegram_bot_token, active=1):
    token=str(telegram_bot_token or "").strip()
    if not token:
        frappe.throw("Telegram Bot Token is required")

    doc=frappe.get_single("SR Telegram Settings")
    doc.telegram_bot_token=token
    doc.active=1 if str(active) in ("1","true","True") else 0
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"ok":True}


@frappe.whitelist()
def sr_stock_alert_employee_telegram(employee):
    employee=str(employee or "").strip()
    if not employee:
        return {"configured":False}

    chat_id=frappe.db.get_value(
        "Employee",
        employee,
        "custom_telegram_chat_id"
    )

    return {
        "configured":bool(chat_id),
        "chat_id":chat_id or ""
    }


@frappe.whitelist()
def sr_get_my_telegram_chat_id():
    token=frappe.db.get_single_value(
        "SR Telegram Settings",
        "telegram_bot_token"
    )

    if not token:
        frappe.throw("Telegram Bot Token is not configured")

    import requests

    response=requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        timeout=15
    )

    data=response.json()

    if not data.get("ok"):
        frappe.throw(
            "Telegram error: "
            + str(data.get("description") or "Unknown error")
        )

    updates=data.get("result") or []

    if not updates:
        frappe.throw(
            "No Telegram message received yet. Open your Stock Alert Bot and press Start first."
        )

    for update in reversed(updates):
        msg=update.get("message") or {}
        chat=msg.get("chat") or {}
        chat_id=chat.get("id")

        if chat_id:
            return {
                "ok":True,
                "chat_id":str(chat_id),
                "name":str(
                    chat.get("first_name")
                    or chat.get("username")
                    or ""
                )
            }

    frappe.throw("Telegram Chat ID could not be found")

