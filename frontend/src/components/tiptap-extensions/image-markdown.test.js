//// Neoffice — added file (no upstream equivalent)
import assert from 'node:assert/strict';
import test from 'node:test';

import { Node } from '@tiptap/core';
import { MarkdownManager } from '@tiptap/markdown';

import {
	imageHtmlStart,
	imageNodeAttrs,
	imageWidth,
	renderImageMarkdown,
	tokenizeImageHtml,
	withoutImageSizeClass,
} from './image-markdown.js';
import { PreserveBlankLines } from './preserve-blank-lines.js';
import { wikiStarterKit } from './wiki-starterkit.js';

// The editor's own markdown parser is `marked-tiptap` (wiki-markdown.js); plain `marked` follows the same CommonMark rules.
const { Marked } = await import('marked-tiptap').catch(() => import('marked'));

/**
 * Regression coverage for the width and the class of an image (neoffice-maintenance#1085).
 *
 * The editor's S / M / L / XL buttons set `width`, and a hand-written `<img class="img-md">`
 * carries a class, but the image node was written as `![alt](src)`: both were lost at the first
 * save. An image with a width or a class is now written as an `<img>` tag, and read back from one.
 *
 * The node view lives in image-extension.js, which imports a .vue file that `node --test`
 * cannot load. The markdown hooks are in image-markdown.js for exactly this reason, and the
 * schema-only node below carries the real ones.
 */
const ImageSchemaOnly = Node.create({
	name: 'image',
	group: 'block',
	addAttributes() {
		return {
			src: { default: null },
			alt: { default: null },
			title: { default: null },
			caption: { default: null },
			width: { default: null },
			height: { default: null },
			className: { default: null, rendered: false },
		};
	},
	renderHTML({ HTMLAttributes }) {
		return ['img', HTMLAttributes];
	},
	markdownTokenizer: {
		name: 'wikiImage',
		level: 'block',
		// image-extension.js composes the same two: the <img> tag first, then the markdown syntax
		start(src) {
			const markdown = src.indexOf('![');
			const html = imageHtmlStart(src);
			if (html < 0) return markdown;
			return markdown < 0 ? html : Math.min(markdown, html);
		},
		tokenize(src) {
			const htmlToken = tokenizeImageHtml(src);
			if (htmlToken) return htmlToken;
			// the markdown syntax, as image-extension.js tokenizes it (upstream's code, copied)
			const imageMatch =
				/^!\[([^\]]*)\]\(((?:[^()"]|\([^()"]*\))+?)(?:\s+"([^"]*)")?\)/.exec(
					src,
				);
			if (!imageMatch) return undefined;
			const [imageRaw, alt, href, title] = imageMatch;
			const captionMatch = /^\n\*([^*]+)\*/.exec(src.slice(imageRaw.length));
			return {
				type: 'wikiImage',
				raw: imageRaw + (captionMatch ? captionMatch[0] : ''),
				text: alt || '',
				href: (href || '').trim(),
				title: title || null,
				caption: captionMatch ? captionMatch[1] : null,
			};
		},
	},
	markdownTokenName: 'wikiImage',
	parseMarkdown: (token, helpers) =>
		helpers.createNode('image', imageNodeAttrs(token)),
	renderMarkdown: renderImageMarkdown,
});

function buildManager() {
	const starterKit = wikiStarterKit();
	const baseExtensions = starterKit.config.addExtensions.call({
		options: starterKit.options,
		name: 'starterKit',
	});
	return new MarkdownManager({
		extensions: [
			...baseExtensions.filter((extension) => extension.name !== 'image'),
			PreserveBlankLines,
			ImageSchemaOnly,
		],
		markedOptions: { breaks: true },
	});
}

/** Serialize -> parse -> serialize, `passes` times, collecting each output. */
function roundTrip(manager, source, passes = 3) {
	const outputs = [];
	let current = source;
	for (let i = 0; i < passes; i++) {
		current = manager.serialize(manager.parse(current));
		outputs.push(current);
	}
	return outputs;
}

function imageNodes(json) {
	return json.content.filter((node) => node.type === 'image');
}

const node = (attrs) => ({ attrs });

test('a width set with the size buttons is written in the page', () => {
	// Before: `![x](/files/a.png)`, the width never left the editing session.
	const md = renderImageMarkdown(
		node({ src: '/files/a.png', alt: 'x', width: 480 }),
	);
	assert.equal(md, '<img src="/files/a.png" alt="x" width="480">');
});

test('a class is kept, with or without a width', () => {
	assert.equal(
		renderImageMarkdown(
			node({ src: '/files/a.png', alt: 'x', className: 'img-md' }),
		),
		'<img src="/files/a.png" alt="x" class="img-md">',
	);
	assert.equal(
		renderImageMarkdown(
			node({
				src: '/files/a.png',
				alt: 'x',
				title: 'T',
				width: 320,
				className: 'img-center img-shadow',
			}),
		),
		'<img src="/files/a.png" alt="x" title="T" width="320" class="img-center img-shadow">',
	);
});

