# //// Neoffice — added file (no upstream equivalent)
#
# The sitemap of the public manual, served as `/wiki-sitemap.xml` (the manual's own host maps `/sitemap.xml` onto it).
#
# Why not Frappe's own `/sitemap.xml`: it is the whole hub's (the shop, the portal) and writes every address with the hub's
# `host_name`, so a crawler that reads it on the manual's own host is told the manual lives somewhere else. This one lists ONLY
# the pages a visitor who is not signed in can read, and writes them under `wiki_canonical_host` (site_config) when it is set.
#
# "Can read" is asked the way a page asks it (`check_space_access("read")` then `check_published()`), as the visitor who fetches
# the sitemap, so a draft, an archived page or a private space never appears, whatever the flags of the document say.
from urllib.parse import quote

import frappe
from frappe.utils import get_url

no_cache = 1
base_template_path = "www/wiki-sitemap.xml"

CACHE_KEY = "wiki_public_sitemap_links"
CACHE_SECONDS = 3600


def get_context(context):
	host = frappe.conf.get("wiki_canonical_host")
	base = f"https://{host}" if host else get_url()
	links = frappe.cache().get_value(CACHE_KEY)
	if links is None:
		links = _public_links()
		frappe.cache().set_value(CACHE_KEY, links, expires_in_sec=CACHE_SECONDS)
	return {"links": [{"loc": f"{base}/{quote(link['route'].encode('utf-8'))}", "lastmod": link["lastmod"]} for link in links]}


def _public_links():
	rows = frappe.get_all(
		"Wiki Document",
		filters={"is_published": 1, "is_external_link": 0},
		fields=["name", "route", "modified", "is_group", "disable_indexing"],
		order_by="route asc",
		limit_page_length=0,
	)
	links = []
	for row in rows:
		if not row.route:
			continue
		# A page its author asked to keep out of search engines (Wiki Document.disable_indexing, 3.3.0)
		# must not be advertised by the sitemap either: upstream drops it from its own sitemap, llms.txt and
		# .md indexes for the same reason, and the page itself carries a noindex tag.
		if row.disable_indexing:
			continue
		doc = frappe.get_cached_doc("Wiki Document", row.name)
		# a chapter that only holds other pages is not a page worth indexing; one that carries its own text is
		if row.is_group and not (doc.content or "").strip():
			continue
		try:
			doc.check_space_access("read")
			doc.check_published()
		except frappe.DoesNotExistError:
			continue
		links.append({"route": row.route, "lastmod": f"{row.modified:%Y-%m-%d}"})
	return links
