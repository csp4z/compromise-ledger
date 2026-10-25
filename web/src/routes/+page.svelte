<script lang="ts">
	import MonthlyChart from '#lib/MonthlyChart.svelte';
	import { count, date, days, nvdUrl, percent } from '#lib/format.ts';

	let { data } = $props();
	const { security, others } = $derived(data);
	const total = $derived(security.kev_count + others.kev_count);
	const topCount = $derived(data.leaderboard[0]?.kev_count ?? 1);
</script>

<svelte:head>
	<title>Compromise Ledger: security vendors' own products in CISA KEV</title>
	<meta
		name="description"
		content="How often security vendors' own products appear in CISA's Known Exploited Vulnerabilities catalog, how fast, and how often ransomware follows."
	/>
</svelte:head>

<h1>When security products are the attack surface</h1>
<p class="lede">
	Of the {count(total)} vulnerabilities CISA has confirmed as exploited in the wild,
	<strong class="security">{count(security.kev_count)}</strong>
	({percent(security.kev_count / total, 1)}) are in security vendors' own products: the
	firewalls, VPNs and endpoint tools meant to keep attackers out.
</p>

<section class="tiles" aria-label="Headline numbers">
	<div class="card tile">
		<div class="value security">{percent(security.ransomware_share)}</div>
		<div>of security-vendor KEV entries are known to be used by ransomware</div>
		<div class="versus">vs {percent(others.ransomware_share)} for all other vendors</div>
	</div>
	<div class="card tile">
		<div class="value security">{days(security.median_days_to_kev)}</div>
		<div>median from CVE publication to confirmed exploitation</div>
		<div class="versus">vs {days(others.median_days_to_kev)} for all other vendors*</div>
	</div>
	<div class="card tile">
		<div class="value security">{percent(security.share_within_7_days)}</div>
		<div>listed as exploited within a week of publication</div>
		<div class="versus">vs {percent(others.share_within_7_days)} for all other vendors*</div>
	</div>
</section>
<p class="small muted">
	* CVEs published since the KEV catalog launched on {date(security.time_to_kev_published_since)}
	({count(security.recent_cves)} security-vendor and {count(others.recent_cves)} other CVEs). Older
	CVEs are left out because the launch added a backlog of long-known flaws.
	<a href="/method">How this is measured</a>.
</p>

<h2>KEV additions per month</h2>
<MonthlyChart months={data.months} />

<h2>Security vendors in KEV</h2>
<div class="table-wrap">
	<table>
		<thead>
			<tr>
				<th>Vendor</th>
				<th class="num">KEV entries</th>
				<th aria-hidden="true"></th>
				<th class="num">Known ransomware use</th>
				<th class="num">Products</th>
				<th>Most recent</th>
			</tr>
		</thead>
		<tbody>
			{#each data.leaderboard as vendor (vendor.slug)}
				<tr>
					<td>{vendor.name}</td>
					<td class="num">{vendor.kev_count}</td>
					<td class="bar-cell" aria-hidden="true">
						<span class="bar" style:width={`${(vendor.kev_count / topCount) * 100}%`}></span>
					</td>
					<td class="num">{vendor.kev_ransomware_known}</td>
					<td class="num">{vendor.kev_products}</td>
					<td>{date(vendor.last_kev_date)}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<h2>Latest security-vendor additions</h2>
<div class="table-wrap">
	<table>
		<thead>
			<tr>
				<th>Added</th>
				<th>CVE</th>
				<th>Vendor</th>
				<th>Product</th>
				<th>Ransomware</th>
				<th class="num">Days from publication</th>
			</tr>
		</thead>
		<tbody>
			{#each data.recent as entry (`${entry.cve_id}-${entry.product_name}`)}
				<tr>
					<td>{date(entry.kev_date_added)}</td>
					<td><a href={nvdUrl(entry.cve_id)}>{entry.cve_id}</a></td>
					<td>{entry.vendor_name}</td>
					<td>{entry.product_name}</td>
					<td>{entry.kev_ransomware_use === 'known' ? 'Known' : '—'}</td>
					<td class="num">{entry.days_to_kev ?? '—'}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.bar-cell {
		width: 25%;
		min-width: 6rem;
	}
	.bar {
		display: block;
		height: 0.7rem;
		margin-top: 0.4rem;
		border-radius: 3px;
		background: var(--security);
	}
</style>
