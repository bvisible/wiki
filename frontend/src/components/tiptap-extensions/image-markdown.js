/**
 * Markdown tokenizer and serializer for the image node.
 *
 * Split out of image-extension.js so it can be unit tested: that module
 * imports a .vue node view at the top level, which `node --test` cannot load.
 */
import { isPdfUrl, isVideoUrl } from './media-urls.js';

// The URL allows spaces and one level of balanced parens so Frappe filenames
// like `/files/CleanShot 2026-05-27 at 00.06.09@2x.png` or
// `/files/image (24).png` survive (otherwise spaces / inner `)` break it).
// The URL group is non-greedy so a trailing quoted title is still split off
// instead of being absorbed into the src.
const IMAGE_PATTERN =
	/^!\[([^\]]*)\]\(((?:[^()"]|\([^()"]*\))+?)(?:\s+"([^"]*)")?\)/;
const PICTURE_PATTERN = /^<picture>\s*([\s\S]*?)\s*<\/picture>/;
const CAPTION_PATTERN = /^\n\*([^*]+)\*/;
const DARK_MEDIA = '(prefers-color-scheme: dark)';
const ALIGNMENTS = ['left', 'center', 'right'];

/**
 * Custom marked tokenizer for an image followed by an optional caption line.
 *
 *   ![alt](src "title")
 *   *caption*
 *
 * or, when the image has a dark mode version (GitBook's Git Sync format):
 *
 *   <picture>
 *     <source srcset="dark.png" media="(prefers-color-scheme: dark)">
 *     <img src="light.png" alt="alt">
 *   </picture>
 *   *caption*
 */
export const imageCaptionTokenizer = {
	name: 'wikiImage',
	level: 'block',

	start(src) {
		const indexes = [
			src.indexOf('!['),
			src.indexOf('<picture>'),
			//// Neoffice — an <img> tag alone on its line starts an image block too (#1085).
			imageHtmlStart(src),
		].filter((index) => index !== -1);
		return indexes.length ? Math.min(...indexes) : -1;
	},

	tokenize(src) {
		const image = matchPicture(src) ?? matchImage(src);
		//// Neoffice — an image written as an <img> tag (a class, a width), see the end of this
		//// file (#1085). A video or a PDF is left to its own block, as for the markdown syntax.
		if (!image) {
			const htmlToken = tokenizeImageHtml(src);
			if (!htmlToken || isVideoUrl(htmlToken.href) || isPdfUrl(htmlToken.href)) {
				return undefined;
			}
			return htmlToken;
		}

		const captionMatch = CAPTION_PATTERN.exec(src.slice(image.raw.length));
		return {
			type: 'wikiImage',
			...image,
			raw: image.raw + (captionMatch?.[0] ?? ''),
			caption: captionMatch?.[1] ?? null,
		};
	},
};

function matchImage(src) {
	const match = IMAGE_PATTERN.exec(src);
	if (!match) return null;

	const [raw, alt, hrefRaw, title] = match;
	const href = (hrefRaw || '').trim();
	if (isVideoUrl(href) || isPdfUrl(href)) return null;

	return {
		raw,
		text: alt || '',
		href,
		title: title || null,
		darkSrc: null,
		width: null,
		align: null,
	};
}

// Only the exact shape we write is claimed, so a <picture> with sources we do
// not model is never silently reduced to one light and one dark image.
function matchPicture(src) {
	const match = PICTURE_PATTERN.exec(src);
	if (!match) return null;

	const tags = match[1].split(/>\s*/).filter(Boolean);
	if (tags.length > 2) return null;

	const img = parseTag(tags.at(-1), 'img');
	const source = tags.length === 2 ? parseTag(tags[0], 'source') : {};
	if (!img?.src || !source) return null;
	if (tags.length === 2 && (!source.srcset || source.media !== DARK_MEDIA)) {
		return null;
	}

	return {
		raw: match[0],
		text: img.alt ?? '',
		href: img.src,
		title: img.title ?? null,
		darkSrc: source.srcset ?? null,
		width: Number(img.width) || null,
		align: ALIGNMENTS.includes(img['data-align']) ? img['data-align'] : null,
	};
}

function parseTag(tag, name) {
	const match = new RegExp(`^<${name}((?:\\s+[a-z-]+="[^"]*")*)\\s*/?$`).exec(
		tag,
	);
	if (!match) return null;

	const attributes = {};
	for (const [, key, value] of match[1].matchAll(/([a-z-]+)="([^"]*)"/g)) {
		attributes[key] = unescapeAttribute(value);
	}
	return attributes;
}

