# //// Neoffice — added file (no upstream equivalent)
"""The legacy `is_private` flag outside the reader (#2232, after #2226).

#2226 made the reader refuse a page flagged `is_private` to an anonymous visitor
and to a portal account. Three paths around it still disagreed with it:

1. The crawler indexes, /sitemap.xml and llms.txt, are built for an anonymous
   visitor, and they listed the address of such a page.
2. The manual's sitemap (www/wiki_sitemap.py) is cached for an hour as its first
   visitor computed it: a member of the staff coming first put the pages only the
   staff may read in it, for everyone.
3. `is_private` is a legacy column (wiki v3 dropped the field, only migrated sites
   keep it). Five queries named it without asking whether it exists, and raised
   "Unknown column" on a site installed fresh.

Each case is played by the three readers there are (frappe.tests.roles.as_role):
an anonymous visitor, a portal account and a member of the staff; the authoring
tree, which refuses all three, by the wiki author who reaches it.
"""

from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.roles import as_role
from pymysql.err import OperationalError

from wiki.api import resolve_wiki_path
from wiki.api.wiki_space import get_public_document, get_public_space_info, get_wiki_tree
from wiki.tests.factory import WikiFixtureMixin
from wiki.tests.test_reader_private_page import make_author
from wiki.wiki.llms_txt import _site_llms_txt, _space_llms_txt
from wiki.wiki.sitemap import _wiki_links
from wiki.www import wiki_sitemap
from wiki.www.wiki_app import _reader_url_for_app_path

READERS = ("Guest", "portal_customer", "accountant")
PRIVATE_TITLE = "Internal settings"
PRIVATE_DESCRIPTION = "Internal settings, kept from outside readers."
PUBLIC_DESCRIPTION = "Anyone may read this."


def has_the_column() -> bool:
	return frappe.db.has_column("Wiki Document", "is_private")


def flag_private(page):
	frappe.db.set_value("Wiki Document", page.name, "is_private", 1, update_modified=False)
	frappe.clear_document_cache("Wiki Document", page.name)


def public_wiki_on(test):
	"""An anonymous visitor reads a public space only while the public wiki is on (it is off on osiris)."""
	patcher = patch("wiki.permissions.public_wiki_enabled", return_value=True)
	patcher.start()
	test.addCleanup(patcher.stop)


def routes(urls) -> set[str]:
	return {unquote(urlsplit(url).path).lstrip("/") for url in urls}


def node_names(nodes) -> set[str]:
	names = set()
	for node in nodes:
		names.add(node["name"])
		names |= node_names(node.get("children") or [])
	return names


def slug(prefix: str) -> str:
	return f"{prefix}-{frappe.generate_hash(length=6)}"


class TestCrawlerIndexesLeaveOutAPrivatePage(WikiFixtureMixin, IntegrationTestCase):
	"""/sitemap.xml and llms.txt never advertise a page the reader refuses to an anonymous visitor."""

	def setUp(self):
		if not has_the_column():
			self.skipTest("no legacy is_private column on this site: no page can carry the flag")
		public_wiki_on(self)
		self.space = self.wiki.space(public_read=1)
		# First in the sidebar: the space's landing entry in the site-wide llms.txt, were it listed.
		self.private = self.wiki.document(
			parent=self.space.root_group,
			title=PRIVATE_TITLE,
			slug=slug("private"),
			meta_description=PRIVATE_DESCRIPTION,
			sort_order=1,
		)
		self.public = self.wiki.document(
			parent=self.space.root_group,
			title="Public page",
			slug=slug("public"),
			meta_description=PUBLIC_DESCRIPTION,
			sort_order=2,
		)
		flag_private(self.private)

	def test_the_sitemap_leaves_out_the_private_page(self):
		for reader in READERS:
			with self.subTest(reader=reader), as_role(reader):
				listed = routes(url for url, _lastmod in _wiki_links())
				self.assertIn(self.public.route, listed)
				self.assertNotIn(self.private.route, listed)

	def test_the_space_llms_txt_leaves_out_the_private_page(self):
		for reader in READERS:
			with self.subTest(reader=reader), as_role(reader):
				index = _space_llms_txt(self.space.name)
				self.assertIn(self.public.route, index)
				self.assertNotIn(self.private.route, index)
				self.assertNotIn(PRIVATE_TITLE, index)

	def test_the_site_llms_txt_does_not_describe_the_space_by_its_private_page(self):
		for reader in READERS:
			with self.subTest(reader=reader), as_role(reader):
				entry = next(
					line for line in _site_llms_txt().splitlines() if f"/{self.space.route}/llms.txt" in line
				)
				self.assertIn(PUBLIC_DESCRIPTION, entry)
				self.assertNotIn(PRIVATE_DESCRIPTION, entry)


