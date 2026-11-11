# //// Neoffice — added file (no upstream equivalent)
"""A visitor leaves feedback through the page's endpoint, and through nothing else.

Upstream ships `Wiki Feedback` with `create` and `write` for `Guest` and for `All`: the
feedback widget's endpoint (`submit_feedback`, rate limited, checks its arguments) inserted
the row under the visitor's own rights. Those rights also opened the REST collection, so any
anonymous visitor or portal account could POST rows straight into `/api/resource/Wiki
Feedback`, past the rate limit and the checks, or rewrite one by its name. The fleet's
open-grants check reported it Critical on every instance (neoffice-maintenance#531).

The endpoint now inserts the row itself (`ignore_permissions`), the role rows are gone from
the doctype, and a patch removes the copies frozen in `Custom DocPerm`, which replace the
doctype's rows on a site that has any.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.roles import as_role

from wiki.tests.factory import WikiFixtures
from wiki.wiki.doctype.wiki_feedback import wiki_feedback
from wiki.wiki.doctype.wiki_feedback.wiki_feedback import submit_feedback

PORTAL_ACCOUNT = "role-test-wiki-feedback-portal@yopmail.com"
FEEDBACK = "Wiki Feedback"


def make_portal_account() -> str:
	"""A signed-in account with no desk role: what sign-up gives anyone."""
	if not frappe.db.exists("User", PORTAL_ACCOUNT):
		user = frappe.new_doc("User")
		user.update(
			{
				"email": PORTAL_ACCOUNT,
				"first_name": "wiki feedback portal",
				"user_type": "Website User",
				"send_welcome_email": 0,
			}
		)
		user.insert(ignore_permissions=True)
	return PORTAL_ACCOUNT


class TestFeedbackGoesThroughItsEndpoint(IntegrationTestCase):
	def setUp(self):
		self.wiki = WikiFixtures()
		self.addCleanup(self.wiki.destroy_all)
		space = self.wiki.space(pages=[{"title": "Feedback page"}])
		self.document = frappe.get_value("Wiki Document", {"wiki_space": space.name, "is_group": 0})
		self.portal = make_portal_account()

	def test_a_visitor_or_a_portal_account_holds_no_right_on_the_collection(self):
		for user in ("Guest", self.portal):
			for ptype in ("create", "write", "delete"):
				self.assertFalse(
					frappe.has_permission(FEEDBACK, ptype, user=user),
					f"{user} may {ptype} any Wiki Feedback",
				)

	def test_a_visitor_still_leaves_feedback_through_the_page(self):
		with patch.object(wiki_feedback, "capture"), as_role("Guest"):
			submit_feedback(wiki_document=self.document, type="Good", feedback="Clear page")
		self.assertTrue(
			frappe.db.exists(FEEDBACK, {"wiki_document": self.document, "feedback": "Clear page"})
		)

	def test_a_portal_account_still_leaves_feedback_through_the_page(self):
		with patch.object(wiki_feedback, "capture"), as_role(self.portal):
			submit_feedback(wiki_document=self.document, type="Bad", feedback="Missing a step")
		self.assertTrue(
			frappe.db.exists(FEEDBACK, {"wiki_document": self.document, "feedback": "Missing a step"})
		)

	def test_a_direct_insert_by_a_visitor_is_refused(self):
		row = frappe.get_doc({"doctype": FEEDBACK, "wiki_document": self.document, "type": "Ok"})
		with patch.object(wiki_feedback, "capture"), as_role("Guest"):
			with self.assertRaises(frappe.PermissionError):
				row.insert()

	def test_the_patch_removes_the_frozen_copies_and_keeps_the_rest(self):
		from wiki.frappe_wiki.patches import feedback_goes_through_its_endpoint as the_patch

		for role, flags in (("All", {"write": 1, "create": 1}), ("Guest", {"write": 1, "create": 1})):
			if not frappe.db.exists("Custom DocPerm", {"parent": FEEDBACK, "role": role}):
				frappe.get_doc(
					{
						"doctype": "Custom DocPerm",
						"parent": FEEDBACK,
						"parenttype": "DocType",
						"parentfield": "permissions",
						"role": role,
						"permlevel": 0,
						**flags,
					}
				).insert(ignore_permissions=True)
		if not frappe.db.exists("Custom DocPerm", {"parent": FEEDBACK, "role": "System Manager"}):
			frappe.get_doc(
				{
					"doctype": "Custom DocPerm",
					"parent": FEEDBACK,
					"parenttype": "DocType",
					"parentfield": "permissions",
					"role": "System Manager",
					"permlevel": 0,
					"read": 1,
					"write": 1,
					"create": 1,
				}
			).insert(ignore_permissions=True)

		the_patch.execute()

		left = frappe.get_all("Custom DocPerm", filters={"parent": FEEDBACK}, pluck="role")
		self.assertNotIn("All", left)
		self.assertNotIn("Guest", left)
		self.assertIn("System Manager", left)
		frappe.clear_cache(doctype=FEEDBACK)  # the class's rollback puts the rows back
