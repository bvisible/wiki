<template>
    <NodeViewWrapper class="wiki-image-wrapper" :class="{ 'is-selected': selected }">
        <div class="wiki-image-container">
            <div class="wiki-image-frame">
                <img
                    :src="node.attrs.src"
                    :alt="node.attrs.alt || ''"
                    :title="node.attrs.title || ''"
                    :height="node.attrs.height || undefined"
                    class="wiki-image"
                    :class="{ 'is-loading': node.attrs.loading }"
                    :style="imageStyle"
                    @click="handleImageClick"
                />
                <!-- Upload / optimization progress overlay -->
                <div v-if="node.attrs.loading" class="wiki-image-loading-overlay">
                    <span class="wiki-image-spinner" />
                    <span class="wiki-image-loading-text">Uploading…</span>
                </div>
            </div>
            <!-- Size controls shown when the image is selected and editable -->
            <div v-if="selected && isEditable" class="wiki-image-size-controls">
                <button
                    v-for="opt in sizeOptions"
                    :key="opt.label"
                    class="wiki-image-size-btn"
                    :class="{ active: currentSize === opt.value }"
                    :title="opt.label"
                    @click.stop="setSize(opt.value)"
                >
                    {{ opt.label }}
                </button>
                <span class="wiki-image-size-separator"></span>
                <input
                    type="number"
                    class="wiki-image-width-input"
                    :value="node.attrs.width || ''"
                    placeholder="px"
                    min="100"
                    max="2000"
                    @change="setCustomWidth($event)"
                    @click.stop
                />
            </div>
            <div v-if="node.attrs.error" class="wiki-image-error">
                Upload failed: {{ node.attrs.error }}
            </div>
            <input
                v-if="(isEditable || node.attrs.caption) && !node.attrs.error"
                ref="captionInput"
                v-model="caption"
                type="text"
                class="wiki-image-caption-input"
                :class="{ 'has-caption': !!caption }"
                placeholder="Add caption..."
                :disabled="!isEditable"
                @input="updateCaption"
                @keydown="handleKeydown"
            />
        </div>

        <!-- Lightbox overlay (read mode only) -->
        <Teleport to="body">
            <div v-if="showLightbox" class="wiki-lightbox-overlay" @click="closeLightbox">
                <button class="wiki-lightbox-close" @click.stop="closeLightbox">&times;</button>
                <img
                    :src="node.attrs.src"
                    :alt="node.attrs.alt || ''"
                    class="wiki-lightbox-image"
                    @click.stop
                />
                <p v-if="caption" class="wiki-lightbox-caption">{{ caption }}</p>
            </div>
        </Teleport>
    </NodeViewWrapper>
</template>

<script setup>
import { useNodeViewEditable } from '@/composables/useNodeViewEditable';
import { NodeViewWrapper } from '@tiptap/vue-3';
import { computed, ref, watch } from 'vue';

const props = defineProps({
	node: {
		type: Object,
		required: true,
	},
	updateAttributes: {
		type: Function,
		required: true,
	},
	selected: {
		type: Boolean,
		default: false,
	},
	editor: {
		type: Object,
		required: true,
	},
	getPos: {
		type: Function,
		required: true,
	},
});

const isEditable = useNodeViewEditable(props.editor);
const captionInput = ref(null);
const caption = ref(props.node.attrs.caption || '');
const showLightbox = ref(false);

const sizeOptions = [
	{ label: 'S', value: 320 },
	{ label: 'M', value: 480 },
	{ label: 'L', value: 720 },
	{ label: 'XL', value: 960 },
	{ label: '100%', value: null },
];

const currentSize = computed(() => props.node.attrs.width || null);

const imageStyle = computed(() => {
	const w = props.node.attrs.width;
	if (w) {
		return { width: `${w}px`, maxWidth: '100%', height: 'auto' };
	}
	// min(860px, 100%): cap width on desktop but never overflow a narrow
	// (mobile) container.
	return {
		maxWidth: 'min(860px, 100%)',
		maxHeight: '600px',
		height: 'auto',
		objectFit: 'contain',
	};
});

function handleImageClick() {
	if (isEditable.value) {
		selectNode();
		return;
	}
	// Read mode: open the lightbox.
	showLightbox.value = true;
	document.body.style.overflow = 'hidden';
}

function closeLightbox() {
	showLightbox.value = false;
	document.body.style.overflow = '';
}

function setSize(value) {
	props.updateAttributes({ width: value, height: null });
}

function setCustomWidth(event) {
	const val = Number.parseInt(event.target.value, 10);
	if (val && val >= 100 && val <= 2000) {
		props.updateAttributes({ width: val, height: null });
	}
}

// Watch for external changes to caption attribute
watch(
	() => props.node.attrs.caption,
	(newCaption) => {
		if (newCaption !== caption.value) {
			caption.value = newCaption || '';
		}
	},
);

function updateCaption() {
	props.updateAttributes({ caption: caption.value });
}

function selectNode() {
	const pos = props.getPos();
	if (typeof pos === 'number') {
		props.editor.commands.setNodeSelection(pos);
	}
}

