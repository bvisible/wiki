<template>
    <div class="flex h-full">
        <aside
            ref="sidebarRef"
            class="border-r border-outline-gray-2 flex flex-col bg-surface-gray-1 flex-shrink-0 fixed inset-y-0 left-0 z-40 transition-transform duration-200 md:relative md:inset-auto md:z-auto md:translate-x-0"
            :class="mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'"
            :style="{ width: `${sidebarWidth}px` }"
        >
            <!-- Header -->
            <div class="p-4 border-b border-outline-gray-2">
                <div class="mb-3">
                    <div class="relative">
                        <FormControl
                            v-model="searchQuery"
                            type="text"
                            :placeholder="__('Rechercher dans ce wiki...')"
                            @input="handleSearchInput"
                            @focus="searchFocused = true"
                            @blur="setTimeout(() => (searchFocused = false), 200)"
                        >
                            <template #prefix>
                                <LucideSearch class="size-4 text-ink-gray-4" />
                            </template>
                        </FormControl>
                        <div
                            v-if="searchQuery && searchResults.length > 0"
                            class="absolute top-full left-0 right-0 mt-1 bg-surface-white border border-outline-gray-2 rounded-lg shadow-lg max-h-96 overflow-y-auto z-50"
                        >
                            <button
                                v-for="result in searchResults"
                                :key="result.name"
                                class="w-full text-left px-3 py-2 hover:bg-surface-gray-2 border-b border-outline-gray-1 last:border-b-0 cursor-pointer"
                                @mousedown="openSearchResult(result)"
                            >
                                <div class="text-sm font-medium text-ink-gray-9 truncate">{{ result.title }}</div>
                                <div v-if="result.content" class="text-xs text-ink-gray-5 mt-0.5 line-clamp-2" v-html="result.content" />
                            </button>
                        </div>
                        <div
                            v-else-if="searchQuery && !searchLoading && searchResults.length === 0"
                            class="absolute top-full left-0 right-0 mt-1 bg-surface-white border border-outline-gray-2 rounded-lg shadow-lg px-3 py-2 text-sm text-ink-gray-5 z-50"
                        >
                            {{ __('Aucun résultat') }}
                        </div>
                    </div>
                </div>
                <div class="flex items-center justify-between mb-3">
                    <Dropdown :options="spaceSwitcherOptions">
                        <Button variant="ghost" class="flex items-center gap-2 max-w-[200px]">
                            <template #suffix>
                                <LucideChevronDown class="size-4 text-ink-gray-5" />
                            </template>
                            <span class="truncate font-semibold text-ink-gray-9">
                                {{ (space.doc?.space_name || guestSpaceInfo.data?.space?.space_name) || spaceId }}
                            </span>
                        </Button>
                    </Dropdown>
                    <div class="flex items-center gap-1">
                        <Button
                            variant="ghost"
                            :icon="themeIcon"
                            :title="__('Toggle Theme')"
                            @click="toggleTheme"
                        />
                        <Button
                            v-if="!isGuest"
                            variant="ghost"
                            icon="settings"
                            :title="__('Settings')"
                            @click="showSettingsDialog = true"
                        />
                    </div>
                </div>
            </div>

            <div v-if="(space.doc || guestSpaceInfo.data?.space) && treeData" class="flex-1 overflow-auto p-2">
                <WikiDocumentList
                    :tree-data="treeData"
                    :change-type-map="changeTypeMap"
                    :space-id="spaceId"
                    :root-node="treeData?.root_group || space.doc?.root_group || guestSpaceInfo.data?.space?.root_group"
                    :selected-page-id="currentPageId"
                    :selected-draft-key="currentDraftKey"
                    @refresh="refreshTree"
                    @reorder-state-change="handleReorderStateChange"
                />
            </div>
            <div v-else class="flex-1 overflow-auto p-2">
                <!-- Sidebar tree skeleton -->
                <div class="space-y-1 animate-pulse">
                    <div v-for="i in 8" :key="i" class="flex items-center gap-2 px-2 py-1.5 rounded">
                        <div class="size-4 rounded bg-surface-gray-3 shrink-0" />
                        <div class="h-3.5 rounded bg-surface-gray-3" :style="{ width: `${60 + (i % 3) * 25}%` }" />
                    </div>
                    <div v-for="i in 4" :key="'nested-' + i" class="flex items-center gap-2 px-2 py-1.5 rounded ml-6">
                        <div class="size-4 rounded bg-surface-gray-3 shrink-0" />
                        <div class="h-3.5 rounded bg-surface-gray-3" :style="{ width: `${50 + (i % 2) * 30}%` }" />
                    </div>
                </div>
            </div>

            <div
                class="absolute top-0 right-0 w-1 h-full cursor-col-resize z-10 hidden md:block"
                :class="sidebarResizing ? 'bg-surface-gray-4' : 'hover:bg-surface-gray-4'"
                @mousedown="startResize"
            />
        </aside>

        <!-- Mobile drawer backdrop (below md only) -->
        <div
            v-if="mobileSidebarOpen"
            class="fixed inset-0 bg-black/40 z-30 md:hidden"
            @click="mobileSidebarOpen = false"
        />

        <main class="flex-1 flex flex-col bg-surface-white min-w-0">
            <!-- Mobile top bar with hamburger (desktop hides this) -->
            <div class="md:hidden flex items-center gap-2 px-3 py-2 border-b border-outline-gray-2 bg-surface-white shrink-0">
                <Button variant="ghost" :title="__('Menu')" @click="mobileSidebarOpen = true">
                    <LucideMenu class="size-5 text-ink-gray-7" />
                </Button>
                <span class="text-sm font-semibold text-ink-gray-9 truncate">
                    {{ space.doc?.space_name || guestSpaceInfo.data?.space?.space_name || '' }}
                </span>
            </div>
            <ContributionBanner
                v-if="!isGuest"
                :mergeDisabled="isTreeReordering"
                @submit="handleSubmitChangeRequest"
                @withdraw="handleArchiveChangeRequest"
                @merge="handleMergeChangeRequest"
            />
            <div class="flex-1 overflow-auto">
                <router-view
                    :space-id="spaceId"
                    @refresh="refreshTree"
                />
            </div>
        </main>

        <Dialog v-model="showSettingsDialog">
            <template #body-title>
                <h3 class="text-xl font-semibold text-ink-gray-9">
                    {{ __('Space Settings') }}
                </h3>
            </template>
            <template #body-content>
                <div class="space-y-4 py-2">
                    <div class="flex items-center justify-between p-3 rounded-lg border border-outline-gray-2 bg-surface-gray-1">
                        <div class="flex-1 mr-4">
                            <p class="text-sm font-medium text-ink-gray-9">
                                {{ __('Published') }}
                            </p>
                            <p class="text-xs text-ink-gray-5 mt-0.5">
                                {{ __('Make this wiki space publicly accessible') }}
                            </p>
                        </div>
                        <Switch
                            v-model="isPublished"
                            :disabled="updatingPublishSetting"
                            @update:modelValue="updatePublishSetting"
                        />
                    </div>
                    <div class="flex items-center justify-between p-3 rounded-lg border border-outline-gray-2 bg-surface-gray-1">
                        <div class="flex-1 mr-4">
                            <p class="text-sm font-medium text-ink-gray-9">
                                {{ __('Enable Feedback Collection') }}
                            </p>
                            <p class="text-xs text-ink-gray-5 mt-0.5">
                                {{ __('Show a feedback widget on wiki pages to collect user reactions') }}
                            </p>
                        </div>
                        <Switch
                            v-model="enableFeedbackCollection"
                            :disabled="updatingFeedbackSetting"
                            @update:modelValue="updateFeedbackSetting"
                        />
                    </div>
                    <div class="flex items-center justify-between p-3 rounded-lg border border-outline-gray-2 bg-surface-gray-1">
                        <div class="flex-1 mr-4">
                            <p class="text-sm font-medium text-ink-gray-9">
                                {{ __('Bulk Update Routes') }}
                            </p>
                            <p class="text-xs text-ink-gray-5 mt-0.5">
                                {{ __('Change the base route for this space and all its pages') }}
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            @click="openUpdateRoutesDialog"
                        >
                            {{ __('Update') }}
                        </Button>
                    </div>
                    <div class="flex items-center justify-between p-3 rounded-lg border border-outline-gray-2 bg-surface-gray-1">
                        <div class="flex-1 mr-4">
                            <p class="text-sm font-medium text-ink-gray-9">
                                {{ __('Clone Space') }}
                            </p>
                            <p class="text-xs text-ink-gray-5 mt-0.5">
                                {{ __('Create a new space with the same structure') }}
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            @click="openCloneSpaceDialog"
                        >
                            {{ __('Clone') }}
                        </Button>
                    </div>
                </div>
            </template>
            <template #actions="{ close }">
                <div class="flex justify-end">
                    <Button variant="outline" @click="close">{{ __('Close') }}</Button>
                </div>
            </template>
        </Dialog>

        <Dialog v-model="showUpdateRoutesDialog">
            <template #body-title>
                <h3 class="text-xl font-semibold text-ink-gray-9">
                    {{ __('Update Wiki Space Routes') }}
                </h3>
            </template>
            <template #body-content>
                <div class="space-y-4 py-2">
                    <FormControl
                        type="text"
                        :label="__('Current Base Route')"
                        :modelValue="space.doc?.route"
                        :disabled="true"
                    />
                    <FormControl
                        type="text"
                        :label="__('New Base Route')"
                        v-model="newRoute"
                        :placeholder="__('Enter new route (without leading slash)')"
                    />
                </div>
            </template>
            <template #actions="{ close }">
                <div class="flex justify-end gap-2">
                    <Button variant="outline" @click="close">{{ __('Cancel') }}</Button>
                    <Button
                        variant="solid"
                        :loading="updatingRoutes"
                        @click="updateRoutes(close)"
                    >
                        {{ __('Update Routes') }}
                    </Button>
                </div>
            </template>
        </Dialog>

        <Dialog v-model="showCloneSpaceDialog">
            <template #body-title>
                <h3 class="text-xl font-semibold text-ink-gray-9">
                    {{ __('Clone Wiki Space') }}
                </h3>
            </template>
            <template #body-content>
                <div class="space-y-4 py-2">
                    <FormControl
                        type="text"
                        :label="__('New Space Route')"
                        v-model="cloneRoute"
                        :placeholder="__('Enter new route (without leading slash)')"
                    />
                </div>
            </template>
            <template #actions="{ close }">
                <div class="flex justify-end gap-2">
                    <Button variant="outline" @click="close">{{ __('Cancel') }}</Button>
                    <Button
                        variant="solid"
                        :loading="cloningSpace"
                        @click="cloneSpace(close)"
                    >
                        {{ __('Start Cloning') }}
                    </Button>
                </div>
            </template>
        </Dialog>
    </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { createDocumentResource, createResource, Button, Dropdown, Dialog, Switch, FormControl, toast } from 'frappe-ui';
