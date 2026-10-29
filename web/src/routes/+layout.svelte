<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { NVD_NOTICE, REPO_URL, date } from '#lib/format.ts';

	let { data, children } = $props();

	const links = [
		{ href: '/', label: 'Dashboard' },
		{ href: '/incidents', label: 'Incidents' },
		{ href: '/data', label: 'Data' },
		{ href: '/method', label: 'Method' }
	];
</script>

<header>
	<nav aria-label="Main">
		<a class="brand" href="/">Compromise Ledger</a>
		<ul>
			{#each links as link (link.href)}
				<li>
					<a href={link.href} aria-current={page.url.pathname === link.href ? 'page' : undefined}
						>{link.label}</a
					>
				</li>
			{/each}
			<li><a href={REPO_URL}>GitHub</a></li>
		</ul>
	</nav>
</header>

<main>
	{@render children()}
</main>

<footer>
	<p>
		Data updated {date(data.generatedAt)}. Dataset licensed
		<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>; sources keep their own
		terms. Code Apache-2.0.
	</p>
	<p>{NVD_NOTICE}</p>
	<p>
		<a href={`${REPO_URL}/blob/main/docs/DATA_POLICY.md`}>Data policy</a> ·
		<a href={`${REPO_URL}/blob/main/CORRECTIONS.md`}>Corrections</a>
	</p>
</footer>

<style>
	header {
		border-bottom: 1px solid var(--border);
		background: var(--surface);
	}
	nav {
		max-width: 72rem;
		margin: 0 auto;
		padding: 0.75rem 1rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1.5rem;
		align-items: center;
		justify-content: space-between;
	}
	.brand {
		font-weight: 700;
		color: var(--text);
		text-decoration: none;
	}
	ul {
		display: flex;
		gap: 1rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}
	nav ul a {
		color: var(--muted);
		text-decoration: none;
	}
	nav ul a[aria-current='page'] {
		color: var(--text);
		font-weight: 600;
	}
	footer {
		border-top: 1px solid var(--border);
		color: var(--muted);
		font-size: 0.85rem;
		max-width: 72rem;
		margin: 0 auto;
		padding: 1rem 1rem 2rem;
	}
	footer p {
		margin: 0.35rem 0;
	}
</style>
