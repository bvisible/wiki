# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

"""Role-based access control for Wiki Spaces.

Read access  -> view a space + its pages and raise Change Requests.
Write access -> additionally merge Change Requests. Write implies Read.

A space with no role rows is open to all logged-in users (backward compatible).
A space whose Read list contains the built-in ``Guest`` role is publicly readable
(``frappe.get_roles()`` returns ``Guest`` for anonymous requests). ``System Manager``
and ``Wiki Manager`` always have full access.
"""

import frappe
from frappe import _

MANAGER_ROLES = {"System Manager", "Wiki Manager"}
WRITE_PTYPES = {"write", "create", "delete", "submit", "cancel", "amend"}


def is_git_synced_space(space) -> bool:
	"""True if the space mirrors a GitHub repo (content is read-only in the wiki)."""
	name = _resolve_space_name(space)
	if not name:
		return False
	return bool(frappe.get_cached_value("Wiki Space", name, "git_synced"))


def assert_space_writable(space) -> None:
	"""Block content mutations on a git-synced space (the repo is the source of truth).

	The sync engine itself bypasses this by running under
	``frappe.flags.in_apply_merge_revision``.
	"""
	if frappe.flags.in_apply_merge_revision:
		return
	if is_git_synced_space(space):
		frappe.throw(
			_("This wiki space is synced from GitHub and is read-only."),
			frappe.PermissionError,
		)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _is_manager(user=None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(MANAGER_ROLES & set(frappe.get_roles(user)))


# //// Neoffice — added (no upstream equivalent). The line between the two
# //// surfaces: /wiki/… is the reader our clients use, /wiki-app is the authoring
# //// app we use. Anyone without an authoring role has nothing to do in the app —
# //// it has no table of contents, no ⌘K search, no copy-as-markdown, and it kept
# //// showing them author chrome (settings gear, publication badge, Edit button)
# //// that we then had to patch away one by one. Mirrors isWikiEditor in
# //// frontend/src/stores/user.js: keep the two in step.
def is_wiki_author(user=None) -> bool:
	"""Whether the user holds a wiki authoring role (so belongs in /wiki-app)."""
	user = user or frappe.session.user
	if user == "Guest":
		return False
	if user == "Administrator":
		return True
	return bool({"Wiki User", *MANAGER_ROLES} & set(frappe.get_roles(user)))


def _resolve_space_name(space):
	if not space:
		return None
	if isinstance(space, str):
		return space
	return space.name


def _space_role_levels(space) -> dict:
	"""Return ``{role: permission_level}`` for a space. Empty dict means open access.

	When a role appears with both levels, ``Write`` wins (it implies Read).
	"""
	name = _resolve_space_name(space)
	if not name:
		return {}

	rows = frappe.get_all(
		"Wiki Space Role",
		filters={"parent": name, "parenttype": "Wiki Space"},
		fields=["role", "permission_level"],
	)

	levels = {}
	for row in rows:
		if levels.get(row.role) == "Write":
			continue
		levels[row.role] = row.permission_level
	return levels


# //// Neoffice — added. Master switch for anonymous access, off by default.
# //// Upstream decides "public" per space, through a Guest row in the space's
# //// role table. That is fine for a wiki meant to be read from the internet
# //// (our shared manual on the hub), but it is the wrong default for a client
# //// instance, where the wiki is an internal tool. Worse, upstream's
# //// seed_space_roles_from_published patch turned every is_published space into
# //// a Guest-readable one at migration time — on osiris that silently exposed
# //// ERPNextSwiss, Déclarations annuelles and DevOps to the open internet.
# //// This switch gates the whole anonymous surface in ONE place that every read
# //// path already goes through, so a client instance leaks nothing until
# //// somebody deliberately turns it on.
def public_wiki_enabled() -> bool:
	"""Whether this instance serves the wiki to visitors without an account."""
	try:
		return bool(
			frappe.get_cached_value("Wiki Settings", "Wiki Settings", "enable_public_wiki")
		)
	except Exception:
		# Settings not migrated yet (fresh install, mid-migrate): stay closed.
		return False


# //// Neoffice — added. THE definition of "this caller has no account and the
# //// instance is not public". It exists because the rule used to live inline in
# //// can_read_space() only: _accessible_space_names(), which answers the very
# //// same question for the list queries, never consulted the switch — so with
# //// enable_public_wiki off a Guest was refused one space at a time and handed
# //// all of them at once. Both go through this now; there is one rule.
def _guest_access_blocked(user: str) -> bool:
	"""Whether this caller is anonymous on an instance that is not public."""
	return user == "Guest" and not public_wiki_enabled()


def can_read_space(space, user=None) -> bool:
	user = user or frappe.session.user
	if _is_manager(user):
		return True

	# //// Neoffice — anonymous visitors get nothing while the master switch is
	# //// off, whatever the space's own role rows say. Shared with
	# //// _accessible_space_names() so the two can never drift apart.
	if _guest_access_blocked(user):
		return False

	levels = _space_role_levels(space)
	if not levels:
		# Open space: every logged-in user, but not anonymous Guests.
		return user != "Guest"

	# Any role row (Read or Write) grants read. Guest/All rows behave naturally
	# because frappe.get_roles() returns them in the appropriate contexts.
	return bool(set(frappe.get_roles(user)) & set(levels))


def can_write_space(space, user=None) -> bool:
	user = user or frappe.session.user
	if _is_manager(user):
		return True

	levels = _space_role_levels(space)
	if not levels:
		# Open space: writers are the global Wiki Approvers.
		return "Wiki Approver" in frappe.get_roles(user)

	user_roles = set(frappe.get_roles(user))
	return any(role in user_roles for role, level in levels.items() if level == "Write")


def can_delete_space(space, user=None) -> bool:
	"""Needs write access to the space and a role that can delete Wiki Space."""
	user = user or frappe.session.user
	return can_write_space(space, user) and bool(frappe.has_permission("Wiki Space", "delete", user=user))


def _space_accepts_contributions(space) -> bool:
	"""Whether a space lets Read-tier users propose changes (raise CRs).

	Missing/NULL is treated as enabled so spaces created before this toggle (and
	rows not yet backfilled) keep accepting contributions.
	"""
	name = _resolve_space_name(space)
	if not name:
		return True
	value = frappe.get_cached_value("Wiki Space", name, "allow_contributions")
	return value is None or bool(value)


def can_contribute_to_space(space, user=None) -> bool:
	"""Whether the user may propose changes (raise/edit Change Requests).

	Write-tier users (and managers) can always contribute. Read-tier users can
	contribute only while the space accepts contributions.
	"""
	user = user or frappe.session.user
	if not can_read_space(space, user):
		return False
	if can_write_space(space, user):
		return True
	return _space_accepts_contributions(space)


def can_manage_tabs(space, user=None) -> bool:
	"""Whether the user may create or promote/demote tabs in a space.

	Deliberately stricter than `can_contribute_to_space`: a tab restructures the
	top-level navigation for every reader of the space, which is an editor
	decision rather than a contribution.
	"""
	return can_write_space(space, user)


def assert_can_manage_tabs(space, user=None) -> None:
	if not can_manage_tabs(space, user):
		frappe.throw(
			_("Only space editors can create or change tabs."),
			frappe.PermissionError,
		)


def _accessible_space_names(user=None) -> set:
	"""Spaces a user may read: open spaces (no role rows) plus restricted spaces
	with a role row whose role the user holds. Guests get only the latter."""
	user = user or frappe.session.user
	user_roles = set(frappe.get_roles(user))

	rows = frappe.get_all(
		"Wiki Space Role",
		filters={"parenttype": "Wiki Space"},
		fields=["parent", "role"],
	)
	restricted_spaces = {row.parent for row in rows}
	accessible_restricted = {row.parent for row in rows if row.role in user_roles}

	# //// Neoffice — the master switch was missing here while can_read_space()
	# //// applied it, so the two disagreed about the same Guest: every read was
	# //// refused one by one while this still returned every Guest-roled space to
	# //// the list queries. Same helper, one answer.
	if _guest_access_blocked(user):
		return set()

	if user == "Guest":
		return accessible_restricted

	all_spaces = set(frappe.get_all("Wiki Space", pluck="name"))
	open_spaces = all_spaces - restricted_spaces
	return open_spaces | accessible_restricted


# //// Neoffice — added (no upstream equivalent). Who may read what is not live
# //// yet. The Wiki Document hooks below only ever asked "may you read this
# //// space", so an unpublished page in a Guest-readable space was served whole
# //// (title, route, content) to any caller of the generic document API, anonymous
# //// visitors included, and a signed-in account without any wiki role could also
# //// list the pages of spaces that are not published at all. The reader, the
# //// tree, the search and get_public_document() all hid them already; the
# //// permission hooks were the one path left open. Drafts belong to the people
# //// who write the wiki: an authoring role (they edit drafts in /wiki-app, and
# //// the change-request tree already hands them every draft) or Write on the space.
def can_see_drafts(space, user=None) -> bool:
	"""Whether the user may read the pages of a space that are not live yet."""
	user = user or frappe.session.user
	return is_wiki_author(user) or can_write_space(space, user)


# //// Neoffice — added. "Live" is what the reader serves: the page is published,
# //// not flagged private, and its space is published. is_private is the legacy
# //// per-page flag: wiki v3 dropped it from the DocType but the column survives on
# //// migrated sites (see search.py), so it is honoured only where it still exists.
def _document_is_live(doc) -> bool:
	if not doc.get("is_published") or doc.get("is_private"):
		return False
	space = doc.get("wiki_space")
	if not space:
		return True
	return bool(frappe.get_cached_value("Wiki Space", space, "is_published"))


# //// Neoffice — added. The spaces can_write_space() says yes to, in one query,
# //// for the list conditions (same rules: open spaces are written by Wiki
# //// Approvers, restricted ones by a role holding a Write row).
def _writable_space_names(user: str) -> set:
	user_roles = set(frappe.get_roles(user))
	rows = frappe.get_all(
		"Wiki Space Role",
		filters={"parenttype": "Wiki Space"},
		fields=["parent", "role", "permission_level"],
	)
	restricted_spaces = {row.parent for row in rows}
	writable = {row.parent for row in rows if row.permission_level == "Write" and row.role in user_roles}
	if "Wiki Approver" in user_roles:
		all_spaces = set(frappe.get_all("Wiki Space", pluck="name"))
		writable |= all_spaces - restricted_spaces
	return writable


# //// Neoffice — added. SQL twin of _document_is_live() OR can_see_drafts(), for
# //// callers that are not wiki authors (the query hook returns early for them).
def _live_or_writable_clause(table: str, user: str) -> str:
	live = [f"`{table}`.`is_published` = 1"]
	if frappe.db.has_column("Wiki Document", "is_private"):
		live.append(f"ifnull(`{table}`.`is_private`, 0) = 0")

	published_spaces = frappe.get_all("Wiki Space", filters={"is_published": 1}, pluck="name")
	space_is_live = f"`{table}`.`wiki_space` is null"
	if published_spaces:
		escaped = ", ".join(frappe.db.escape(name) for name in published_spaces)
		space_is_live = f"({space_is_live} or `{table}`.`wiki_space` in ({escaped}))"
	live.append(space_is_live)
	live_clause = "(" + " and ".join(live) + ")"

	writable = _writable_space_names(user)
	if not writable:
		return live_clause
	escaped = ", ".join(frappe.db.escape(name) for name in sorted(writable))
	return f"({live_clause} or `{table}`.`wiki_space` in ({escaped}))"


# //// Neoffice — added. The spaces of `names` a reader who does not write the wiki may see: the live ones (published),
# //// and those this user can write. An unpublished space is its authors' draft, as an unpublished page is: open spaces
# //// (no role rows) are readable by any logged-in user, so the generic API gave a portal account the name and route of
# //// every unpublished space, where an anonymous visitor saw only the published ones (maintenance#1350).
def _live_or_writable_space_names(names, user: str) -> set:
	names = set(names)
	if not names:
		return set()
	live = set(
		frappe.get_all("Wiki Space", filters={"name": ("in", sorted(names)), "is_published": 1}, pluck="name")
	)
	return live | (names & _writable_space_names(user))


def _space_in_clause(table: str, user: str, allow_null: bool) -> str:
	"""Build a WHERE fragment restricting ``table`` to spaces the user can read."""
	names = _accessible_space_names(user)
	parts = []
	if allow_null:
		parts.append(f"`{table}`.`wiki_space` is null")
	if names:
		escaped = ", ".join(frappe.db.escape(name) for name in names)
		parts.append(f"`{table}`.`wiki_space` in ({escaped})")

	if not parts:
		return "1=0"
	if len(parts) == 1:
		return parts[0]
	return "(" + " or ".join(parts) + ")"


# ---------------------------------------------------------------------------
# Hook entry points
# ---------------------------------------------------------------------------


def wiki_space_query_conditions(user=None, doctype=None):
	user = user or frappe.session.user
	if _is_manager(user):
		return ""

	names = _accessible_space_names(user)
	# //// Neoffice — and only the live ones, unless the caller writes the wiki: see _live_or_writable_space_names.
	if not is_wiki_author(user):
		names = _live_or_writable_space_names(names, user)
	if not names:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(name) for name in names)
	return f"`tabWiki Space`.`name` in ({escaped})"


