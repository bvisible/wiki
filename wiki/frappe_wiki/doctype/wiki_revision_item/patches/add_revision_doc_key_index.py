"""Add a composite index on (revision, doc_key) for Wiki Revision Item.

The Change Request read path (get_cr_page / diff_change_request) looks up
revision items by {revision, doc_key}. Without an index on these columns every
lookup is a full table scan. On large wikis this child table grows to hundreds
of thousands of rows (revisions x documents), so each lookup takes tens of
seconds and the editor content panel never loads. add_index is idempotent.
"""

import frappe


def execute():
	frappe.db.add_index("Wiki Revision Item", ["revision", "doc_key"])
