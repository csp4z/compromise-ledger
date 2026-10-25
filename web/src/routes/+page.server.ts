import { kevEntries, monthly, summary, vendors } from '#lib/server/gold.ts';

const RECENT = 12;

export const load = () => {
	const groups = summary();
	const security = groups.find((g) => g.vendor_group === 'security_vendors');
	const others = groups.find((g) => g.vendor_group === 'all_other_vendors');
	if (!security || !others) throw new Error('security_vendor_summary is missing a group');

	return {
		security,
		others,
		months: monthly(),
		leaderboard: vendors().filter((v) => v.is_security_vendor && v.kev_count > 0),
		recent: kevEntries()
			.filter((k) => k.is_security_vendor)
			.slice(0, RECENT)
	};
};