import { useTheme } from '../composables/useTheme';
import LucideChevronDown from '~icons/lucide/chevron-down';
import LucideSearch from '~icons/lucide/search';
import LucideMenu from '~icons/lucide/menu';
import LucideSun from '~icons/lucide/sun';
import LucideMoon from '~icons/lucide/moon';
import WikiDocumentList from '../components/WikiDocumentList.vue';
import ContributionBanner from '../components/ContributionBanner.vue';
import { useSidebarResize } from '../composables/useSidebarResize';
import { useChangeRequestStore } from '@/stores/changeRequest';
import { useUserStore } from '@/stores/user';

const props = defineProps({
    spaceId: {
        type: String,
        required: true,
    },
});

const route = useRoute();

const router = useRouter();
const crStore = useChangeRequestStore();
const userStore = useUserStore();

const isManager = computed(() => userStore.isWikiManager);
const isGuest = computed(() => !userStore.data?.is_logged_in || route.query.preview === '1');

// --- Mobile sidebar drawer ---
// On phones the px-width sidebar crushes the article into an unreadable column.
// Render it as an off-canvas drawer below md; md:* resets keep desktop untouched.
const mobileSidebarOpen = ref(false);
watch(() => route.fullPath, () => { mobileSidebarOpen.value = false; });

