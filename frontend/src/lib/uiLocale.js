//// Neoffice — added file (no upstream equivalent): the language the editor prints dates and numbers in
//// (maintenance#1383). frappe-ui writes every date through dayjs, a relative date (`fromNow()`) as well as a
//// chart's month tick (`MMM`), and reads <html lang> for a chart's numbers. The editor set neither, so a French
//// author read « a day ago » and « Oct ». main.js calls this once, before mounting, with the language of the
//// boot (wiki/www/wiki_app.py), the one the label catalogue is picked by.

/**
 * Puts dayjs in `lang`'s language when `locales` holds its data (`fr-CH` reads `fr`), in English otherwise,
 * and declares `lang` on `root`, the page's <html>. No language leaves `root` as it was. Returns the name of
 * the dayjs locale now in force.
 */
export function applyUiLocale(dayjs, locales, lang, root) {
	const code = String(lang || '')
		.toLowerCase()
		.split(/[-_]/)[0];
	const locale = Object.prototype.hasOwnProperty.call(locales, code)
		? locales[code]
		: null;
	dayjs.locale(locale || 'en');
	if (lang && root) root.lang = lang;
	return locale ? locale.name : 'en';
}
