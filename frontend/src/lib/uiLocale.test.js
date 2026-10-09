//// Neoffice — added file (no upstream equivalent): the editor's dates speak its author's language (maintenance#1383).
// Real dayjs and real locale data (the CommonJS builds: Node cannot load the extensionless ESM ones), the way
// frappe-ui formats a relative date and a chart's month tick.
import assert from 'node:assert/strict';
import test from 'node:test';

import dayjs from 'dayjs';
import de from 'dayjs/locale/de.js';
import fr from 'dayjs/locale/fr.js';
import it from 'dayjs/locale/it.js';
import relativeTime from 'dayjs/plugin/relativeTime.js';

import { applyUiLocale } from './uiLocale.js';

dayjs.extend(relativeTime);

const LOCALES = { de, fr, it };

// Made at each call, as the editor makes them at render time: a dayjs date keeps the locale it was born in.
function aDayAgo() {
	return dayjs('2026-10-08T12:00:00').from(dayjs('2026-10-09T12:00:00'));
}

test('a French author reads relative dates and month ticks in French', () => {
	const root = { lang: 'en' };
	assert.equal(applyUiLocale(dayjs, LOCALES, 'fr', root), 'fr');
	assert.equal(aDayAgo(), 'il y a un jour');
	assert.equal(dayjs('2026-10-09').format('MMM'), 'oct.');
	assert.equal(root.lang, 'fr');
});

test('a regional code reads in its language', () => {
	const root = { lang: 'en' };
	assert.equal(applyUiLocale(dayjs, LOCALES, 'de-CH', root), 'de');
	assert.equal(aDayAgo(), 'vor einem Tag');
	assert.equal(root.lang, 'de-CH');
});

test('a language without locale data reads English, and the page still declares it', () => {
	applyUiLocale(dayjs, LOCALES, 'fr', { lang: 'en' });
	const root = { lang: 'en' };
	assert.equal(applyUiLocale(dayjs, LOCALES, 'pt-BR', root), 'en');
	assert.equal(aDayAgo(), 'a day ago');
	assert.equal(root.lang, 'pt-BR');
});

test('no language at all leaves dayjs in English and the page as it was', () => {
	applyUiLocale(dayjs, LOCALES, 'it', { lang: 'en' });
	const root = { lang: 'en' };
	assert.equal(applyUiLocale(dayjs, LOCALES, null, root), 'en');
	assert.equal(aDayAgo(), 'a day ago');
	assert.equal(root.lang, 'en');
});
