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

const EDITABLE_STATUSES = ['Draft', 'Changes Requested'];
const REVIEW_STATUSES = ['In Review', 'Approved'];

// Per tab, so a reload comes back to the change request in review the user was
// editing, and another tab is not pulled into it.
const reviewEditKey = (spaceId) => `wiki:editing-in-review:${spaceId}`;

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
	// shows the loaded document until the bootstrap below refreshes it.
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
						auto: false,
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

	// A change request in review is edited only after its Edit button, never
	// because the user happens to own one.
	const reviewEditName = ref(null);
	const isEditingInReview = computed(() => {
		const changeRequest = crStore.currentChangeRequest;
		return (
			canEdit.value &&
			changeRequest?.wiki_space === spaceId.value &&
			changeRequest.name === reviewEditName.value &&
			REVIEW_STATUSES.includes(changeRequest.status)
		);
	});

	const isEditing = computed(() => {
		const changeRequest = crStore.currentChangeRequest;
		if (!canEdit.value || changeRequest?.wiki_space !== spaceId.value) {
			return false;
		}
		return (
			Boolean(crStore.finalizing) ||
			EDITABLE_STATUSES.includes(changeRequest.status) ||
			isEditingInReview.value
		);
	});
	const isReading = computed(() => canEdit.value && !isEditing.value);
	const showsLiveTree = computed(() => isReadonly.value || isReading.value);

	const readonlyTreeResource = createResource({
		url: 'wiki.api.wiki_space.get_wiki_tree',
		method: 'GET',
	});

	const readonlyTreeSpaceId = ref(null);

	// The space document, the capabilities and the user's draft, in one round
	// trip instead of three in a row.
	const bootstrapResource = createResource({
		url: 'wiki.api.wiki_space.get_space_bootstrap',
		method: 'GET',
	});

	async function loadSpace(id) {
		const inReview = sessionStorage.getItem(reviewEditKey(id));
		const params = { space_id: id };
		if (inReview) params.change_request = inReview;
		const data = await bootstrapResource.submit(params).catch(() => null);
		if (!data || id !== spaceId.value) return;
		space.value.setDoc(data.doc);
		space.value.originalDoc = JSON.parse(JSON.stringify(data.doc));
		canWriteSpace.value = Boolean(data.capabilities.can_write);
		canDeleteSpace.value = Boolean(data.capabilities.can_delete);
		canContribute.value = Boolean(data.capabilities.can_contribute);
		const changeRequest = data.change_request;
		if (inReview && changeRequest?.name !== inReview) {
			sessionStorage.removeItem(reviewEditKey(id));
		}
		reviewEditName.value =
			inReview && changeRequest?.name === inReview ? inReview : null;
		if (changeRequest) draftStore.hydrate(id, changeRequest);
		else if (crStore.currentChangeRequest) stopEditing();
	}

	//// Neoffice — watches isReader as well as the space: a reader answers locally below.
	watch(
		[spaceId, isReader],
		async ([id, reader]) => {
			canWriteSpace.value = false;
			canDeleteSpace.value = false;
			canContribute.value = null;
			//// Neoffice — the bootstrap needs a session and the right to read the space
			//// document, and a reader can neither write nor contribute: answer locally
			//// rather than eat a 403. Saying `false` (not leaving it null) is what sends
			//// them down the read-only tree path below instead of waiting forever for a yes.
			if (id && reader) {
				canContribute.value = false;
				return;
			}
			if (!id) return;
			const changeRequest = crStore.currentChangeRequest;
			if (changeRequest && changeRequest.wiki_space !== id) stopEditing();
			await loadSpace(id);
		},
		{ immediate: true },
	);

	// A review inside the space can merge or reopen the draft the space shows.
	async function reload() {
		await loadSpace(spaceId.value);
		if (showsLiveTree.value) await loadReadonlyTree();
	}

	const createChangeRequestResource = createResource({
		url: 'wiki.frappe_wiki.doctype.wiki_change_request.wiki_change_request.create_change_request',
	});

	async function startEditing({ title, description }) {
		const id = spaceId.value;
		const changeRequest = await createChangeRequestResource.submit({
			wiki_space: id,
			title,
			description,
		});
		await draftStore.hydrate(id, changeRequest);
		return changeRequest;
	}

	async function editInReview(changeRequest) {
		const id = changeRequest.wiki_space;
		sessionStorage.setItem(reviewEditKey(id), changeRequest.name);
		reviewEditName.value = changeRequest.name;
		// Entering the space bootstraps it; only an open space needs this here.
		if (id === spaceId.value) await draftStore.hydrate(id, changeRequest);
	}

	// Back to the user's own draft, if they have one.
	async function stopEditingInReview() {
		const id = crStore.currentChangeRequest?.wiki_space;
		if (!id) return;
		sessionStorage.removeItem(reviewEditKey(id));
		reviewEditName.value = null;
		stopEditing();
		if (id === spaceId.value) await loadSpace(id);
	}

	function stopEditing() {
		crStore.currentChangeRequest = null;
		crStore.clearChanges();
		draftStore.reset({ keepTree: true });
		readonlyTreeSpaceId.value = null;
	}

	function adaptReadonlyNode(node) {
		return {
			doc_key: node.doc_key,
			document_name: node.name,
			title: node.title,
			route: node.route,
			is_group: !!node.is_group,
			is_published: toPublished(node.is_published),
			is_external_link: Boolean(node.is_external_link),
			external_url: node.external_url || null,
			children: (node.children || []).map(adaptReadonlyNode),
		};
	}

	const liveTreeData = computed(() => {
		//// Neoffice — get_public_space_info wraps the same payload as {space, tree}.
		const data = isReader.value
			? publicInfo.value?.data?.tree
			: readonlyTreeResource.data;
		if (!data || readonlyTreeSpaceId.value !== spaceId.value) return null;
		return {
			root_group: data.root_key || '',
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

	const hasDraftTree = computed(
		() => draftStore.spaceId === spaceId.value && draftStore.hasLoadedTree,
	);

	const treeData = computed(() => {
		if (showsLiveTree.value) {
			if (liveTreeData.value || !hasDraftTree.value) return liveTreeData.value;
			return draftStore.treeAsLegacy;
		}
		if (hasDraftTree.value) return draftStore.treeAsLegacy;
		if (liveTreeData.value) return liveTreeData.value;
		if (draftStore.spaceId !== spaceId.value) return null;
		return draftStore.hasStaleTree ? draftStore.staleTreeAsLegacy : null;
	});

	const isTreeStale = computed(
		() =>
			!showsLiveTree.value &&
			!hasDraftTree.value &&
			!liveTreeData.value &&
			draftStore.spaceId === spaceId.value &&
			draftStore.hasStaleTree,
	);

	const changeTypeMap = computed(() => {
		const map = new Map();
		// A merge from the review page clears the change request but not its changes.
		if (showsLiveTree.value) return map;
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

	watch(
		[() => doc.value?.name, () => doc.value?.git_synced, showsLiveTree],
		async ([name, gitSynced, live]) => {
			const currentDoc = doc.value;
			if (!name || !currentDoc || !live) return;
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
		if (showsLiveTree.value) {
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
		isEditing,
		isEditingInReview,
		isReading,
		startEditing,
		stopEditing,
		editInReview,
		stopEditingInReview,
		selectedPageId,
		selectedDraftKey,
		treeData,
		isTreeStale,
		changeTypeMap,
		isTreeReordering,
		setTreeReordering,
		syncing,
		syncNow,
		refreshTree,
		reload,
	};
});
