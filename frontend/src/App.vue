<script setup lang="ts">
import { FrappeUIProvider, setConfig } from "frappe-ui";
import MainLayout from "./layouts/MainLayout.vue";
import { useTheme } from "./composables/useTheme";

setConfig("systemTimezone", window.timezone?.system || null);
setConfig("localTimezone", window.timezone?.user || null);

// Apply the light/dark theme at boot — follows the OS unless the user chose one.
useTheme();
</script>

<template>
	<FrappeUIProvider>
		<MainLayout>
			<router-view />
		</MainLayout>
	</FrappeUIProvider>
</template>