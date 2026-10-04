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

	# //// Neoffice — each of the first hits also says WHERE in the page the typed words are: `anchor` is the id of the
	# //// heading that holds most of them (an id of the page's own table of contents, the one the reader scrolls to),
	# //// so that a result, or an assistant quoting the page, can land on the right section instead of the top.
	# //// Upstream returns the page only. The rest of the list gets no anchor: the render is cached per page, but a
	# //// first render of eighty pages for one search would not be.
	results = []
	for index, r in enumerate(hits):
		item = {
			"name": r["name"],
			"title": r["title"],
			"route": r.get("route", ""),
			"content": r["content"],
			"score": r["score"],
		}
		if index < ANCHOR_HITS:
			item["anchor"] = _best_heading(r["name"], query)
		results.append(item)

	# //// Neoffice — the results are the list built above (same items as upstream, plus the anchor of the first hits).
	return {
		"results": results,
		"total": len(hits),
	}


# //// Neoffice — added (see the block above): how many hits are given an anchor.
ANCHOR_HITS = 8
_ANCHOR_STOPWORDS = frozenset(
	"a au aux avec ce ces cet cette d dans de des du en et l la le les ou par pour sur un une vos votre the of to for in and or".split()
)


# //// Neoffice — added (see the block above).
def _fold(text: str) -> list[str]:
	import re
	import unicodedata

	text = unicodedata.normalize("NFD", text or "")
	text = "".join(c for c in text if not unicodedata.combining(c)).lower()
	return re.sub(r"[^a-z0-9]+", " ", text).split()


# //// Neoffice — added (see the block above).
def _best_heading(doc_name: str, query: str) -> str | None:
	"""Id of the heading of this page that holds most of the typed words, or None when no heading holds one."""
	from wiki.frappe_wiki.doctype.wiki_document.wiki_document import get_rendered_content

	words = [w for w in _fold(query) if w not in _ANCHOR_STOPWORDS] or _fold(query)
	if not words:
		return None
	try:
		content = frappe.db.get_value("Wiki Document", doc_name, "content") or ""
		_html, toc = get_rendered_content(doc_name, content)
	except Exception:
		return None
	best, best_score = None, 0
	for heading in toc or []:
		heading_words = _fold(heading.get("text", ""))
		score = sum(1 for w in words if any(h.startswith(w) for h in heading_words))
		if score > best_score:
			best, best_score = heading.get("id"), score
	return best


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

	# //// Neoffice — is_published and is_private come along now. The space was the
	# //// only thing checked, so a private page inside a Guest-readable space came
	# //// back to anonymous visitors with its title AND its content snippet.
	# //// Verified on osiris: a search for "configuration" as Guest returned
	# //// wiki/erpnextswiss-settings-configuration, is_private=1.
	# //// Neoffice — `is_private` is the LEGACY per-page guest flag: wiki v3 removed it
	# //// from the DocType (backfill_space_access.py translates it into space access) and
	# //// only the DB column survives on migrated sites. A fresh v3 site has no such
	# //// column, and selecting it broke every search there ("Unknown column
	# //// 'is_private'", CI #196). Read it only where it still exists, like the patch does.
	has_legacy_private = frappe.db.has_column("Wiki Document", "is_private")
	fields = ["name", "wiki_space", "is_published"]
	if has_legacy_private:
		fields.append("is_private")
	row_by_name = {
		row.name: row
		for row in frappe.get_all(
			"Wiki Document",
			filters={"name": ("in", names)},
			# //// Neoffice — is_published and is_private added; see above.
			fields=fields,
		)
	}

	visible: dict[str, bool] = {}

	def _is_visible(space_name: str) -> bool:
		if space_name not in visible:
			space_published = frappe.get_cached_value("Wiki Space", space_name, "is_published")
			visible[space_name] = bool(space_published) and can_read_space(space_name)
		return visible[space_name]

	# //// Neoffice — added, memoised like the one above. Drafts and private pages
	# //// belong to whoever may write the space; this is the same rule
	# //// get_wiki_tree() and get_public_space_info() apply, so the reader, the
	# //// tree and the search can never disagree about what exists.
	writable: dict[str, bool] = {}

	def _is_writable(space_name) -> bool:
		if space_name not in writable:
			writable[space_name] = can_write_space(space_name)
		return writable[space_name]

	# //// Neoffice — orphan hits (no wiki_space) used to pass unconditionally, so
	# //// this allow_guest endpoint leaked their titles and snippets to anonymous
	# //// visitors: the same hole closed in permissions.py and in
	# //// WikiDocument.check_space_access, and closing two of the three would have
	# //// been worse than useless. can_read_space(None) is the shared answer for
	# //// "no space": any logged-in user, never a Guest.
	orphans_visible = can_read_space(None)

	allowed = []
	for hit in hits:
		# //// Neoffice — a hit with no Wiki Document row is a stale index entry for
		# //// a deleted page; it used to be treated as an orphan and shown.
		row = row_by_name.get(hit["name"])
		if row is None:
			continue
		hit_space = row.wiki_space
		# //// Neoffice — orphan hits (no wiki_space) used to pass unconditionally
		# //// (`if not hit_space or _is_visible(...)`), so this allow_guest search
		# //// handed their titles and snippets to anonymous visitors. The name is
		# //// hit_visible and NOT visible: `visible` is the memo dict _is_visible()
		# //// closes over, so binding a bool to it turned the second hit of every
		# //// search into "argument of type bool is not iterable".
		hit_visible = _is_visible(hit_space) if hit_space else orphans_visible
		if not hit_visible:
			continue
		# //// Neoffice — and the page's own state, not just its space's. Editors keep
		# //// their drafts; everyone else sees only what is published and not private.
		if not (row.is_published and not row.get("is_private")) and not _is_writable(hit_space):
			continue
		allowed.append(hit)
	return allowed
