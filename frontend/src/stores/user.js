import { createResource } from 'frappe-ui';
import { defineStore } from 'pinia';
import { computed } from 'vue';

export const useUserStore = defineStore('user', () => {
	const userResource = createResource({
		url: 'wiki.api.get_user_info',
		cache: 'User',
		onError(error) {
			if (error && error.exc_type === 'AuthenticationError') {
				window.location.href = '/login';
			}
		},
	});

	const data = computed(() => userResource.data);
	const roles = computed(() => userResource.data?.roles || []);
	const isLoading = computed(() => !userResource.data);

	const isWikiManager = computed(() => {
		const user = userResource.data;
		if (!user || !user.roles) return false;
		return user.roles.some(
			(role) => role.role === 'Wiki Manager' || role.role === 'System Manager',
		);
	});

	//// Neoffice — added. Holds one of the wiki authoring roles. Everyone else —
	//// anonymous visitors and signed-in portal users alike — is a reader.
	//// Components key their read-only behaviour off this, not off is_logged_in.
	const isWikiEditor = computed(() => {
		const user = userResource.data;
		if (!user?.is_logged_in || !user.roles) return false;
		return user.roles.some(
			(role) =>
				role.role === 'Wiki User' ||
				role.role === 'Wiki Manager' ||
				role.role === 'System Manager',
		);
	});

	//// Neoffice — rewritten. Upstream gated the app shell on holding an
	//// authoring role, which made a signed-in Website User (portal customer, no
	//// wiki role) hit "Access Denied" on a wiki an anonymous visitor reads
	//// fine — signing in made you see LESS. Reaching the shell is not a
	//// permission: the API filters every payload per space. Anyone whose user
	//// info loaded may enter; what they see and do is decided per space.
	const canAccessWiki = computed(() => Boolean(userResource.data));

	//// Neoffice — was Boolean(is_logged_in). Change requests need an authoring
	//// role, not merely an account.
	const shouldUseChangeRequestMode = computed(() => isWikiEditor.value);

	function fetch() {
		return userResource.fetch();
	}

	function reload() {
		return userResource.reload();
	}

	function reset() {
		return userResource.reset();
	}

	return {
		userResource,
		data,
		roles,
		isLoading,
		isWikiManager,
		//// Neoffice — exported: components branch on the authoring role, not on
		//// is_logged_in (see the two computed above).
		isWikiEditor,
		canAccessWiki,
		shouldUseChangeRequestMode,
		fetch,
		reload,
		reset,
	};
});