def wiki_space_has_permission(doc, ptype, user=None):
	user = user or frappe.session.user
	if ptype in WRITE_PTYPES:
		return can_write_space(doc, user)
	# //// Neoffice — the same line for one record: an unpublished space is read by the wiki's authors, its writers
	# //// and the managers only (maintenance#1350).
	published = (
		frappe.get_cached_value("Wiki Space", doc, "is_published")
		if isinstance(doc, str)
		else doc.get("is_published")
	)
	if not published and not (_is_manager(user) or is_wiki_author(user) or can_write_space(doc, user)):
		return False
	return can_read_space(doc, user)


def wiki_document_query_conditions(user=None, doctype=None):
	user = user or frappe.session.user
	if _is_manager(user):
		return ""
	# //// Neoffice — allow_null was hardcoded True, so every list query got the
	# //// orphan documents (empty wiki_space) on top of what its spaces allow,
	# //// anonymous callers included: the master switch is meant to close the whole
	# //// anonymous surface in one place, and orphans walked around it. Whether "no
	# //// space" is readable is a question can_read_space already answers
	# //// (open-space rules: any logged-in user, never a Guest), so ask it rather
	# //// than assume yes.
	space_clause = _space_in_clause("tabWiki Document", user, allow_null=can_read_space(None, user))
	# //// Neoffice — and only what is live, unless the caller writes the wiki: this
	# //// clause alone let a Guest list every draft of a public space through the
	# //// generic document API. See can_see_drafts().
	if space_clause == "1=0" or is_wiki_author(user):
		return space_clause
	return f"({space_clause}) and {_live_or_writable_clause('tabWiki Document', user)}"


