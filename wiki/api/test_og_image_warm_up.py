# //// Neoffice — added file (no upstream equivalent)
"""No card is warmed on a Frappe without the headless renderer (v15).

Each warm-up rendered anyway, raised, and logged "Wiki OG image generation
failed": ten instances, every night (2026-09-13).
"""

import unittest
from unittest import mock

from wiki.api import og_image


class TestWarmUpWithoutRenderer(unittest.TestCase):
	def test_nothing_is_rendered_without_the_renderer(self):
		with (
			mock.patch.object(og_image, "get_preview_from_html", None),
			mock.patch.object(og_image, "_cards_enabled", return_value=True),
			mock.patch.object(og_image, "_generate_and_store") as generate,
			mock.patch.object(og_image.frappe, "get_cached_doc") as get_doc,
		):
			og_image.warm_og_image("any-document")
		generate.assert_not_called()
		get_doc.assert_not_called()
