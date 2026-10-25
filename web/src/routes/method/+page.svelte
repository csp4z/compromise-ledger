<script lang="ts">
	import { REPO_URL } from '#lib/format.ts';

	const seeds = `${REPO_URL}/blob/main/data/seeds`;
</script>

<svelte:head>
	<title>Method · Compromise Ledger</title>
</svelte:head>

<h1>Method</h1>
<p class="lede">
	What the numbers mean, where they come from, and what they leave out. Everything here is
	reproducible from the open code and the published files.
</p>

<h2>Sources</h2>
<ul>
	<li>
		<strong>CISA Known Exploited Vulnerabilities (KEV).</strong> CVEs that CISA has confirmed as
		exploited in the wild, with the date each was added, the vendor and product named, and whether
		ransomware use is known. Public domain (CC0).
	</li>
	<li>
		<strong>NIST National Vulnerability Database (NVD).</strong> The CVE record for each KEV entry:
		publication date, CVSS severity, weakness types, and description. Only CVEs in KEV are
		collected for now.
	</li>
</ul>
<p>Both are fetched daily. Every row in the downloads names its source, crawl time, and license.</p>

<h2>Who counts as a security vendor</h2>
<p>
	A vendor counts if <strong>security is its primary business</strong>: what it is mainly known for
	and earns most of its revenue from. A generalist with a security product line does not count,
	however large: Cisco, Microsoft, and Juniper are not security vendors here, while Fortinet, Palo
	Alto Networks, and Sophos are.
</p>
<p>
	The rule applies to the company KEV names. An acquired security company keeps its own row (Pulse
	Secure counts, although Ivanti owns it now). Borderline calls, such as Ivanti, F5, and Splunk,
	are listed with the reason in the <a href={`${seeds}/vendors.csv`}>curated vendor list</a>, each
	security vendor cites a source, and changes go through public review.
</p>

<h2>Matching vendor names</h2>
<p>
	KEV names vendors in free text. Names are matched exactly to the curated list, after Unicode and
	whitespace normalization and ignoring case, and through a reviewed
	<a href={`${seeds}/vendor_aliases.csv`}>alias table</a> (for example, Android counts as Google).
	Names that match nothing are published on the <a href="/data">data page</a> rather than guessed;
	their entries count toward totals but not toward any vendor.
</p>

<h2>Measures</h2>
<dl>
	<dt>Known ransomware use</dt>
	<dd>
		CISA's own flag on each KEV entry. "Unknown" means not known, not "no"; the share is a lower
		bound.
	</dd>
	<dt>Time to KEV</dt>
	<dd>
		Days from the CVE's NVD publication date to the day CISA added it to KEV. Zero means it was
		listed the day it was published, often because it was already being exploited as a zero-day.
		Only CVEs published since KEV launched (November 3, 2021) are included: the launch added a
		backlog of long-known flaws, which would otherwise dominate the comparison.
	</dd>
	<dt>Security-vendor share per month</dt>
	<dd>
		KEV entries added each month, counting an entry once even when it names several products.
	</dd>
</dl>

<h2>Limits</h2>
<ul>
	<li>
		KEV covers vulnerabilities CISA has confirmed as exploited, mostly in products used by US
		agencies. It is not a census of all exploitation.
	</li>
	<li>
		A vendor with more KEV entries is not necessarily less secure: popular products attract more
		attackers, and vendors differ in how they disclose.
	</li>
	<li>
		Medians are over small groups (tens of security-vendor CVEs), so single entries can move them.
	</li>
</ul>

<h2>Corrections</h2>
<p>
	This dataset names real organizations, so every record is sourced and correctable. See the
	<a href={`${REPO_URL}/blob/main/CORRECTIONS.md`}>corrections process</a> and the
	<a href={`${REPO_URL}/blob/main/docs/DATA_POLICY.md`}>data policy</a>. Leaked data is never
	collected. If a public correction request would itself cause harm, email
	<a href="mailto:contact5@kuricove.com">contact5@kuricove.com</a>.
</p>

<style>
	dt {
		font-weight: 600;
		margin-top: 0.75rem;
	}
	dd {
		margin: 0.25rem 0 0 0;
		max-width: 48rem;
	}
	ul {
		max-width: 48rem;
	}
</style>
