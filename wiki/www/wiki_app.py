# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import get_system_timezone

no_cache = 1
#//// Neoffice — added: the SPA shell itself is served to visitors without an
#//// account. Neoffice wikis are public-facing; the data behind it is still
#//// filtered per space by the API.
allow_guest = 1
sitemap = 0

ROBOTS_DIRECTIVE = "noindex, nofollow"


def get_context():
	#//// Neoffice — upstream calls frappe.local.response_headers.set() directly.
	#//// That attribute does not exist before Frappe ~15.9x and raised on older
	#//// instances of the fleet, so read it defensively.
	response_headers = getattr(frappe.local, "response_headers", None)
	if response_headers is not None:
		response_headers.set("X-Robots-Tag", ROBOTS_DIRECTIVE)
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosemgrep
	context = frappe._dict()
	context.boot = get_boot()
	context.boot.csrf_token = csrf_token
	return context


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw(frappe._("This method is only meant for developer mode"))
	return get_boot()


def get_boot():
	return frappe._dict(
		{
			"frappe_version": frappe.__version__,
			"site_name": frappe.local.site,
			"read_only_mode": frappe.flags.read_only,
			"system_timezone": get_system_timezone(),
		}
	)
