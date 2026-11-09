import { Node, mergeAttributes, nodeInputRule } from '@tiptap/core';
import { VueNodeViewRenderer } from '@tiptap/vue-3';
import ImageNodeView from './ImageNodeView.vue';
//// Neoffice — the <img> tag helpers of image-markdown.js: a width, a class (#1085)
import {
	imageHtmlStart,
	imageNodeAttrs,
	renderImageMarkdown,
	tokenizeImageHtml,
} from './image-markdown.js';
import { isPdfUrl } from './pdf-block.js';
import { isVideoUrl } from './video-block.js';

// Markdown image regex: ![alt](src "title")
// The src allows spaces and one level of balanced parens so Frappe filenames
// like `/files/CleanShot 2026-05-27 at 00.06.09@2x.png` or `/files/image (24).png`
// round-trip correctly. The src group is non-greedy so the optional title
// (quoted, whitespace-separated) is still split off rather than swallowed.
const inputRegex =
	/(?:^|\s)(!\[([^\]]*)]\(((?:[^()"]|\([^()"]*\))+?)(?:\s+["']([^"']+)["'])?\))$/;

/**
 * Custom Image extension with caption support
 *
 * Captions use the Stack Overflow pattern in markdown:
 *   ![alt text](image.jpg)
 *   *caption text*
 *
 * - alt: For accessibility (screen readers)
 * - caption: Visible caption text below the image
 */

/**
 * Custom marked tokenizer that matches image followed by caption on next line.
 * Pattern: ![alt](src "title")\n*caption*
 */
const imageCaptionTokenizer = {
	name: 'wikiImage',
	level: 'block',

	start(src) {
		//// Neoffice — an <img> tag alone on its line starts an image block too (#1085).
		const markdown = src.indexOf('![');
		const html = imageHtmlStart(src);
		if (html < 0) return markdown;
		return markdown < 0 ? html : Math.min(markdown, html);
	},

	tokenize(src, tokens, lexer) {
		//// Neoffice — an image written as an <img> tag (a width, a class), see image-markdown.js
		//// (#1085). A video or a PDF is left to its own block, as for the markdown syntax.
		const htmlToken = tokenizeImageHtml(src);
		if (htmlToken) {
			return isVideoUrl(htmlToken.href) || isPdfUrl(htmlToken.href)
				? undefined
				: htmlToken;
		}

		// Match: ![alt](src) or ![alt](src "title") optionally followed by \n*caption*
		// The URL allows spaces and one level of balanced parens so Frappe
		// filenames like `/files/CleanShot 2026-05-27 at 00.06.09@2x.png` or
		// `/files/image (24).png` survive (otherwise spaces / inner `)` break it).
		// The URL group is non-greedy so a trailing quoted title is still split
		// off instead of being absorbed into the src.
		const imagePattern =
			/^!\[([^\]]*)\]\(((?:[^()"]|\([^()"]*\))+?)(?:\s+"([^"]*)")?\)/;
		const captionPattern = /^\n\*([^*]+)\*/;

		const imageMatch = imagePattern.exec(src);
		if (!imageMatch) {
			return undefined;
		}

		const [imageRaw, alt, hrefRaw, title] = imageMatch;
		const href = (hrefRaw || '').trim();
		if (isVideoUrl(href) || isPdfUrl(href)) {
			return undefined;
		}
		let caption = null;
		let raw = imageRaw;

		// Check for caption on next line
		const remaining = src.slice(imageRaw.length);
		const captionMatch = captionPattern.exec(remaining);
		if (captionMatch) {
			caption = captionMatch[1];
			raw += captionMatch[0];
		}

		return {
			type: 'wikiImage',
			raw,
			text: alt || '',
			href: href || '',
			title: title || null,
			caption: caption,
		};
	},
};

export const WikiImage = Node.create({
	name: 'image',

	group: 'block',

	draggable: true,

	addOptions() {
		return {
			inline: false,
			allowBase64: true,
			HTMLAttributes: {},
		};
	},

	addAttributes() {
		return {
			src: {
				default: null,
			},
			alt: {
				default: null,
			},
			title: {
				default: null,
			},
			caption: {
				default: null,
			},
			width: {
				default: null,
			},
			height: {
				default: null,
			},
			//// Neoffice — the class of an image written as an <img> tag (img-md, img-center…),
			//// kept so that it survives a save (#1085). Not read from pasted HTML: a page
			//// copied from the web carries classes of its own.
			className: {
				default: null,
				rendered: false,
			},
			// Transient editor-only state for the upload/optimization lifecycle.
			// `rendered: false` keeps these out of the serialized HTML, and
			// renderMarkdown ignores them, so they never persist to content.
			loading: {
				default: false,
				rendered: false,
			},
			uploadId: {
				default: null,
				rendered: false,
			},
			error: {
				default: null,
				rendered: false,
			},
		};
	},

	parseHTML() {
		return [
			{
				tag: 'img[src]',
			},
		];
	},

	renderHTML({ HTMLAttributes }) {
		return [
			'img',
			mergeAttributes(this.options.HTMLAttributes, HTMLAttributes),
		];
	},

	// Custom tokenizer for marked.js to capture image + caption pattern
	markdownTokenizer: imageCaptionTokenizer,

	// Token name must match the tokenizer's type
	markdownTokenName: 'wikiImage',

	// Parse markdown image with optional caption
	parseMarkdown: (token, helpers) => {
		//// Neoffice — imageNodeAttrs adds the width and the class of an <img> tag (#1085).
		return helpers.createNode('image', imageNodeAttrs(token));
	},

	// Render to markdown using Stack Overflow caption pattern:
	// ![alt](src "title")
	// *caption*
	renderMarkdown: renderImageMarkdown,

	addNodeView() {
		return VueNodeViewRenderer(ImageNodeView);
	},

	addCommands() {
		return {
			setImage:
				(options) =>
				({ commands }) => {
					return commands.insertContent({
						type: this.name,
						attrs: options,
					});
				},
		};
	},

	addInputRules() {
		return [
			nodeInputRule({
				find: inputRegex,
				type: this.type,
				getAttributes: (match) => {
					const [, , alt, src, title] = match;
					return { src, alt, title };
				},
			}),
		];
	},
});

export default WikiImage;
