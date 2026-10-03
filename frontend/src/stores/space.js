import { createDocumentResource, createResource, toast } from 'frappe-ui';
import { defineStore } from 'pinia';
import { computed, ref, watch } from 'vue';

import router from '../router';
import { useSocket } from '../socket';
import { useChangeRequestStore } from './changeRequest';
import { useDraftWorkspaceStore } from './draftWorkspace';
import { toPublished } from './draftWorkspace/utils';
//// Neoffice — useUserStore added: the reader branch below keys off the authoring role.
import { useUserStore } from './user';

/**
 * The space the app is currently in: its document, its tree, and its sync
 * state.
 *
 * This used to live in SpaceDetails, which owned both the tree column and the
 * content column. The tree now renders in the app sidebar — a sibling of the
 * page, not a descendant — so the two columns need a shared owner above them
 * both. Everything here is derived from the route, so neither column has to
 * hand it to the other.
 */
export const useSpaceStore = defineStore('space', () => {
	const crStore = useChangeRequestStore();
	const draftStore = useDraftWorkspaceStore();
	//// Neoffice — added. Readers are anonymous visitors AND signed-in users without
	//// a wiki role (portal customers), plus an author previewing (?preview=1). They
	//// cannot call frappe.client.get / get_wiki_tree / get_space_capabilities (403),
	//// so every read below goes through our published-only endpoint for them. This
	//// logic lived in SpaceDetails.vue before upstream moved it into this store in
	//// 3.3.0; it is the same branch, re-homed.
	const userStore = useUserStore();

	const route = router.currentRoute;
	//// Neoffice — isReader: see the block above.
	const isReader = computed(
		() => !userStore.isWikiEditor || route.value.query.preview === '1',
	);
	const spaceId = computed(() => route.value.params.spaceId || null);
	const selectedPageId = computed(() => route.value.params.pageId || null);
	const selectedDraftKey = computed(() => route.value.params.docKey || null);

	// createDocumentResource caches by doctype+name, so re-entering a space
	// reuses the loaded document instead of refetching it.
	const space = ref(null);
	//// Neoffice — added. For a reader, ONE call (get_public_space_info) answers both
	//// the space and its tree, and refreshing the tree reloads it. Exposed as `.doc`
	//// below so nothing downstream cares which source it came from; the whitelisted
	//// methods of the editor resource (updateRoutes, cloneWikiSpace, syncNow) are
	//// editor actions a reader can never trigger.
	const publicInfo = ref(null);
	//// Neoffice — watches isReader as well as the space (see the comment above).
	watch(
		[spaceId, isReader],
		([id, reader]) => {
			if (id && reader) {
				const res = createResource({
					url: 'wiki.api.wiki_space.get_public_space_info',
					makeParams: () => ({ space_id: id }),
					auto: true,
				});
				publicInfo.value = res;
				space.value = {
					get doc() {
						return res.data?.space;
					},
					get loading() {
						return res.loading;
					},
					reload: () => res.reload(),
				};
				return;
			}
			publicInfo.value = null;
			space.value = id
				? createDocumentResource({
						doctype: 'Wiki Space',
						name: id,
						auto: true,
						whitelistedMethods: {
							updateRoutes: 'update_routes',
							cloneWikiSpace: 'clone_wiki_space_in_background',
							syncNow: 'sync_now',
						},
				  })
				: null;
		},
		{ immediate: true },
	);

	const doc = computed(() => space.value?.doc || null);
	const isLoaded = computed(() => Boolean(doc.value));

	// Git-synced spaces are read-only: the repo owns the content, so there is no
	// change request and no editing. The tree comes from the published live tree
	// instead of a CR.
	const isGitSynced = computed(() => Boolean(doc.value?.git_synced));

	// "Pending"/"Running" are transient internal states; show one friendly label.
	function syncStatusLabel(status) {
		return (
			{ Pending: __('Sync in progress'), Running: __('Sync in progress') }[
				status
			] ||
			status ||
			__('Sync in progress')
		);
	}

	// Editing a space is gated server-side; this only hides the UI.
	const canWriteSpace = ref(false);
	const canDeleteSpace = ref(false);
	// null until the capabilities land: a space is neither drafted nor read-only
	// until we know which, and picking either one early hydrates the wrong tree.
	const canContribute = ref(null);
	// A synced space is read-only for everyone, and a space this user cannot
	// contribute to is read-only for them: neither can open a change request.
	const isReadonly = computed(
		() => isGitSynced.value || canContribute.value === false,
	);
	// Not simply !isReadonly: while the capabilities are pending a space is
	// neither, and anything that opens a change request must wait for a yes.
	const canEdit = computed(
		() => !isGitSynced.value && canContribute.value === true,
	);
	const capabilitiesResource = createResource({
		url: 'wiki.api.get_space_capabilities',
		onSuccess: (data) => {
			canWriteSpace.value = Boolean(data?.can_write);
			canDeleteSpace.value = Boolean(data?.can_delete);
			canContribute.value = Boolean(data?.can_contribute);
		},
	});

	watch(
		[spaceId, isReader],
		([id, reader]) => {
			canWriteSpace.value = false;
			canDeleteSpace.value = false;
			canContribute.value = null;
			//// Neoffice — the capabilities endpoint needs a session, and a reader can
			//// neither write nor contribute: answer locally rather than eat a 403. Saying
			//// `false` (not leaving it null) is what sends them down the read-only tree
			//// path below instead of waiting forever for a yes.
			if (id && reader) {
				canContribute.value = false;
				return;
			}
			if (id) capabilitiesResource.submit({ space: id });
		},
		{ immediate: true },
	);

	const readonlyTreeResource = createResource({
		url: 'wiki.api.wiki_space.get_wiki_tree',
	});

	// The space the loaded readonly tree belongs to. The resource holds the
	// previous space's tree until the new one lands, so track the owner and let
	// `treeData` reject a stale cross-space tree.
	const readonlyTreeSpaceId = ref(null);

	// Adapt get_wiki_tree's (name-keyed) shape into the snake_case shape the tree
	// components consume. The Wiki Document `name` doubles as both the navigation
	// target (document_name) and the row key (doc_key) here — synced trees have
	// no CR overlay, so the internal doc_key is never needed.
	function adaptReadonlyNode(node) {
		return {
			doc_key: node.name,
			document_name: node.name,
			title: node.title,
			route: node.route,
			is_group: !!node.is_group,
			is_published: toPublished(node.is_published),
			is_external_link: false,
			external_url: null,
			children: (node.children || []).map(adaptReadonlyNode),
		};
	}

	const readonlyTreeData = computed(() => {
		//// Neoffice — get_public_space_info wraps the same payload as {space, tree}.
		const data = isReader.value
			? publicInfo.value?.data?.tree
			: readonlyTreeResource.data;
		if (!data) return null;
		return {
			root_group: data.root_group || '',
			children: (data.children || []).map(adaptReadonlyNode),
		};
	});

	async function loadReadonlyTree() {
		const target = spaceId.value;
		//// Neoffice — a reader's tree comes with the space (see publicInfo above).
		if (isReader.value) {
			await publicInfo.value?.reload();
		} else {
			await readonlyTreeResource.submit({ space_id: target });
		}
		readonlyTreeSpaceId.value = target;
	}

	// Tree, page drafts, and pending mutations live in the draft workspace store.
	// We hydrate it on space load and after merge/archive transitions; routine
	// edits update the store optimistically without a server round-trip.
	// `treeAsLegacy` is an empty-but-truthy object before hydration, so gate on
	// `hasLoadedTree` — otherwise the sidebar flashes "No pages yet" instead of
	// the loading skeleton while the tree is being fetched.
	const treeData = computed(() => {
		// Both sources outlive a space switch: the readonly resource keeps the old
		// space's tree until the new fetch lands, and draftStore is a global
		// singleton still hydrated for the previous space. Returning a stale tree
		// here makes auto-open navigate into the wrong space's page, so gate each
		// on belonging to the current space.
		if (isReadonly.value) {
			return readonlyTreeSpaceId.value === spaceId.value
				? readonlyTreeData.value
				: null;
		}
		if (draftStore.spaceId !== spaceId.value) return null;
		return draftStore.hasLoadedTree ? draftStore.treeAsLegacy : null;
	});

	const changeTypeMap = computed(() => {
		const map = new Map();
		for (const change of crStore.changes) {
			map.set(change.doc_key, change.change_type);
		}
		return map;
	});

	// Merging while the tree is mid-reorder would race the pending moves, so the
	// tree reports its reorder state up here for the banner to disable on.
	const isTreeReordering = ref(false);
	function setTreeReordering(reordering) {
		isTreeReordering.value = Boolean(reordering);
	}

	const syncing = ref(false);
	// Guards the auto first-sync so the watch can't enqueue it (and toast) twice
	// while the document re-renders before last_sync_status lands.
	const firstSyncKicked = ref(false);
	// Cancels an in-flight poll when the user navigates away mid-sync.
	let syncPollCancelled = false;

	watch(spaceId, () => {
		firstSyncKicked.value = false;
		syncPollCancelled = true;
		syncing.value = false;
	});

	// The sync runs on the long queue, so poll the doc until it reports a
	// terminal status — refreshing the tree each tick so pages (and the
	// in-progress state) update as soon as the sync lands, however long it takes.
	async function pollSyncUntilDone({ tries = 30, interval = 2000 } = {}) {
		for (let i = 0; i < tries && !syncPollCancelled; i++) {
			await new Promise((resolve) => setTimeout(resolve, interval));
			if (syncPollCancelled) return;
			await Promise.all([space.value?.reload(), loadReadonlyTree()]);
			const status = doc.value?.last_sync_status;
			if (status === 'Success' || status === 'Error') return;
		}
	}

	async function syncNow({ silent = false } = {}) {
		syncing.value = true;
		syncPollCancelled = false;
		try {
			await space.value.syncNow.submit();
			if (!silent)
				toast.success(__('Sync started — pulling the latest from GitHub'));
			// Realtime (below) normally resolves this first; the poll is the
			// fallback for when the socket isn't connected.
			await pollSyncUntilDone();
		} catch (error) {
			toast.error(error.messages?.[0] || __('Could not start sync'));
		} finally {
			syncing.value = false;
		}
	}

	// Live sync updates from the background job (broadcast site-wide by
	// wiki.wiki.git_sync._publish_sync_status) — reflect progress instantly and
	// refresh the tree on completion, without waiting on the poll fallback. Also
	// covers webhook-triggered syncs, which never go through syncNow() here.
	function onSyncRealtime(data) {
		if (!data || data.space !== spaceId.value) return;
		if (doc.value) doc.value.last_sync_status = data.status;
		if (data.status === 'Success' || data.status === 'Error') {
			syncPollCancelled = true;
			syncing.value = false;
			Promise.all([space.value?.reload(), loadReadonlyTree()]);
		}
	}

	// The store outlives every space route, so this subscribes once instead of
	// riding a component's lifecycle.
	useSocket()?.on('wiki_git_sync_update', onSyncRealtime);

	// Keyed on the two fields that decide which workspace to build — never on
	// `doc` itself. `setValue` replaces the document with a fresh object on
	// every field write, so watching the document made a logo shuffle, a rename
	// or a publish toggle look exactly like a move to another space: the change
	// request was dropped, the draft workspace reset and the tree refetched,
	// flashing the sidebar and the breadcrumbs for a change that touched
	// neither. Sources are passed as an array so Vue compares them one by one.
	watch(
		[
			() => doc.value?.name,
			() => doc.value?.git_synced,
			() => crStore.isChangeRequestMode,
			canContribute,
		],
		async ([name, gitSynced, isMode, mayContribute], previous) => {
			if (!name || !isMode) return;
			// Contributions can be switched off for a space, or withheld from this
			// user. Opening a change request would be refused server-side, leaving
			// the tree stuck on its loading skeleton.
			if (mayContribute !== true) return;
			// Synced spaces never open a change request — they hydrate the
			// read-only tree path below instead.
			if (gitSynced) return;

			// A different space, not a different revision of the same one.
			if (name !== previous?.[0]) {
				crStore.currentChangeRequest = null;
				draftStore.reset();
			}

			await draftStore.hydrate(spaceId.value);
		},
		{ immediate: true },
	);

	// Read-only tree hydration: git-synced spaces, and anyone who cannot open a
	// change request here. Loads the published live tree (no CR) and, for a
	// never-synced space (e.g. just created), kicks off the first sync so its
	// content appears without a manual click.
	// Same keying as above, and for the same reason: a field write on a synced
	// space must not refetch its tree.
	watch(
		[() => doc.value?.name, () => doc.value?.git_synced, canContribute],
		async ([name, gitSynced, mayContribute]) => {
			const currentDoc = doc.value;
			if (!name || !currentDoc) return;
			if (!gitSynced && mayContribute !== false) return;
			await loadReadonlyTree();
			if (!gitSynced) return;
			// First-ever sync of a freshly-created space: kick it once, silently —
			// the "created successfully" toast already covers the action, and the
			// status badge reflects progress. The guard stops a double-enqueue.
			if (
				!firstSyncKicked.value &&
				!currentDoc.last_sync_time &&
				!['Running', 'Pending', 'Success'].includes(currentDoc.last_sync_status)
			) {
				firstSyncKicked.value = true;
				syncNow({ silent: true });
			}
		},
		{ immediate: true },
	);

	async function refreshTree() {
		if (isReadonly.value) {
			await loadReadonlyTree();
			return;
		}
		if (!crStore.currentChangeRequest?.name) {
			return;
		}
		await draftStore.reloadTree();
		await draftStore.reloadChanges();
	}

	//// Neoffice — added. Spaces to offer in the space switcher. The caller picks the
	//// endpoint: readers cannot list Wiki Space through frappe.client.get_list (403),
	//// so they go through our guest-safe endpoint, which returns the published spaces
	//// the caller may actually read. Never widen this to a plain get_list for them:
	//// that is precisely how a client instance would advertise its internal spaces to
	//// the open internet.
	const readerSwitcher = createResource({ url: 'wiki.api.list_public_spaces' });
	const editorSwitcher = createResource({
		url: 'frappe.client.get_list',
		params: {
			doctype: 'Wiki Space',
			fields: ['name', 'space_name', 'route'],
			order_by: 'switcher_order asc, space_name asc',
			limit_page_length: 0,
		},
	});
	watch(
		[spaceId, isReader],
		([id, reader]) => {
			if (!id) return;
			(reader ? readerSwitcher : editorSwitcher).reload();
		},
		{ immediate: true },
	);
	const switcherSpaces = computed(
		() => (isReader.value ? readerSwitcher.data : editorSwitcher.data) || [],
	);

	return {
		spaceId,
		//// Neoffice — isReader and switcherSpaces are ours (see above).
		isReader,
		switcherSpaces,
		space,
		doc,
		isLoaded,
		isGitSynced,
		syncStatusLabel,
		canWriteSpace,
		canDeleteSpace,
		canContribute,
		isReadonly,
		canEdit,
		selectedPageId,
		selectedDraftKey,
		treeData,
		changeTypeMap,
		isTreeReordering,
		setTreeReordering,
		syncing,
		syncNow,
		refreshTree,
	};
});
