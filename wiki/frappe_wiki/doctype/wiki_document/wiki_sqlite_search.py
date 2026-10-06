import re

# //// Neoffice — unicodedata: accents are folded to compare a title with what was typed (see the ranking block below).
import unicodedata
from typing import ClassVar

import frappe

# //// Neoffice — the two title boosts are reused by our own _get_title_boost (see the ranking block below).
from frappe.search.sqlite_search import (
	TITLE_EXACT_MATCH_BOOST,
	TITLE_PARTIAL_MATCH_BOOST,
	SQLiteSearch,
)


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

	# //// Neoffice — the manual's ranking, four measured defects (2026-10-04, « note de crédit » found
	# //// « Modifier les informations de votre entreprise » before the page about credit notes):
	# //// 1. `_get_base_score` is 1 / (1 + |bm25|), but FTS5's bm25() is NEGATIVE and the more negative the better:
	# ////    the better a page matched a rare word, the LOWER it scored (and a word found everywhere, whose idf
	# ////    SQLite clamps at 1e-6, scored 1.0, the maximum). Relevance is -bm25.
	# //// 2. `_get_title_boost` doubled the score of any page whose title holds ANY query word: « de » is in almost
	# ////    every French title, so the boost was nearly constant. Words that say nothing are ignored, and a title
	# ////    that holds the whole phrase, or all its words, beats one that holds a word.
	# //// 3. `_get_recency_boost` (x1.8 for a page edited in the last 24 h) rewards the pages reworked most recently:
	# ////    a manual is rewritten page by page for weeks, so the pages edited today beat the ones that answer.
	# //// 4. « avoir » is the colloquial name of what the product calls « note de crédit » (sales) and the page is
	# ////    titled with the product's word: a search for one finds the other.
	# //// Drop these four when upstream's ranking is fixed (they are an override of three scoring methods and of the
	# //// FTS query builder, nothing in the index changes).
	STOPWORDS: ClassVar[frozenset] = frozenset(
		"a au aux avec ce ces cet cette d dans de des du en et l la le les ma mes mon ne ou par pas pour qu que qui sa "
		"ses son sur un une vos votre notre the an of to for in on and or my our with at by "
		# //// Neoffice — the words of a question say nothing either (2026-10-05): « comment rapprocher la banque ? »
		# //// required « comment » and lost « Le rapprochement bancaire », a page that does not hold it, and
		# //// « comment créer un devis ? » put « Envoyer un devis… » before « Créer un devis ». The Quick Chat's
		# //// Help button searches the question as it was typed, and so does a person in the search bar.
		"comment quel quelle quels quelles quoi pourquoi quand combien est sont c j je m n s t y on il elle nous "
		"vous faire fait faut peut peux puis dois doit how what why when where which who do does did can i is are"
		.split()
	)
	# what people type -> what the manual calls it (one way: « note de crédit » must not find every « avoir »)
	SYNONYMS: ClassVar[dict] = {"avoir": "note de crédit", "avoirs": "notes de crédit"}
	MAX_RELEVANCE: ClassVar[float] = 12.0

	@staticmethod
	def _fold(text):
		"""Lower case, no accent, words only: « Note de Crédit » -> « note de credit »."""
		text = unicodedata.normalize("NFD", text or "")
		text = "".join(c for c in text if not unicodedata.combining(c)).lower()
		return re.sub(r"[^a-z0-9]+", " ", text).strip()

	def _meaningful(self, text):
		words = self._fold(text).split()
		return [w for w in words if w not in self.STOPWORDS] or words

	def _variants(self, query):
		"""The query, then the same query with a colloquial word said the manual's way."""
		words = query.split()
		variants = [words]
		for i, word in enumerate(words):
			synonym = self.SYNONYMS.get(self._fold(word))
			if synonym:
				variants.append(words[:i] + synonym.split() + words[i + 1 :])
		return variants

	def _get_base_score(self, row, query):
		"""Relevance of the match itself: bm25 is negative, the more negative the better."""
		relevance = max(0.0, -(row["bm25_score"] or 0.0))
		return 1.0 + min(relevance, self.MAX_RELEVANCE) / 4.0

	def _get_title_boost(self, row, query, query_words):
		"""The whole phrase in the title > all its words > one word. A word that says nothing counts for nothing."""
		title = self._fold(row["original_title"])
		title_words = title.split()
		for words in self._variants(query):
			meaningful = self._meaningful(" ".join(words))
			if " ".join(meaningful) in title:
				return TITLE_EXACT_MATCH_BOOST
		best = 1.0
		for words in self._variants(query):
			meaningful = self._meaningful(" ".join(words))
			found = [w for w in meaningful if any(t.startswith(w) for t in title_words)]
			if found and len(found) == len(meaningful):
				return (TITLE_EXACT_MATCH_BOOST + TITLE_PARTIAL_MATCH_BOOST) / 2
			if found:
				best = TITLE_PARTIAL_MATCH_BOOST
		return best

	def _get_recency_boost(self, row, query):
		"""A manual is not news: when a page was last edited says nothing about whether it answers."""
		return 1.0

	def _prepare_fts_query(self, query):
		"""Drop the words that say nothing (« de ») and let a colloquial word find the manual's own: AVOIR or NOTE DE CRÉDIT."""
		built = []
		for words in self._variants(query):
			kept = [w for w in words if self._fold(w) not in self.STOPWORDS] or words
			part = super()._prepare_fts_query(" ".join(kept))
			if part:
				built.append(part)
		if len(built) > 1:
			return " OR ".join(f"({part})" for part in built)
		return built[0] if built else ""

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
	"""Re-index Wiki Documents after a merge.

	Merge fast paths write content with raw ``frappe.db.set_value``, which
	skips the framework's on_update hook that normally triggers the re-index,
	so without this the search index keeps serving the pre-merge content.

	Goes through ``index_doc`` rather than the framework's queue table: the
	queue only exists on Frappe develop, while ``index_doc`` is present on
	version-16 too (indexing inline there, queueing on develop).
	"""
	search = WikiSQLiteSearch()
	if not (search.is_search_enabled() and search.index_exists()):
		return

	try:
		for docname in docnames:
			search.index_doc("Wiki Document", docname)
	except Exception:
		frappe.log_error(
			title="Wiki Search Reindex Error",
			message=f"Failed to re-index Wiki Documents: {docnames}",
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
