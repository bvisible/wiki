<!-- //// Neoffice — added file (no upstream equivalent). Wiki flavour of the
     shared Neoffice chrome; falls back to upstream's own Sidebar when the
     cockpit cannot boot, so the app never loses its navigation. ADR-015. -->
<template>
	<Sidebar v-if="failed" />
	<NeoCockpitBridge
		v-else
		:surface-app="surfaceApp"
		:context-nav="contextNav"
		:navigate="navigate"
		@failed="failed = true"
	/>
</template>

<script setup>
/**
 * Wiki flavor of the shared Neoffice chrome (NeoCockpit). Maps the two
 * nav items into contextNav; native Sidebar kept as auto fallback (and
 * for guests, where the cockpit boot endpoint denies access anyway).
 * Recipe: neoffice ADR-015.
 */
import Sidebar from "@/components/Sidebar.vue";
import NeoCockpitBridge from "@/components/NeoCockpitBridge.vue";

import { useRouter, useRoute } from "vue-router";
import { ref, computed } from "vue";
import { useUserStore } from "@/stores/user";
import { useWikiSettings } from "@/composables/useWikiSettings";

const router = useRouter();
const route = useRoute();
const failed = ref(false);
const userStore = useUserStore();
const { open: openWikiSettings } = useWikiSettings();

const surfaceApp = {
	name: "wiki",
	title: "Wiki",
	logo: "/assets/wiki/images/wiki-logo.png",
};

function navigate(r) {
	if (!r) return;
	if (r.startsWith("/app") || r.startsWith("http")) window.location.href = r;
	else router.push(r);
}

const contextNav = computed(() => {
	const items = [
		{ label: __("Spaces"), icon: "lucide-rocket", to: { name: "SpaceList" } },
	];
	if (userStore.data?.is_logged_in) {
		items.push({
			label: __("Change Requests"),
			icon: "lucide-git-branch",
			to: { name: "ChangeRequests" },
		});
	}
	// The app's own sidebar held « Settings » for a manager; it is replaced here, so the cockpit offers it
	// (maintenance#1096: on a desktop a manager had no way left to open the dialog).
	if (userStore.isWikiManager) {
		items.push({
			label: __("Settings"),
			icon: "lucide-settings",
			onClick: () => openWikiSettings(),
		});
	}
	return [
		{
			items: items.map((item) => ({
				label: item.label,
				icon: item.icon,
				active: item.to ? route.path.startsWith(router.resolve(item.to).path) : false,
				onClick: item.onClick || (() => router.push(item.to)),
			})),
		},
	];
});
</script>
