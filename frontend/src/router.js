import { createRouter, createWebHistory } from 'vue-router';

const routes = [
	{
		path: '/',
		name: 'Home',
		redirect: '/spaces',
	},
	{
		path: '/spaces',
		name: 'SpaceList',
		component: () => import('@/pages/Spaces.vue'),
	},
	{
		path: '/change-requests',
		name: 'ChangeRequests',
		component: () => import('@/pages/Contributions.vue'),
	},
	{
		path: '/change-requests/:changeRequestId',
		name: 'ChangeRequestReview',
		component: () => import('@/pages/ContributionReview.vue'),
		props: true,
	},
	{
		path: '/contributions',
		redirect: { name: 'ChangeRequests' },
	},
	{
		path: '/contributions/:batchId',
		redirect: (to) => ({
			name: 'ChangeRequestReview',
			params: { changeRequestId: to.params.batchId },
		}),
	},
	{
		path: '/spaces/:spaceId',
		component: () => import('@/pages/SpaceDetails.vue'),
		props: true,
		children: [
			{
				path: '',
				name: 'SpaceDetails',
				component: () => import('@/components/SpaceWelcome.vue'),
			},
			{
				path: 'page/:pageId',
				name: 'SpacePage',
				component: () => import('@/components/WikiDocumentPanel.vue'),
				props: true,
			},
			{
				path: 'draft/:docKey',
				name: 'DraftChangeRequest',
				component: () => import('@/components/DraftContributionPanel.vue'),
				props: true,
			},
			{
				path: 'draft/:contributionId',
				redirect: (to) => ({
					name: 'DraftChangeRequest',
					params: {
						spaceId: to.params.spaceId,
						docKey: to.params.contributionId,
					},
				}),
			},
		],
	},
	{
		// Pretty URL routing. Catches anything not matched by /spaces, /change-requests, etc.
		// Examples:
		//   /wiki/rh                            -> space "RH" (first page auto-opened)
		//   /wiki/rh/configuration-assurances   -> specific page in RH space
		//   /wiki/Web-Domaines                  -> space "Web & Domaines"
		path: '/:wikiPath(.+)',
		name: 'WikiPrettyPath',
		component: () => import('@/pages/SpaceDetails.vue'),
		beforeEnter: async (to, from, next) => {
			try {
				const resp = await fetch(`/api/method/wiki.api.resolve_wiki_path?path=${encodeURIComponent(to.params.wikiPath)}`);
				const data = await resp.json();
				const spaceId = data?.message?.space_id;
				const pageId = data?.message?.page_id;
				if (spaceId && pageId) {
					next({
						name: 'SpacePage',
						params: { spaceId, pageId },
						query: to.query,
						replace: true,
					});
					return;
				}
				if (spaceId) {
					next({
						name: 'SpaceDetails',
						params: { spaceId },
						query: to.query,
						replace: true,
					});
					return;
				}
			} catch (e) { /* fallthrough */ }
			next({ name: 'SpaceList', replace: true });
		},
	},
];

const router = createRouter({
	history: createWebHistory('/wiki'),
	routes,
});

router.beforeEach(async (to, from, next) => {
	const { useSessionStore } = await import('@/stores/session');
	const { useUserStore } = await import('@/stores/user');
	const sessionStore = useSessionStore();

	const userStore = useUserStore();
	let isLoggedIn = sessionStore.isLoggedIn;
	try {
		if (!userStore.data) {
			await userStore.fetch();
		}
	} catch (error) {
		isLoggedIn = false;
	}

	// Routes that require login (editing / reviewing)
	const AUTH_REQUIRED = new Set([
		'ChangeRequests',
		'ChangeRequestReview',
		'DraftChangeRequest',
	]);

	if (!isLoggedIn && AUTH_REQUIRED.has(to.name)) {
		window.location.href = `/login?redirect-to=/wiki${encodeURIComponent(to.fullPath)}`;
		return;
	}

	// Guests land directly in the first public space instead of the intermediate Space List
	if (!isLoggedIn && to.name === 'SpaceList') {
		try {
			const { createResource } = await import('frappe-ui');
			const res = createResource({ url: 'wiki.api.list_public_spaces' });
			const list = await res.fetch();
			if (Array.isArray(list) && list.length > 0) {
				next({ path: `/spaces/${list[0].name}` });
				return;
			}
		} catch (e) {
			// fall through to normal navigation
		}
	}

	next();
});

export default router;