// --- Search ---
const searchQuery = ref('');
const searchResults = ref([]);
const searchLoading = ref(false);
const searchFocused = ref(false);
let searchDebounceTimer = null;

async function performSearch() {
    const q = (searchQuery.value || '').trim();
    if (!q) {
        searchResults.value = [];
        searchLoading.value = false;
        return;
    }
    searchLoading.value = true;
    try {
        const spaceRoot = guestSpaceInfo.data?.space?.root_group || space.doc?.root_group;
        const params = new URLSearchParams({ query: q });
        if (spaceRoot) params.set('space', spaceRoot);
        const resp = await fetch(`/api/method/wiki.frappe_wiki.doctype.wiki_document.search.search?${params.toString()}`);
        const data = await resp.json();
        searchResults.value = (data?.message?.results) || [];
    } catch (e) {
        searchResults.value = [];
    } finally {
        searchLoading.value = false;
    }
}

function handleSearchInput() {
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(performSearch, 300);
}

function openSearchResult(result) {
    searchQuery.value = '';
    searchResults.value = [];
    searchFocused.value = false;
    router.push({
        name: 'SpacePage',
        params: { spaceId: props.spaceId, pageId: result.name },
    });
}

// Theme: follows the OS by default; the toggle persists a manual choice.
const { isDark, toggleTheme } = useTheme();
const themeIcon = computed(() => isDark.value ? LucideSun : LucideMoon);

