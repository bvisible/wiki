<template>
	<div class="flex h-full min-h-0 flex-col">
		<!-- Header: fixed 48px region so its bottom border lines up with the
		     main column's banner/header bars. -->
		<div
			v-if="!compactHeader"
			class="flex h-12 shrink-0 items-center gap-1 border-b border-outline-gray-2 px-2"
		>
			<!-- //// Neoffice — v-if added: readers have no Spaces list to go back to (it is
			     an authoring screen; the router sends them to the first public space), so
			     the arrow would only loop them onto the page they are on. -->
			<Tooltip v-if="!spaceStore.isReader" :text="__('Back to All Spaces')">
				<Button
					variant="ghost"
					icon="lucide-arrow-left"
					:aria-label="__('Back to All Spaces')"
					:route="{ name: 'AllSpaces' }"
				/>
			</Tooltip>
			<!-- //// Neoffice — the space name is a switcher, the way the public
			     reader's navbar already works. Upstream offers a lone back arrow to the
			     Spaces list, which is a dead end for a reader and one click too many for
			     everyone else. We had this dropdown before the v3 merge; it lived in
			     SpaceDetails.vue, in the header region upstream rewrote into this
			     component, so it went out with the container. -->
			<Dropdown
				v-if="switcherOptions.length > 1"
				:options="switcherOptions"
				placement="bottom-start"
				class="min-w-0 flex-1"
			>
				<button
					type="button"
					class="flex w-full min-w-0 items-center gap-1 rounded-4 px-1 py-1 text-left hover:bg-surface-gray-3"
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
			<div v-else class="min-w-0 flex-1">
				<div class="truncate text-base-medium leading-none text-ink-gray-8">
					{{ spaceName || spaceId }}
				</div>
				<div class="mt-0.5 truncate text-sm leading-none text-ink-gray-6">
					{{ spaceRoute }}
				</div>
			</div>
			<Tooltip :text="__('View space')">
				<Button
					v-if="spaceRoute"
					variant="ghost"
					icon="lucide-external-link"
					:aria-label="__('View space')"
					:href="'/' + spaceRoute"
				/>
			</Tooltip>
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
			<!-- //// Neoffice — v-if added, gated on can_write (the space's
			     writers). Upstream renders this gear unconditionally: on neoservice an
			     anonymous visitor got the full Space Settings panel — Published toggle,
			     feedback widget, logo upload, bulk route rewrite, Clone space, and the
			     Permissions tab. The writes were refused server-side, but none of it is
			     a reader's business. Our pre-merge guard (v-if="!isGuest") lived in
			     SpaceDetails.vue and did not survive the v3 header refactor — it
			     survived the 3.3.0 one as `canManageTabs`, which is gone with the
			     tabs, so it keys off the space store's own capability now. -->
			<Tooltip v-if="spaceStore.canWriteSpace" :text="__('Space settings')">
				<Button
					variant="ghost"
					icon="lucide-settings"
					:aria-label="__('Space settings')"
					@click="emit('open-settings')"
				/>
			</Tooltip>
		</div>

		<!-- The list owns the scroller: its search row and New page footer have
		     to stay put while the tree between them scrolls. -->
		<div v-if="spaceLoaded && treeData" class="flex min-h-0 flex-1 flex-col pt-2">
			<WikiDocumentList
				class="min-h-0 flex-1"
				:tree-data="treeData"
				:change-type-map="changeTypeMap"
				:space-id="spaceId"
				:readonly="readonly"
				:root-node="treeData.root_group || ''"
				:selected-page-id="selectedPageId"
				:selected-draft-key="selectedDraftKey"
				:space-route="spaceRoute"
				@refresh="emit('refresh')"
				@reorder-state-change="emit('reorder-state-change', $event)"
			>
				<template v-if="$slots['above-footer']" #above-footer>
					<slot name="above-footer" />
				</template>
			</WikiDocumentList>
		</div>
		<div v-else class="flex-1 overflow-auto p-2">
			<!-- Sidebar tree skeleton -->
			<div class="space-y-1">
				<div
					v-for="i in 8"
					:key="i"
					class="flex items-center gap-2 px-2 py-1.5 rounded-4"
				>
					<Skeleton class="size-4 rounded-4 shrink-0" />
					<Skeleton
						class="h-3.5 rounded-4"
						:style="{ width: `${60 + (i % 3) * 25}%` }"
					/>
				</div>
				<div
					v-for="i in 4"
					:key="'nested-' + i"
					class="flex items-center gap-2 px-2 py-1.5 rounded-4 ml-6"
				>
					<Skeleton class="size-4 rounded-4 shrink-0" />
					<Skeleton
						class="h-3.5 rounded-4"
						:style="{ width: `${50 + (i % 2) * 30}%` }"
					/>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
//// Neoffice — Dropdown added for the space switcher this header carries (see the
//// template above); its options come from useSpaceSwitcher().
import { Button, Dropdown, Skeleton, Tooltip } from 'frappe-ui';

//// Neoffice — added: the theme toggle we put back in this header needs it.
import { useTheme } from '../composables/useTheme';
import { useSpaceSwitcher } from '../composables/useSpaceSwitcher';
//// Neoffice — the can_write gate on the gear and the reader flag come from the space store.
import { useSpaceStore } from '../stores/space';
import WikiDocumentList from './WikiDocumentList.vue';

defineProps({
	spaceId: { type: String, required: true },
	spaceName: { type: String, default: '' },
	spaceRoute: { type: String, default: '' },
	spaceLoaded: { type: Boolean, default: false },
	treeData: { type: Object, default: null },
	changeTypeMap: { type: Map, default: () => new Map() },
	readonly: { type: Boolean, default: false },
	selectedPageId: { type: String, default: null },
	selectedDraftKey: { type: String, default: null },
	compactHeader: { type: Boolean, default: false },
});

const emit = defineEmits(['refresh', 'reorder-state-change', 'open-settings']);

//// Neoffice — everything below is ours: the space switcher and the theme
//// toggle that used to live in this header before the v3 refactor.
const spaceStore = useSpaceStore();
const { switcherOptions } = useSpaceSwitcher();
const { themeIcon, toggleTheme } = useTheme();
</script>
