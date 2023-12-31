# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

from frappe import _
import functools
import re

def load_vehicle_dynamic_link(doc, key=None):

	filters = [
		["Dynamic Link", "link_doctype", "=", doc.doctype],
		["Dynamic Link", "link_name", "=", doc.name],
		["Dynamic Link", "parenttype", "=", "Vehicle"],
	]
	address_list = frappe.get_all("Vehicle", filters=filters, fields=["*"])

	address_list = [a.update({"display": get_vehicle_display(a)})
		for a in address_list]

	address_list = sorted(address_list,
		key = functools.cmp_to_key(lambda a, b:
			(1 if a.modified - b.modified else 0)), reverse=True)

	doc.set_onload('vehicle_list', address_list)

	# filters = [
	# 	["Dynamic Link", "link_doctype", "=", doc.doctype],
	# 	["Dynamic Link", "link_name", "=", doc.name],
	# 	["Dynamic Link", "parenttype", "=", "Customer"],
	# ]
	# customer_list = frappe.get_all("Customer", filters=filters, fields=["*"])
	#
	# customer_list = [a.update({"display": get_customer_display(a)})
	# 				for a in customer_list]
	#
	# customer_list = sorted(customer_list,
	# 					key=functools.cmp_to_key(lambda a, b:
	# 					(1 if a.modified - b.modified else 0)), reverse=True)
	#
	# doc.set_onload('customer_list', customer_list)


# def get_customer_display(customer_list):
# 	if not customer_list:
# 		return
# 	template = """{{customer_type}}<br>{{customer_group}}<br/> {{territory}} """
#
# 	return frappe.render_template(template, customer_list)

def get_vehicle_display(address_dict):
	if not address_dict:
		return
	template = """{{model}} {{make}}<br>{{last_odometer}} """

	return frappe.render_template(template, address_dict)

def has_permission(doc, ptype, user):
	links = get_permitted_and_not_permitted_links(doc.doctype)
	if not links.get("not_permitted_links"):
		# optimization: don't determine permissions based on link fields
		return True

	# True if any one is True or all are empty
	names = []
	for df in (links.get("permitted_links") + links.get("not_permitted_links")):
		doctype = df.options
		name = doc.get(df.fieldname)
		names.append(name)

		if name and frappe.has_permission(doctype, ptype, doc=name):
			return True

	if not any(names):
		return True
	return False


def get_permission_query_conditions_for_vehicle(user):
	return get_permission_query_conditions("Vehicle")

def get_permission_query_conditions_for_customer(user):
	return get_permission_query_conditions("Customer")

def get_permission_query_conditions(doctype):
	links = get_permitted_and_not_permitted_links(doctype)

	if not links.get("not_permitted_links"):
		# when everything is permitted, don't add additional condition
		return ""

	elif not links.get("permitted_links"):
		conditions = []

		# when everything is not permitted
		for df in links.get("not_permitted_links"):
			# like ifnull(customer, '')='' and ifnull(supplier, '')=''
			conditions.append("ifnull(`tab{doctype}`.`{fieldname}`, '')=''".format(doctype=doctype, fieldname=df.fieldname))

		return "( " + " and ".join(conditions) + " )"

	else:
		conditions = []

		for df in links.get("permitted_links"):
			# like ifnull(customer, '')!='' or ifnull(supplier, '')!=''
			conditions.append("ifnull(`tab{doctype}`.`{fieldname}`, '')!=''".format(doctype=doctype, fieldname=df.fieldname))

		return "( " + " or ".join(conditions) + " )"

def get_permitted_and_not_permitted_links(doctype):
	permitted_links = []
	not_permitted_links = []

	meta = frappe.get_meta(doctype)
	allowed_doctypes = frappe.permissions.get_doctypes_with_read()

	for df in meta.get_link_fields():
		if df.options not in ("Customer", "Supplier", "Company", "Sales Partner"):
			continue

		if df.options in allowed_doctypes:
			permitted_links.append(df)
		else:
			not_permitted_links.append(df)

	return {
		"permitted_links": permitted_links,
		"not_permitted_links": not_permitted_links
	}

def delete_contact_and_address(doctype, docname):
	for parenttype in ('Contact', 'Address'):
		items = frappe.db.sql_list("""select parent from `tabDynamic Link`
			where parenttype=%s and link_doctype=%s and link_name=%s""",
			(parenttype, doctype, docname))

		for name in items:
			doc = frappe.get_doc(parenttype, name)
			if len(doc.links)==1:
				doc.delete()

def filter_dynamic_link_doctypes(doctype, txt, searchfield, start, page_len, filters):
	if not txt: txt = ""

	doctypes = frappe.db.get_all("DocField", filters=filters, fields=["parent"],
		distinct=True, as_list=True)

	doctypes = tuple([d for d in doctypes if re.search(txt+".*", _(d[0]), re.IGNORECASE)])

	filters.update({
		"dt": ("not in", [d[0] for d in doctypes])
	})

	_doctypes = frappe.db.get_all("Custom Field", filters=filters, fields=["dt"],
		as_list=True)

	_doctypes = tuple([d for d in _doctypes if re.search(txt+".*", _(d[0]), re.IGNORECASE)])

	all_doctypes = [d[0] for d in doctypes + _doctypes]
	allowed_doctypes = frappe.permissions.get_doctypes_with_read()

	valid_doctypes = sorted(set(all_doctypes).intersection(set(allowed_doctypes)))
	valid_doctypes = [[doctype] for doctype in valid_doctypes]

	return valid_doctypes

def set_link_title(doc):
	if not doc.links:
		return
	for link in doc.links:
		if not link.link_title:
			linked_doc = frappe.get_doc(link.link_doctype, link.link_name)
			link.link_title = linked_doc.get("title_field") or linked_doc.get("name")
