<script lang="ts">
	import { NVD_NOTICE, bytes, count, date } from '#lib/format.ts';
	import type { Manifest } from '#lib/types.ts';

	let { data } = $props();

	const DESCRIPTIONS: Record<string, string> = {
		'gold.kev_vendor_products': 'One row per KEV entry and affected vendor product. Start here.',
		'gold.vulnerabilities': 'One row per CVE, merging CISA KEV and NVD.',
		'gold.vendors': 'Each curated vendor, whether it is a security vendor, and its KEV totals.',
		'gold.security_vendor_summary': 'Security vendors vs everyone else: the headline numbers.',
		'gold.security_vendor_kev_monthly': 'KEV additions per month, and how many are security vendors’.',
		'gold.unresolved_vendor_names': 'Source vendor names that match no curated vendor.',
		'gold.vendor_cve_counts':
			'Per curated vendor: CVEs in NVD, how many reached KEV, and the share.',
		'gold.corrections_log': 'Accepted corrections: which record changed, how, why, and when.'
	};

	type File = Manifest['files'][number];
	const tables = $derived(
		Object.entries(
			data.manifest.files.reduce<Record<string, File[]>>((acc, file) => {
				(acc[file.table] ??= []).push(file);
				return acc;
			}, {})
		)
	);
</script>

<svelte:head>
	<title>Data downloads · Compromise Ledger</title>
</svelte:head>

<h1>Data</h1>
<p class="lede">
	Every number on this site comes from these files. They are rebuilt daily; this export was
	generated {date(data.manifest.generated_at)} (schema {data.manifest.schema_version}).
</p>

<p>
	<a href="/files/datasets.json">datasets.json</a> lists every file with its row count, full SHA-256
	checksum, and Iceberg snapshot. Verify a download with <code>shasum -a 256 &lt;file&gt;</code>
	against it; the table below shows the first characters.
</p>

{#each tables as [table, files] (table)}
	<section class="card dataset">
		<h2>{table.replace('gold.', '')}</h2>
		<p class="muted">{DESCRIPTIONS[table] ?? ''} {count(files[0]?.rows ?? 0)} rows.</p>
		<div class="table-wrap">
			<table>
				<thead>
					<tr><th>File</th><th class="num">Size</th><th>SHA-256</th></tr>
				</thead>
				<tbody>
					{#each files as file (file.path)}
						<tr>
							<td><a href={`/files/${file.path}`} download>{file.path}</a></td>
							<td class="num">{bytes(file.bytes)}</td>
							<td><code title={file.sha256}>{file.sha256.slice(0, 12)}…</code></td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
{/each}

<h2>Licenses and attribution</h2>
<p>{data.manifest.attribution}</p>
<div class="table-wrap">
	<table>
		<thead><tr><th>Source</th><th>License</th><th>Notice</th></tr></thead>
		<tbody>
			{#each data.manifest.sources as source (source.id)}
				<tr>
					<td>{source.description}</td>
					<td><code>{source.license}</code></td>
					<td>{source.attribution ?? '—'}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
<p class="small muted">{NVD_NOTICE}</p>

<h2>Unresolved vendor names</h2>
<p>
	Vendor names from the sources that match no curated vendor. Their entries count toward totals
	but not toward any vendor.
</p>
<ul>
	{#each data.unresolved as name (name.vendor_name)}
		<li>{name.vendor_name} ({name.mentions} {name.mentions === 1 ? 'entry' : 'entries'})</li>
	{/each}
</ul>

<style>
	.dataset {
		margin: 1rem 0;
	}
	.dataset h2 {
		margin-top: 0;
	}
</style>
