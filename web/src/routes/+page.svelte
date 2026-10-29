<script lang="ts">
	import MonthlyChart from '#lib/MonthlyChart.svelte';
	import { count, date, days, nvdUrl, percent } from '#lib/format.ts';

	let { data } = $props();
	const { security, others } = $derived(data);
	const total = $derived(security.kev_count + others.kev_count);
	const topCount = $derived(data.leaderboard[0]?.kev_count ?? 1);
	const cveShare = $derived(data.cveShare);
	const topShare = $derived(cveShare.vendors[0]?.kev_share ?? 1);
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
	Of the {count(total)} vulnerabilities in CISA's Known Exploited Vulnerabilities (KEV) catalog,
	<strong class="security">{count(security.kev_count)}</strong>
	({percent(security.kev_count / total, 1)}) are in security vendors' own products: firewalls,
	VPNs, endpoint protection and other security tools.
</p>

<section class="tiles" aria-label="Headline numbers">
	<div class="card tile">
		<div class="value security">{percent(security.ransomware_share)}</div>
		<div>of security-vendor KEV entries are known to be used by ransomware†</div>
		<div class="versus">vs {percent(others.ransomware_share)} for all other vendors</div>
	</div>
	<div class="card tile">
		<div class="value security">{days(security.median_days_to_kev)}</div>
		<div>median from CVE publication to KEV listing</div>
		<div class="versus">vs {days(others.median_days_to_kev)} for all other vendors*</div>
	</div>
	<div class="card tile">
		<div class="value security">{percent(security.share_within_7_days)}</div>
		<div>added to KEV within a week of publication, or before it</div>
		<div class="versus">vs {percent(others.share_within_7_days)} for all other vendors*</div>
	</div>
</section>
<p class="small muted">
	† All {count(total)} KEV entries. CISA flags ransomware use only when it is known, so these shares
	are lower bounds.
</p>
<p class="small muted">
	* CVEs published since the KEV catalog launched on {date(security.time_to_kev_published_since)}
	({count(security.recent_cves)} security-vendor and {count(others.recent_cves)} other CVEs). Older
	CVEs are left out because the launch added a backlog of long-known flaws. Security-vendor flaws
	tend to be listed sooner, but the group is small ({count(security.recent_cves)} CVEs) and the gap
	depends on which vendors count as security vendors, so treat it as indicative.
	<a href="/method">How this is measured</a>.
</p>

<h2>KEV additions per month</h2>
<MonthlyChart months={data.months} />

<h2>Security vendors in KEV</h2>
<p class="small muted">
	More KEV entries does not mean a vendor is less secure: widely deployed products attract more
	attackers, and vendors differ in how they disclose.
</p>
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

{#if cveShare.vendors.length}
	<h2>How many of a vendor's CVEs reach KEV</h2>
	<p>
		Raw KEV counts favor vendors with many products. Dividing by each vendor's CVE count in NVD
		gives the share of its published flaws that were later exploited and listed:
		<strong class="security">{percent(cveShare.security.share, 1)}</strong> for the
		{cveShare.security.vendors} security vendors ({count(cveShare.security.kev)} of
		{count(cveShare.security.cves)} CVEs), against {percent(cveShare.others.share, 1)} for the
		{cveShare.others.vendors} other vendors with the most KEV entries ({count(cveShare.others.kev)} of
		{count(cveShare.others.cves)}).
	</p>
	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>Vendor</th>
					<th class="num">Share in KEV</th>
					<th aria-hidden="true"></th>
					<th class="num">In KEV</th>
					<th class="num">CVEs in NVD</th>
				</tr>
			</thead>
			<tbody>
				{#each cveShare.vendors as vendor (vendor.slug)}
					<tr>
						<td>
							{vendor.name}{#if vendor.is_security_vendor}<span class="security tag">security</span
								>{/if}
						</td>
						<td class="num">{percent(vendor.kev_share, 1)}</td>
						<td class="bar-cell" aria-hidden="true">
							<span
								class="bar"
								class:other={!vendor.is_security_vendor}
								style:width={`${((vendor.kev_share ?? 0) / topShare) * 100}%`}
							></span>
						</td>
						<td class="num">{count(vendor.nvd_kev_count)}</td>
						<td class="num">{count(vendor.nvd_cve_count)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="small muted">
		Vendors with at least {cveShare.minCves} CVEs in NVD; the group totals above include all of them.
		Both counts match the vendor's name in NVD's product dictionary (CPE), counted on {date(
			cveShare.countedAt
		)}. They follow how each vendor issues CVEs and how far NVD has catalogued products, which lags
		for recent CVEs. For platform vendors (Microsoft, Apple, Google, Linux) they also include flaws
		in other products that run on the platform. Treat the comparison as indicative.
		<a href="/method">How this is measured</a>.
	</p>
{/if}

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
	.bar.other {
		background: var(--other);
	}
	.tag {
		margin-left: 0.4rem;
		font-size: 0.75rem;
	}
</style>
