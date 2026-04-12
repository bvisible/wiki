import frappe
from frappe.translate import get_all_translations


@frappe.whitelist(allow_guest=True)
def get_user_info() -> dict:
	"""Get basic information about the logged-in user."""
	if frappe.session.user == "Guest":
		return {"is_logged_in": False}

	user = frappe.get_cached_doc("User", frappe.session.user)

	return {
		"name": user.name,
		"is_logged_in": True,
		"first_name": user.first_name,
		"last_name": user.last_name,
		"full_name": user.full_name,
		"email": user.email,
		"user_image": user.user_image,
		"roles": user.roles,
		"brand_image": frappe.get_single_value("Website Settings", "banner_image"),
		"language": user.language,
	}


@frappe.whitelist(allow_guest=True)
def get_translations():
	if frappe.session.user != "Guest":
		language = frappe.db.get_value("User", frappe.session.user, "language")
	else:
		language = frappe.db.get_single_value("System Settings", "language")

	return get_all_translations(language)



@frappe.whitelist(allow_guest=True)
def list_public_spaces():
	"""Return published Wiki Spaces visible to everyone (guest-safe)."""
	return frappe.get_all(
		"Wiki Space",
		filters={"is_published": 1, "show_in_switcher": 1},
		fields=["name", "space_name", "route", "root_group", "is_published", "switcher_order"],
		order_by="switcher_order asc, creation asc",
		ignore_permissions=True,
	)



@frappe.whitelist(allow_guest=True)
def resolve_space_slug(slug: str) -> dict:
	"""Resolve a URL slug (e.g. 'technique', 'utilisateur', 'Web-Domaines')
	to a Wiki Space name (ID). Tries exact route match, then 'wiki/<slug>',
	then case-insensitive match.
	"""
	slug = (slug or "").strip().strip("/")
	if not slug:
		return {"space_id": None}

	candidates = [slug, f"wiki/{slug}"]
	for route in candidates:
		name = frappe.db.get_value("Wiki Space", {"route": route}, "name")
		if name:
			return {"space_id": name}

	# Case-insensitive fallback
	row = frappe.db.sql(
		"""SELECT name FROM `tabWiki Space`
		WHERE LOWER(route) IN (LOWER(%s), LOWER(%s))
		LIMIT 1""",
		(slug, f"wiki/{slug}"),
		as_dict=True,
	)
	if row:
		return {"space_id": row[0]["name"]}

	return {"space_id": None}



@frappe.whitelist(allow_guest=True)
def resolve_wiki_path(path: str) -> dict:
	"""Unified resolver for wiki pretty URLs.
	Handles:
		- Space slug only: 'technique', 'utilisateur' -> returns space_id
		- Full document route: 'wiki/rh/configuration-assurances' -> returns {space_id, page_id}
		- Without 'wiki/' prefix: 'rh/configuration-assurances' -> same as above
	"""
	path = (path or "").strip().strip("/")
	if not path:
		return {"space_id": None, "page_id": None}

	# Try exact Wiki Document route match (supports full multi-segment paths)
	candidates_doc = [path, f"wiki/{path}"]
	for route in candidates_doc:
		doc = frappe.db.get_value(
			"Wiki Document",
			{"route": route, "is_group": 0},
			["name", "parent_wiki_document"],
			as_dict=True,
		)
		if doc:
			# Walk up to find the owning space
			current = doc.name
			while True:
				parent = frappe.db.get_value("Wiki Document", current, "parent_wiki_document")
				if not parent:
					break
				current = parent
			# current = root_group, find the space
			space_id = frappe.db.get_value("Wiki Space", {"root_group": current}, "name")
			return {"space_id": space_id, "page_id": doc.name}

	# Try Wiki Space route match
	candidates_space = [path, f"wiki/{path}"]
	for route in candidates_space:
		name = frappe.db.get_value("Wiki Space", {"route": route}, "name")
		if name:
			return {"space_id": name, "page_id": None}

	# Case-insensitive fallback on Wiki Space route
	row = frappe.db.sql(
		"""SELECT name FROM `tabWiki Space`
		WHERE LOWER(route) IN (LOWER(%s), LOWER(%s))
		LIMIT 1""",
		(path, f"wiki/{path}"),
		as_dict=True,
	)
	if row:
		return {"space_id": row[0]["name"], "page_id": None}

	return {"space_id": None, "page_id": None}
