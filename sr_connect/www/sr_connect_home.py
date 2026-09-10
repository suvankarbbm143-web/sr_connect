import frappe
from frappe import _

def get_context(context):
	context.no_cache = 1
	
	quick_links = [
		{
			'label': 'Work Order',
			'url': '/app/work-order',
			'icon': 'icon-list',
			'description': 'View and manage work orders'
		},
		{
			'label': 'Job Card',
			'url': '/app/job-card',
			'icon': 'icon-list',
			'description': 'Track job cards'
		},
		{
			'label': 'Sales Order',
			'url': '/app/sales-order',
			'icon': 'icon-shopping-cart',
			'description': 'Manage sales orders'
		},
		{
			'label': 'Delivery Note',
			'url': '/app/delivery-note',
			'icon': 'icon-truck',
			'description': 'Track deliveries'
		}
	]
	
	context.quick_links = quick_links
	return context