import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		// Every page is prerendered from the gold exports (ADR 0005); no server runs.
		sveltekit({ adapter: adapter({ strict: true, fallback: '404.html' }) })
	]
});