// Space switcher: list public spaces for guests, all spaces for logged-in users
const allSpacesForSwitcher = createResource({
	url: isGuest.value ? 'wiki.api.list_public_spaces' : 'frappe.client.get_list',
	makeParams() {
		if (isGuest.value) return {};
		return {
			doctype: 'Wiki Space',
			fields: ['name', 'space_name', 'route', 'is_published'],
			limit_page_length: 0,
			order_by: 'creation asc',
		};
	},
	auto: true,
});

const spaceSwitcherOptions = computed(() => {
	const list = allSpacesForSwitcher.data || [];
	return list.map((sp) => ({
		label: sp.space_name || sp.route || sp.name,
		onClick: () => {
			if (sp.name !== props.spaceId) {
				router.push({ name: 'SpaceDetails', params: { spaceId: sp.name } });
			}
		},
	}));
});

const showSettingsDialog = ref(false);
const showUpdateRoutesDialog = ref(false);
const showCloneSpaceDialog = ref(false);
const newRoute = ref('');
const updatingRoutes = ref(false);
const cloneRoute = ref('');
const cloningSpace = ref(false);

const enableFeedbackCollection = ref(false);
const updatingFeedbackSetting = ref(false);

const isPublished = ref(true);
const updatingPublishSetting = ref(false);

const sidebarRef = ref(null);
const { sidebarWidth, sidebarResizing, startResize } = useSidebarResize(sidebarRef);
const isTreeReordering = ref(false);

const currentPageId = computed(() => route.params.pageId || null);
const currentDraftKey = computed(() => route.params.docKey || null);

const space = createDocumentResource({
    doctype: 'Wiki Space',
    name: props.spaceId,
    auto: true,
    whitelistedMethods: {
        updateRoutes: 'update_routes',
        cloneWikiSpace: 'clone_wiki_space_in_background',
    },
});

// Guest-safe public space info + tree (hits allow_guest=True endpoints)
const guestSpaceInfo = createResource({
    url: 'wiki.api.wiki_space.get_public_space_info',
    makeParams() { return { space_id: props.spaceId }; },
    auto: true,
});

// When spaceId changes (via switcher), refetch guest info
watch(() => route.query.preview, () => {
        guestSpaceInfo.submit();
    });

    watch(() => props.spaceId, (newId, oldId) => {
    if (newId && newId !== oldId) {
        if (isGuest.value) {
            guestSpaceInfo.submit();
        } else {
            space.name = newId;
            space.reload();
        }
    }
});

watch(() => space.doc, (doc) => {
    if (doc) {
        enableFeedbackCollection.value = Boolean(doc.enable_feedback_collection);
        isPublished.value = Boolean(doc.is_published);
    }
}, { immediate: true });

async function updateFeedbackSetting(value) {
    updatingFeedbackSetting.value = true;
    try {
        await space.setValue.submit({
            enable_feedback_collection: value ? 1 : 0
        });
    } catch (error) {
        console.error('Failed to update feedback setting:', error);
        enableFeedbackCollection.value = !value;
    } finally {
        updatingFeedbackSetting.value = false;
    }
}

async function updatePublishSetting(value) {
    updatingPublishSetting.value = true;
    try {
        await space.setValue.submit({
            is_published: value ? 1 : 0
        });
    } catch (error) {
        console.error('Failed to update publish setting:', error);
        isPublished.value = !value;
    } finally {
        updatingPublishSetting.value = false;
    }
}

function openUpdateRoutesDialog() {
    newRoute.value = space.doc?.route || '';
    showUpdateRoutesDialog.value = true;
}

function openCloneSpaceDialog() {
    if (space.doc?.route) {
        cloneRoute.value = `${space.doc.route}-copy`;
    } else {
        cloneRoute.value = '';
    }
    showCloneSpaceDialog.value = true;
}

async function updateRoutes(close) {
    if (!newRoute.value?.trim()) {
        return;
    }

    updatingRoutes.value = true;
    try {
        await space.updateRoutes.submit({ new_route: newRoute.value.trim() });
        close();
        await space.reload();
        await refreshTree();
    } catch (error) {
        console.error('Failed to update routes:', error);
    } finally {
        updatingRoutes.value = false;
    }
}

