<template>
    <NodeViewWrapper class="wiki-image-wrapper" :class="{ 'is-selected': selected }">
        <div class="wiki-image-container" :style="containerStyle">
            <img
                :src="node.attrs.src"
                :alt="node.attrs.alt || ''"
                :title="node.attrs.title || ''"
                class="wiki-image"
                :style="imageStyle"
                @click="handleImageClick"
            />
            <!-- Size controls shown when image is selected and editor is editable -->
            <div v-if="selected && editor.isEditable" class="wiki-image-size-controls">
                <button
                    v-for="opt in sizeOptions"
                    :key="opt.value"
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
            <input
                v-if="editor.isEditable || node.attrs.caption"
                ref="captionInput"
                v-model="caption"
                type="text"
                class="wiki-image-caption-input"
                :class="{ 'has-caption': !!caption }"
                placeholder="Add caption..."
                :disabled="!editor.isEditable"
                @input="updateCaption"
                @keydown="handleKeydown"
            />
        </div>

        <!-- Lightbox overlay -->
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
import { ref, computed, watch } from 'vue';
import { NodeViewWrapper } from '@tiptap/vue-3';

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

const currentSize = computed(() => {
    return props.node.attrs.width || null;
});

const imageStyle = computed(() => {
    const w = props.node.attrs.width;
    if (w) {
        return { width: `${w}px`, maxWidth: '100%', height: 'auto' };
    }
    return { maxWidth: '860px', maxHeight: '600px', height: 'auto', objectFit: 'contain' };
});

const containerStyle = computed(() => {
    return {};
});

function handleImageClick() {
    if (props.editor.isEditable) {
        // In edit mode: select the node
        selectNode();
    } else {
        // In read mode: open lightbox
        showLightbox.value = true;
        document.body.style.overflow = 'hidden';
    }
}

function closeLightbox() {
    showLightbox.value = false;
    document.body.style.overflow = '';
}

function setSize(value) {
    props.updateAttributes({ width: value, height: null });
}

function setCustomWidth(event) {
    const val = parseInt(event.target.value, 10);
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
    }
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
        const endPos = pos + props.node.nodeSize;
        props.editor
            .chain()
            .focus()
            .insertContentAt(endPos, { type: 'paragraph' })
            .setTextSelection(endPos + 1)
            .run();
    } else if (event.key === 'Escape' || event.key === 'ArrowDown') {
        event.preventDefault();
        const endPos = pos + props.node.nodeSize;
        props.editor.chain().focus().setTextSelection(endPos).run();
    } else if (event.key === 'ArrowUp') {
        event.preventDefault();
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

.wiki-image {
    border-radius: 0.375rem;
    cursor: pointer;
    margin: 0;
    transition: opacity 0.15s;
}

.wiki-image:hover {
    opacity: 0.9;
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

/* Caption */
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
</style>

<style>
/* Lightbox styles - global (not scoped) so Teleport works */
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
