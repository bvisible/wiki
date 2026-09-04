//// Neoffice — rewritten wholesale. Upstream stores useStorage('wiki-theme',
//// 'dark'), whose writeDefaults writes "dark" on the FIRST visit of every
//// browser: indistinguishable from a real choice, so everyone was pinned to
//// dark forever. Ours follows the OS until the user actually toggles.
//// Upstream's API (userTheme / themeIcon / toggleTheme / initTheme) is kept so
//// its own components keep working unmodified.
import { computed, ref } from 'vue';

// Shared light/dark theme for the wiki frontend.
//
// Default behaviour = follow the OS (`prefers-color-scheme`). A manual toggle
// persists an explicit choice in localStorage; as long as the user has NOT
// toggled, the theme tracks the system and reacts to live changes. Applied via
// `data-theme` on <html>. Singleton module state so every component (Sidebar,
// MobileAppMenu, SpaceDetails, DiffViewer, Mermaid blocks…) shares the same
// reactive value.
//
// Upstream stores `useStorage('wiki-theme', 'dark')`, whose writeDefaults pins
// every fresh browser to dark on the first visit — a default, not a choice.
// 'wiki-theme-pref' is written ONLY on an explicit toggle, so an untouched
// browser falls back to the OS theme. The legacy key is cleared on load.
const STORAGE_KEY = 'wiki-theme-pref';
const LEGACY_KEY = 'wiki-theme';
try {
	if (typeof localStorage !== 'undefined') localStorage.removeItem(LEGACY_KEY);
} catch (_) {
	/* ignore */
}

const media =
	typeof window !== 'undefined' && window.matchMedia
		? window.matchMedia('(prefers-color-scheme: dark)')
		: null;

function savedChoice() {
	const v =
		typeof localStorage !== 'undefined'
			? localStorage.getItem(STORAGE_KEY)
			: null;
	return v === 'dark' || v === 'light' ? v : null;
}

//// Neoffice — added, part of the rewrite described at the top of this file:
//// the OS preference, the shared ref, applying it at import time (no flash on
//// first paint) and following live OS changes while no choice was made.
function systemTheme() {
	return media?.matches ? 'dark' : 'light';
}

const theme = ref(savedChoice() || systemTheme());

function applyTheme(t) {
	if (typeof document !== 'undefined') {
		document.documentElement.setAttribute('data-theme', t);
	}
	theme.value = t;
}

// Apply at module load so there is no stale/flashing theme on first paint.
applyTheme(theme.value);

// Track the OS theme while no explicit choice has been made.
if (media) {
	media.addEventListener('change', (e) => {
		if (!savedChoice()) applyTheme(e.matches ? 'dark' : 'light');
	});
}

export function useTheme() {
	//// Neoffice — added: upstream compared userTheme.value inline in each caller.
	const isDark = computed(() => theme.value === 'dark');
	const themeIcon = computed(() =>
		//// Neoffice — reads isDark instead of comparing the raw ref (same icon).
		isDark.value ? 'lucide-sun' : 'lucide-moon',
	);

	function toggleTheme() {
		//// Neoffice — toggling now WRITES the choice (upstream only mutated the
		//// useStorage ref, which was already pre-filled with 'dark' on first visit).
		//// Guarded because localStorage throws in private mode.
		const next = theme.value === 'dark' ? 'light' : 'dark';
		try {
			localStorage.setItem(STORAGE_KEY, next); // explicit choice persists
		} catch (_) {
			/* ignore storage errors (private mode) */
		}
		//// Neoffice — applyTheme also sets the ref now, so upstream's trailing
		//// `userTheme.value = next` disappeared.
		applyTheme(next);
	}

	//// Neoffice — added. Drops the explicit choice and hands the theme back to
	//// the OS; there is no way back to system in upstream once toggled.
	function resetToSystem() {
		try {
			localStorage.removeItem(STORAGE_KEY);
		} catch (_) {
			/* ignore */
		}
		applyTheme(systemTheme());
	}

	// Kept for parity with upstream, which calls it from the always-mounted
	// shell. The module already applied the theme at import time, so this is a
	// no-op safety net rather than the real entry point.
	function initTheme() {
		//// Neoffice — applies the module ref (upstream applied the storage ref).
		applyTheme(theme.value);
	}

	//// Neoffice — return widened: upstream returns userTheme/themeIcon/
	//// toggleTheme/initTheme. Those four names are kept exactly so its own
	//// components keep working; theme, isDark and resetToSystem are ours.
	// `userTheme` is upstream's name for the same ref.
	return {
		theme,
		userTheme: theme,
		isDark,
		themeIcon,
		toggleTheme,
		resetToSystem,
		initTheme,
	};
}
