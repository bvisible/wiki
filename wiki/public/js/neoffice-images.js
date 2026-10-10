//// Neoffice — added file (no upstream equivalent)
//
// A window or a panel captured on its own is much narrower than a whole-page capture: 600 to 930px for a dialog, against 1440px for a full
// screen. Shown at its own size next to the text it looks far too big, because the text inside a capture is as large as the page's own
// (a "Confirm" box with three words took half the column), and the "fill the column" rule that is right for a full page (small print stays
// legible) is wrong for it. So the reader shows an image between 400 and 1000px wide at 70% of its real size. Wider images (full pages,
// regions) are untouched, and so are small crops (icons, buttons) under 400px. A click still opens the image large in the viewer.
// An author's explicit width or img-* class wins.
//
// A fixed cap (720px, then 600px) was tried first and was wrong: it left a 600px dialog at full size, just under the cap. A proportion
// treats every dialog the same whatever its width.
//
// Why here and not in the pages: the editor's S/M/L/XL buttons set a width that is NOT saved in the markdown (image-extension.js
// writes only src, alt, title and caption), so a width set by hand is lost, and a rule that lives in the data is lost with it. A rule in
// the reader holds for every page, the old ones and the next ones, whoever wrote them.
(function () {
	var MIN = 400;
	var MAX = 1000;
	var SCALE = 0.7;
	var CAP = 560; // the tallest a capture may be (neoffice-wiki.css: img:not(.img-full) { max-height: 560px })

	function fit(img) {
		if (!img.matches || !img.matches('#wiki-content img')) return;
		// image-viewer.js puts `cursor: zoom-in` in the style attribute of every image, so the attribute alone says nothing: look at the width.
		if (img.hasAttribute('width') || img.style.width || img.style.maxWidth || /(^|\s)img-/.test(img.className)) return;
		var w = img.naturalWidth;
		// The reader's CSS keeps max-width: 100% and height: auto, so a narrow column (phone) still wins and the proportions hold.
		if (w >= MIN && w < MAX) {
			var shown = Math.round(w * SCALE);
			// A width set here is a fixed width: the CSS cap on the height would then squash the capture (a 660 x 1320 menu
			// shown 462 wide and 560 tall). So the width is the one that keeps the proportions under the cap.
			var h = img.naturalHeight;
			if (h && shown * h / w > CAP) shown = Math.round(CAP * w / h);
			img.style.width = shown + 'px';
		}
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
