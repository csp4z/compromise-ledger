import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		// Every page is prerendered from the gold exports (ADR 0005); no server runs.
		sveltekit({
			adapter: adapter({ strict: true, fallback: '404.html' }),
			// Prerendered pages get a <meta> CSP with hashes of SvelteKit's own inline scripts, so
			// scripts need no 'unsafe-inline'. Inline styles stay allowed: Plot styles its charts.
			csp: {
				mode: 'hash',
				directives: {
					'default-src': ['self'],
					'script-src': ['self'],
					'style-src': ['self', 'unsafe-inline'],
					'img-src': ['self', 'data:'],
					'connect-src': ['self'],
					'object-src': ['none'],
					'base-uri': ['self'],
					'form-action': ['self']
				}
			}
		})
	]
});
