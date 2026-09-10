import frappe

def get_context(context):
    context.no_cache = 1
    if frappe.session.user != "Guest":
        frappe.local.flags.redirect_location = "/sr_connect/home"
        raise frappe.Redirect
    return context
