//// Neoffice — added file (no upstream equivalent)
//
// A window or a panel captured on its own is narrower than a whole-page capture: about 930px for a "send by e-mail" dialog, against 1440px
// for a full screen. Shown at its own size in a wide column it looks far too big next to the text, and the "fill the column" rule that
// is right for a full page (small print stays legible) is wrong for it. So the reader shows an image narrower than 1000px at 600px at
// most (between the editor's "M" 480 and "L" 720 presets; was 720, still a bit big for Daniel on 2026-10-03), unless the author gave it a width or an img-* class. A click still opens it large in the
// image viewer. Wider images are untouched.
//
// Why here and not in the pages: the editor's S/M/L/XL buttons set a width that is NOT saved in the markdown (image-extension.js
// writes only src, alt, title and caption), so a width set by hand is lost, and a rule that lives in the data is lost with it. A rule in the
// reader holds for every page, the old ones and the next ones, whoever wrote them.
(function () {
	var NARROW = 1000;
	var SHOWN = 600;

	function fit(img) {
		if (!img.matches || !img.matches('#wiki-content img')) return;
		// image-viewer.js puts `cursor: zoom-in` in the style attribute of every image, so the attribute alone says nothing: look at the width.
		if (img.hasAttribute('width') || img.style.width || img.style.maxWidth || /(^|\s)img-/.test(img.className)) return;
		var w = img.naturalWidth;
		// min(…, 100%): the cap must not let the image overflow a narrow column (phone).
		if (w > SHOWN && w < NARROW) img.style.maxWidth = 'min(' + SHOWN + 'px, 100%)';
	}

	// The load event does not bubble: listen in the capture phase. That also catches the images of a page the SPA navigation swaps in.
	document.addEventListener('load', function (e) {
		if (e.target && e.target.tagName === 'IMG') fit(e.target);
	}, true);

	// Images that finished loading before this script ran.
	document.querySelectorAll('#wiki-content img').forEach(function (img) {
		if (img.complete) fit(img);
	});
})();
