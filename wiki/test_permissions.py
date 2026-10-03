# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

"""Regression tests for the role-based Wiki Space access control helpers.

These cover the full permission matrix the feature promises:
manager / open space / read-role / write-role / wrong-role / Guest, plus the
hook entry points (query conditions + has_permission) and the role editor API.
"""

import frappe
from frappe.tests import IntegrationTestCase

from wiki.permissions import (
	_accessible_space_names,
	_is_manager,
	can_contribute_to_space,
	can_delete_space,
	can_read_space,
	can_write_space,
	wiki_cr_has_permission,
	wiki_document_has_permission,
	# //// Neoffice — imported for the draft tests at the end of the class below.
	wiki_document_query_conditions,
	wiki_space_has_permission,
)
from wiki.tests.factory import make_space

# //// Neoffice — imported for TestAppScreenGate at the end of the file.
from wiki.permissions import is_wiki_author
from wiki.utils import check_app_permission


def _set_contributions(space: str, allow: bool) -> None:
	frappe.db.set_value("Wiki Space", space, "allow_contributions", 1 if allow else 0)


READER_ROLE = "_Test WSAC Reader"
WRITER_ROLE = "_Test WSAC Writer"
OTHER_ROLE = "_Test WSAC Other"


def _ensure_role(role_name: str) -> None:
	if not frappe.db.exists("Role", role_name):
		frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 0}).insert(
			ignore_permissions=True
		)


def _ensure_user(email: str, roles: list[str]) -> str:
	if not frappe.db.exists("User", email):
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = "WSAC"
		user.send_welcome_email = 0
		user.insert(ignore_permissions=True)
	else:
		user = frappe.get_doc("User", email)

	existing = {r.role for r in user.roles}
	for role in roles:
		if role not in existing:
			user.add_roles(role)
	return email


def _make_space(test_case, name: str, roles: list[tuple[str, str]]) -> str:
	# //// Neoffice — public_read is the source of truth for "this space is on the
	# //// open internet" in our fork, and Wiki Space.sync_public_read_with_guest_role()
	# //// mirrors it into the Guest role row — it also STRIPS a Guest row the checkbox
	# //// does not back. A fixture that only appended the row therefore produced a
	# //// space with no Guest role at all, which is why the two Guest assertions below
	# //// failed. Ask for public the way the product asks for it. (Upstream 3.3.0 moved
	# //// the fixture into wiki.tests.factory.make_space; the flag rides on its **fields.)
	space = make_space(
		space_name=name,
		route=frappe.scrub(name).replace("_", "-"),
		roles=roles,
		# //// Neoffice — public_read: see the note above.
		public_read=1 if any(role == "Guest" for role, _level in roles) else 0,
	)
	test_case._spaces.append(space.name)
	return space.name


