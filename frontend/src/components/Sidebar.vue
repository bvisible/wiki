<template>
	<Sidebar v-model:collapsed="isSidebarCollapsed">
		<div class="flex h-full flex-col p-2">
			<!-- //// Neoffice — "Wiki", not "Frappe Wiki": we ship this under the
			     Neoffice brand, upstream product names don't belong in the UI. -->
			<SidebarHeader
				:title="__('Wiki')"
				:subtitle="userStore.data?.full_name"
				logo="/assets/wiki/images/wiki-logo.png"
				:menu-items="headerMenuItems"
			/>
			<nav class="mt-2 flex flex-1 flex-col gap-0.5 overflow-y-auto">
				<SidebarItem
					v-for="item in navItems"
					:key="item.label"
					:label="item.label"
					:icon="item.icon"
					:to="item.to"
					:active="route.path.startsWith(router.resolve(item.to).path)"
				/>
			</nav>
			<SidebarCollapseToggle class="mt-auto" />
		</div>
	</Sidebar>
</template>

<script setup>
import {
	Sidebar,
	SidebarCollapseToggle,
	SidebarHeader,
	SidebarItem,
} from 'frappe-ui';

import { useSessionStore } from '@/stores/session';
import { useUserStore } from '@/stores/user';
import { useStorage } from '@vueuse/core';
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useTheme } from '../composables/useTheme';
import { useWikiSettings } from '../composables/useWikiSettings';

const route = useRoute();
const router = useRouter();
const sessionStore = useSessionStore();
const userStore = useUserStore();
//// Neoffice — added. Anonymous visitors and signed-in users without a wiki
//// role read alike.
const isReader = computed(() => !userStore.isWikiEditor);
const { open: openWikiSettings } = useWikiSettings();

const { themeIcon, toggleTheme } = useTheme();

const isSidebarCollapsed = useStorage('is-sidebar-collapsed', false);

const headerMenuItems = computed(() => [
	...(userStore.isWikiManager
		? [
				{
					label: __('Settings'),
					icon: 'lucide-settings',
					onClick: () => openWikiSettings(),
				},
			]
		: []),
	{ label: __('Toggle Theme'), icon: themeIcon.value, onClick: toggleTheme },
	//// Neoffice — nothing to log out of when browsing anonymously.
	...(isReader.value
		? []
		: [{ label: __('Log out'), icon: 'lucide-log-out', onClick: logout }]),
]);

//// Neoffice — change requests need a wiki role; readers only get the reading
//// entry point.
const navItems = computed(() => [
	{ label: __('Spaces'), icon: 'lucide-rocket', to: { name: 'SpaceList' } },
	...(isReader.value
		? []
		: [
				{
					label: __('Change Requests'),
					icon: 'lucide-git-branch',
					to: { name: 'ChangeRequests' },
				},
			]),
]);

function logout() {
	sessionStore.logout.submit();
}
</script>
