<template>
	<!-- The app is a fixed frame: the sidebar and the open page each own a
	     scroller, and nothing scrolls the layout itself. The frame is both
	     `relative` and `overflow-hidden`: the clip only catches an absolutely
	     positioned stray — frappe-ui Tree's aria-live region, for one — when the
	     frame is its containing block. Without `relative` the stray resolves
	     against the page, grows the document, and drags the whole chrome up. -->
	<div class="relative h-screen w-full overflow-hidden bg-surface-sidebar">
		<template v-if="isLoading"></template>
		<template v-else-if="hasAccess">
			<MobileShell v-if="isMobile" class="wiki-mobile-shell">
				<slot></slot>

				<template #nav>
					<MobileNav>
						<MobileNavItem
							v-if="userStore.isWikiManager"
							:label="__('Overview')"
							:route="{ name: 'Overview' }"
							:active="route.name === 'Overview'"
						>
							<template #default="{ active }">
								<span
									class="lucide-layout-grid size-6"
									:class="active ? 'text-ink-gray-8' : 'text-ink-gray-5'" aria-hidden="true" />
							</template>
						</MobileNavItem>
						<MobileNavItem
							:label="__('Spaces')"
							:route="{ name: 'AllSpaces' }"
							:active="isSpacesRoute"
						>
							<template #default="{ active }">
								<span
									class="lucide-rocket size-6"
									:class="active ? 'text-ink-gray-8' : 'text-ink-gray-5'" aria-hidden="true" />
							</template>
						</MobileNavItem>
						<MobileNavItem
							:label="__('Change Requests')"
							:route="{ name: 'ChangeRequests' }"
							:active="['ChangeRequests', 'ChangeRequestReview'].includes(route.name)"
						>
							<template #default="{ active }">
								<span
									class="lucide-git-branch size-6"
									:class="active ? 'text-ink-gray-8' : 'text-ink-gray-5'" aria-hidden="true" />
							</template>
						</MobileNavItem>
					</MobileNav>
				</template>
			</MobileShell>
			<DesktopShell v-else class="wiki-desktop-shell h-full">
				<!-- //// Neoffice — added. Shared Neoffice chrome (ADR-015) in place of the
				     library sidebar upstream mounts at the top level (LibrarySidebar); it
				     falls back to that sidebar on its own if the cockpit fails to boot.
				     It sits in the shell's `rail` slot so that, inside a space, it stays
				     beside the space's own tree (SpaceSidebar, `sidebar` slot) the way it
				     stood beside the tree column before 3.3.0 moved the tree into the
				     sidebar. Readers get NO cockpit at all: theirs held a single "Spaces"
				     link and an upstream product name, so it cost a column of screen and
				     gave nothing back. The space tree is their navigation. -->
				<template v-if="!isReader" #rail>
					<NeoCockpitWikiSidebar />
				</template>
				<template #sidebar>
					<!-- One navigation column that drills into a space: the space's
					     own tree, once you are inside one. (Upstream's library level,
					     LibrarySidebar, is what the shared Neoffice chrome above replaces:
					     see the rail slot.) -->
					<SpaceSidebar v-if="spaceId" :key="spaceId" :space-id="spaceId" />
				</template>
				<slot></slot>
			</DesktopShell>
		</template>
		<div
			v-else
			class="flex h-full items-center justify-center bg-surface-gray-1"
		>
			<div class="text-center">
				<div class="text-ink-gray-4 mb-4">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="h-16 w-16 mx-auto"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="1.5"
							d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
						/>
					</svg>
				</div>
				<h2 class="text-xl-semibold text-ink-gray-8 mb-2">
					{{ __('Access Denied') }}
				</h2>
				<p class="text-ink-gray-6">
					{{ __("You don't have permission to access the Wiki.") }}
				</p>
				<p class="text-ink-gray-5 text-sm mt-1">
					{{ __('Please contact your administrator to request access.') }}
				</p>
			</div>
		</div>

		<!-- //// Neoffice — mounted for a wiki manager only (maintenance#1096). Upstream
		//// mounts it for everyone, and it reads « Wiki Settings » as soon as it is
		//// mounted, dialog closed: a Wiki User may not read it, so every opening of
		//// the app raised a PermissionError. Only managers have its menu entry. -->
		<WikiSettings
			v-if="userStore.isWikiManager"
			v-model="showWikiSettings"
			:initial-tab="initialTab"
		/>
		<CommandPalette v-if="hasAccess" />
	</div>
</template>

<script setup>
import { useUserStore } from '@/stores/user';
import { DesktopShell, MobileNav, MobileNavItem, MobileShell } from 'frappe-ui';
import { computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import CommandPalette from '../components/CommandPalette.vue';
//// Neoffice — added. The shared Neoffice chrome (ADR-015) replaces upstream's library
//// sidebar at the top level; the wrapper falls back to LibrarySidebar if the cockpit
//// fails to boot.
import NeoCockpitWikiSidebar from '../components/NeoCockpitWikiSidebar.vue';
import SpaceSidebar from '../components/SpaceSidebar.vue';
import WikiSettings from '../components/WikiSettings/WikiSettings.vue';
import { useMobile } from '../composables/useMobile';
import { useTheme } from '../composables/useTheme';
import { useWikiSettings } from '../composables/useWikiSettings';

const { isMobile } = useMobile();
const userStore = useUserStore();
const route = useRoute();
const router = useRouter();
const { showWikiSettings, initialTab, open } = useWikiSettings();
// The first useColorScheme() call restores the saved preference and starts
// following the OS, so mounting this one always-mounted component is enough to
// apply the theme to both the desktop and mobile shells.
useTheme();

const isLoading = computed(() => userStore.isLoading);
const hasAccess = computed(() => userStore.canAccessWiki);
//// Neoffice — added. Readers are anonymous visitors AND signed-in users
//// without a wiki role (portal customers), plus anyone previewing.
const isReader = computed(
	() => !userStore.isWikiEditor || route.query.preview === '1',
);

const spaceId = computed(() => route.params.spaceId || null);

// Spaces stays lit across every space route (overview + space details).
const isSpacesRoute = computed(
	() => route.name === 'AllSpaces' || Boolean(spaceId.value),
);

// The GitHub-App manifest flow redirects back here with ?github_app_created=1.
// Re-open the settings dialog on the GitHub tab and strip the query param. This
// watches (rather than runs once on mount) because the app mounts before the
// router resolves the initial route, so the query isn't populated yet at mount.
watch(
	() => route.query.github_app_created,
	(created) => {
		if (!created) return;
		open('github');
		const { github_app_created, ...query } = route.query;
		router.replace({ query });
	},
	{ immediate: true },
);
</script>

<style scoped>
/* The content column sits flush against the sidebar, separated by a hairline
   rather than floated as a rounded card: the app window already rounds the
   outer corners, so a second radius inside it just reads as noise. */
.wiki-desktop-shell :deep([data-slot='desktop-shell-content']) {
	background-color: var(--surface-base);
	border-left: 1px solid var(--outline-gray-2);
	overflow: hidden;
}

/* Wiki pages are app-like (columns + their own scroll regions), so they need
   the full height of the shell's scroll viewport. reka's ScrollArea wraps the
   slot in an unstyled display:table div that breaks h-full chains — give it
   full height explicitly. */
.wiki-desktop-shell :deep([data-reka-scroll-area-viewport]),
.wiki-desktop-shell :deep([data-reka-scroll-area-viewport] > div) {
	height: 100%;
}
.wiki-mobile-shell :deep([data-slot='mobile-shell-scroll']) > * {
	height: 100%;
}
</style>
