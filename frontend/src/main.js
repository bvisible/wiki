import { telemetryPlugin } from '@framework/ui/telemetry/index.ts';
import { createApp, watchEffect } from 'vue';

import App from './App.vue';
import router from './router';
import { initSocket } from './socket';
import { pinia } from './stores';
import { useSessionStore } from './stores/session';

import { trackPageviews } from './telemetry';
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

// Telemetry is for signed-in app users; the Jinja reader sends nothing.
const session = useSessionStore();
let telemetryStarted = false;
watchEffect(() => {
	if (!session.isLoggedIn || telemetryStarted) return;
	telemetryStarted = true;
	app.use(telemetryPlugin, { app_name: 'wiki' });
	trackPageviews(router);
});

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
