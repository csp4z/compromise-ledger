<script lang="ts">
	import * as Plot from '@observablehq/plot';
	import type { BreachNoticeYear } from '#lib/types.ts';

	let { years, limit }: { years: BreachNoticeYear[]; limit: number } = $props();
	let container: HTMLDivElement | undefined = $state();
	let width = $state(800);

	const NOTIFY = 'Aware → Attorney General notified';
	const DISCOVER = 'Breach began → organization aware';
	// The site is rebuilt daily, so the newest year is the one still in progress.
	const partial = $derived(years.at(-1)?.year ?? null);

	$effect(() => {
		if (!container) return;
		const style = getComputedStyle(container);
		const muted = style.getPropertyValue('--muted');
		const rows = years.flatMap((y) => [
			{ year: y.year, series: DISCOVER, days: y.median_days_to_discover, n: y.discover_measured },
			{ year: y.year, series: NOTIFY, days: y.median_days_to_notify, n: y.notify_measured }
		]);
		const drawn = rows.filter((r) => r.days !== null);
		const last = drawn.filter((r) => r.year === partial);
		const chart = Plot.plot({
			width,
			height: 300,
			marginLeft: 40,
			marginRight: width < 520 ? 30 : 48,
			x: { label: null, tickFormat: 'd', ticks: width < 520 ? 6 : years.length },
			y: { label: 'Median days', grid: true, nice: true, zero: true },
			color: {
				domain: [NOTIFY, DISCOVER],
				range: [style.getPropertyValue('--security'), style.getPropertyValue('--other')],
				legend: true
			},
			marks: [
				Plot.ruleY([limit], { stroke: muted, strokeDasharray: '4 4' }),
				Plot.text([`${limit}-day limit`], {
					frameAnchor: 'right',
					y: limit,
					dy: -8,
					fill: muted,
					textAnchor: 'end'
				}),
				Plot.ruleY([0]),
				Plot.lineY(drawn, { x: 'year', y: 'days', stroke: 'series', strokeWidth: 2 }),
				Plot.dot(drawn, {
					x: 'year',
					y: 'days',
					fill: 'series',
					r: 4,
					stroke: style.getPropertyValue('--surface'),
					strokeWidth: 2,
					channels: { Notices: 'n' },
					tip: { format: { x: 'd', fill: true } }
				}),
				// The value at the end of each line, in text ink; the legend carries the names.
				Plot.text(last, {
					x: 'year',
					y: 'days',
					text: (d: { days: number }) => `${d.days}`,
					dx: 10,
					textAnchor: 'start',
					fill: style.getPropertyValue('--text')
				})
			]
		});
		container.replaceChildren(chart);
		return () => chart.remove();
	});
</script>

<div bind:this={container} bind:clientWidth={width} class="chart"></div>
{#if partial}<p class="small muted">{partial} is the year so far.</p>{/if}
<details class="small">
	<summary>Show the data</summary>
	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>Year</th>
					<th class="num">Notices</th>
					<th class="num">Median days to become aware</th>
					<th class="num">Median days to notify</th>
					<th class="num">Notified after {limit} days</th>
				</tr>
			</thead>
			<tbody>
				{#each years as y (y.year)}
					<tr>
						<td>{y.year}</td>
						<td class="num">{y.notices}</td>
						<td class="num">{y.median_days_to_discover ?? '—'}</td>
						<td class="num">{y.median_days_to_notify ?? '—'}</td>
						<td class="num">
							{y.share_notified_after_30_days === null
								? '—'
								: `${Math.round(y.share_notified_after_30_days * 100)}%`}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</details>

<style>
	.chart {
		min-height: 320px;
		overflow: hidden;
	}
	.chart :global(svg) {
		max-width: 100%;
		height: auto;
	}
</style>
