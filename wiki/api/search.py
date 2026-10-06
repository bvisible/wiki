import frappe

from wiki.telemetry import capture

PAGE_SEARCH_LIMIT = 20


@frappe.whitelist()
def search_pages(query: str) -> list[dict]:
	"""Find pages by URL across every space the user can read."""
	query = (query or "").strip()
	if not query:
		return []

	# Routes hyphenate words, so "getting started" still finds `getting-started`.
	# The slash skips the space's own segment, which every page in it shares.
	route = query.replace(" ", "-")
	pages = frappe.get_list(
		"Wiki Document",
		filters={
			"route": ("like", f"%/%{route}%"),
			"is_group": 0,
			"is_external_link": 0,
			"wiki_space": ("is", "set"),
		},
		fields=[
			"name",
			"title",
			"route",
			"is_published",
			"wiki_space",
			"wiki_space.space_name as space_name",
			"wiki_space.route as space_route",
		],
		# //// Neoffice — `modified` qualified with its table. The fields above join Wiki Space
		# //// (`wiki_space.space_name`), which has a `modified` of its own; Frappe v15 emits the
		# //// bare column in ORDER BY and MariaDB answers 1052 "ambiguous", so the palette's page
		# //// search raised on every call. Qualified, it is the same order on v15 and v16.
		order_by="`tabWiki Document`.modified desc",
		limit=PAGE_SEARCH_LIMIT,
	)
	capture("search_performed", interval="1d", surface="app", hits=bool(pages))
	return pages