class TestWikiSpacePermissions(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for role in (READER_ROLE, WRITER_ROLE, OTHER_ROLE):
			_ensure_role(role)

		cls.reader = _ensure_user("wsac_reader@example.com", ["Wiki User", READER_ROLE])
		cls.writer = _ensure_user("wsac_writer@example.com", ["Wiki User", WRITER_ROLE])
		cls.outsider = _ensure_user("wsac_outsider@example.com", ["Wiki User", OTHER_ROLE])
		cls.manager = _ensure_user("wsac_manager@example.com", ["Wiki Manager"])
		cls.approver = _ensure_user("wsac_approver@example.com", ["Wiki User", "Wiki Approver"])
		# //// Neoffice — two accounts without any wiki role, for the draft tests: a
		# //// portal account (Website User, no role at all) and a writer of the
		# //// restricted space who holds no authoring role.
		cls.portal = _ensure_user("wsac_portal@example.com", [])
		cls.bare_writer = _ensure_user("wsac_bare_writer@example.com", [WRITER_ROLE])
		frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit

	def setUp(self):
		self._docs = []
		self._spaces = []
		# //// Neoffice — enable_public_wiki is the master switch for the whole
		# //// anonymous surface and it is OFF by default, so every Guest assertion
		# //// below silently depended on however the site running the suite happened
		# //// to be configured. State the premise instead of inheriting it: these
		# //// tests describe a public-facing instance. tearDown restores the site.
		self._public_wiki_was = frappe.db.get_single_value(
			"Wiki Settings", "enable_public_wiki"
		)
		frappe.db.set_single_value("Wiki Settings", "enable_public_wiki", 1)
		# A space gated to the reader (Read) and writer (Write) roles.
		self.restricted = _make_space(
			self, "WSAC Restricted", [(READER_ROLE, "Read"), (WRITER_ROLE, "Write")]
		)
		# A space with no role rows: open to all logged-in users.
		self.open_space = _make_space(self, "WSAC Open", [])
		# A publicly readable space (built-in Guest role on the read list).
		self.public = _make_space(self, "WSAC Public", [("Guest", "Read")])

	def tearDown(self):
		frappe.set_user("Administrator")
		# //// Neoffice — restore the master switch (see setUp).
		frappe.db.set_single_value(
			"Wiki Settings", "enable_public_wiki", self._public_wiki_was
		)
		for space in self._spaces:
			if frappe.db.exists("Wiki Space", space):
				frappe.delete_doc("Wiki Space", space, force=True)
		for doc in reversed(self._docs):
			if frappe.db.exists("Wiki Document", doc):
				frappe.delete_doc("Wiki Document", doc, force=True)

	# --- _is_manager -----------------------------------------------------

	def test_administrator_and_wiki_manager_are_managers(self):
		self.assertTrue(_is_manager("Administrator"))
		self.assertTrue(_is_manager(self.manager))
		self.assertFalse(_is_manager(self.reader))

	# --- can_read_space --------------------------------------------------

	def test_manager_reads_any_space(self):
		self.assertTrue(can_read_space(self.restricted, self.manager))
		self.assertTrue(can_read_space(self.restricted, "Administrator"))

	def test_read_role_grants_read(self):
		self.assertTrue(can_read_space(self.restricted, self.reader))

	def test_write_role_implies_read(self):
		self.assertTrue(can_read_space(self.restricted, self.writer))

	def test_unlisted_role_denied_read_on_restricted_space(self):
		self.assertFalse(can_read_space(self.restricted, self.outsider))

	def test_open_space_readable_by_any_logged_in_user(self):
		self.assertTrue(can_read_space(self.open_space, self.outsider))

	def test_open_space_not_readable_by_guest(self):
		self.assertFalse(can_read_space(self.open_space, "Guest"))

	def test_guest_role_makes_space_publicly_readable(self):
		self.assertTrue(can_read_space(self.public, "Guest"))

	def test_restricted_space_not_readable_by_guest(self):
		self.assertFalse(can_read_space(self.restricted, "Guest"))

	# //// Neoffice — added. The master switch is the one thing standing between a
	# //// client instance and the open internet, and it had no test at all. Both
	# //// paths must obey it: can_read_space() refuses one space at a time, and
	# //// _accessible_space_names() answers the list queries — they disagreed about
	# //// the same Guest until they were made to share _guest_access_blocked().
	def test_master_switch_closes_the_whole_guest_surface(self):
		frappe.db.set_single_value("Wiki Settings", "enable_public_wiki", 0)

		self.assertFalse(can_read_space(self.public, "Guest"))
		self.assertEqual(_accessible_space_names("Guest"), set())

		# and it closes nothing for somebody who actually has an account
		self.assertTrue(can_read_space(self.open_space, self.outsider))

	# --- can_write_space -------------------------------------------------

	def test_manager_writes_any_space(self):
		self.assertTrue(can_write_space(self.restricted, self.manager))

	def test_write_role_grants_write(self):
		self.assertTrue(can_write_space(self.restricted, self.writer))

	def test_read_role_does_not_grant_write(self):
		self.assertFalse(can_write_space(self.restricted, self.reader))

	def test_unlisted_role_denied_write(self):
		self.assertFalse(can_write_space(self.restricted, self.outsider))

	def test_open_space_writable_only_by_approver(self):
		self.assertTrue(can_write_space(self.open_space, self.approver))
		self.assertFalse(can_write_space(self.open_space, self.outsider))

	# --- can_delete_space ------------------------------------------------

	def test_manager_deletes_any_space(self):
		self.assertTrue(can_delete_space(self.restricted, self.manager))

	def test_write_role_does_not_grant_delete(self):
		self.assertFalse(can_delete_space(self.restricted, self.writer))

	def test_read_role_does_not_grant_delete(self):
		self.assertFalse(can_delete_space(self.restricted, self.reader))

	def test_open_space_deletable_by_approver(self):
		self.assertTrue(can_delete_space(self.open_space, self.approver))
		self.assertFalse(can_delete_space(self.open_space, self.outsider))

	# --- _accessible_space_names ----------------------------------------

	def test_accessible_spaces_for_listed_reader(self):
		names = _accessible_space_names(self.reader)
		self.assertIn(self.restricted, names)
		self.assertIn(self.open_space, names)

	def test_accessible_spaces_excludes_restricted_for_outsider(self):
		names = _accessible_space_names(self.outsider)
		self.assertNotIn(self.restricted, names)
		self.assertIn(self.open_space, names)

	def test_accessible_spaces_for_guest_only_public(self):
		names = _accessible_space_names("Guest")
		self.assertIn(self.public, names)
		self.assertNotIn(self.open_space, names)
		self.assertNotIn(self.restricted, names)

	# --- query-condition filtering via get_list -------------------------

	def test_get_list_filters_restricted_space_for_outsider(self):
		frappe.set_user(self.outsider)
		names = {s.name for s in frappe.get_list("Wiki Space", limit=0)}
		self.assertIn(self.open_space, names)
		self.assertNotIn(self.restricted, names)

	def test_get_list_includes_restricted_space_for_reader(self):
		frappe.set_user(self.reader)
		names = {s.name for s in frappe.get_list("Wiki Space", limit=0)}
		self.assertIn(self.restricted, names)
		self.assertIn(self.open_space, names)

	def test_get_list_unfiltered_for_manager(self):
		frappe.set_user(self.manager)
		names = {s.name for s in frappe.get_list("Wiki Space", limit=0)}
		self.assertIn(self.restricted, names)
		self.assertIn(self.open_space, names)
		self.assertIn(self.public, names)

	# --- has_permission hook entry points -------------------------------

	def test_space_has_permission_read_vs_write(self):
		doc = frappe.get_doc("Wiki Space", self.restricted)
		self.assertTrue(wiki_space_has_permission(doc, "read", self.reader))
		self.assertFalse(wiki_space_has_permission(doc, "write", self.reader))
		self.assertTrue(wiki_space_has_permission(doc, "write", self.writer))
		self.assertFalse(wiki_space_has_permission(doc, "read", self.outsider))

	def test_document_has_permission_delegates_to_space(self):
		doc = frappe.get_doc({"doctype": "Wiki Document", "title": "Gated", "wiki_space": self.restricted})
		self.assertTrue(wiki_document_has_permission(doc, "read", self.reader))
		self.assertFalse(wiki_document_has_permission(doc, "read", self.outsider))
		self.assertFalse(wiki_document_has_permission(doc, "write", self.reader))
		self.assertTrue(wiki_document_has_permission(doc, "write", self.writer))

	def test_orphan_document_readable_by_all_writable_by_manager(self):
		doc = frappe.get_doc({"doctype": "Wiki Document", "title": "Orphan", "wiki_space": None})
		self.assertTrue(wiki_document_has_permission(doc, "read", self.outsider))
		self.assertFalse(wiki_document_has_permission(doc, "write", self.outsider))
		self.assertTrue(wiki_document_has_permission(doc, "write", self.manager))

	def test_cr_has_permission_is_governed_by_space_read(self):
		doc = frappe.get_doc({"doctype": "Wiki Change Request", "wiki_space": self.restricted})
		# Reading a CR requires space Read; editing (proposing) additionally
		# requires the space to accept contributions (on by default). Merge is
		# gated separately in the controller.
		self.assertTrue(wiki_cr_has_permission(doc, "read", self.reader))
		self.assertTrue(wiki_cr_has_permission(doc, "write", self.reader))
		self.assertFalse(wiki_cr_has_permission(doc, "read", self.outsider))

	# --- can_contribute_to_space (Accept Contributions toggle) -------------

	def test_contributions_on_lets_reader_contribute(self):
		_set_contributions(self.restricted, True)
		self.assertTrue(can_contribute_to_space(self.restricted, self.reader))

	def test_contributions_off_blocks_reader(self):
		_set_contributions(self.restricted, False)
		self.assertFalse(can_contribute_to_space(self.restricted, self.reader))

	def test_contributions_off_still_allows_writer_and_manager(self):
		_set_contributions(self.restricted, False)
		self.assertTrue(can_contribute_to_space(self.restricted, self.writer))
		self.assertTrue(can_contribute_to_space(self.restricted, self.manager))

	def test_contributions_never_grant_access_without_read(self):
		_set_contributions(self.restricted, True)
		self.assertFalse(can_contribute_to_space(self.restricted, self.outsider))

	def test_new_space_defaults_to_accepting(self):
		# The doctype default keeps contributions on unless explicitly disabled.
		self.assertEqual(frappe.db.get_value("Wiki Space", self.restricted, "allow_contributions"), 1)
		self.assertTrue(can_contribute_to_space(self.restricted, self.reader))

	def test_cr_write_blocked_for_reader_when_contributions_off(self):
		_set_contributions(self.restricted, False)
		doc = frappe.get_doc({"doctype": "Wiki Change Request", "wiki_space": self.restricted})
		# Reads still allowed; writes (proposing) blocked for Read-tier, allowed
		# for Write-tier even with contributions off.
		self.assertTrue(wiki_cr_has_permission(doc, "read", self.reader))
		self.assertFalse(wiki_cr_has_permission(doc, "write", self.reader))
		self.assertTrue(wiki_cr_has_permission(doc, "write", self.writer))

	def test_create_change_request_blocked_for_reader_when_off(self):
		from wiki.frappe_wiki.doctype.wiki_change_request.wiki_change_request import (
			create_change_request,
		)

		_set_contributions(self.restricted, False)
		frappe.set_user(self.reader)
		with self.assertRaises(frappe.PermissionError):
			create_change_request(self.restricted, "Reader proposal")

	# //// Neoffice — added. A page that is not live (unpublished, or in an
	# //// unpublished space) belongs to the wiki's authors and to the writers of its
	# //// space. The document hooks only ever checked the space, so the generic
	# //// document API served drafts whole to anyone who could read the space,
	# //// anonymous visitors of a public space included.

	def _document(self, space: str, title: str, published: bool):
		root = frappe.db.get_value("Wiki Space", space, "root_group")
		doc = frappe.get_doc(
			{
				"doctype": "Wiki Document",
				# The suffix keeps the route unique if an aborted run left a page behind.
				"title": f"{title} {frappe.generate_hash(length=6)}",
				"wiki_space": space,
				"parent_wiki_document": root,
				"is_published": 1 if published else 0,
				"content": title,
			}
		).insert(ignore_permissions=True)
		self._docs.append(doc.name)
		return doc

	def _listed(self, user: str, space: str) -> set:
		"""What the list-query hook lets `user` see of `space`.

		Called directly: on a stock site neither Guest nor a portal account has a
		DocPerm on Wiki Document, so frappe.get_list would refuse them before the
		hook ran — the hub grants Guest read through a Custom DocPerm, which is how
		the drafts got out, and then this clause is the only gate left.
		"""
		condition = wiki_document_query_conditions(user) or "1=1"
		return set(
			frappe.db.sql_list(  # nosemgrep
				f"select name from `tabWiki Document` where wiki_space = %s and {condition}",
				space,
			)
		)

	def test_a_draft_is_hidden_from_a_guest_and_a_portal_account(self):
		live = self._document(self.public, "WSAC Live", True)
		draft = self._document(self.public, "WSAC Draft", False)
		for user in ("Guest", self.portal):
			self.assertTrue(wiki_document_has_permission(live, "read", user), user)
			self.assertFalse(wiki_document_has_permission(draft, "read", user), user)
			listed = self._listed(user, self.public)
			self.assertIn(live.name, listed, user)
			self.assertNotIn(draft.name, listed, user)

	def test_a_draft_stays_with_the_authors_and_the_writers_of_its_space(self):
		draft = self._document(self.restricted, "WSAC Restricted Draft", False)
		for user in (self.reader, self.writer, self.bare_writer, self.manager):
			self.assertTrue(wiki_document_has_permission(draft, "read", user), user)
		self.assertIn(draft.name, self._listed(self.bare_writer, self.restricted))
		# an author still needs the space: the draft rule adds nothing to it
		self.assertFalse(wiki_document_has_permission(draft, "read", self.outsider))
		self.assertNotIn(draft.name, self._listed(self.outsider, self.restricted))

		frappe.set_user(self.reader)
		listed = set(
			frappe.get_list("Wiki Document", filters={"wiki_space": self.restricted}, pluck="name", limit=0)
		)
		self.assertIn(draft.name, listed)

	def test_an_unpublished_space_is_not_read_by_a_portal_account(self):
		page = self._document(self.open_space, "WSAC Open Page", True)
		frappe.db.set_value("Wiki Space", self.open_space, "is_published", 0)
		frappe.clear_document_cache("Wiki Space", self.open_space)

		self.assertFalse(wiki_document_has_permission(page, "read", self.portal))
		self.assertNotIn(page.name, self._listed(self.portal, self.open_space))
		# a wiki author reading the open space keeps it
		self.assertTrue(wiki_document_has_permission(page, "read", self.outsider))
		self.assertIn(page.name, self._listed(self.outsider, self.open_space))

	def test_an_orphan_draft_stays_with_the_authors(self):
		orphan = frappe.get_doc({"doctype": "Wiki Document", "title": "Orphan draft", "wiki_space": None})
		self.assertFalse(wiki_document_has_permission(orphan, "read", self.portal))
		self.assertTrue(wiki_document_has_permission(orphan, "read", self.outsider))
		orphan.is_published = 1
		self.assertTrue(wiki_document_has_permission(orphan, "read", self.portal))


class TestSpaceRolesAPI(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_role(READER_ROLE)
		_ensure_role(WRITER_ROLE)
		cls.reader = _ensure_user("wsac_reader@example.com", ["Wiki User", READER_ROLE])
		cls.manager = _ensure_user("wsac_manager@example.com", ["Wiki Manager"])
		frappe.db.commit()  # nosemgrep: frappe-semgrep-rules.rules.frappe-manual-commit

	def setUp(self):
		self._docs = []
		self._spaces = []
		self.space = _make_space(self, "WSAC API", [(READER_ROLE, "Read")])

	def tearDown(self):
		frappe.set_user("Administrator")
		for space in self._spaces:
			if frappe.db.exists("Wiki Space", space):
				frappe.delete_doc("Wiki Space", space, force=True)
		for doc in reversed(self._docs):
			if frappe.db.exists("Wiki Document", doc):
				frappe.delete_doc("Wiki Document", doc, force=True)

	def test_update_space_roles_denied_for_read_tier_user(self):
		from wiki.api.wiki_space import update_space_roles

		frappe.set_user(self.reader)
		with self.assertRaises(frappe.PermissionError):
			update_space_roles(self.space, [{"role": WRITER_ROLE, "permission_level": "Write"}])

	def test_update_space_roles_replaces_rows_for_manager(self):
		from wiki.api.wiki_space import get_space_roles, update_space_roles

		frappe.set_user(self.manager)
		update_space_roles(
			self.space,
			[
				{"role": READER_ROLE, "permission_level": "Read"},
				{"role": WRITER_ROLE, "permission_level": "Write"},
			],
		)
		rows = get_space_roles(self.space)
		levels = {r["role"]: r["permission_level"] for r in rows}
		self.assertEqual(levels, {READER_ROLE: "Read", WRITER_ROLE: "Write"})

	def test_update_space_roles_skips_blank_rows(self):
		from wiki.api.wiki_space import get_space_roles, update_space_roles

		frappe.set_user(self.manager)
		update_space_roles(
			self.space,
			[
				{"role": "", "permission_level": "Read"},
				{"role": READER_ROLE, "permission_level": "Read"},
			],
		)
		rows = get_space_roles(self.space)
		self.assertEqual([r["role"] for r in rows], [READER_ROLE])

	def test_set_space_contributions_updates_flag_for_manager(self):
		from wiki.api.wiki_space import set_space_contributions

		frappe.set_user(self.manager)
		set_space_contributions(self.space, 0)
		self.assertEqual(frappe.db.get_value("Wiki Space", self.space, "allow_contributions"), 0)
		set_space_contributions(self.space, 1)
		self.assertEqual(frappe.db.get_value("Wiki Space", self.space, "allow_contributions"), 1)

	def test_set_space_contributions_denied_for_read_tier_user(self):
		from wiki.api.wiki_space import set_space_contributions

		frappe.set_user(self.reader)
		with self.assertRaises(frappe.PermissionError):
			set_space_contributions(self.space, 0)

	def test_set_space_contributions_blocked_on_git_synced_space(self):
		from wiki.api.wiki_space import set_space_contributions

		frappe.db.set_value("Wiki Space", self.space, "git_synced", 1)
		frappe.clear_document_cache("Wiki Space", self.space)
		frappe.set_user(self.manager)
		with self.assertRaises(frappe.PermissionError):
			set_space_contributions(self.space, 0)


# //// Neoffice — added (no upstream equivalent). The wiki tile on the apps screen
# //// (`add_to_apps_screen` in hooks.py, gated by `check_app_permission`) followed "Wiki Manager"
# //// alone, while /wiki-app admits every wiki author (`is_wiki_author`), so an account allowed to
# //// use the app had no tile to reach it (#805). The tile now follows the rule of the page it opens.
# //// The accounts are yopmail addresses created inside each test's transaction and rolled back at
# //// the end: nothing persists on the site that runs the suite.
class TestAppScreenGate(IntegrationTestCase):
	"""Who sees the wiki tile on the apps screen: the accounts /wiki-app admits, and nobody else."""

	# A role with desk access and no wiki role: what a desk account looks like without Wiki User.
	DESK_ROLE = "Desk User"

	def setUp(self):
		self._emails = []

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for email in self._emails:
			frappe.clear_cache(user=email)

	def _account(self, name: str, roles: list[str]) -> str:
		email = f"wiki-tile-{name}@yopmail.com"
		self._emails.append(email)
		return _ensure_user(email, roles)

	def _tile_shown_to(self, user: str) -> bool:
		frappe.set_user(user)
		try:
			return bool(check_app_permission())
		finally:
			frappe.set_user("Administrator")

	def test_a_desk_account_holding_wiki_user_sees_the_tile(self):
		# The case #805 is about: /wiki-app lets a Wiki User in, and upstream hid the tile from them
		# because they are not a Wiki Manager.
		author = self._account("author", [self.DESK_ROLE, "Wiki User"])
		self.assertEqual(frappe.db.get_value("User", author, "user_type"), "System User")
		self.assertNotIn("Wiki Manager", frappe.get_roles(author))
		self.assertTrue(self._tile_shown_to(author))

	def test_an_account_holding_only_the_wiki_user_role_sees_the_tile(self):
		author = self._account("only", ["Wiki User"])
		self.assertTrue(self._tile_shown_to(author))

	def test_managers_and_administrator_see_the_tile(self):
		wiki_manager = self._account("wikimanager", ["Wiki Manager"])
		system_manager = self._account("sysmanager", ["System Manager"])
		self.assertTrue(self._tile_shown_to(wiki_manager))
		self.assertTrue(self._tile_shown_to(system_manager))
		self.assertTrue(self._tile_shown_to("Administrator"))

	def test_a_desk_account_without_a_wiki_role_does_not_see_the_tile(self):
		desk = self._account("desk", [self.DESK_ROLE])
		self.assertEqual(frappe.db.get_value("User", desk, "user_type"), "System User")
		self.assertNotIn("Wiki User", frappe.get_roles(desk))
		self.assertFalse(self._tile_shown_to(desk))

	def test_a_portal_account_does_not_see_the_tile(self):
		# A Website User: no desk, no wiki role. They read the wiki at /wiki/..., they get no app tile.
		portal = self._account("portal", [])
		self.assertEqual(frappe.db.get_value("User", portal, "user_type"), "Website User")
		self.assertFalse(self._tile_shown_to(portal))

	def test_guest_does_not_see_the_tile(self):
		self.assertFalse(self._tile_shown_to("Guest"))

	def test_the_tile_gate_grants_no_document_permission(self):
		# The gate only decides whether a tile is drawn; it must not become a way in.
		portal = self._account("nothing-new", [])
		for user in (portal, "Guest"):
			self.assertFalse(frappe.has_permission("Wiki Space", "write", user=user))
			self.assertFalse(frappe.has_permission("Wiki Space", "create", user=user))
			self.assertFalse(frappe.has_permission("Wiki Document", "create", user=user))

	def test_the_tile_and_the_authoring_page_admit_the_same_accounts(self):
		# /wiki-app turns away whoever is not is_wiki_author(); the tile must not promise more, or less.
		accounts = {
			"Guest": "Guest",
			"Administrator": "Administrator",
			"portal": self._account("same-portal", []),
			"desk": self._account("same-desk", [self.DESK_ROLE]),
			"author": self._account("same-author", [self.DESK_ROLE, "Wiki User"]),
			"manager": self._account("same-manager", ["Wiki Manager"]),
		}
		for label, user in accounts.items():
			frappe.set_user(user)
			try:
				self.assertEqual(check_app_permission(), is_wiki_author(), msg=label)
			finally:
				frappe.set_user("Administrator")

	def test_the_apps_screen_asks_this_gate(self):
		gates = [tile.get("has_permission") for tile in frappe.get_hooks("add_to_apps_screen", app_name="wiki")]
		self.assertEqual(gates, ["wiki.utils.check_app_permission"])
