import os

import frappe
from frappe.translate import get_all_translations

CONVERTIBLE_IMAGE_EXTENSIONS = (".png", ".jpeg", ".jpg")


@frappe.whitelist()
def get_space_capabilities(space: str) -> dict:
	"""Return the current user's read/write capabilities for a Wiki Space.

	Used by the SPA to show/hide the Merge and contribute actions. Enforcement
	always remains server-side in the permission hooks and Change Request
	controller.
	"""
	from wiki.permissions import can_contribute_to_space, can_read_space, can_write_space

	return {
		"can_read": can_read_space(space),
		"can_write": can_write_space(space),
		"can_contribute": can_contribute_to_space(space),
	}


# //// Neoffice — allow_guest added (upstream: @frappe.whitelist()). The SPA asks
# //// who it is talking to before it renders anything; on a public wiki that
# //// caller has no session, and upstream's plain whitelist answered 403, so the
# //// user store stayed empty and canAccessWiki was false for every anonymous
# //// visitor. Nothing is disclosed: the Guest branch below returns
# //// {"is_logged_in": False} and never touches the User doctype.
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


# //// Neoffice — everything from here to resolve_wiki_path() is ours; upstream
# //// has no equivalent. Two needs it serves:
# ////   1. readers (anonymous or portal Website Users) can't list Wiki Space
# ////      through frappe.client.get_list — this exposes the published ones only;
# ////   2. pretty URLs: our wikis are linked as /wiki/<space>/<page>, which the
# ////      SPA resolves through resolve_wiki_path() instead of internal IDs.
# //// ignore_permissions is deliberate and safe HERE because the filter already
# //// restricts the rows to published + switcher-visible spaces.
@frappe.whitelist(allow_guest=True)
def list_public_spaces():
	"""Return the spaces the caller may actually read, published + in the switcher.

	Named "public" because it is the guest-safe entry point, but it is not a
	bypass: every row is checked against the space's own access rules.
	"""
	from wiki.permissions import can_read_space

	spaces = frappe.get_all(
		"Wiki Space",
		filters={"is_published": 1, "show_in_switcher": 1},
		fields=["name", "space_name", "route", "root_group", "is_published", "switcher_order"],
		order_by="switcher_order asc, creation asc",
		# //// Neoffice — ignore_permissions is safe ONLY because can_read_space()
		# //// filters the rows right below. It stays because the Wiki Space
		# //// permission query alone would hide rows a guest is entitled to.
		ignore_permissions=True,
	)
	# //// Neoffice — this used to return every published space to anyone. It fed
	# //// the reader's space list, so a client instance advertised its internal
	# //// spaces to the open internet. Now each row goes through the same access
	# //// check as the rest of the app (which itself honours the master switch).
	return [s for s in spaces if can_read_space(s.name)]



# //// Neoffice — added. The two resolvers below are ours and both allow_guest.
# //// They answered straight from the route column, so a visitor who guessed a
# //// URL was told whether an unpublished page or a space they cannot read
# //// exists, and was handed its internal ID to feed the rest of the API. These
# //// helpers are that filter, and they answer FOR THE CALLER: an editor still
# //// resolves the drafts they are working on, everybody else only ever sees what
# //// is published. Same rules as get_public_space_info(), so the reader and the
# //// resolver can never disagree about what exists.
def _can_see_space(space_id: str | None) -> bool:
	"""Whether the caller may be told this Wiki Space exists.

	Read access is necessary but not sufficient: an unpublished space is a
	draft, and only someone who can write it has any business resolving it.
	"""
	if not space_id:
		return False

	from wiki.permissions import can_read_space, can_write_space

	if not can_read_space(space_id):
		return False
	if frappe.db.get_value("Wiki Space", space_id, "is_published"):
		return True
	return can_write_space(space_id)