export function renderImageMarkdown(node) {
	// Skip images still uploading/optimizing, or whose upload failed — their
	// `src` is a transient base64 preview that must never be written to saved
	// content. Once the upload resolves, `loading` clears and the node
	// re-serializes normally.
	if (node.attrs?.loading || node.attrs?.error) {
		return '';
	}

	const src = node.attrs?.src ?? '';
	const darkSrc = node.attrs?.darkSrc ?? '';
	const alt = node.attrs?.alt ?? '';
	const title = node.attrs?.title ?? '';
	const caption = (node.attrs?.caption ?? '').trim();
	//// Neoffice — imageWidth(): a width in pixels or nothing (upstream: the raw attribute). A
	//// pasted <img width="50%"> reached renderPicture, which wrote width="NaN".
	const width = imageWidth(node.attrs?.width);
	const align = node.attrs?.align === 'center' ? null : node.attrs?.align;

	//// Neoffice — an image that carries a class (a hand-written <img class="img-md">, img-center,
	//// img-shadow…) is written back as an <img> tag with that class, its caption under it as <em>
	//// (neoffice-maintenance#1085): upstream's node has no class, so the class was dropped at the
	//// first save, and the <picture> form cannot carry it (the reader's PICTURE_BLOCK_PATTERN in
	//// wiki/wiki/markdown.py matches the exact attributes upstream writes, a class breaks the
	//// caption). A width set in the editor drops a size class first (ImageNodeView, sizedWidth).
	//// A dark version or an alignment takes upstream's <picture> form, class left out.
	const className = String(node.attrs?.className ?? '').trim() || null;
	if (className && !darkSrc && !align) {
		return renderImageTag({ src, alt, title, width, className, caption });
	}

	let md = `![${alt}](${src})`;
	if (darkSrc || width || align) {
		md = renderPicture({ src, darkSrc, alt, title, width, align });
	} else if (title) {
		md = `![${alt}](${src} "${title}")`;
	}

	// Add caption on next line (no blank line) if present
	if (caption) {
		md += `\n*${caption}*`;
	}

	return md;
}

function renderPicture({ src, darkSrc, alt, title, width, align }) {
	let imgAttributes = `src="${escapeAttribute(src)}" alt="${escapeAttribute(
		alt,
	)}"`;
	if (title) imgAttributes += ` title="${escapeAttribute(title)}"`;
	if (width) imgAttributes += ` width="${Math.round(width)}"`;
	if (align) imgAttributes += ` data-align="${escapeAttribute(align)}"`;

	const lines = ['<picture>'];
	if (darkSrc) {
		// srcset splits candidates on commas and descriptors on spaces, so both
		// must be percent-encoded or a Frappe filename with either would not load.
		const srcset = darkSrc.replaceAll(' ', '%20').replaceAll(',', '%2C');
		lines.push(
			`  <source srcset="${escapeAttribute(srcset)}" media="${DARK_MEDIA}">`,
		);
	}
	lines.push(`  <img ${imgAttributes}>`, '</picture>');
	return lines.join('\n');
}

function escapeAttribute(value) {
	return value
		.replaceAll('&', '&amp;')
		.replaceAll('"', '&quot;')
		.replaceAll('<', '&lt;')
		.replaceAll('>', '&gt;');
}

function unescapeAttribute(value) {
	return value
		.replaceAll('&quot;', '"')
		.replaceAll('&#39;', "'")
		.replaceAll('&lt;', '<')
		.replaceAll('&gt;', '>')
		.replaceAll('&amp;', '&');
}

//// Neoffice — everything below is ours: reading and writing an image as an <img> tag
//// (neoffice-maintenance#1085), so that its class survives a save. Added code, no upstream
//// equivalent. Upstream's own form for a width, an alignment or a dark version is the
//// <picture> block above; the <img> tags written before the 3.5.0 merge (a width alone) are
//// still read here, and written back as <picture>.

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
		// upstream's token fields (see matchPicture): an <img> tag has no dark version
		darkSrc: null,
		align: ALIGNMENTS.includes(attributes['data-align'])
			? attributes['data-align']
			: null,
	};
}

/** The attributes of the image node for a `wikiImage` token: upstream's, plus the class of an <img> tag. */
export function imageNodeAttrs(token) {
	return {
		src: token.href,
		darkSrc: token.darkSrc || null,
		title: token.title,
		alt: token.text,
		caption: token.caption || null,
		width: token.width || null,
		align: token.align || null,
		className: token.className ?? null,
	};
}

/** An image with a class, as an <img> tag; its caption on the next line as <em> (under an HTML block a `*caption*` line belongs to the block and would be shown with its asterisks). */
function renderImageTag({ src, alt, title, width, className, caption }) {
	const pixels = imageWidth(width);
	let tag = `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}"`;
	if (title) tag += ` title="${escapeHtml(title)}"`;
	if (pixels) tag += ` width="${pixels}"`;
	tag += ` class="${escapeHtml(className)}">`;
	return caption ? `${tag}\n<em>${escapeHtml(caption)}</em>` : tag;
}
