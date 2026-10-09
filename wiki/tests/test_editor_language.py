# //// Neoffice — added file (no upstream equivalent): the editor boots in its author's language (maintenance#1383).
"""The editor's boot names the language it prints dates and numbers in (frontend/src/lib/uiLocale.js): the one
wiki.api.get_translations picks the label catalogue by, so that the dates and the labels agree."""

import frappe
from frappe.tests import IntegrationTestCase

from wiki.www.wiki_app import get_boot

AUTHOR = "wiki-language-author@example.com"


class TestEditorLanguage(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("User", AUTHOR):
			user = frappe.new_doc("User")
			user.email = AUTHOR
			user.first_name = "Wiki language"
			user.send_welcome_email = 0
			user.insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_the_boot_names_the_authors_language(self):
		frappe.db.set_value("User", AUTHOR, "language", "fr")
		frappe.set_user(AUTHOR)
		self.assertEqual(get_boot().lang, "fr")

	def test_an_author_without_a_language_reads_dates_in_the_language_of_the_labels(self):
		# get_translations sends this author no catalogue: the labels stay English, and so do the dates.
		frappe.db.set_value("User", AUTHOR, "language", None)
		frappe.set_user(AUTHOR)
		self.assertEqual(get_boot().lang, "en")

	def test_a_visitor_reads_the_sites_language(self):
		frappe.set_user("Guest")
		site_language = frappe.db.get_single_value("System Settings", "language") or "en"
		self.assertEqual(get_boot().lang, site_language)
