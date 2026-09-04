import frappe


@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
def search(query: str, space: str | None = None) -> dict:
	"""
	Search wiki documents with space-scoped filtering.

	Args:
	    query: Search query string
	    space: Wiki space (root group) name to scope search

	Returns:
	    Search results with title, content snippets, and scores
	"""
	from wiki.frappe_wiki.doctype.wiki_document.wiki_sqlite_search import WikiSQLiteSearch

	if not query or not query.strip():
		return {"results": [], "total": 0}

	search_engine = WikiSQLiteSearch()
	filters = {"space": space} if space else {}

	result = search_engine.search(query, filters=filters)

	hits = _filter_hits_by_space_visibility(result["results"])

	return {
		"results": [
			{
				"name": r["name"],
				"title": r["title"],
				"route": r.get("route", ""),
				"content": r["content"],
				"score": r["score"],
			}
			for r in hits
		],
		"total": len(hits),
	}


def _filter_hits_by_space_visibility(hits: list[dict]) -> list[dict]:
	"""Drop search hits the current user couldn't open as a page.

	The SQLite index is built without user context, so titles/snippets from
	restricted spaces can surface here. Resolve each hit's denormalized
	wiki_space and gate it through the same checks as page rendering: the
	space must be published (`check_published`) and readable by the current
	user (`check_space_access`).

	//// Neoffice — this paragraph used to end "Orphan documents (no wiki_space)
	//// stay readable by all", and the code did exactly that. Orphans now follow
	//// the rule that holds everywhere else: any logged-in user, never an
	//// anonymous visitor. The marker sits inside the docstring because that is
	//// the text being corrected; a `#` comment cannot reach it.
	"""
	from wiki.permissions import can_read_space, can_write_space

	names = [hit["name"] for hit in hits]
	if not names:
		return hits

	#//// Neoffice — is_published and is_private come along now. The space was the
	#//// only thing checked, so a private page inside a Guest-readable space came
	#//// back to anonymous visitors with its title AND its content snippet.
	#//// Verified on osiris: a search for "configuration" as Guest returned
	#//// wiki/erpnextswiss-settings-configuration, is_private=1.
	row_by_name = {
		row.name: row
		for row in frappe.get_all(
			"Wiki Document",
			filters={"name": ("in", names)},
			#//// Neoffice — is_published and is_private added; see above.
			fields=["name", "wiki_space", "is_published", "is_private"],
		)
	}

	visible: dict[str, bool] = {}

	def _is_visible(space_name: str) -> bool:
		if space_name not in visible:
			space_published = frappe.get_cached_value("Wiki Space", space_name, "is_published")
			visible[space_name] = bool(space_published) and can_read_space(space_name)
		return visible[space_name]

	#//// Neoffice — added, memoised like the one above. Drafts and private pages
	#//// belong to whoever may write the space; this is the same rule
	#//// get_wiki_tree() and get_public_space_info() apply, so the reader, the
	#//// tree and the search can never disagree about what exists.
	writable: dict[str, bool] = {}

	def _is_writable(space_name) -> bool:
		if space_name not in writable:
			writable[space_name] = can_write_space(space_name)
		return writable[space_name]

	#//// Neoffice — orphan hits (no wiki_space) used to pass unconditionally, so
	#//// this allow_guest endpoint leaked their titles and snippets to anonymous
	#//// visitors: the same hole closed in permissions.py and in
	#//// WikiDocument.check_space_access, and closing two of the three would have
	#//// been worse than useless. can_read_space(None) is the shared answer for
	#//// "no space": any logged-in user, never a Guest.
	orphans_visible = can_read_space(None)

	allowed = []
	for hit in hits:
		#//// Neoffice — a hit with no Wiki Document row is a stale index entry for
		#//// a deleted page; it used to be treated as an orphan and shown.
		row = row_by_name.get(hit["name"])
		if row is None:
			continue
		hit_space = row.wiki_space
		#//// Neoffice — orphan hits (no wiki_space) used to pass unconditionally
		#//// (`if not hit_space or _is_visible(...)`), so this allow_guest search
		#//// handed their titles and snippets to anonymous visitors. The name is
		#//// hit_visible and NOT visible: `visible` is the memo dict _is_visible()
		#//// closes over, so binding a bool to it turned the second hit of every
		#//// search into "argument of type bool is not iterable".
		hit_visible = _is_visible(hit_space) if hit_space else orphans_visible
		if not hit_visible:
			continue
		#//// Neoffice — and the page's own state, not just its space's. Editors keep
		#//// their drafts; everyone else sees only what is published and not private.
		if not (row.is_published and not row.is_private) and not _is_writable(hit_space):
			continue
		allowed.append(hit)
	return allowed
