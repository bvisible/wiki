# //// Neoffice — added file (no upstream equivalent): « 1 page », not « 1 cette page » (maintenance#1383).
"""The spaces list counts a space's pages with the bare word `page`, the same msgid the delete dialog builds
« Voulez-vous vraiment supprimer » + « cette page » + « ? » with. One translation cannot serve both, so the count
asks for the word through a context of its own, which the French catalogue translates « page »."""

import os
import re
import unittest

MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL_SPACES = os.path.join(os.path.dirname(MODULE), "frontend", "src", "pages", "AllSpaces.vue")
CATALOGUE = os.path.join(MODULE, "locale", "fr.po")


def _french(msgid: str, context: str | None) -> str | None:
	with open(CATALOGUE, encoding="utf-8") as f:
		catalogue = f.read()
	head = f'msgctxt "{context}"\n' if context else ""
	entry = re.search(rf'^{re.escape(head)}msgid "{re.escape(msgid)}"\nmsgstr "(.*)"$', catalogue, re.M)
	return entry.group(1) if entry else None


class TestEditorPageCount(unittest.TestCase):
	def test_a_space_with_one_page_reads_1_page(self):
		with open(ALL_SPACES, encoding="utf-8") as f:
			call = re.search(r"count === 1 \? __\('page'(?:, null, '([^']+)')?\)", f.read())
		self.assertIsNotNone(call, "the page count of the spaces list moved: find it again")
		self.assertIsNotNone(call.group(1), "the count asks for the dialog's word, « cette page »")
		self.assertEqual(_french("page", call.group(1)), "page")

	def test_the_delete_dialog_keeps_its_wording(self):
		self.assertEqual(
			_french("Are you sure you want to delete this", None), "Voulez-vous vraiment supprimer"
		)
		self.assertEqual(_french("page", None), "cette page")