function handleKeydown(event) {
	const pos = props.getPos();
	if (typeof pos !== 'number') return;

	if (event.key === 'Enter') {
		event.preventDefault();
		// Insert paragraph after image and move cursor there
		const endPos = pos + props.node.nodeSize;
		props.editor
			.chain()
			.focus()
			.insertContentAt(endPos, { type: 'paragraph' })
			.setTextSelection(endPos + 1)
			.run();
	} else if (event.key === 'Escape' || event.key === 'ArrowDown') {
		event.preventDefault();
		// Move cursor after the image
		const endPos = pos + props.node.nodeSize;
		props.editor.chain().focus().setTextSelection(endPos).run();
	} else if (event.key === 'ArrowUp') {
		event.preventDefault();
		// Move cursor before the image
		props.editor.chain().focus().setTextSelection(pos).run();
	}
}
</script>

<style scoped>
.wiki-image-wrapper {
    display: block;
    margin: 1rem 0;
}

.wiki-image-wrapper.is-selected .wiki-image {
    outline: 2px solid var(--primary, #171717);
    outline-offset: 2px;
}

.wiki-image-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin: 0;
}

.wiki-image-frame {
    position: relative;
    display: inline-flex;
    max-width: 100%;
}

.wiki-image {
    max-width: 100%;
    height: auto;
    border-radius: 0.375rem;
    cursor: pointer;
    margin: 0;
}

.wiki-image.is-loading {
    filter: brightness(0.7);
}

.wiki-image-loading-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    border-radius: 0.375rem;
    background: rgba(17, 17, 17, 0.35);
    color: #fff;
    font-size: 0.8125rem;
}

.wiki-image-spinner {
    width: 1.25rem;
    height: 1.25rem;
    border: 2px solid rgba(255, 255, 255, 0.4);
    border-top-color: #fff;
    border-radius: 50%;
    animation: wiki-image-spin 0.7s linear infinite;
}

@keyframes wiki-image-spin {
    to {
        transform: rotate(360deg);
    }
}

.wiki-image-error {
    width: 100%;
    text-align: center;
    font-size: 0.8125rem;
    color: var(--ink-red-5, #dc2626);
    padding: 0.5rem 0;
}

.wiki-image-caption-input {
    width: 100%;
    max-width: 100%;
    text-align: center;
    background: transparent;
    border: none;
    font-style: italic;
    font-size: 0.875rem;
    color: var(--ink-gray-6, #4b5563);
    padding: 0 0.25rem;
    margin-top: 0.25rem;
    outline: none;
    box-shadow: none;
}

.wiki-image-caption-input::placeholder {
    color: var(--ink-gray-4, #9ca3af);
}

.wiki-image-caption-input:focus {
    outline: none;
    box-shadow: none;
    border: none;
}

.wiki-image-caption-input:disabled {
    cursor: default;
}

.wiki-image-caption-input:disabled:not(.has-caption) {
    display: none;
}

/* Size controls */
.wiki-image-size-controls {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    margin-top: 0.5rem;
    padding: 0.25rem 0.5rem;
    background: var(--surface-gray-2, #f3f4f6);
    border: 1px solid var(--outline-gray-2, #e5e7eb);
    border-radius: 0.375rem;
}

.wiki-image-size-btn {
    padding: 0.125rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 500;
    border: 1px solid transparent;
    border-radius: 0.25rem;
    background: transparent;
    color: var(--ink-gray-6, #4b5563);
    cursor: pointer;
    transition: all 0.15s;
}

.wiki-image-size-btn:hover {
    background: var(--surface-gray-3, #e5e7eb);
}

.wiki-image-size-btn.active {
    background: var(--surface-white, #fff);
    border-color: var(--outline-gray-3, #d1d5db);
    color: var(--ink-gray-9, #111827);
    font-weight: 600;
}

.wiki-image-size-separator {
    width: 1px;
    height: 1rem;
    background: var(--outline-gray-2, #e5e7eb);
    margin: 0 0.25rem;
}

.wiki-image-width-input {
    width: 3.5rem;
    padding: 0.125rem 0.25rem;
    font-size: 0.75rem;
    border: 1px solid var(--outline-gray-2, #e5e7eb);
    border-radius: 0.25rem;
    background: var(--surface-white, #fff);
    color: var(--ink-gray-8, #1f2937);
    text-align: center;
    outline: none;
    -moz-appearance: textfield;
}

.wiki-image-width-input::-webkit-inner-spin-button,
.wiki-image-width-input::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}

.wiki-image-width-input:focus {
    border-color: var(--outline-gray-3, #d1d5db);
}
</style>

<style>
/* Lightbox styles — global (not scoped) so the Teleport'd markup is styled. */
.wiki-lightbox-overlay {
    position: fixed;
    inset: 0;
    z-index: 99999;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(4px);
    cursor: zoom-out;
    padding: 2rem;
    animation: wiki-lightbox-in 0.2s ease-out;
}

@keyframes wiki-lightbox-in {
    from { opacity: 0; }
    to { opacity: 1; }
}

.wiki-lightbox-close {
    position: absolute;
    top: 1rem;
    right: 1.5rem;
    background: none;
    border: none;
    color: white;
    font-size: 2.5rem;
    cursor: pointer;
    line-height: 1;
    opacity: 0.7;
    transition: opacity 0.15s;
    z-index: 1;
}

.wiki-lightbox-close:hover {
    opacity: 1;
}

.wiki-lightbox-image {
    max-width: 90vw;
    max-height: 85vh;
    object-fit: contain;
    border-radius: 0.5rem;
    box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
    cursor: default;
}

.wiki-lightbox-caption {
    color: rgba(255, 255, 255, 0.8);
    font-style: italic;
    font-size: 0.875rem;
    margin-top: 0.75rem;
    text-align: center;
}
</style>