test('an image with no width and no class is still written as markdown', () => {
	assert.equal(
		renderImageMarkdown(node({ src: '/files/a.png', alt: 'x' })),
		'![x](/files/a.png)',
	);
	assert.equal(
		renderImageMarkdown(
			node({ src: '/files/a.png', alt: 'x', title: 'T', caption: ' c ' }),
		),
		'![x](/files/a.png "T")\n*c*',
	);
	// the 100 % button sets the width to null, an empty class is no class
	assert.equal(
		renderImageMarkdown(
			node({ src: '/files/a.png', alt: 'x', width: null, className: '  ' }),
		),
		'![x](/files/a.png)',
	);
});

test('a width that is not a number of pixels is not written', () => {
	for (const width of ['50%', 'auto', 0, -3, '', 'abc']) {
		assert.equal(
			renderImageMarkdown(node({ src: '/a.png', alt: '', width })),
			'![](/a.png)',
			`width ${JSON.stringify(width)}`,
		);
	}
	assert.equal(imageWidth('480px'), 480);
	assert.equal(imageWidth('480'), 480);
	assert.equal(imageWidth(480), 480);
});

test('the caption follows an <img> tag as <em>, so that the reader does not show its asterisks', () => {
	const md = renderImageMarkdown(
		node({ src: '/a.png', alt: 'x', width: 480, caption: 'A < B & C' }),
	);
	assert.equal(
		md,
		'<img src="/a.png" alt="x" width="480">\n<em>A &lt; B &amp; C</em>',
	);
	// The reason: under an HTML block, `*caption*` is part of the block and stays literal.
	const marked = new Marked({ breaks: true });
	const asterisks = marked.parse('<img src="/a.png" width="480">\n*cap*');
	assert.ok(asterisks.includes('*cap*'), asterisks);
	const html = marked.parse(md);
	assert.ok(html.includes('<em>A &lt; B &amp; C</em>'), html);
	assert.ok(!html.includes('*'), html);
});

test('the values of the tag are escaped', () => {
	const md = renderImageMarkdown(
		node({
			src: '/files/a.png?x=1&y=2',
			alt: 'say "hi" <b>',
			width: 480,
			className: 'a"b',
		}),
	);
	assert.equal(
		md,
		'<img src="/files/a.png?x=1&amp;y=2" alt="say &quot;hi&quot; &lt;b&gt;" width="480" class="a&quot;b">',
	);
	const token = tokenizeImageHtml(md);
	assert.equal(token.href, '/files/a.png?x=1&y=2');
	assert.equal(token.text, 'say "hi" <b>');
	assert.equal(token.className, 'a"b');
});

test('an image still uploading, or whose upload failed, is not written whatever its width', () => {
	assert.equal(
		renderImageMarkdown(
			node({ src: 'data:image/png;base64,AAAA', width: 480, loading: true }),
		),
		'',
	);
	assert.equal(
		renderImageMarkdown(node({ src: '/a.png', width: 480, error: 'boom' })),
		'',
	);
});

test('a hand-written <img class="img-md"> is read with its class, its width and its caption', () => {
	const token = tokenizeImageHtml(
		'<img class="img-md" src="/files/shot one.png" alt="A screen" title="T" width="480">\n*the caption*\n\nnext',
	);
	assert.deepEqual(imageNodeAttrs(token), {
		src: '/files/shot one.png',
		title: 'T',
		alt: 'A screen',
		caption: 'the caption',
		width: 480,
		className: 'img-md',
	});
	assert.equal(
		token.raw,
		'<img class="img-md" src="/files/shot one.png" alt="A screen" title="T" width="480">\n*the caption*',
		'the token takes the tag and its caption, not the blank line after',
	);
});

test('the tag is read the way HTML writes it: any order, single quotes, no quotes, self-closing, several lines', () => {
	assert.deepEqual(
		imageNodeAttrs(tokenizeImageHtml("<IMG SRC='/a.png' ALT='x' WIDTH=320 />")),
		{
			src: '/a.png',
			title: null,
			alt: 'x',
			caption: null,
			width: 320,
			className: null,
		},
	);
	const multiline = tokenizeImageHtml(
		'<img\n  src="/a.png"\n  alt="a > b"\n  class="img-lg"\n>',
	);
	assert.equal(multiline.href, '/a.png');
	assert.equal(multiline.text, 'a > b');
	assert.equal(multiline.className, 'img-lg');
	// the first attribute of a name wins, like in a browser
	assert.equal(
		tokenizeImageHtml('<img src="/a.png" src="/b.png">').href,
		'/a.png',
	);
	// an entity in the caption
	assert.equal(
		tokenizeImageHtml('<img src="/a.png">\n<em>Q &amp; A</em>').caption,
		'Q & A',
	);
});

