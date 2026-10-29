<script lang="ts">
	import IncidentChart from '#lib/IncidentChart.svelte';
	import { REPO_URL, count, date } from '#lib/format.ts';

	let { data } = $props();
	const total = $derived(data.incidents.length);
</script>

<svelte:head>
	<title>Incidents disclosed to the SEC · Compromise Ledger</title>
	<meta
		name="description"
		content="Cybersecurity incidents that US-listed companies disclosed in SEC Form 8-K filings, by month, with a link to each filing."
	/>
</svelte:head>

<h1>Cybersecurity incidents disclosed to the SEC</h1>
<p class="lede">
	Since {date(data.ruleStart)}, US-listed companies must report material cybersecurity incidents in
	a Form 8-K. This page lists <strong>{count(total)}</strong> incidents at {count(data.companies)}
	companies; <strong class="security">{count(data.material)}</strong> were filed under Item 1.05,
	meaning the company judged the incident material.
</p>

<h2>Incidents per month</h2>
<IncidentChart months={data.months} />
<p class="small muted">
	Counts show how companies file, not how often incidents happen. Since SEC staff guidance in May
	2024, companies report incidents they have not judged material under Item 8.01 instead of 1.05.
	Item 8.01 reports are found by the phrases companies use to disclose an incident ("identified a
	cybersecurity incident", "detected unauthorized access"), so they are a lower bound. Only
	companies that file with the SEC are covered. <a href="/method">How this is measured</a>.
</p>

<h2>All incidents</h2>
<div class="table-wrap">
	<table>
		<thead>
			<tr>
				<th>First disclosed</th>
				<th>Company</th>
				<th>Item</th>
				<th class="num">Filings</th>
				<th>Source</th>
			</tr>
		</thead>
		<tbody>
			{#each data.incidents as incident (incident.incident_id)}
				<tr>
					<td>{date(incident.first_disclosed_on)}</td>
					<td>
						{incident.organization_name}{#if incident.tickers}<span class="muted ticker"
								>{incident.tickers.split(';').join(', ')}</span
							>{/if}
					</td>
					<td>
						{#if incident.material}<span class="security">1.05 material</span>{:else}8.01{/if}
					</td>
					<td class="num">{incident.filings}</td>
					<td><a href={incident.source_url}>SEC filing</a></td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
<p class="small muted">
	Every incident is the company's own filing, so its status is confirmed. Names are as EDGAR records
	them. A company's later filings about the same incident (amendments, or a 1.05 filing after an
	8.01 report) are counted once; the download lists each filing. To correct a record, see the
	<a href={`${REPO_URL}/blob/main/CORRECTIONS.md`}>corrections process</a>.
</p>

<style>
	.ticker {
		margin-left: 0.4rem;
		font-size: 0.8rem;
	}
</style>
