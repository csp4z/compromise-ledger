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
		<strong>CISA Known Exploited Vulnerabilities (KEV).</strong> CVEs that CISA has reliable
		evidence are exploited in the wild, with the date each was added, the vendor and product named, and whether
		ransomware use is known. Public domain (CC0).
	</li>
	<li>
		<strong>NIST National Vulnerability Database (NVD).</strong> The CVE record for each KEV entry:
		publication date, CVSS severity, weakness types, and description. Only CVEs in KEV are
		collected for now. Separately, two counts per vendor: how many CVEs NVD matches to the vendor,
		and how many of those are in KEV.
	</li>
	<li>
		<strong>SEC EDGAR (Form 8-K).</strong> Cybersecurity incidents companies disclose: filings
		under Item 1.05 (material incidents), and Item 8.01 filings that use the language of a
		disclosure, found through EDGAR full-text search. Only the company's name, identifiers, and the
		filing's date, form, item, and link are kept. US government public records.
	</li>
</ul>
<p>All are fetched daily. Every row in the downloads names its source, crawl time, and license.</p>

<h2>Who counts as a security vendor</h2>
<p>
	A vendor counts if <strong>security is its primary business</strong>: what it is mainly known for
	and earns most of its revenue from. A generalist with a security product line does not count,
	however large: Cisco, Microsoft, and Juniper are not security vendors here, while Fortinet, Palo
	Alto Networks, and Sophos are.
</p>
<p>
	The rule applies to the company KEV names. An acquired security company keeps its own row (Pulse
	Secure counts on its own, and so does Ivanti, which owns it now). Borderline calls are listed
	with the reason in the <a href={`${seeds}/vendors.csv`}>curated vendor list</a>. Ivanti is
	counted because its KEV entries are mostly its Connect Secure VPN and endpoint management. F5 and
	Splunk are not counted. Each security vendor cites a source, and changes go through public
	review.
</p>
<p>
	"Security product" is broader than defensive tools. Fortra counts as a security company, so its
	Cobalt Strike (an attack-simulation tool) and GoAnywhere (file transfer) entries count too.
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
		A negative value means CISA listed it before NVD published the CVE; those count as listed
		within a week. This measures time to listing, not time to first exploitation, which is
		usually earlier and rarely known. Only CVEs published since KEV launched (November 3, 2021) are included: the launch added a
		backlog of long-known flaws, which would otherwise dominate the comparison.
	</dd>
	<dt>Share of a vendor's CVEs in KEV</dt>
	<dd>
		NVD's count of CVEs whose affected-product records (CPE) name the vendor, and the count of those
		that are in KEV, both taken the same day. The vendor's CPE name is curated in the vendor list.
		Counts cover every security vendor and the 20 other vendors with the most KEV entries; the
		dashboard lists vendors with at least 20 CVEs, since below that one entry moves the share by 5
		points or more. Because the KEV side is matched by CPE too, it can differ slightly from the
		vendor's KEV count elsewhere on the site.
	</dd>
	<dt>SEC-disclosed incidents</dt>
	<dd>
		A company's filings about one incident are counted once: an amendment joins the company's
		latest incident, and an original filing within 90 days of its previous one joins that
		incident, since companies often report under Item 8.01 first and file under 1.05 once they
		judge the incident material. An incident is dated by its first filing and counts as material
		if any of its filings is under Item 1.05. Item 8.01 reports are matched by phrases such as
		"identified a cybersecurity incident"; in a sample, about 4 in 5 matches were real disclosures,
		and the phrases miss reports worded otherwise.
	</dd>
	<dt>Security-vendor share per month</dt>
	<dd>
		KEV entries added each month, counting an entry once even when it names several products.
		November 2021 (the catalog's launch) and March 2022 were bulk additions of older flaws, and the
		current month is incomplete.
	</dd>
</dl>

<h2>Limits</h2>
<ul>
	<li>
		KEV covers vulnerabilities CISA has reliable evidence are exploited, mostly in products used
		by US agencies. It is not a census of all exploitation, and it reflects what CISA sees and
		prioritizes, which leans toward internet-facing devices.
	</li>
	<li>
		A vendor with more KEV entries is not necessarily less secure: popular products attract more
		attackers, and vendors differ in how they disclose.
	</li>
	<li>
		A vendor's CVE count reflects how it issues CVEs (some file one per flaw, others group them)
		and how far NVD has catalogued affected products, which has lagged since 2024. For platform
		vendors (Microsoft, Apple, Google, Linux) the counts also include flaws in other products that
		run on the platform. The share is a rough comparison, not a security rating.
	</li>
	<li>
		Medians are over small groups (tens of security-vendor CVEs), so single entries can move them.
		The difference in time to KEV is sensitive to which vendors count as security vendors. The
		difference in ransomware use holds under most alternative choices, though it narrows if the
		networking vendors with firewall lines are counted.
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
