# //// Neoffice — added file (no upstream equivalent)
"""A page flagged `is_private` is not served to outside readers (#2226).

The reader (WikiDocumentRenderer: get_web_context() for the HTML page, its
`Accept: text/markdown` branch, and the `.md` route of CrawlerRenderer) asked only
the space's role rows and whether the page was published. A page flagged private
inside a space everyone may read was therefore served whole to an anonymous
visitor (public wiki on) and to a signed-in portal account.

Each test opens the page the way the reader does, as the account that would open
it (frappe.tests.roles.as_role). `is_private` is the legacy column: wiki v3 dropped
the field and only migrated sites keep the column, so the tests that store the flag
skip where it is absent; the last class sets it on the loaded document and runs
everywhere.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.roles import as_role
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from wiki.frappe_wiki.doctype.wiki_document.wiki_document import WikiDocumentRenderer
from wiki.tests.factory import WikiFixtureMixin
from wiki.wiki.crawler_renderer import MARKDOWN_SUFFIX, CrawlerRenderer

AUTHOR = "role-test-wiki-author@yopmail.com"
PRIVATE_TITLE = "Internal settings"
PRIVATE_CONTENT = "Internal settings, kept from outside readers."
WAYS = ("html", "accept-markdown", ".md")


def make_author() -> str:
	"""A wiki author: holds Wiki User, the authoring role (wiki.permissions.is_wiki_author)."""
	if not frappe.db.exists("User", AUTHOR):
		user = frappe.new_doc("User")
		user.update({"email": AUTHOR, "first_name": "wiki author", "send_welcome_email": 0})
		user.append("roles", {"role": "Wiki User"})
		user.insert(ignore_permissions=True)
		frappe.clear_cache(user=AUTHOR)
	return AUTHOR


def open_page(way: str, route: str):
	"""What the reader serves at `route`, asked the way `way` names. Raises its 404."""
	if way == "html":
		renderer = WikiDocumentRenderer(path=route, http_status_code=200)
		assert renderer.can_render(), route
		return frappe.get_cached_doc("Wiki Document", renderer.wiki_doc_name).get_web_context()["doc"].content

	if way == "accept-markdown":
		renderer = WikiDocumentRenderer(path=route, http_status_code=200)
		assert renderer.can_render(), route
		request = Request(EnvironBuilder(path="/" + route, headers={"Accept": "text/markdown"}).get_environ())
		with patch.object(frappe.local, "request", request, create=True):
			return renderer.render().get_data(as_text=True)

	renderer = CrawlerRenderer(path=route + MARKDOWN_SUFFIX, http_status_code=200)
	assert renderer.can_render(), route
	return renderer.render().get_data(as_text=True)


class TestReaderPrivatePage(WikiFixtureMixin, IntegrationTestCase):
	def setUp(self):
		if not frappe.db.has_column("Wiki Document", "is_private"):
			self.skipTest("no legacy is_private column on this site: no page can carry the flag")

		# A public space, like the one on osiris: public_read, which Wiki Space keeps as
		# a Guest / Read row (without it, validate drops the row and only signed-in
		# accounts may read).
		space = self.wiki.space(public_read=1)
		self.private = self.wiki.document(
			parent=space.root_group,
			title=PRIVATE_TITLE,
			slug=f"private-{frappe.generate_hash(length=6)}",
			content=PRIVATE_CONTENT,
		)
		self.public = self.wiki.document(
			parent=space.root_group,
			title="Public page",
			slug=f"public-{frappe.generate_hash(length=6)}",
			content="Anyone may read this.",
		)
		frappe.db.set_value("Wiki Document", self.private.name, "is_private", 1, update_modified=False)
		frappe.clear_document_cache("Wiki Document", self.private.name)

		# With the public wiki off, the space itself refuses an anonymous visitor, and
		# the anonymous case would prove nothing about the flag.
		public_wiki = patch("wiki.permissions.public_wiki_enabled", return_value=True)
		public_wiki.start()
		self.addCleanup(public_wiki.stop)

	def assert_refused(self):
		for way in WAYS:
			with self.subTest(way=way), self.assertRaises(frappe.DoesNotExistError):
				open_page(way, self.private.route)
		# The space lets this reader in: the refusal is the flag's, not the space's.
		self.assertIn("Anyone may read this.", open_page("html", self.public.route))

	def assert_served(self):
		for way in WAYS:
			with self.subTest(way=way):
				self.assertIn(PRIVATE_CONTENT, open_page(way, self.private.route))

	def test_an_anonymous_visitor_is_refused_the_private_page(self):
		with as_role("Guest"):
			self.assert_refused()

	def test_a_portal_account_is_refused_the_private_page(self):
		with as_role("portal_customer"):
			self.assert_refused()

	def test_a_wiki_author_is_served_the_private_page(self):
		with as_role(make_author()):
			self.assert_served()

	def test_the_staff_is_served_the_private_page(self):
		# Nora's company knowledge base (nora-kb) flags every page and is read by all
		# the staff: a desk account without any wiki role keeps the page.
		with as_role("accountant"):
			self.assert_served()


class TestReaderPrivateFlagOnTheDocument(WikiFixtureMixin, IntegrationTestCase):
	"""The flag as the reader meets it, on the loaded document: runs on a site without the column too."""

	def test_a_portal_account_is_refused_a_page_whose_document_carries_the_flag(self):
		space = self.wiki.space(public_read=1)
		page = self.wiki.document(parent=space.root_group, title=PRIVATE_TITLE, content=PRIVATE_CONTENT)
		doc = frappe.get_doc("Wiki Document", page.name)

		with as_role("portal_customer"):
			self.assertEqual(doc.get_web_context()["doc"].content, PRIVATE_CONTENT)
			doc.is_private = 1
			with self.assertRaises(frappe.DoesNotExistError):
				doc.get_web_context()
