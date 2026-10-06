"""Point the Wiki desktop icon at /wiki-app on sites still holding the pre-rename /wiki link."""

import frappe


def execute():
	# //// Neoffice — skip when the column is absent. `icon_type` belongs to the
	# //// Desktop Icon of Frappe v16; our fleet runs v15, whose Desktop Icon has no such
	# //// column, and the lookup below raised "Unknown column 'icon_type'" from inside
	# //// the patch handler: `bench migrate` died on every v15 site (found on a clone of
	# //// the production database, 2026-10-03). Nothing to repoint on v15, where the
	# //// app's tile is not a Desktop Icon of this kind. Drop the guard at the v16 move.
	if not frappe.db.has_column("Desktop Icon", "icon_type"):
		return

	frappe.db.set_value(
		"Desktop Icon",
		{"app": "wiki", "icon_type": "App", "link": "/wiki"},
		"link",
		"/wiki-app",
	)
