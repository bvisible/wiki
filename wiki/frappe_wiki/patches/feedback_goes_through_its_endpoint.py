"""//// Neoffice — added file (no upstream equivalent).

A visitor leaves wiki feedback through the page's endpoint, and through nothing else
(neoffice-maintenance#531).

Upstream ships `Wiki Feedback` with `create` and `write` for `Guest` and for `All`, because
`submit_feedback` inserted the row under the visitor's own rights. The same rights opened the
REST collection: an anonymous visitor or any portal account could POST rows straight into
`/api/resource/Wiki Feedback`, past the endpoint's rate limit and checks, or rewrite one by its
name. The fleet's open-grants check reported it Critical on every instance.

The endpoint now inserts the row itself, and wiki_feedback.json no longer carries the two rows.
That is not enough on a site that already exists: once any `Custom DocPerm` exists for a
doctype, those rows REPLACE the ones the code ships, and on our sites the whole permission table
of Wiki Feedback was copied there (late August 2026, when an app first added a role to it), the
`Guest` and `All` rows with it. This removes the two copies and nothing else.

Checked before removing, because a role row can be load-bearing (frappe evaluates role
permissions BEFORE any `has_permission` hook): Wiki Feedback has no `has_permission` hook and no
`permission_query_conditions`, and the only path a visitor uses is `submit_feedback`, which no
longer asks for them. The rows grant no `read`, so nothing a visitor sees changes.
"""

import frappe

DOCTYPE = "Wiki Feedback"
OPEN_ROLES = ("Guest", "All")


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	removed = 0
	for table in ("Custom DocPerm", "DocPerm"):
		rows = frappe.get_all(table, filters={"parent": DOCTYPE, "role": ("in", OPEN_ROLES)}, pluck="name")
		if rows:
			frappe.db.delete(table, {"name": ("in", rows)})
			removed += len(rows)

	if removed:
		frappe.clear_cache(doctype=DOCTYPE)
		print(f"feedback_goes_through_its_endpoint: removed {removed} open grant(s) on {DOCTYPE}")
