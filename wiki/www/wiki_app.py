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
	from wiki.permissions import is_wiki_author, public_wiki_enabled

	if frappe.session.user == "Guest" and not public_wiki_enabled():
		frappe.local.flags.redirect_location = "/login?redirect-to=/wiki-app"
		raise frappe.Redirect

	#//// Neoffice — a reader never enters the authoring app. /wiki-app is ours;
	#//// /wiki/… is the client's, and it is the better read anyway (table of
	#//// contents, ⌘K search, copy-as-markdown, prev/next). Sending them to the
	#//// SAME page of the reader keeps a shared /wiki-app link working instead of
	#//// dropping it on a landing page. Server-side on purpose: the app must not
	#//// even boot for them, or they get a flash of author chrome. Authors are
	#//// untouched, so ?preview=1 still works — it only flips the SPA's own
	#//// reader mode, it does not make an author a reader here.
	if not is_wiki_author():
		frappe.local.flags.redirect_location = _reader_url_for_app_path()
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


#//// Neoffice — added (no upstream equivalent). Translates an authoring-app URL
#//// into the reader URL for the same thing, so a reader who was handed a
#//// /wiki-app link lands on the page that link meant. Never raises: a URL we
#//// cannot map is still better served by the wiki root than by a 500.
def _reader_url_for_app_path() -> str:
	"""Reader URL matching the requested /wiki-app path, or the wiki root."""
	from wiki.permissions import can_read_space

	parts = [p for p in (frappe.request.path if frappe.request else "").split("/") if p]
	# /wiki-app/spaces/<space_id>[/page/<page_id>] → ["wiki-app", "spaces", …]
	space_id = parts[2] if len(parts) > 2 and parts[1] == "spaces" else None
	page_id = parts[4] if len(parts) > 4 and parts[3] == "page" else None

	if page_id:
		# Published + public only: this runs for readers, so an unpublished page
		# must not be turned into a URL that confirms it exists.
		route = frappe.db.get_value(
			"Wiki Document", {"name": page_id, "is_published": 1, "is_private": 0}, "route"
		)
		if route:
			return "/" + route.lstrip("/")

	if space_id:
		space = frappe.db.get_value(
			"Wiki Space", {"name": space_id, "is_published": 1}, ["name", "route"], as_dict=True
		)
		if space and space.route and can_read_space(space.name):
			return "/" + space.route.lstrip("/")

	# No usable target (bare /wiki-app, or a space they may not read): hand them
	# the first space they are actually entitled to, and the site root if none.
	from wiki.api import list_public_spaces

	spaces = list_public_spaces()
	if spaces and spaces[0].get("route"):
		return "/" + spaces[0]["route"].lstrip("/")
	return "/"


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
