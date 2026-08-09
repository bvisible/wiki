"""Keep the bare /wiki URL working after the v3 rename to /wiki-app.

v3 moved the editor SPA from /wiki to /wiki-app, so /wiki now 404s. That URL is
published on Neoffice instances — neoffice_theme boots it as
`neoffice_wiki_url`, NORA's help panel falls back to it, frappe's desk.js opens
it, and users have bookmarked it — so it is redirected to the new location.

This is a per-instance patch rather than a `website_redirects` hook because the
hook would apply fleet-wide: on an instance where a Wiki Space owns the route
"wiki" (redirects are resolved before routes, so the hook always wins) the
redirect would hide that space's public reader. Here, an occupied route simply
means no redirect is written.

Idempotent: re-running never duplicates the row.
"""

import frappe

SOURCE = "/wiki"
TARGET = "/wiki-app"


def execute():
	if frappe.db.exists("Wiki Space", {"route": "wiki"}):
		# A space serves /wiki on this instance — it keeps the URL.
		return

	settings = frappe.get_single("Website Settings")
	for row in settings.route_redirects or []:
		if (row.source or "").strip("/ ") == SOURCE.strip("/ "):
			return

	settings.append("route_redirects", {"source": SOURCE, "target": TARGET})
	settings.save(ignore_permissions=True)