test('what is not an image block is left alone', () => {
	// text after the tag on its line: an inline image
	assert.equal(tokenizeImageHtml('<img src="/a.png"> and text'), undefined);
	assert.equal(tokenizeImageHtml('text <img src="/a.png">'), undefined);
	// no src
	assert.equal(tokenizeImageHtml('<img alt="x" width="480">'), undefined);
	assert.equal(tokenizeImageHtml('<img src="">'), undefined);
	// another tag whose name starts with img
	assert.equal(tokenizeImageHtml('<imgx src="/a.png">'), undefined);
	// a *…* that is not alone on its line is text, not a caption
	const token = tokenizeImageHtml('<img src="/a.png">\n*word* and more');
	assert.equal(token.caption, null);
	assert.equal(token.raw, '<img src="/a.png">');
});

test('a paragraph stops where an <img> tag stands alone on a line, and only there', () => {
	assert.equal(imageHtmlStart('text\n<img src="/a.png">\nmore'), 5);
	assert.equal(
		imageHtmlStart('<img src="/a.png">'),
		-1,
		"the first line is the tokenizer's own start",
	);
	assert.equal(imageHtmlStart('text <img src="/a.png">\nmore'), -1);
	assert.equal(imageHtmlStart('text\n<img src="/a.png"> trailing\nmore'), -1);
	assert.equal(imageHtmlStart('text\nno image here'), -1);
});

test('the size buttons replace a size class and keep the other classes', () => {
	assert.equal(withoutImageSizeClass('img-md'), null);
	assert.equal(withoutImageSizeClass('img-md img-center'), 'img-center');
	assert.equal(
		withoutImageSizeClass('img-center img-shadow'),
		'img-center img-shadow',
	);
	assert.equal(withoutImageSizeClass('rounded IMG-FULL'), 'rounded');
	assert.equal(withoutImageSizeClass(null), null);
	assert.equal(withoutImageSizeClass(undefined), null);
});

test('a page with a hand-written <img class="img-md"> keeps its class and its width through a save', () => {
	const manager = buildManager();
	const source =
		'Before\n\n<img class="img-md" src="/files/a.png" alt="x" width="480">\n\nAfter';
	const json = manager.parse(source);
	assert.deepEqual(
		json.content.map((n) => n.type),
		['paragraph', 'image', 'paragraph'],
	);
	assert.equal(imageNodes(json)[0].attrs.className, 'img-md');
	assert.equal(imageNodes(json)[0].attrs.width, 480);
	const saved = manager.serialize(json);
	assert.match(
		saved,
		/<img src="\/files\/a\.png" alt="x" width="480" class="img-md">/,
	);
	assert.match(saved, /^Before/);
	assert.match(saved, /After$/);
});

test('a width set in the editor survives a save and a reopening', () => {
	const manager = buildManager();
	// what the M button does to a node that came from `![x](/files/a.png)`
	const json = manager.parse('![x](/files/a.png)');
	assert.deepEqual(
		json.content.map((n) => n.type),
		['image'],
		'the markdown syntax still makes an image block',
	);
	imageNodes(json)[0].attrs.width = 480;
	const saved = manager.serialize(json);
	assert.equal(saved, '<img src="/files/a.png" alt="x" width="480">');
	const reopened = manager.parse(saved);
	assert.equal(imageNodes(reopened)[0].attrs.width, 480);
	assert.equal(manager.serialize(reopened), saved);
});

test('the markdown form is read and written as before when there is nothing to keep', () => {
	const manager = buildManager();
	for (const source of [
		'![x](/files/a.png)',
		'![x](/files/a.png "T")',
		'![x](/files/a.png)\n*caption*',
		'before\n\n![x](/files/image (24).png)\n*c*\n\nafter',
	]) {
		const output = manager.serialize(manager.parse(source));
		assert.equal(output, source);
	}
});

const CASES = {
	'an image with a width': '<img src="/files/a.png" alt="x" width="480">',
	'an image with a class': '<img src="/files/a.png" alt="x" class="img-md">',
	'an image with a width, a class and a title':
		'<img src="/files/a.png" alt="x" title="T" width="320" class="img-center">',
	'an image with a width and a caption':
		'<img src="/files/a.png" alt="x" width="480">\n<em>the caption</em>',
	'a width image between two paragraphs':
		'one\n\n<img src="/files/a.png" alt="x" width="720">\n<em>c</em>\n\ntwo',
	'two images, one of each form':
		'<img src="/files/a.png" alt="x" width="480">\n\n![y](/files/b.png)',
	'a width image in a list':
		'- item\n  <img src="/files/a.png" alt="x" width="480">',
};

for (const [label, source] of Object.entries(CASES)) {
	test(`${label} round-trips to a fixed point`, () => {
		const outputs = roundTrip(buildManager(), source);
		assert.deepEqual(
			outputs,
			Array(outputs.length).fill(outputs[0]),
			`markdown kept changing across round-trips: ${JSON.stringify(outputs)}`,
		);
		assert.equal(outputs[0], source);
	});
}

test('an <img> tag in the middle of a paragraph stays inline text, as before', () => {
	const manager = buildManager();
	const json = manager.parse(
		'some text <img src="/a.png" width="300"> and more',
	);
	assert.deepEqual(
		json.content.map((n) => n.type),
		['paragraph'],
	);
});
