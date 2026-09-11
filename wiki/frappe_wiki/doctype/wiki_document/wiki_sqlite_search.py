import re
from typing import ClassVar

import frappe
from frappe.search.sqlite_search import SQLiteSearch


class WikiSQLiteSearch(SQLiteSearch):
	INDEX_NAME = "wiki_search.db"

	INDEX_SCHEMA: ClassVar[dict] = {
		"text_fields": ["title", "content"],
		"metadata_fields": ["doctype", "name", "route", "space", "published", "modified"],
		"tokenizer": "unicode61 remove_diacritics 2 tokenchars '-_'",
	}

	INDEXABLE_DOCTYPES: ClassVar[dict] = {
		"Wiki Document": {
			"fields": [
				"name",
				"title",
				"content",
				"route",
				{"published": "is_published"},
				"modified",
			],
			"filters": {"is_published": 1, "is_group": 0, "is_external_link": 0},
		}
	}

	# //// Neoffice — added: this app's index stays idempotent HERE, not in frappe.
	# //// `search_fts` has no unique key on doc_id and `update_doc_index` re-indexes
	# //// on every save of an indexed field, so a document edited n times sat n times
	# //// in the index: duplicate hits, and a pre-merge row still answering searches
	# //// after a content-only merge. Our frappe fork carries the same removal in
	# //// `SQLiteSearch.index_doc`, but that is the framework's chokepoint, every
	# //// app's indexing goes through it, and this app is the one that needs it.
	# //// `update_doc_index` instantiates the class registered in the `sqlite_search`
	# //// hook — this one — so the override is enough, and the app is correct on an
	# //// unpatched v15 as well (neoffice-maintenance#343).
	# ////
	# //// The removal is conditional ON PURPOSE. `prepare_document` returns nothing
	# //// for a document that is no longer indexable (an unpublished page: the config
	# //// filters on `is_published`), and that case must NOT drop the row here —
	# //// removal on unpublish is deferred to the commit by this app's own hook, and
	# //// a rolled-back save has to keep its row. Removing unconditionally breaks
	# //// `test_unpublish_index_removal_discarded_on_rollback` on BOTH forks.
	# ////
	# //// Drop this once the fleet is on v16, which drains a queue instead.
	def index_doc(self, doctype, docname):
		"""Re-indexing replaces the document's row instead of adding one."""
		if self.prepare_document(frappe.get_doc(doctype, docname)):
			self.remove_doc(doctype, docname)
		super().index_doc(doctype, docname)

	def get_search_filters(self):
		"""Permission-based filtering - only return published documents"""
		return {"published": 1}

	def prepare_document(self, doc):
		"""Override to compute space and strip markdown from content"""
		prepared = super().prepare_document(doc)
		if prepared and doc.get("doctype") == "Wiki Document":
			prepared["space"] = self._get_root_space(doc.get("name"))
			if prepared.get("content"):
				prepared["content"] = self._strip_markdown(prepared["content"])
		return prepared

	def _strip_markdown(self, text):
		"""Convert markdown to plain text for cleaner search indexing"""
		if not text:
			return text

		# Remove code blocks (``` ... ```)
		text = re.sub(r"```[\s\S]*?```", " ", text)

		# Remove inline code (`code`)
		text = re.sub(r"`[^`]+`", " ", text)

		# Remove custom directives (:::note, :::danger, etc.)
		text = re.sub(r":::[a-z]+\s*", " ", text)
		text = re.sub(r":::\s*", " ", text)

		# Remove images ![alt](url)
		text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)

		# Convert links [text](url) to just text
		text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

		# Remove headers (# ## ### etc.)
		text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

		# Remove bold/italic markers
		text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
		text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)

		# Remove blockquotes
		text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)

		# Remove horizontal rules
		text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

		# Remove HTML tags
		text = re.sub(r"<[^>]+>", " ", text)

		# Collapse multiple whitespace/newlines
		text = re.sub(r"\s+", " ", text)

		return text.strip()

	def _get_root_space(self, docname):
		"""Get the root wiki space for a document"""
		wiki_doc = frappe.get_doc("Wiki Document", docname)
		return wiki_doc.get_root_group() or docname


def enqueue_reindex(docnames: list[str]):
	"""Queue Wiki Documents for search re-indexing.

	Merge fast paths write content with raw ``frappe.db.set_value``, which
	skips the framework's on_update hook that normally queues the re-index —
	without this, the search index keeps serving the pre-merge content.
	"""
	search = WikiSQLiteSearch()
	if not (search.is_search_enabled() and search.index_exists()):
		return

	# //// Neoffice — SQLiteSearch.add_to_queue (and the scheduler drain) exist in
	# //// frappe v16 only; on our v15 fork the call raised, was swallowed below as
	# //// "Wiki Search Reindex Queue Error", and search kept serving the pre-merge
	# //// content after every content-only merge. Without the queue, index now,
	# //// synchronously, with the v15 API. Drop the fallback at the v16 upgrade.
	queue = getattr(search, "add_to_queue", None)
	try:
		for docname in docnames:
			# //// Neoffice — see the block marker above: v15 queue fallback
			if queue:
				queue(f"Wiki Document:{docname}")
			else:
				search.index_doc("Wiki Document", docname)
	except Exception:
		frappe.log_error(
			title="Wiki Search Reindex Queue Error",
			message=f"Failed to queue Wiki Documents for re-indexing: {docnames}",
		)


def remove_doc_from_index(docname: str):
	"""Remove a Wiki Document from the search index immediately.

	The framework's index update path only *queues* a re-index (drained by a
	5-minute scheduler job, 30 docs per run), so an unpublished page would keep
	surfacing in search until the queue catches up. Unpublishing must take
	effect right away, so we delete the row synchronously.
	"""
	search = WikiSQLiteSearch()
	if not (search.is_search_enabled() and search.index_exists()):
		return

	try:
		search.remove_doc("Wiki Document", docname)
	except Exception:
		frappe.log_error(
			title="Wiki Search Index Removal Error",
			message=f"Failed to remove Wiki Document {docname} from the search index",
		)
