<script setup lang="ts">
import { FrappeUIProvider, setConfig, toast } from 'frappe-ui';
import { computed, onBeforeUnmount, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import MainLayout from './layouts/MainLayout.vue';
import { useSocket } from './socket';

const route = useRoute();

//// Neoffice — added. SpaceDetails reads props.spaceId once, at setup: its space
//// resource, tree, tabs and capabilities all capture the id and never re-submit
//// when it changes. Upstream gets away with it because the only way to reach
//// another space was the Spaces list, which unmounts the component. Our header
//// switcher moves between spaces WITHIN the component, so without this key the
//// tree came up empty and the header kept the previous space's name.
//// Keyed on the space alone, never the full path: pages inside a space must
//// keep navigating without tearing the tree down and refetching it.
const viewKey = computed(() =>
	route.params.spaceId ? `space-${route.params.spaceId}` : String(route.name || route.path),
);

setConfig('systemTimezone', window.timezone?.system || null);
setConfig('localTimezone', window.timezone?.user || null);

// Realtime reviewer-decision pings to the change-request author. The matching
// Notification Log entry (created server-side) is the durable copy; this is
// just the live nudge while the author has the app open.
function onChangeRequestUpdate(data: { subject?: string }) {
	if (data?.subject) toast.info(data.subject);
}

onMounted(() => {
	useSocket()?.on('wiki_change_request_update', onChangeRequestUpdate);
});
onBeforeUnmount(() => {
	useSocket()?.off('wiki_change_request_update', onChangeRequestUpdate);
});
</script>

<template>
	<FrappeUIProvider>
		<MainLayout>
			<router-view :key="viewKey" />
		</MainLayout>
	</FrappeUIProvider>
</template>