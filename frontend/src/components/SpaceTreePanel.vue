<template>
	<div class="flex h-full min-h-0 flex-col">
		<!-- Header: fixed 48px region so its bottom border lines up with the
		     main column's banner/header bars. -->
		<div
			v-if="!compactHeader"
			class="flex h-12 shrink-0 items-center gap-1 border-b border-outline-gray-2 px-2"
		>
			<!-- //// Neoffice — the space name is a switcher, the way the public
			     reader's navbar already works. Upstream offers a lone back arrow to
			     the Spaces list, which is a dead end for a reader and one click too
			     many for everyone else. We had this dropdown before the v3 merge; it
			     lived in SpaceDetails.vue, in the header region upstream rewrote
			     into this component, so it went out with the container. -->
			<Dropdown
				v-if="switcherOptions.length > 1"
				:options="switcherOptions"
				placement="bottom-start"
				class="min-w-0 flex-1"
			>
				<button
					type="button"
					class="flex w-full min-w-0 items-center gap-1 rounded px-1 py-1 text-left hover:bg-surface-gray-3"
					:title="__('Switch wiki space')"
				>
					<span class="min-w-0 flex-1">
						<span class="block truncate text-base-medium leading-none text-ink-gray-8">
							{{ spaceName || spaceId }}
						</span>
						<span class="mt-0.5 block truncate text-sm leading-none text-ink-gray-6">
							{{ spaceRoute }}
						</span>
					</span>
					<span class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
				</button>
			</Dropdown>
			<div v-else class="min-w-0 flex-1 px-1">
				<div class="truncate text-base-medium leading-none text-ink-gray-8">
					{{ spaceName || spaceId }}
				</div>
				<div class="mt-0.5 truncate text-sm leading-none text-ink-gray-6">
					{{ spaceRoute }}
				</div>
			</div>
			<Button
				v-if="spaceRoute"
				variant="ghost"
				icon="external-link"
				:title="__('View Space')"
				:link="'/' + spaceRoute"
			/>
			<!-- //// Neoffice — added. The theme toggle used to sit in this header and
			     was reachable by everyone. Upstream moved it into the app sidebar,
			     which MainLayout does not mount for a reader — so readers lost the
			     ability to switch to dark at all. -->
			<Button
				variant="ghost"
				:icon="themeIcon"
				:title="__('Toggle Theme')"
				@click="toggleTheme"
			/>
			<!-- //// Neoffice — gated on canManageTabs (the space's can_write). Upstream
			     renders this gear unconditionally: on neoservice an anonymous visitor
			     got the full Space Settings panel — Published toggle, feedback widget,
			     logo upload, bulk route rewrite, Clone space, and the Permissions tab.
			     The writes were refused server-side, but none of it is a reader's
			     business. Our pre-merge guard (v-if="!isGuest") lived in
			     SpaceDetails.vue and did not survive the v3 header refactor. -->
			<!-- //// Neoffice — the v-if on the next line is ours; the reason is in the
			     //// comment just above. -->
			<Button
				v-if="canManageTabs"
				variant="ghost"
				icon="settings"
				:title="__('Settings')"
				@click="emit('open-settings')"
			/>
		</div>

		<div v-if="spaceLoaded && treeData" class="flex-1 overflow-auto px-2 pt-2 pb-10">
			<WikiDocumentList
				:tree-data="treeData"
				:change-type-map="changeTypeMap"
				:space-id="spaceId"
				:readonly="readonly"
				:root-node="treeData.root_group || ''"
				:selected-page-id="selectedPageId"
				:selected-draft-key="selectedDraftKey"
				:can-manage-tabs="canManageTabs"
				:space-root-node="spaceRootNode"
				:space-route="spaceRoute"
				@refresh="emit('refresh')"
				@reorder-state-change="emit('reorder-state-change', $event)"
			/>
		</div>
		<div v-else class="flex-1 overflow-auto p-2">
			<!-- Sidebar tree skeleton -->
			<div class="space-y-1">
				<div
					v-for="i in 8"
					:key="i"
					class="flex items-center gap-2 px-2 py-1.5 rounded"
				>
					<Skeleton class="size-4 rounded shrink-0" />
					<Skeleton
						class="h-3.5 rounded"
						:style="{ width: `${60 + (i % 3) * 25}%` }"
					/>
				</div>
				<div
					v-for="i in 4"
					:key="'nested-' + i"
					class="flex items-center gap-2 px-2 py-1.5 rounded ml-6"
				>
					<Skeleton class="size-4 rounded shrink-0" />
					<Skeleton
						class="h-3.5 rounded"
						:style="{ width: `${50 + (i % 2) * 30}%` }"
					/>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
//// Neoffice — Dropdown, computed and useRouter added for the space switcher
//// this header now carries (see the template above).
import { Button, Dropdown, Skeleton } from 'frappe-ui';
import { computed } from 'vue';
import { useRouter } from 'vue-router';

//// Neoffice — added: the theme toggle we put back in this header needs it.
import { useTheme } from '../composables/useTheme';
import WikiDocumentList from './WikiDocumentList.vue';

//// Neoffice — props captured (upstream calls defineProps without binding it):
//// the switcher and the toggle below read props.spaceId / props.spaces.
const props = defineProps({
	spaceId: { type: String, required: true },
	spaceName: { type: String, default: '' },
	spaceRoute: { type: String, default: '' },
	spaceLoaded: { type: Boolean, default: false },
	// Already narrowed to the active tab's subtree by useSpaceTabs; `root_group`
	// is that tab, so top-level drops reparent into it.
	treeData: { type: Object, default: null },
	changeTypeMap: { type: Map, default: () => new Map() },
	readonly: { type: Boolean, default: false },
	selectedPageId: { type: String, default: null },
	selectedDraftKey: { type: String, default: null },
	canManageTabs: { type: Boolean, default: false },
	// The space root, where a new tab must be parented regardless of which tab
	// is currently being browsed.
	spaceRootNode: { type: String, default: '' },
	compactHeader: { type: Boolean, default: false },
	//// Neoffice — added. Spaces to offer in the header switcher. The parent
	//// fetches them, because only it knows whether the caller is a reader (and
	//// so which endpoint is allowed to answer).
	spaces: { type: Array, default: () => [] },
});

const emit = defineEmits(['refresh', 'reorder-state-change', 'open-settings']);

//// Neoffice — everything below is ours: the space switcher and the theme
//// toggle that used to live in this header before the v3 refactor.
const router = useRouter();
const { themeIcon, toggleTheme } = useTheme();

const switcherOptions = computed(() => {
	const options = (props.spaces || []).map((space) => ({
		label: space.space_name || space.name,
		//// The active space is marked rather than hidden, so the list always
		//// answers "where am I" as well as "where can I go".
		icon: space.name === props.spaceId ? 'check' : null,
		onClick: () => {
			if (space.name === props.spaceId) return;
			router.push({ name: 'SpaceDetails', params: { spaceId: space.name } });
		},
	}));

	//// Readers have no Spaces list to go back to — it is an authoring screen.
	if (!props.readonly) {
		options.push({
			label: __('All spaces'),
			icon: 'grid',
			onClick: () => router.push({ name: 'SpaceList' }),
		});
	}

	return options;
});
</script>
