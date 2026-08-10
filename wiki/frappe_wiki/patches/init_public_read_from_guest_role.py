"""//// Neoffice — added file (no upstream equivalent).

Fill the new ``Wiki Space.public_read`` checkbox from the state that already
exists, so the box tells the truth on day one instead of reading "private" for a
space that is in fact served to the open internet.

Public-ness upstream is a ``Guest`` row in the space's Roles table. This copies
that fact into the checkbox — it does NOT change who can read what. Closing the
door is the master switch's job (``Wiki Settings.enable_public_wiki``, off by
default), which is deliberately a separate, reversible decision: flipping role
rows here would silently break the hub, whose wiki is meant to be public.

Idempotent: re-running just recomputes the same flag.
"""

import frappe


def execute():
	frappe.reload_doc("wiki", "doctype", "wiki_space")

	for name in frappe.get_all("Wiki Space", pluck="name"):
		has_guest = frappe.db.exists(
			"Wiki Space Role",
			{"parent": name, "parenttype": "Wiki Space", "role": "Guest"},
		)
		frappe.db.set_value(
			"Wiki Space", name, "public_read", 1 if has_guest else 0, update_modified=False
		)

	frappe.db.commit()
