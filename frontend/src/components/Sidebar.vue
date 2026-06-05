<template>
<Sidebar
	v-model:collapsed="isSidebarCollapsed"
	:header="{
		title: __('Frappe Wiki'),
		logo: '/assets/wiki/images/wiki-logo.png',
		menuItems: [
			{ label: __('Toggle Theme'), icon: themeIcon, onClick: toggleTheme },
			{ label: __('Log out'), icon: LucideLogOut, onClick: logout },
		],
	}"
	:sections="sections"
/>
</template>

<script setup>
import { Sidebar } from "frappe-ui";

import { onMounted, computed } from "vue";
import { useUserStore } from "@/stores/user";
import { useRoute, useRouter } from "vue-router";
import { useStorage } from "@vueuse/core";
import LucideMoon from "~icons/lucide/moon";
import LucideSun from "~icons/lucide/sun";
import LucideRocket from "~icons/lucide/rocket";
import LucideGitBranch from "~icons/lucide/git-branch";
import LucideLogOut from "~icons/lucide/log-out";
import { useSessionStore } from "@/stores/session";

const route = useRoute();
const userStore = useUserStore();
const isGuest = computed(() => !userStore.data?.is_logged_in);
const router = useRouter();
const sessionStore = useSessionStore();

const userTheme = useStorage("wiki-theme", "dark");

const themeIcon = computed(() => {
	return userTheme.value === "dark" ? LucideSun : LucideMoon;
});

const isSidebarCollapsed  = useStorage("is-sidebar-collapsed", false);

const navItems = computed(() => {
	const items = [{ label: __("Spaces"), icon: LucideRocket, to: { name: "SpaceList" } }];
	if (!isGuest.value) {
		items.push({ label: __("Change Requests"), icon: LucideGitBranch, to: { name: "ChangeRequests" } });
	}
	return items;
});

const sections = computed(() => [
	{
		label: "",
		items: navItems.value.map((item) => ({
			...item,
			isActive: route.path.startsWith(router.resolve(item.to).path),
		})),
	},
]);

onMounted(() => {
	document.documentElement.setAttribute("data-theme", userTheme.value);
});

function toggleTheme() {
	const currentTheme = userTheme.value;
	const newTheme = currentTheme === "dark" ? "light" : "dark";
	document.documentElement.setAttribute("data-theme", newTheme);
	userTheme.value = newTheme;
}

function logout() {
	sessionStore.logout.submit();
}
</script>
