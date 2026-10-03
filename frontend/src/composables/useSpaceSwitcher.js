//// Neoffice — added file (no upstream equivalent). The space switcher: the options
//// the header's space name opens, so a writer (or a reader previewing) moves
//// between spaces without going back to the list first. The public reader's navbar
//// works the same way. It lived in SpaceDetails.vue before the v3 merge, then in
//// SpaceTreePanel.vue; 3.3.0 moved the tree into the sidebar (SpaceSidebar.vue) and
//// its header into another component again, so the options are built here, once,
//// for both headers.
import { computed } from 'vue';
import { useRouter } from 'vue-router';

import { useSpaceStore } from '../stores/space';

export function useSpaceSwitcher() {
	const router = useRouter();
	const spaceStore = useSpaceStore();

	// The list comes from the store, which knows whether the caller is a reader and
	// so which endpoint is allowed to answer (see stores/space.js).
	const switcherOptions = computed(() => {
		const options = (spaceStore.switcherSpaces || []).map((space) => ({
			label: space.space_name || space.name,
			// The active space is marked rather than hidden, so the list always
			// answers "where am I" as well as "where can I go".
			icon: space.name === spaceStore.spaceId ? 'check' : null,
			onClick: () => {
				if (space.name === spaceStore.spaceId) return;
				router.push({ name: 'SpaceDetails', params: { spaceId: space.name } });
			},
		}));

		// Readers have no Spaces list to go back to: it is an authoring screen. (A
		// git-synced space is read-only for authors too, and they do have a list, so
		// this keys off the reader flag and not off `readonly`.)
		if (!spaceStore.isReader) {
			options.push({
				label: __('All spaces'),
				icon: 'grid',
				onClick: () => router.push({ name: 'AllSpaces' }),
			});
		}

		return options;
	});

	return { switcherOptions };
}
