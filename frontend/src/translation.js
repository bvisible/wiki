import { createResource } from 'frappe-ui';

export default function translationPlugin(app) {
	app.config.globalProperties.__ = translate;
	window.__ = translate;
	if (!window.translatedMessages) fetchTranslations();
}

//// Neoffice — added. translate() reads window.translatedMessages at render
//// time and is not reactive, so whatever renders before the fetch above lands
//// stays in English forever: the whole first screen. Awaiting this in main.js
//// before app.mount() costs one round-trip and makes the UI actually
//// translated. Resolves (never rejects) so a failed fetch degrades to English
//// instead of a blank page.
export function translationsReady() {
	if (window.translatedMessages) return Promise.resolve();
	return fetchTranslations()
		.promise.catch(() => {})
		.then(() => undefined);
}

function format(message, replace) {
	return message.replace(/{(\d+)}/g, (match, number) =>
		typeof replace[number] !== 'undefined' ? replace[number] : match,
	);
}

function translate(message, replace, context = null) {
	const translatedMessages = window.translatedMessages || {};
	let translatedMessage = '';

	if (context) {
		const key = `${message}:${context}`;
		if (translatedMessages[key]) {
			translatedMessage = translatedMessages[key];
		}
	}

	if (!translatedMessage) {
		translatedMessage = translatedMessages[message] || message;
	}

	const hasPlaceholders = /{\d+}/.test(message);
	if (!hasPlaceholders) {
		return translatedMessage;
	}

	return format(translatedMessage, replace);
}

function fetchTranslations() {
	//// Neoffice — returns the resource (upstream discarded it) so
	//// translationsReady() can await the in-flight fetch instead of firing a
	//// second one.
	return createResource({
		url: 'wiki.api.get_translations',
		auto: true,
		transform: (data) => {
			window.translatedMessages = data;
		},
	});
}
