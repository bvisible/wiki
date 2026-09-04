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
	user (`check_space_access`). Orphan documents (no wiki_space) follow the
	same rule as everywhere else: any logged-in user, never an anonymous
	visitor.
	"""
	from wiki.permissions import can_read_space

	names = [hit["name"] for hit in hits]
	if not names:
		return hits

	space_by_name = {
		row.name: row.wiki_space
		for row in frappe.get_all(
			"Wiki Document",
			filters={"name": ("in", names)},
			fields=["name", "wiki_space"],
		)
	}

	visible: dict[str, bool] = {}

	def _is_visible(space_name: str) -> bool:
		if space_name not in visible:
			space_published = frappe.get_cached_value("Wiki Space", space_name, "is_published")
			visible[space_name] = bool(space_published) and can_read_space(space_name)
		return visible[space_name]

	#//// Neoffice — orphan hits (no wiki_space) used to pass unconditionally, so
	#//// this allow_guest endpoint leaked their titles and snippets to anonymous
	#//// visitors: the same hole closed in permissions.py and in
	#//// WikiDocument.check_space_access, and closing two of the three would have
	#//// been worse than useless. can_read_space(None) is the shared answer for
	#//// "no space": any logged-in user, never a Guest.
	orphans_visible = can_read_space(None)

	allowed = []
	for hit in hits:
		hit_space = space_by_name.get(hit["name"])
		#//// Neoffice — orphan hits (no wiki_space) used to pass unconditionally
		#//// (`if not hit_space or _is_visible(...)`), so this allow_guest search
		#//// handed their titles and snippets to anonymous visitors. The name is
		#//// hit_visible and NOT visible: `visible` is the memo dict _is_visible()
		#//// closes over, so binding a bool to it turned the second hit of every
		#//// search into "argument of type bool is not iterable".
		hit_visible = _is_visible(hit_space) if hit_space else orphans_visible
		if hit_visible:
			allowed.append(hit)
	return allowed
