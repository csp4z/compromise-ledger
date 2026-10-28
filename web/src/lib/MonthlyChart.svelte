<script lang="ts">
	import * as Plot from '@observablehq/plot';
	import { percent } from '#lib/format.ts';
	import type { Month } from '#lib/types.ts';

	let { months }: { months: Month[] } = $props();
	let container: HTMLDivElement | undefined = $state();
	let width = $state(800);

	const SECURITY = 'Security vendors';
	const OTHER = 'All other vendors';
	// Bulk additions of older flaws: the catalog's launch, and a large batch in March 2022.
	const BACKLOG = ['2021-11', '2022-03'];

	const label = (month: string) =>
		new Date(month).toLocaleDateString('en-US', { year: 'numeric', month: 'long', timeZone: 'UTC' });
	// The site is rebuilt daily, so the newest month is the one still in progress.
	const partial = $derived(months.at(-1)?.month ?? null);

	$effect(() => {
		if (!container) return;
		const style = getComputedStyle(container);
		const rows = months.flatMap((m) => [
			{
				month: new Date(m.month),
				group: OTHER,
				n: m.kev_added - m.security_vendor_kev_added,
				partial: m.month === partial
			},
			{
				month: new Date(m.month),
				group: SECURITY,
				n: m.security_vendor_kev_added,
				partial: m.month === partial
			}
		]);
		const chart = Plot.plot({
			width,
			height: 280,
			marginLeft: 40,
			x: { type: 'utc', label: null },
			y: { label: 'KEV entries added', grid: true, nice: true },
			color: {
				domain: [SECURITY, OTHER],
				range: [style.getPropertyValue('--security'), style.getPropertyValue('--other')],
				legend: true
			},
			marks: [
				Plot.rectY(rows, {
					x: 'month',
					y: 'n',
					fill: 'group',
					fillOpacity: (d: { partial: boolean }) => (d.partial ? 0.45 : 1),
					interval: 'month',
					order: [OTHER, SECURITY],
					tip: true
				}),
				Plot.ruleY([0])
			]
		});
		container.replaceChildren(chart);
		return () => chart.remove();
	});
</script>

<div bind:this={container} bind:clientWidth={width} class="chart"></div>
<p class="small muted">
	{BACKLOG.map(label).join(' and ')} were bulk additions of older flaws.
	{#if partial}{label(partial)} (faded) is the month so far.{/if}
</p>
<details class="small">
	<summary>Show the data</summary>
	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>Month</th>
					<th class="num">KEV added</th>
					<th class="num">Security vendors</th>
					<th class="num">Share</th>
				</tr>
			</thead>
			<tbody>
				{#each months as m (m.month)}
					<tr>
						<td>{m.month.slice(0, 7)}</td>
						<td class="num">{m.kev_added}</td>
						<td class="num">{m.security_vendor_kev_added}</td>
						<td class="num">{percent(m.security_vendor_share)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</details>

<style>
	.chart {
		min-height: 300px;
		overflow: hidden;
	}
	.chart :global(svg) {
		max-width: 100%;
		height: auto;
	}
</style>
