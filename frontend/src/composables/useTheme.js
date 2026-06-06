import { ref, computed } from 'vue';

// Shared light/dark theme for the wiki frontend.
//
// Default behaviour = follow the OS (`prefers-color-scheme`). A manual toggle
// persists an explicit choice in localStorage ('wiki-theme'); as long as the
// user has NOT toggled, the theme tracks the system and reacts to live changes.
// Applied via `data-theme` on <html>. Singleton module state so every component
// (Sidebar, SpaceDetails, DiffViewer…) shares the same reactive value.

// New key: the old 'wiki-theme' was auto-written to 'dark' by useStorage's
// writeDefaults on every visit (NOT a real user choice), which would pin
// everyone to dark forever. 'wiki-theme-pref' is written ONLY on an explicit
// toggle, so an untouched browser falls back to the OS theme.
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
	const v = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
	return v === 'dark' || v === 'light' ? v : null;
}

function systemTheme() {
	return media && media.matches ? 'dark' : 'light';
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
	const isDark = computed(() => theme.value === 'dark');

	function toggleTheme() {
		const next = theme.value === 'dark' ? 'light' : 'dark';
		try {
			localStorage.setItem(STORAGE_KEY, next); // explicit choice persists
		} catch (_) {
			/* ignore storage errors (private mode) */
		}
		applyTheme(next);
	}

	function resetToSystem() {
		try {
			localStorage.removeItem(STORAGE_KEY);
		} catch (_) {
			/* ignore */
		}
		applyTheme(systemTheme());
	}

	return { theme, isDark, toggleTheme, resetToSystem };
}
