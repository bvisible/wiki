/**
 * Markdown serialization for the image node.
 *
 * Split out of image-extension.js so it can be unit tested: that module
 * imports a .vue node view at the top level, which `node --test` cannot load.
 */
export function renderImageMarkdown(node) {
	// Skip images still uploading/optimizing, or whose upload failed — their
	// `src` is a transient base64 preview that must never be written to saved
	// content. Once the upload resolves, `loading` clears and the node
	// re-serializes normally.
	if (node.attrs?.loading || node.attrs?.error) {
		return '';
	}

	const src = node.attrs?.src ?? '';
	const alt = node.attrs?.alt ?? '';
	const title = node.attrs?.title ?? '';
	const caption = (node.attrs?.caption ?? '').trim();

	//// Neoffice — an image with a width or a class is written as an <img> tag. The editor's
	//// size buttons set `width`, and a hand-written <img class="img-md"> carries a class, but
	//// the markdown image syntax has no place for either, so both were dropped at the first
	//// save (neoffice-maintenance#1085). The reader's markdown-it passes raw HTML through. The
	//// caption follows as <em>: a `*caption*` line right under an HTML block belongs to that
	//// block and would be shown with its asterisks. To remove if upstream's image node saves
	//// its width itself.
	const width = imageWidth(node.attrs?.width);
	const className = String(node.attrs?.className ?? '').trim();
	if (width || className) {
		let tag = `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}"`;
		if (title) tag += ` title="${escapeHtml(title)}"`;
		if (width) tag += ` width="${width}"`;
		if (className) tag += ` class="${escapeHtml(className)}"`;
		tag += '>';
		return caption ? `${tag}\n<em>${escapeHtml(caption)}</em>` : tag;
	}

	let md = title ? `![${alt}](${src} "${title}")` : `![${alt}](${src})`;

	// Add caption on next line (no blank line) if present
	if (caption) {
		md += `\n*${caption}*`;
	}

	return md;
}

//// Neoffice — everything below is ours: reading and writing an image as an <img> tag
//// (neoffice-maintenance#1085), so that its width and its class survive a save. Added code,
//// no upstream equivalent.

// A whole <img> tag, attributes included. A quoted value may hold a `>`.
const IMG_TAG = /<img(?=[\s/>])((?:[^>"']|"[^"]*"|'[^']*')*)>/i;
const IMG_TAG_AT_START = new RegExp(`^${IMG_TAG.source}`, 'i');
// An <img> tag alone on a line, after a newline: where a paragraph must stop for it.
const IMG_TAG_LINE = new RegExp(`\\n(${IMG_TAG.source}[ \\t]*(?:\\n|$))`, 'i');
// The caption under an <img> tag: <em>…</em> as we write it, or *…* as the markdown form has it.
const CAPTION_UNDER_TAG =
	/^[ \t]*\n(?:<em>([^<\n]+)<\/em>|\*([^*\n]+)\*)[ \t]*(?=\n|$)/;

const NAMED_ENTITIES = {
	amp: '&',
	lt: '<',
	gt: '>',
	quot: '"',
	apos: "'",
};

export function escapeHtml(text) {
	return String(text)
		.replace(/&/g, '&amp;')
		.replace(/"/g, '&quot;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;');
}

export function unescapeHtml(text) {
	return String(text).replace(
		/&(#\d+|#x[0-9a-f]+|[a-z]+);/gi,
		(whole, entity) => {
			if (entity[0] === '#') {
				const code =
					entity[1].toLowerCase() === 'x'
						? Number.parseInt(entity.slice(2), 16)
						: Number.parseInt(entity.slice(1), 10);
				return code > 0 && code <= 0x10ffff
					? String.fromCodePoint(code)
					: whole;
			}
			return NAMED_ENTITIES[entity.toLowerCase()] ?? whole;
		},
	);
}

/** The width in pixels of an image, from a number or from `480` / `480px`; null for anything else (`50%`, `auto`). */
export function imageWidth(value) {
	const text = String(value ?? '').trim();
	if (!/^\d+(px)?$/i.test(text)) return null;
	const pixels = Number.parseInt(text, 10);
	return pixels > 0 ? pixels : null;
}

/**
 * The classes of an image without its size class (`img-xs`, `img-sm`, `img-md`, `img-lg`, `img-full`): a size
 * chosen with the editor's buttons replaces it, otherwise the reader's CSS for the class would win over the
 * width. The other classes (`img-center`, `img-shadow`…) stay. Null when nothing is left.
 */
export function withoutImageSizeClass(className) {
	const kept = String(className ?? '')
		.split(/\s+/)
		.filter((name) => name && !/^img-(?:xs|sm|md|lg|full)$/i.test(name));
	return kept.length ? kept.join(' ') : null;
}

function parseTagAttributes(text) {
	const attributes = Object.create(null);
	const pattern =
		/([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
	for (const match of text.matchAll(pattern)) {
		const name = match[1].toLowerCase();
		// like a browser, the first one of a name wins
		if (!(name in attributes)) {
			attributes[name] = unescapeHtml(match[2] ?? match[3] ?? match[4] ?? '');
		}
	}
	return attributes;
}

/**
 * Where an <img> tag standing alone on its line starts in `src`, or -1. A block tokenizer's `start`: it tells
 * marked where a paragraph has to stop. A tag in the middle of a line stays inline.
 */
export function imageHtmlStart(src) {
	const match = IMG_TAG_LINE.exec(src);
	return match ? match.index + 1 : -1;
}

/**
 * A marked block token for an <img> tag that opens `src` and stands alone on its line, with the caption on the
 * next line if there is one; undefined for anything else (a tag followed by text, a tag with no `src`).
 * Reads `src`, `alt`, `title`, `width` and `class`; the other attributes are not kept.
 */
export function tokenizeImageHtml(src) {
	const tag = IMG_TAG_AT_START.exec(src);
	if (!tag) return undefined;
	if (!/^[ \t]*(?:\n|$)/.test(src.slice(tag[0].length))) return undefined;
	const attributes = parseTagAttributes(tag[1]);
	if (!attributes.src || !attributes.src.trim()) return undefined;

	let raw = tag[0];
	let caption = null;
	const captionMatch = CAPTION_UNDER_TAG.exec(src.slice(raw.length));
	if (captionMatch) {
		raw += captionMatch[0];
		caption = unescapeHtml(captionMatch[1] ?? captionMatch[2]);
	}

	return {
		type: 'wikiImage',
		raw,
		text: attributes.alt ?? '',
		href: attributes.src.trim(),
		title: attributes.title || null,
		caption,
		width: imageWidth(attributes.width),
		className: (attributes.class ?? '').trim() || null,
	};
}

/** The attributes of the image node for a `wikiImage` token, from the markdown syntax or from an <img> tag. */
export function imageNodeAttrs(token) {
	return {
		src: token.href,
		title: token.title,
		alt: token.text,
		caption: token.caption || null,
		width: token.width ?? null,
		className: token.className ?? null,
	};
}
