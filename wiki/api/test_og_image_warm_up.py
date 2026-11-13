# //// Neoffice — added file (no upstream equivalent)
"""No card is warmed on a Frappe without any card renderer.

Each warm-up rendered anyway, raised, and logged "Wiki OG image generation
failed": ten instances, every night (2026-09-13). Since 3.5.0 upstream draws
the card with satori (Node) where Frappe v15 has no headless Chromium, so "no
renderer" now means neither of the two.
"""

import unittest
from unittest import mock

from wiki.api import og_image


class TestWarmUpWithoutRenderer(unittest.TestCase):
	def test_nothing_is_rendered_without_the_renderer(self):
		with (
			mock.patch.object(og_image, "get_preview_from_html", None),
			mock.patch.object(og_image.og_satori, "available", return_value=False),
			mock.patch.object(og_image.frappe, "get_cached_value", return_value=1),
			mock.patch.object(og_image, "_generate_and_store") as generate,
			mock.patch.object(og_image.frappe, "get_cached_doc") as get_doc,
		):
			og_image.warm_og_image("any-document")
		generate.assert_not_called()
		get_doc.assert_not_called()
