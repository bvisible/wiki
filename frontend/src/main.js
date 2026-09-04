import { createApp } from 'vue';

import App from './App.vue';
import router from './router';
import { initSocket } from './socket';
import { pinia } from './stores';

//// Neoffice — translationsReady added to this import; it is what the mount
//// below waits on.
import translationPlugin, { translationsReady } from './translation';

import {
	Alert,
	Badge,
	Button,
	Dialog,
	ErrorMessage,
	FormControl,
	TextInput,
	frappeRequest,
	pageMetaPlugin,
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
	Alert,
	Badge,
};

const app = createApp(App);

setConfig('resourceFetcher', frappeRequest);

app.use(pinia);
app.use(router);
app.use(translationPlugin);
app.use(resourcesPlugin);
app.use(pageMetaPlugin);

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