async function cloneSpace(close) {
    if (!cloneRoute.value?.trim()) {
        return;
    }

    cloningSpace.value = true;
    try {
        await space.cloneWikiSpace.submit({ new_space_route: cloneRoute.value.trim() });
        toast.success(__('Cloning started in background'));
        close();
    } catch (error) {
        console.error('Failed to start clone:', error);
        toast.error(error.messages?.[0] || __('Error starting clone'));
    } finally {
        cloningSpace.value = false;
    }
}

const crTree = createResource({
    url: 'wiki.frappe_wiki.doctype.wiki_change_request.wiki_change_request.get_cr_tree',
    makeParams() {
        if (!crStore.currentChangeRequest?.name) {
            return null;
        }
        return { name: crStore.currentChangeRequest.name };
    },
    auto: false,
});

const treeData = computed(() => crTree.data || guestSpaceInfo.data?.tree);

// Auto-navigate to first leaf page when landing on a space without a selected page
function findFirstLeaf(nodes) {
    if (!nodes) return null;
    for (const n of nodes) {
        if (!n.is_group && n.document_name) return n;
        if (n.is_group && n.children && n.children.length) {
            const found = findFirstLeaf(n.children);
            if (found) return found;
        }
    }
    return null;
}

watch(treeData, (tree) => {
    if (!tree || !tree.children || !tree.children.length) return;
    if (currentPageId.value || currentDraftKey.value) return;
    const first = findFirstLeaf(tree.children);
    if (first && first.document_name) {
        router.replace({
            name: 'SpacePage',
            params: { spaceId: props.spaceId, pageId: first.document_name },
        });
    }
}, { immediate: true });


const changeTypeMap = computed(() => {
    const map = new Map();
    for (const change of crStore.changes) {
        map.set(change.doc_key, change.change_type);
    }
    return map;
});

watch(
    [() => space.doc, () => crStore.isChangeRequestMode, () => crStore.currentChangeRequest?.name],
    async ([doc, isMode, crName], oldValues) => {
        if (!doc || !isMode) return;

        const [oldDoc, , oldCrName] = oldValues || [];

        if (doc !== oldDoc) {
            crStore.currentChangeRequest = null;
        }

        if (!crStore.currentChangeRequest) {
            await crStore.initChangeRequest(props.spaceId);
            return;
        }

        if (crName && crName !== oldCrName) {
            await crStore.loadChanges();
            await crTree.reload();
        }
    },
    { immediate: true },
);

async function refreshTree() {
    if (!crStore.currentChangeRequest?.name) {
        return;
    }
    await crTree.reload();
    await crStore.loadChanges();
}

function handleReorderStateChange(isReordering) {
    isTreeReordering.value = Boolean(isReordering);
}

async function handleSubmitChangeRequest() {
    try {
        const result = await crStore.submitForReview();
        toast.success(__('Change request submitted for review'));
        if (result?.name) {
            router.push({ name: 'ChangeRequestReview', params: { changeRequestId: result.name } });
        }
    } catch (error) {
        toast.error(error.messages?.[0] || __('Error submitting for review'));
    }
}

async function handleArchiveChangeRequest() {
    try {
        await crStore.archiveChangeRequest();
        toast.success(__('Change request archived'));
        crStore.currentChangeRequest = null;
        await crStore.initChangeRequest(props.spaceId);
        await refreshTree();
    } catch (error) {
        toast.error(error.messages?.[0] || __('Error archiving change request'));
    }
}

function findNodeByDocKey(nodes, docKey) {
    if (!nodes) return null;
    for (const node of nodes) {
        if (node.doc_key === docKey) return node;
        const found = findNodeByDocKey(node.children, docKey);
        if (found) return found;
    }
    return null;
}

async function handleMergeChangeRequest() {
    const docKey = currentDraftKey.value;
    try {
        await crStore.mergeChangeRequest();
        toast.success(__('Change request merged'));
        crStore.currentChangeRequest = null;
        await crStore.initChangeRequest(props.spaceId);
        await refreshTree();

        if (docKey) {
            const node = findNodeByDocKey(treeData.value?.children, docKey);
            if (node?.document_name) {
                router.push({ name: 'SpacePage', params: { spaceId: props.spaceId, pageId: node.document_name } });
            }
        }
    } catch (error) {
        toast.error(error.messages?.[0] || __('Error merging change request'));
    }
}
</script>
