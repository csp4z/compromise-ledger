<script lang="ts">
	import * as Plot from '@observablehq/plot';
	import type { Month } from '#lib/types.ts';

	let { months }: { months: Month[] } = $props();
	let container: HTMLDivElement | undefined = $state();
	let width = $state(800);

	const SECURITY = 'Security vendors';
	const OTHER = 'All other vendors';

	$effect(() => {
		if (!container) return;
		const style = getComputedStyle(container);
		const rows = months.flatMap((m) => [
			{ month: new Date(m.month), group: OTHER, n: m.kev_added - m.security_vendor_kev_added },
			{ month: new Date(m.month), group: SECURITY, n: m.security_vendor_kev_added }
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
<details class="small">
	<summary>Show the data</summary>
	<div class="table-wrap">
		<table>
			<thead>
				<tr><th>Month</th><th class="num">KEV added</th><th class="num">Security vendors</th></tr>
			</thead>
			<tbody>
				{#each months as m (m.month)}
					<tr>
						<td>{m.month.slice(0, 7)}</td>
						<td class="num">{m.kev_added}</td>
						<td class="num">{m.security_vendor_kev_added}</td>
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
