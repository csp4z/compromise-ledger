<script lang="ts">
	import BreachChart from '#lib/BreachChart.svelte';
	import { count, date, percent } from '#lib/format.ts';
	import type { BreachNoticeGroup } from '#lib/types.ts';

	let { data } = $props();
	const { recent, latest } = $derived(data);
</script>

<svelte:head>
	<title>Breach notices: found sooner, reported later · Compromise Ledger</title>
	<meta
		name="description"
		content="Data-breach notifications filed with the Washington State Attorney General: how long organizations take to notice a breach, and how long to report it."
	/>
</svelte:head>

{#snippet groupTable(heading: string, rows: BreachNoticeGroup[], ransomware = true)}
	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>{heading}</th>
					<th class="num">Notices</th>
					{#if ransomware}<th class="num">Ransomware</th>{/if}
					<th class="num">Median days to become aware</th>
					<th class="num">Median days to notify</th>
					<th class="num">Notified after {data.limit} days</th>
				</tr>
			</thead>
			<tbody>
				{#each rows as row (row.label)}
					<tr>
						<td>{row.label}</td>
						<td class="num">{count(row.notices)}</td>
						{#if ransomware}<td class="num">{percent(row.ransomware_share)}</td>{/if}
						<td class="num">{row.median_days_to_discover ?? '—'}</td>
						<td class="num">{row.median_days_to_notify ?? '—'}</td>
						<td class="num">{percent(row.share_notified_after_30_days)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/snippet}

<h1>Breaches are found sooner and reported later</h1>
{#if data.years.length && latest}
	<p class="lede">
		Organizations must tell the Washington State Attorney General about any breach involving more
		than 500 residents, within {data.limit} days of discovering it. Of the notices filed from
		{recent.from} to {recent.to},
		<strong class="security">{percent(recent.lateShare)}</strong> arrived more than {data.limit}
		days after the organization says it became aware.
	</p>

	<h2>Time to notice a breach, and time to report it</h2>
	<BreachChart years={data.charted} limit={data.limit} />
	<p class="small muted">
		Medians per year of filing, from the dates each organization reported, over
		{count(data.total)} notices since {data.firstYear} (years with at least {data.minNotices}
		notices are charted). A notice with a missing date, or dates out of order, is left out of that
		measure. "Aware" is the day the organization says it learned that Washington residents were
		affected. The limit has exceptions, for a law-enforcement request or the time needed to
		establish a breach's scope, so a late notice is not by itself a violation. One breach at a
		service provider can produce many notices, as in 2020. <a href="/method">How this is measured</a>.
	</p>

	<h2>By cause</h2>
	{@render groupTable('Cause', data.causes)}

	<h2>Cyberattacks by kind</h2>
	{@render groupTable('Kind of attack', data.attackTypes, false)}

	<h2>By industry</h2>
	{@render groupTable('Industry', data.industries)}
	<p class="small muted">
		All years together. Industry, cause and kind of attack are the Attorney General's office's
		labels. Only statistics are published here: the notices name organizations, some of them
		small practices, and this site does not list them. Latest notice: {date(latest.latest_notice_on)}.
		{#if data.source?.attribution}Source: {data.source.attribution}{/if}
	</p>
{:else}
	<p class="lede">No breach-notice statistics are in this export yet.</p>
{/if}