def _can_see_document(doc_name: str, space_id: str | None) -> bool:
	"""Whether the caller may be told this Wiki Document exists.

	A document whose space cannot be resolved is never disclosed: an orphan has
	no access rules of its own to apply, and the reader could not render it in a
	space context anyway.
	"""
	from wiki.permissions import can_write_space

	if not _can_see_space(space_id):
		return False
	if can_write_space(space_id):
		return True

	row = frappe.db.get_value(
		"Wiki Document", doc_name, ["is_published", "is_private"], as_dict=True
	)
	return bool(row and row.is_published and not row.is_private)


# //// Neoffice — added. Both resolvers used to climb `parent_wiki_document` in a
# //// bare `while True`. Wiki Document is a nested set, but the parent link is a
# //// plain Link field: a bad move, a restored backup or a hand-edited row can
# //// make a document its own ancestor, and the loop then spins forever inside a
# //// worker — from an allow_guest endpoint, so one request from any visitor pins
# //// a worker. Stop on a repeat and on an absurd depth.
MAX_DOCUMENT_DEPTH = 50


def climb_to_root_document(name: str) -> str | None:
	"""Walk `parent_wiki_document` up to the tree root, cycle- and depth-safe.

	Returns the topmost ancestor reached, or None when the climb hit a cycle or
	MAX_DOCUMENT_DEPTH. Callers then resolve no space, which reads as "not
	found" — the safe answer when the tree is corrupt.
	"""
	current = name
	visited = {current}

	for _ in range(MAX_DOCUMENT_DEPTH):
		parent = frappe.db.get_value("Wiki Document", current, "parent_wiki_document")
		if not parent:
			return current
		if parent in visited:
			frappe.log_error(
				"Wiki Document parent cycle",
				f"Climbing from {name} reached {parent} twice; the tree is corrupt.",
			)
			return None
		visited.add(parent)
		current = parent

	frappe.log_error(
		"Wiki Document tree too deep",
		f"Climbing from {name} passed {MAX_DOCUMENT_DEPTH} levels; the tree is likely corrupt.",
	)
	return None


# //// Neoffice — this resolver is ours (pretty URLs) and it is allow_guest. It
# //// used to answer straight from the route column, so a visitor who guessed a
# //// slug was told whether a space they cannot read exists, and handed its
# //// internal ID to feed the rest of the API. _can_see_space() above is that
# //// filter: a space the caller may not see now answers exactly like a slug
# //// that matches nothing.
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
		# //// Neoffice — was `if name:`. Any row matching the route was handed
		# //// over, published or not, readable by this caller or not.
		if name and _can_see_space(name):
			return {"space_id": name}

	# Case-insensitive fallback
	# //// Neoffice — this raw-SQL fallback bypassed every check above, so a slug
	# //// in the wrong case reached spaces the ORM path had already refused. It
	# //// goes through the same filter now, and the LIMIT 1 had to go with it:
	# //// with a filter, stopping at the first row would hide a space the caller
	# //// may read behind one they may not.
	rows = frappe.db.sql(
		"""SELECT name FROM `tabWiki Space`
		WHERE LOWER(route) IN (LOWER(%s), LOWER(%s))""",
		(slug, f"wiki/{slug}"),
		as_dict=True,
	)
	# //// Neoffice — was `if row: return {"space_id": row[0]["name"]}`. Filtered
	# //// now, and looped rather than LIMIT 1: with a filter, stopping at the first
	# //// row would hide a space the caller may read behind one they may not.
	for candidate in rows:
		if _can_see_space(candidate["name"]):
			return {"space_id": candidate["name"]}

	return {"space_id": None}



