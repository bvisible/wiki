<template>
	<!-- Level 1 of the drill-in model: the sidebar becomes the space. Fixed
	     width and no collapse toggle — the tree is the navigation here, so
	     collapsing it would leave the space with no way around.

	     `aside` is what this region is; `contents` keeps the wrapper out of the
	     shell's flex row so Sidebar still sizes itself. -->
	<aside class="contents">
		<Sidebar width="260px" disable-collapse>
			<div
				class="flex h-12 shrink-0 items-center gap-1.5 border-b border-outline-gray-2 px-2"
			>
				<!-- //// Neoffice — v-if added: readers have no All Spaces list to go back to
				     (an authoring screen; the router sends them to the first public space),
				     so the arrow would only loop them onto the page they are on. -->
				<Tooltip v-if="!spaceStore.isReader" :text="__('Back to All Spaces')">
					<Button
						variant="ghost"
						icon="lucide-chevron-left"
						:aria-label="__('Back to All Spaces')"
						:route="{ name: 'AllSpaces' }"
					/>
				</Tooltip>
				<!-- The header tile is the same control as the settings row: a
				     space's mark is worth changing from where you look at it.
				     A space you cannot write still shows its mark, unclickable. -->
				<SpaceIdentityPicker
					v-if="spaceStore.canWriteSpace"
					:identity="spaceStore.doc || {}"
					:label="spaceName"
					size="lg"
					@update="saveIdentity"
				/>
				<SpaceAvatar
					v-else
					:space="spaceStore.doc || {}"
					:label="spaceName"
					size="lg"
				/>
				<!-- //// Neoffice — the space name is a switcher, the way the public reader's
				     navbar already works (see composables/useSpaceSwitcher.js). Upstream shows
				     a plain name here, and its only way to another space is the arrow back to
				     All Spaces, which a reader does not even have. -->
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
						<span class="min-w-0 flex-1 truncate text-base-medium leading-tighter text-ink-gray-8">
							{{ spaceName }}
						</span>
						<span class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
					</button>
				</Dropdown>
				<span
					v-else
					class="min-w-0 flex-1 truncate text-base-medium leading-tighter text-ink-gray-8"
				>
					{{ spaceName }}
				</span>
				<Dropdown :options="spaceActions" placement="right">
					<Button
						variant="ghost"
						icon="lucide-more-horizontal"
						:title="__('Space actions')"
					/>
				</Dropdown>
			</div>

			<!-- //// Neoffice — v-if added: readers have nothing to contribute from (no draft,
			     no change request, no settings); the strip carries submit / discard /
			     merge / sync. -->
			<SpaceModeStrip v-if="!spaceStore.isReader" />

			<!-- Sidebar is a flex column, so the tree needs a sized track to scroll
			     inside rather than the sidebar's full height. -->
			<div class="flex min-h-0 flex-1 flex-col">
				<SpaceTreePanel
					:space-id="spaceId"
					:space-name="spaceStore.doc?.space_name"
					:space-route="spaceStore.doc?.route"
					:space-loaded="spaceStore.isLoaded"
					:tree-data="spaceStore.treeData"
					:space-root-node="spaceStore.treeData?.root_group || ''"
					:change-type-map="spaceStore.changeTypeMap"
					:readonly="spaceStore.isReadonly"
					:selected-page-id="spaceStore.selectedPageId"
					:selected-draft-key="spaceStore.selectedDraftKey"
					compact-header
					@refresh="spaceStore.refreshTree"
					@reorder-state-change="spaceStore.setTreeReordering"
				>
					<!-- The sync notice floats over the bottom of the tree rather
					     than taking a row of its own. The sidebar is one vertical
					     stack, so anything in flow above the tree shoves it down
					     every time the notice comes and goes — a jump on every
					     save, for a message usually gone in a second. -->
					<template #above-footer>
						<SyncStateAlert class="shadow-md" />
					</template>
				</SpaceTreePanel>
			</div>
		</Sidebar>
	</aside>
</template>

<script setup>
import { Button, Dropdown, Sidebar, Tooltip } from 'frappe-ui';
import { computed } from 'vue';

import { useSpaceIdentitySaver } from '../composables/useSpaceIdentitySaver.js';
import { useSpaceSettings } from '../composables/useSpaceSettings';
//// Neoffice — the space name in the header is a switcher (see the template).
import { useSpaceSwitcher } from '../composables/useSpaceSwitcher';
import { useSpaceStore } from '../stores/space';
import SpaceAvatar from './SpaceAvatar.vue';
import SpaceIdentityPicker from './SpaceIdentityPicker.vue';
import SpaceModeStrip from './SpaceModeStrip.vue';
import SpaceTreePanel from './SpaceTreePanel.vue';
import SyncStateAlert from './SyncStateAlert.vue';

const props = defineProps({
	spaceId: { type: String, required: true },
});

const spaceStore = useSpaceStore();
const { open: openSpaceSettings } = useSpaceSettings();
//// Neoffice — the options of the space switcher in the header (see the template).
const { switcherOptions } = useSpaceSwitcher();

const spaceName = computed(
	() => spaceStore.doc?.space_name || spaceStore.doc?.name || props.spaceId,
);

// The store's document resource is replaced when the route moves to another
// space, so the saver reads it each time rather than closing over one.
const saveIdentity = useSpaceIdentitySaver(() => spaceStore.space);

const spaceActions = computed(() => {
	const options = [
		{
			label: __('Space settings'),
			icon: 'lucide-settings',
			onClick: openSpaceSettings,
		},
	];
	//// Neoffice — "Space settings" is offered to the space's writers only. Upstream lists it
	//// for everyone who can see the space; on neoservice an anonymous visitor got the full
	//// Space Settings panel (Published toggle, feedback widget, logo upload, bulk route
	//// rewrite, Clone space, Permissions tab). The writes were refused server-side, but none
	//// of it is a reader's business. (Upstream's own array above, so the diff stays one line.)
	if (!spaceStore.canWriteSpace) options.shift();
	if (spaceStore.doc?.route) {
		options.push({
			label: __('View live site'),
			icon: 'lucide-external-link',
			onClick: () => window.open(`/${spaceStore.doc.route}`, '_blank'),
		});
	}
	if (spaceStore.isGitSynced) {
		options.push({
			label: __('Sync now'),
			icon: 'lucide-refresh-cw',
			onClick: () => spaceStore.syncNow(),
		});
	}
	return options;
});
</script>
