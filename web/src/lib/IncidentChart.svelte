<script lang="ts">
	import * as Plot from '@observablehq/plot';
	import type { IncidentMonth } from '#lib/types.ts';

	let { months }: { months: IncidentMonth[] } = $props();
	let container: HTMLDivElement | undefined = $state();
	let width = $state(800);

	const MATERIAL = 'Material (Item 1.05)';
	const OTHER = 'Item 8.01 only';

	const label = (month: string) =>
		new Date(month).toLocaleDateString('en-US', { year: 'numeric', month: 'long', timeZone: 'UTC' });
	// The site is rebuilt daily, so the newest month is the one still in progress.
	const partial = $derived(months.at(-1)?.month ?? null);

	$effect(() => {
		if (!container) return;
		const style = getComputedStyle(container);
		const rows = months.flatMap((m) => [
			{ month: new Date(m.month), group: OTHER, n: m.other, partial: m.month === partial },
			{ month: new Date(m.month), group: MATERIAL, n: m.material, partial: m.month === partial }
		]);
		const chart = Plot.plot({
			width,
			height: 240,
			marginLeft: 40,
			x: { type: 'utc', label: null },
			y: { label: 'Incidents disclosed', grid: true, nice: true, tickFormat: 'd' },
			color: {
				domain: [MATERIAL, OTHER],
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
					order: [OTHER, MATERIAL],
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
{#if partial}<p class="small muted">{label(partial)} (faded) is the month so far.</p>{/if}
<details class="small">
	<summary>Show the data</summary>
	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>Month</th>
					<th class="num">Material (1.05)</th>
					<th class="num">8.01 only</th>
				</tr>
			</thead>
			<tbody>
				{#each months as m (m.month)}
					<tr>
						<td>{m.month.slice(0, 7)}</td>
						<td class="num">{m.material}</td>
						<td class="num">{m.other}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</details>

<style>
	.chart {
		min-height: 260px;
		overflow: hidden;
	}
	.chart :global(svg) {
		max-width: 100%;
		height: auto;
	}
</style>