# //// Neoffice — ours too, and allow_guest like the resolver above. Same hole,
# //// same filter: anything the caller may not see answers exactly like a path
# //// that matches nothing, so the response never separates "private" from "does
# //// not exist".
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
			# //// Neoffice — bounded climb; see climb_to_root_document() above.
			# //// The bare `while True` it replaces spun forever on a cycle in
			# //// parent_wiki_document, inside a worker, from an allow_guest
			# //// endpoint.
			root_group = climb_to_root_document(doc.name)
			# root_group = the tree root, find the space
			space_id = (
				frappe.db.get_value("Wiki Space", {"root_group": root_group}, "name")
				if root_group
				else None
			)
			# //// Neoffice — was an unconditional return. It disclosed the
			# //// internal ID of any page whose route you could guess —
			# //// unpublished drafts, private pages, pages in spaces the caller
			# //// cannot read — which is then enough to pull it through the rest
			# //// of the API. A page we may not show is not a match: fall through
			# //// to the space lookups and, failing those, to the shared "not
			# //// found" at the end.
			if _can_see_document(doc.name, space_id):
				return {"space_id": space_id, "page_id": doc.name}

	# Try Wiki Space route match
	candidates_space = [path, f"wiki/{path}"]
	for route in candidates_space:
		name = frappe.db.get_value("Wiki Space", {"route": route}, "name")
		# //// Neoffice — same filter as resolve_space_slug: a space the caller
		# //// may not see answers like one that does not exist.
		if name and _can_see_space(name):
			return {"space_id": name, "page_id": None}

	# Case-insensitive fallback on Wiki Space route
	# //// Neoffice — filtered too, and un-LIMIT-ed for the same reason as in
	# //// resolve_space_slug: the first row is not necessarily the readable one.
	rows = frappe.db.sql(
		"""SELECT name FROM `tabWiki Space`
		WHERE LOWER(route) IN (LOWER(%s), LOWER(%s))""",
		(path, f"wiki/{path}"),
		as_dict=True,
	)
	# //// Neoffice — same as in resolve_space_slug: filtered, and looped instead of
	# //// LIMIT 1 so a readable space is not hidden behind an unreadable one.
	for candidate in rows:
		if _can_see_space(candidate["name"]):
			return {"space_id": candidate["name"], "page_id": None}

	return {"space_id": None, "page_id": None}


def _to_webp(path_or_url: str) -> str:
	"""Swap any file extension for `.webp` (works for both fs paths and URLs)."""
	return os.path.splitext(path_or_url)[0] + ".webp"


def convert_file_to_webp(file_doc) -> str:
	"""Convert a local PNG/JPEG File doc to WebP in place.

	Replaces the file on disk, deletes the original, and updates the doc's
	file_url. Returns the new (or unchanged, if not convertible) file_url.
	"""
	from frappe.core.doctype.file.file import get_local_image
	from frappe.core.doctype.file.utils import delete_file

	if not file_doc:
		return ""

	file_url = file_doc.file_url or ""
	# Only act on local site files of a convertible raster format.
	if not file_url.startswith("/files") or not file_url.lower().endswith(CONVERTIBLE_IMAGE_EXTENSIONS):
		return file_url

	try:
		image, _, _ = get_local_image(file_url)
		image.save(_to_webp(file_doc.get_full_path()), "WEBP")
	except Exception:
		# Corrupt or unsupported image — keep the original upload rather than
		# failing the whole request and losing the author's image.
		frappe.log_error(title="Wiki WebP conversion failed")
		return file_url

	# delete_file resolves public/private from the URL's leading segment, so it
	# must be given the /files/... url — not the absolute filesystem path.
	delete_file(file_url)

	file_doc.file_url = _to_webp(file_url)
	if file_doc.file_name:
		file_doc.file_name = _to_webp(file_doc.file_name)
	file_doc.save()
	return file_doc.file_url


@frappe.whitelist()
def upload_wiki_asset():
	"""Upload handler for wiki editor assets.

	Wraps Frappe's standard file upload. When the `auto_convert_images_to_webp`
	Wiki Setting is enabled, uploaded PNG/JPEG images are converted to WebP
	before the File doc is returned, so the editor receives the optimized URL.
	"""
	from frappe.handler import upload_file

	file_doc = upload_file()
	if (
		file_doc
		and (file_doc.file_url or "").lower().endswith(CONVERTIBLE_IMAGE_EXTENSIONS)
		and frappe.get_cached_value("Wiki Settings", "Wiki Settings", "auto_convert_images_to_webp")
	):
		convert_file_to_webp(file_doc)
	return file_doc
