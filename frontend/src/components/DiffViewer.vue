<template>
	<div ref="wrapper" class="diff-viewer" />
</template>

<script setup>
import { FileDiff } from '@pierre/diffs';
//// Neoffice — useStorage('wiki-theme') import dropped, useTheme() imported
//// instead: upstream read the theme straight from localStorage here, which
//// bypassed our OS-following theme and re-pinned this viewer to dark.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useTheme } from '../composables/useTheme';

const THEMES = {
	dark: 'github-dark',
	light: 'github-light',
};

//// Neoffice — was useStorage('wiki-theme', 'dark'); now the shared ref (see
//// the import note above). Same value, one source of truth.
const { theme: userTheme } = useTheme();
const themeType = computed(() =>
	userTheme.value === 'dark' ? 'dark' : 'light',
);

const props = defineProps({
	oldContent: {
		type: String,
		default: '',
	},
	newContent: {
		type: String,
		default: '',
	},
	fileName: {
		type: String,
		default: 'changes.md',
	},
	language: {
		type: String,
		default: 'markdown',
	},
	diffStyle: {
		type: String,
		default: 'split',
	},
});

const wrapper = ref(null);
let diffInstance = null;

function normalizeContent(content) {
	const normalized = (content || '')
		.replace(/\r\n/g, '\n')
		.replace(/\r/g, '\n');
	if (!normalized) {
		return '';
	}
	return normalized.endsWith('\n') ? normalized : `${normalized}\n`;
}

function renderDiff() {
	if (!wrapper.value) return;
	if (diffInstance) {
		diffInstance.cleanUp();
		diffInstance = null;
	}
	diffInstance = new FileDiff({
		theme: THEMES,
		diffStyle: props.diffStyle,
		lineDiffType: 'word',
		themeType: themeType.value,
	});

	diffInstance.render({
		oldFile: {
			name: props.fileName,
			contents: normalizeContent(props.oldContent),
			lang: props.language,
		},
		newFile: {
			name: props.fileName,
			contents: normalizeContent(props.newContent),
			lang: props.language,
		},
		containerWrapper: wrapper.value,
	});
}

onMounted(renderDiff);

watch(
	() => [
		props.oldContent,
		props.newContent,
		props.fileName,
		props.language,
		props.diffStyle,
		themeType.value,
	],
	() => {
		renderDiff();
	},
);

onBeforeUnmount(() => {
	diffInstance?.cleanUp();
	diffInstance = null;
});
</script>

<style scoped>
.diff-viewer {
	width: 100%;
	overflow: auto;
}
</style>
