# //// Neoffice — added file (no upstream equivalent): the editor's empty charts speak the catalogue (maintenance#1383).
"""frappe-ui writes « No data to show » in English inside its chart container, out of the catalogue's reach. Each
chart of the editor replaces it through the chart's `#empty` slot with a translatable text, and the French
catalogue translates it. A chart added without the slot, or an upstream merge that drops one, shows English
again: this says which."""

import os
import re
import unittest

MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(os.path.dirname(MODULE), "frontend", "src")
CATALOGUE = os.path.join(MODULE, "locale", "fr.po")
CHART = re.compile(
	r"<(AreaChart|BarChart|LineChart|DonutChart|ScatterChart|HeatmapChart|FunnelChart|SankeyChart)\b"
)
EMPTY_SLOT = re.compile(r"<template #empty>.*?\{\{ __\('No data to show'\) \}\}.*?</template>", re.S)


def _charts(source: str):
	"""(name, children) of each chart element; a self-closing one has no children, so no slot."""
	for match in CHART.finditer(source):
		name, i, quote = match.group(1), match.end(), None
		while True:  # the end of the opening tag, outside the quoted attribute values
			c = source[i]
			if quote:
				quote = None if c == quote else quote
			elif c in "\"'":
				quote = c
			elif c == ">":
				break
			i += 1
		if source[i - 1] == "/":
			yield name, ""
		else:
			yield name, source[i + 1 : source.index(f"</{name}>", i)]


def _editor_charts():
	for folder, _dirs, files in os.walk(SOURCES):
		for file in files:
			if file.endswith(".vue"):
				path = os.path.join(folder, file)
				with open(path, encoding="utf-8") as f:
					for name, children in _charts(f.read()):
						yield os.path.relpath(path, SOURCES), name, children


class TestEditorChartEmptyState(unittest.TestCase):
	def test_every_chart_of_the_editor_says_its_empty_state_through_the_catalogue(self):
		charts = list(_editor_charts())
		# The overview's donut and area charts and the analytics bar chart, at least.
		self.assertGreaterEqual(len(charts), 3)
		untranslated = [
			f"{path}: {name}" for path, name, children in charts if not EMPTY_SLOT.search(children)
		]
		self.assertEqual(untranslated, [])

	def test_the_french_catalogue_translates_it(self):
		with open(CATALOGUE, encoding="utf-8") as f:
			entry = re.search(r'^msgid "No data to show"\nmsgstr "(.*)"$', f.read(), re.M)
		self.assertIsNotNone(entry, "fr.po has no entry for « No data to show »")
		self.assertNotEqual(entry.group(1), "")
