"""//// Neoffice — added file (no upstream equivalent).

A proposed wiki edit was readable by anybody, with no account at all.

`Wiki Page Patch` granted `Guest: read`, blanket — while a SIGNED-IN account
may only read its own (`All` carries `if_owner`). So being anonymous showed
MORE than being signed in: every pending change, its full proposed text, and
its author. Measured on a dev instance with a witness row, over plain HTTP and
no session: the collection listed it and the document came back whole.

Checked before removing, because a role row can be load-bearing — frappe
evaluates role permissions BEFORE any `has_permission` hook, so deleting the
row that lets a hook run closes every path the hook opened. Not the case here:
no `has_permission` and no `permission_query_conditions` on this doctype, and
nothing in the v3 wiki reads it at all — it belongs to the v2 model that
`Wiki Document` replaced. Space-level public read is a different mechanism
(`Wiki Space Role`, see `init_public_read_from_guest_role`) and is untouched.

Removing the row from the doctype JSON is not enough on a site that already
exists: once any `Custom DocPerm` exists for a doctype, those rows REPLACE the
ones the code ships, so a file-only fix would look applied and change nothing.
"""

import frappe


def execute():
	if not frappe.db.exists("DocType", "Wiki Page Patch"):
		return

	removed = 0
	for table in ("Custom DocPerm", "DocPerm"):
		rows = frappe.get_all(table, filters={"parent": "Wiki Page Patch", "role": "Guest"}, pluck="name")
		if rows:
			frappe.db.delete(table, {"name": ("in", rows)})
			removed += len(rows)

	if removed:
		frappe.clear_cache(doctype="Wiki Page Patch")
		print(f"proposed_edits_are_not_public: removed {removed} anonymous grant(s)")