def wiki_document_has_permission(doc, ptype, user=None):
	user = user or frappe.session.user
	space = doc.wiki_space
	if not space:
		# Orphan document: writable only by managers.
		if ptype in WRITE_PTYPES:
			return _is_manager(user)
		# //// Neoffice — was `return True`, which handed every orphan document to
		# //// anyone at all, Guest included, straight past the master switch. Defer
		# //// to the space rules for "no space" — open-space rules: any logged-in
		# //// user, never an anonymous Guest — so an orphan is read under the same
		# //// rule as everything else.
		# //// Neoffice — and an orphan that is not live stays with the wiki authors
		# //// (see can_see_drafts; the list clause applies the same rule).
		if not can_read_space(None, user):
			return False
		return _document_is_live(doc) or is_wiki_author(user)

	if ptype in WRITE_PTYPES:
		# A git-synced space is read-only; only the sync engine (running under
		# in_apply_merge_revision) may write its documents.
		if not frappe.flags.in_apply_merge_revision and is_git_synced_space(space):
			return False
		return can_write_space(space, user)
	# //// Neoffice — was `return can_read_space(space, user)`: reading the space
	# //// was enough to read any of its pages, drafts included. See can_see_drafts().
	if not can_read_space(space, user):
		return False
	return _document_is_live(doc) or can_see_drafts(space, user)


def wiki_cr_query_conditions(user=None, doctype=None):
	user = user or frappe.session.user
	if _is_manager(user):
		return ""
	return _space_in_clause("tabWiki Change Request", user, allow_null=True)


def wiki_cr_has_permission(doc, ptype, user=None):
	user = user or frappe.session.user
	space = doc.wiki_space
	if not space:
		if ptype in WRITE_PTYPES:
			return _is_manager(user)
		return True

	# Reading a CR requires space Read. Editing/saving it (proposing changes)
	# additionally requires the space to accept contributions (Write-tier users
	# bypass that). Merging is gated separately by can_write_space in the CR
	# controller.
	if ptype in WRITE_PTYPES:
		return can_contribute_to_space(space, user)
	return can_read_space(space, user)
