# //// Neoffice — added file (no upstream equivalent): the manual's search keeps the subject of a question.
"""A question searched as it was typed keeps its subject and drops its question words (2026-10-05).

« comment rapprocher la banque ? » required « comment »: the page « Le rapprochement bancaire », which does not
hold the word, was not found. The query builder needs no index, so these tests run anywhere.
"""

import unittest

from wiki.frappe_wiki.doctype.wiki_document.wiki_sqlite_search import WikiSQLiteSearch


class TestManualSearchQuery(unittest.TestCase):
	def setUp(self):
		# the query builder reads class attributes only: no index, no site
		self.engine = WikiSQLiteSearch.__new__(WikiSQLiteSearch)

	def _terms(self, query):
		return self.engine._prepare_fts_query(query).lower()

	def test_a_question_keeps_only_its_subject(self):
		for question, subject in (
			("comment rapprocher la banque ?", ("rapprocher", "banque")),
			("Comment créer un devis ?", ("créer", "devis")),
			("Pourquoi ma facture est-elle encore en brouillon ?", ("facture", "brouillon")),
			("Quel compte pour une facture d'électricité ?", ("compte", "facture")),
			("how do I create a quote?", ("create", "quote")),
		):
			with self.subTest(question=question):
				built = self._terms(question)
				for word in subject:
					self.assertIn(word, built)
				for word in ("comment", "pourquoi", "quel", "how", '"est"', '"do"'):
					self.assertNotIn(word, built)

	def test_a_plain_search_is_unchanged(self):
		self.assertEqual(self._terms("rapprochement bancaire"), '"rapprochement"* "bancaire"*')
		self.assertEqual(self._terms("note de crédit"), '"note"* "crédit"*')

	def test_a_query_of_question_words_only_still_searches(self):
		self.assertEqual(self._terms("comment faire"), '"comment"* "faire"*')

	def test_avoir_still_finds_the_manuals_word(self):
		built = self._terms("comment faire un avoir ?")
		self.assertIn('"avoir"*', built)
		self.assertIn('"crédit"*', built)
		self.assertNotIn("comment", built)
