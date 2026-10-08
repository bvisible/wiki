# //// Neoffice — added file (no upstream equivalent): the public reader's tab icon (maintenance#1316).
"""A wiki space without a favicon of its own shows Neoffice's mark in the browser tab, the desk's own icon, not
Frappe Wiki's: the public manual is read by every customer, and its tab said Frappe."""

import os
import re
import unittest

TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "wiki", "document.html")
NEOFFICE_ICON = "/assets/neoffice_theme/images/neoffice_icon.png"


class TestReaderFavicon(unittest.TestCase):
	def test_a_space_without_a_favicon_shows_neoffices_mark(self):
		with open(TEMPLATE, encoding="utf-8") as f:
			source = f.read()
		links = re.findall(r'<link rel="icon" href="\{\{ favicon or \'([^\']+)\' \}\}">', source)
		self.assertEqual(links, [NEOFFICE_ICON])
		self.assertNotIn("/assets/wiki/favicon.png", source)
