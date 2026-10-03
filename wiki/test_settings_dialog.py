# //// Neoffice — added file (no upstream equivalent). The settings dialog is mounted for a wiki manager only
# //// (maintenance#1096): mounted for everyone, as upstream does, it read « Wiki Settings » at every opening of
# //// /wiki-app, which a Wiki User may not read, so every page load raised a PermissionError.
import re
import unittest
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "src"
LAYOUT = FRONTEND / "layouts" / "MainLayout.vue"
COCKPIT = FRONTEND / "components" / "NeoCockpitWikiSidebar.vue"


class TestTheSettingsDialogIsForManagers(unittest.TestCase):
	def test_the_layout_mounts_it_for_a_wiki_manager_only(self):
		tags = re.findall(r"<WikiSettings\b[^>]*>", LAYOUT.read_text(encoding="utf-8"))
		self.assertEqual(len(tags), 1, tags)
		self.assertIn('v-if="userStore.isWikiManager"', tags[0])

	def test_a_manager_opens_it_from_the_cockpit(self):
		# Under the cockpit the app's own sidebar, which held « Settings », is replaced: on a desktop a manager had no
		# way left to open the dialog (maintenance#1096). The cockpit's menu offers it to a manager, and to no one else.
		source = COCKPIT.read_text(encoding="utf-8")
		gated = re.search(r"if \(userStore\.isWikiManager\) \{(.*?)\n\t\}", source, re.S)
		self.assertTrue(gated, "no manager-only entry in the cockpit's menu")
		self.assertIn("openWikiSettings()", gated.group(1))
		self.assertEqual(source.count("openWikiSettings()"), 1)
