# //// Neoffice — added file (no upstream equivalent). The settings dialog is mounted for a wiki manager only
# //// (maintenance#1096): mounted for everyone, as upstream does, it read « Wiki Settings » at every opening of
# //// /wiki-app, which a Wiki User may not read, so every page load raised a PermissionError.
import re
import unittest
from pathlib import Path

LAYOUT = Path(__file__).resolve().parent.parent / "frontend" / "src" / "layouts" / "MainLayout.vue"


class TestTheSettingsDialogIsForManagers(unittest.TestCase):
	def test_the_layout_mounts_it_for_a_wiki_manager_only(self):
		tags = re.findall(r"<WikiSettings\b[^>]*>", LAYOUT.read_text(encoding="utf-8"))
		self.assertEqual(len(tags), 1, tags)
		self.assertIn('v-if="userStore.isWikiManager"', tags[0])
