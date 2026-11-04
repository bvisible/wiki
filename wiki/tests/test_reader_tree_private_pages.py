# //// Neoffice — added file (no upstream equivalent)
"""The reader shows a page flagged `is_private` only to those it serves it to (#2234).

Since #2226 the reader refuses such a page (404) to an anonymous visitor and to a
portal account, and keeps it for the staff. Around the page itself, it still
handed both outside readers what the page is: its title and address in the
sidebar, in the previous / next links, as the page a space URL lands on, and as
the target of an internal link. The sidebar tree was one tree per space, cached
for everyone.

Each case is played by the three readers there are (frappe.tests.roles.as_role),
the staff first so that a tree it leaves in the cache is the one the next reader
would be handed: a member of the staff (who keeps the private page: a space whose
every page is flagged, like nora-kb, is read by all the staff), a portal account
and an anonymous visitor.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.roles import as_role

from wiki.frappe_wiki.doctype.wiki_document.wiki_document import (
	clear_wiki_tree_cache,
	get_landing_page_for_route,
	resolve_wiki_links,
)
from wiki.tests.factory import WikiFixtureMixin
from wiki.tests.test_is_private_outside_the_reader import (
	a_site_without_the_column,
	node_names,
	public_wiki_on,
	slug,
)

STAFF = "accountant"
OUTSIDE_READERS = ("portal_customer", "Guest")
READERS = (STAFF, *OUTSIDE_READERS)
PRIVATE_TITLE = "Internal settings"


class ReaderSpaceMixin(WikiFixtureMixin):
	def make_space(self):
		"""A public space whose first page is the private one, then a page that links to it."""
		public_wiki_on(self)
		self.space = self.wiki.space(public_read=1)
		self.private = self.wiki.document(
			parent=self.space.root_group, title=PRIVATE_TITLE, slug=slug("private"), sort_order=1
		)
		self.public = self.wiki.document(
			parent=self.space.root_group,
			title="Public page",
			slug=slug("public"),
			sort_order=2,
			content=f"See [the settings](wiki:{self.private.doc_key}).",
		)
		clear_wiki_tree_cache()

	def reader_view(self) -> dict:
		"""What the reader hands the current user around the public page."""
		context = frappe.get_doc("Wiki Document", self.public.name).get_web_context()
		return {
			"sidebar": node_names(context["nested_tree"]),
			"previous": (context["prev_doc"] or {}).get("route"),
			"landing": (get_landing_page_for_route(self.space.route) or {}).get("route"),
			"content": context["rendered_content"],
		}


class TestTheReaderShowsAPrivatePageOnlyToThoseItServesItTo(ReaderSpaceMixin, IntegrationTestCase):
	def setUp(self):
		if not frappe.db.has_column("Wiki Document", "is_private"):
			self.skipTest("no legacy is_private column on this site: no page can carry the flag")
		self.make_space()
		frappe.db.set_value("Wiki Document", self.private.name, "is_private", 1, update_modified=False)
		frappe.clear_document_cache("Wiki Document", self.private.name)
		clear_wiki_tree_cache()

	def test_the_staff_keeps_the_private_page_around_the_reader(self):
		with as_role(STAFF):
			view = self.reader_view()
		self.assertIn(self.private.name, view["sidebar"])
		self.assertEqual(view["previous"], self.private.route)
		self.assertEqual(view["landing"], self.private.route)
		self.assertIn(f'href="/{self.private.route}"', view["content"])

	def test_an_outside_reader_is_not_shown_the_private_page(self):
		# The staff warms the cache first: its tree must not be the one handed on.
		with as_role(STAFF):
			self.assertIn(self.private.name, self.reader_view()["sidebar"])
		for reader in OUTSIDE_READERS:
			with as_role(reader):
				view = self.reader_view()
			with self.subTest(reader=reader, shown="sidebar"):
				self.assertIn(self.public.name, view["sidebar"])
				self.assertNotIn(self.private.name, view["sidebar"])
			with self.subTest(reader=reader, shown="previous link"):
				self.assertIsNone(view["previous"])
			with self.subTest(reader=reader, shown="landing page"):
				self.assertEqual(view["landing"], self.public.route)
			with self.subTest(reader=reader, shown="internal link"):
				self.assertNotIn(self.private.route, view["content"])
				self.assertIn("See the settings.", view["content"])


class TestTheReaderTreeOnASiteWithoutTheColumn(ReaderSpaceMixin, IntegrationTestCase):
	"""The reader's tree, landing page and links name `is_private` only where the column exists."""

	def setUp(self):
		self.make_space()
		self.enterContext(a_site_without_the_column())

	def test_every_reader_is_served_the_whole_published_space(self):
		for reader in READERS:
			with self.subTest(reader=reader), as_role(reader):
				view = self.reader_view()
				self.assertEqual({self.private.name, self.public.name}, view["sidebar"])
				self.assertEqual(view["landing"], self.private.route)
				self.assertIn(f'href="/{self.private.route}"', view["content"])

	def test_the_links_resolve_without_the_column(self):
		with as_role("Guest"):
			html = resolve_wiki_links(f'<a data-wiki-link="{self.private.doc_key}">x</a>', self.space.name)
		self.assertEqual(html, f'<a href="/{self.private.route}">x</a>')
