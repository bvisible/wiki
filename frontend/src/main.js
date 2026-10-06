//// Neoffice — telemetryPlugin import removed: see the telemetry block below.
//// Neoffice — watchEffect no longer imported: it only started the telemetry (see below).
import { createApp } from 'vue';

import App from './App.vue';
import router from './router';
import { initSocket } from './socket';
import { pinia } from './stores';
//// Neoffice — useSessionStore no longer imported: it only gated the telemetry (see below).

//// Neoffice — trackPageviews import removed: see the telemetry block below.

//// Neoffice — translationsReady added to this import; it is what the mount
//// below waits on.
import translationPlugin, { translationsReady } from './translation';

import {
	Badge,
	Button,
	Dialog,
	ErrorMessage,
	FormControl,
	TextInput,
	frappeRequest,
	resourcesPlugin,
	setConfig,
} from 'frappe-ui';

import './index.css';
import './wiki-editor-content.css';

const globalComponents = {
	Button,
	TextInput,
	FormControl,
	ErrorMessage,
	Dialog,
	Badge,
};

const app = createApp(App);

setConfig('resourceFetcher', frappeRequest);

app.use(pinia);
app.use(router);
app.use(translationPlugin);
app.use(resourcesPlugin);

//// Neoffice — upstream's telemetry is not started (v3.3.0 starts it for every signed-in author).
//// Its plugin first asks frappe.utils.telemetry.pulse.client.boot_config, which our Frappe v15 does
//// not have, then imports https://pulse.m.frappe.cloud/assets/pulse/js/pulse_client.js anyway: Frappe
//// Cloud's JavaScript would run on our domain with the author's session, telemetry switched off or
//// not. Nothing of our wikis is sent anywhere. Drop this when upstream stops loading a third-party
//// script before it knows telemetry is on.

const socket = initSocket();
app.config.globalProperties.$socket = socket;

for (const key in globalComponents) {
	app.component(key, globalComponents[key]);
}

//// Neoffice — mount AFTER the translations land. __() is not reactive: any
//// component rendered before the fetch resolves keeps its English labels for
//// the life of the page, which is why a fully translated fr.po still showed an
//// English UI. One round-trip, and the app is actually in French.
translationsReady().then(() => {
	app.mount('#app');
});
