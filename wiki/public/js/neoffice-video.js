//// Neoffice — added file (no upstream equivalent)
//
// Clips in the manual (a 20-second demonstration under the opening paragraph of a page) were shown small, and the only way to enlarge one was
// the browser's own full-screen button, which covers the whole screen with the browser's controls: too much for a clip. A click on the
// picture now opens it in a large window over the page, the same gesture as for an image (image-viewer.js); Escape, a click outside or the
// cross closes it, and the playing position is carried both ways. The browser's full-screen button is taken off the small player (Chrome
// honours `controlsList="nofullscreen"`; other browsers keep theirs) and stays in the large one.
//
// A click in the strip of native controls at the bottom (play, volume, seek bar…) is left alone.
(function () {
	var viewer = document.getElementById('video-viewer');
	var big = document.getElementById('video-viewer-video');
	if (!viewer || !big) return;

	var BAR = 52; // px of native controls at the bottom of the small player
	var source = null; // the small player the large one was opened from

	function prepare(video) {
		if (video.dataset.neoBound) return;
		video.dataset.neoBound = 'true';
		video.setAttribute('controlsList', 'nofullscreen');
		video.title = viewer.dataset.title || '';
	}

	function open(video) {
		source = video;
		var at = video.currentTime;
		video.pause();
		big.muted = video.muted;
		big.loop = video.loop;
		big.src = video.currentSrc || video.src;
		big.addEventListener('loadedmetadata', function start() {
			big.removeEventListener('loadedmetadata', start);
			try { big.currentTime = at; } catch (e) { /* not seekable yet */ }
			// The popup is the size of the player's window, not of the clip: width from the clip's own ratio (see the CSS).
			if (big.videoWidth && big.videoHeight) big.style.setProperty('--neo-ratio', String(big.videoWidth / big.videoHeight));
			// Clicking to enlarge means wanting to watch it: always play, from where the small player was.
			big.play().catch(function () {});
		});
		viewer.classList.add('active');
		document.body.classList.add('video-viewer-open');
	}

	function close() {
		if (!viewer.classList.contains('active')) return;
		big.pause();
		if (source) {
			try { source.currentTime = big.currentTime; } catch (e) { /* ignore */ }
		}
		viewer.classList.remove('active');
		document.body.classList.remove('video-viewer-open');
		big.removeAttribute('src');
		big.load();
		source = null;
	}

	// Capture phase, so that a click on the picture is ours before the player turns it into play/pause. Delegated on the document: the
	// SPA navigation swaps the content of #wiki-content and the next page's clips are already covered.
	document.addEventListener('click', function (e) {
		var video = e.target.closest && e.target.closest('#wiki-content video');
		if (!video) return;
		var r = video.getBoundingClientRect();
		if (e.clientY > r.bottom - BAR) return;
		e.preventDefault();
		e.stopImmediatePropagation();
		open(video);
	}, true);

	viewer.addEventListener('click', function (e) {
		if (e.target === viewer || e.target.closest('#video-viewer-close')) close();
	});
	document.addEventListener('keydown', function (e) {
		if (e.key === 'Escape') close();
	});

	function prepareAll() {
		document.querySelectorAll('#wiki-content video').forEach(prepare);
	}
	prepareAll();
	var content = document.getElementById('wiki-content');
	if (content) new MutationObserver(prepareAll).observe(content, { childList: true, subtree: true });
})();
