import { cveCounts, kevEntries, monthly, summary, vendors } from '#lib/server/gold.ts';
import type { VendorCveCount } from '#lib/types.ts';

const RECENT = 12;
// Below this, one KEV entry swings a vendor's share by 5 points or more.
const MIN_CVES = 20;

function pooled(rows: VendorCveCount[]) {
	const cves = rows.reduce((n, r) => n + r.nvd_cve_count, 0);
	const kev = rows.reduce((n, r) => n + r.nvd_kev_count, 0);
	return { vendors: rows.length, cves, kev, share: cves ? kev / cves : null };
}

export const load = () => {
	const groups = summary();
	const security = groups.find((g) => g.vendor_group === 'security_vendors');
	const others = groups.find((g) => g.vendor_group === 'all_other_vendors');
	if (!security || !others) throw new Error('security_vendor_summary is missing a group');
	const counts = cveCounts();

	return {
		security,
		others,
		months: monthly(),
		leaderboard: vendors().filter((v) => v.is_security_vendor && v.kev_count > 0),
		recent: kevEntries()
			.filter((k) => k.is_security_vendor)
			.slice(0, RECENT),
		cveShare: {
			minCves: MIN_CVES,
			security: pooled(counts.filter((c) => c.is_security_vendor)),
			others: pooled(counts.filter((c) => !c.is_security_vendor)),
			vendors: counts.filter((c) => c.nvd_cve_count >= MIN_CVES),
			countedAt: counts.reduce<string | null>(
				(min, c) => (min === null || c.counted_at < min ? c.counted_at : min),
				null
			)
		}
	};
};
