# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import get_system_timezone

no_cache = 1
#//// Neoffice — added: the SPA shell is served to visitors without an account
#//// when the wiki is public. The data behind it is filtered per space by the
#//// API either way; get_context() below turns anonymous visitors away when the
#//// master switch is off, so they get a login page instead of an empty shell.
allow_guest = 1
sitemap = 0

ROBOTS_DIRECTIVE = "noindex, nofollow"


def get_context():
	#//// Neoffice — no anonymous access while the wiki is private: send them to
	#//// the login page rather than an app shell every API call will refuse.
	from wiki.permissions import public_wiki_enabled

	if frappe.session.user == "Guest" and not public_wiki_enabled():
		frappe.local.flags.redirect_location = "/login?redirect-to=/wiki-app"
		raise frappe.Redirect

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