class TestTheManualSitemapIsComputedAsAnAnonymousVisitor(WikiFixtureMixin, IntegrationTestCase):
	"""www/wiki_sitemap.py: whoever fetches it first, the cached list is what an anonymous visitor may read."""

	def setUp(self):
		public_wiki_on(self)
		self.space = self.wiki.space(public_read=1)
		self.public = self.wiki.document(
			parent=self.space.root_group, title="Public page", slug=slug("public")
		)
		# No role row and no public_read: every signed-in account may read it, an anonymous visitor may not.
		signed_in_space = self.wiki.space()
		self.signed_in_page = self.wiki.document(
			parent=signed_in_space.root_group, title="Signed-in page", slug=slug("signed-in")
		)
		self.addCleanup(frappe.cache().delete_value, wiki_sitemap.CACHE_KEY)

	def sitemap_first_fetched_by(self, reader) -> set[str]:
		frappe.cache().delete_value(wiki_sitemap.CACHE_KEY)
		with as_role(reader):
			first = wiki_sitemap.get_context(frappe._dict())["links"]
		# What the first visitor left in the cache is what the next one, a crawler, is served.
		with as_role("Guest"):
			served = wiki_sitemap.get_context(frappe._dict())["links"]
		self.assertEqual(first, served)
		return routes(link["loc"] for link in served)

	def test_a_space_closed_to_visitors_stays_out_whoever_comes_first(self):
		for reader in READERS:
			with self.subTest(reader=reader):
				listed = self.sitemap_first_fetched_by(reader)
				self.assertIn(self.public.route, listed)
				self.assertNotIn(self.signed_in_page.route, listed)

	def test_a_private_page_stays_out_whoever_comes_first(self):
		if not has_the_column():
			self.skipTest("no legacy is_private column on this site: no page can carry the flag")
		private = self.wiki.document(parent=self.space.root_group, title=PRIVATE_TITLE, slug=slug("private"))
		flag_private(private)
		for reader in READERS:
			with self.subTest(reader=reader):
				listed = self.sitemap_first_fetched_by(reader)
				self.assertIn(self.public.route, listed)
				self.assertNotIn(private.route, listed)


@contextmanager
def a_site_without_the_column():
	"""Run as on a site installed fresh, where wiki v3 left no `is_private` column.

	Where the column really is absent (the CI), there is nothing to do. Where it
	exists (a migrated site), the site answers like a fresh one: has_column() says
	no, and a query on Wiki Document that names the column fails as MariaDB fails it.
	"""
	if not has_the_column():
		yield
		return

	db = frappe.local.db
	real_sql, real_has_column = db.sql, db.has_column

	def sql(query, *args, **kwargs):
		text = str(query)
		if "tabWiki Document" in text and "is_private" in text:
			raise OperationalError(1054, "Unknown column 'is_private' in 'WHERE'")
		return real_sql(query, *args, **kwargs)

	def has_column(doctype, column):
		if (doctype, column) == ("Wiki Document", "is_private"):
			return False
		return real_has_column(doctype, column)

	with patch.object(db, "sql", sql), patch.object(db, "has_column", has_column):
		yield


class TestTheReaderEndpointsOnASiteWithoutTheColumn(WikiFixtureMixin, IntegrationTestCase):
	"""The five queries that named `is_private` answer on a site that has no such column."""

	def setUp(self):
		public_wiki_on(self)
		self.space = self.wiki.space(public_read=1)
		self.page = self.wiki.document(
			parent=self.space.root_group, title="Public page", slug=slug("public"), content=PUBLIC_DESCRIPTION
		)
		self.enterContext(a_site_without_the_column())

	def test_the_public_space_tree(self):
		for reader in READERS:
			with self.subTest(reader=reader), as_role(reader):
				info = get_public_space_info(self.space.name)
				self.assertIn(self.page.name, node_names(info["tree"]["children"]))

	def test_the_space_tree_of_a_reader_who_cannot_write_the_space(self):
		# The authoring tree is refused (403) to the three outside readers whatever the
		# column: the one who reaches its published-only branch is a wiki author who
		# reads the space without writing it.
		for reader in READERS:
			with self.subTest(reader=reader), as_role(reader), self.assertRaises(frappe.PermissionError):
				get_wiki_tree(self.space.name)
		with as_role(make_author()):
			self.assertIn(self.page.name, node_names(get_wiki_tree(self.space.name)["children"]))

	def test_a_public_document(self):
		for reader in READERS:
			with self.subTest(reader=reader), as_role(reader):
				self.assertEqual(get_public_document(self.page.name)["content"], PUBLIC_DESCRIPTION)

	def test_a_page_route_resolves_to_its_page(self):
		for reader in READERS:
			with self.subTest(reader=reader), as_role(reader):
				self.assertEqual(
					resolve_wiki_path(self.page.route),
					{"space_id": self.space.name, "page_id": self.page.name},
				)

	def test_a_wiki_app_link_turns_into_the_reader_url(self):
		request = frappe._dict(path=f"/wiki-app/spaces/{self.space.name}/page/{self.page.name}")
		for reader in READERS:
			with (
				self.subTest(reader=reader),
				as_role(reader),
				patch.object(frappe.local, "request", request, create=True),
			):
				self.assertEqual(_reader_url_for_app_path(), "/" + self.page.route)
