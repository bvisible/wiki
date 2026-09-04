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
		//// Neoffice — added route. Pretty URL routing: our wikis are linked as
		//// /wiki/<space>/<page> everywhere (docs, NORA, emails), never by
		//// internal IDs. Catches anything not matched by /spaces,
		//// /change-requests, etc. and resolves it through resolve_wiki_path().
		// Examples:
		//   /wiki/rh                            -> space "RH" (first page auto-opened)
		//   /wiki/rh/configuration-assurances   -> specific page in RH space
		//   /wiki/Web-Domaines                  -> space "Web & Domaines"
		path: '/:wikiPath(.+)',
		name: 'WikiPrettyPath',
		component: () => import('@/pages/SpaceDetails.vue'),
		beforeEnter: async (to, from, next) => {
			try {
				const resp = await fetch(
					`/api/method/wiki.api.resolve_wiki_path?path=${encodeURIComponent(
						to.params.wikiPath,
					)}`,
				);
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
			} catch (e) {
				/* fallthrough */
			}
			next({ name: 'SpaceList', replace: true });
		},
	},
];

// The app's base path. Kept in sync with APP_ROUTE in wiki_document.py (which
// also feeds website_route_rules) and APP_BASE in e2e/helpers/routes.ts.
const router = createRouter({
	history: createWebHistory('/wiki-app'),
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

	//// Neoffice — rewritten guard. Upstream bounces EVERY route to /login when
	//// signed out. Neoffice wikis are public-facing, so only the
	//// authoring/reviewing routes are gated; reading a published space stays
	//// open to anyone.
	const EDITOR_ONLY = new Set([
		'ChangeRequests',
		'ChangeRequestReview',
		'DraftChangeRequest',
	]);

	if (EDITOR_ONLY.has(to.name)) {
		if (!isLoggedIn) {
			window.location.href = `/login?redirect-to=/wiki-app${encodeURIComponent(
				to.fullPath,
			)}`;
			return;
		}
		//// Neoffice — signed in but with no wiki role (portal Website User):
		//// logging in again would not help, so send them to what they can
		//// actually read instead of bouncing them through /login forever.
		if (!userStore.isWikiEditor) {
			next({ name: 'SpaceList', replace: true });
			return;
		}
	}

	//// Neoffice — added. Readers land directly in the first public space rather
	//// than on the Space List, which for them lists that one space anyway.
	if (!userStore.isWikiEditor && to.name === 'SpaceList') {
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
//// Neoffice — single terminal next(). Upstream ended on an if/else that only
//// ever called next() for a signed-in user; the guard above now decides route
//// by route, so navigation continues here for everyone else.

	next();
});

export default router;
