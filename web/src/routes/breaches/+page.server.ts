import { breachGroups, breachYears, manifest } from '#lib/server/gold.ts';
import type { BreachNoticeGroup } from '#lib/types.ts';

// RCW 19.255.010(7): notify the Attorney General no more than thirty days after discovery.
const LIMIT_DAYS = 30;
// Years with enough notices for a median to mean something (the first year has 14).
const MIN_NOTICES = 40;
const RECENT_YEARS = 3;

const LABELS: Record<string, string> = {
	cyberattack: 'Cyberattack',
	'unauthorized-access': 'Unauthorized access',
	'theft-or-mistake': 'Theft or mistake',
	ransomware: 'Ransomware',
	malware: 'Malware',
	phishing: 'Phishing',
	skimmer: 'Card skimmer',
	other: 'Other',
	unknown: 'Unclear or unknown',
	'not-stated': 'Not stated'
};

export const load = () => {
	const years = breachYears();
	const groups = breachGroups().map((g) => ({ ...g, label: LABELS[g.label] ?? g.label }));
	const by = (dimension: BreachNoticeGroup['dimension']) =>
		groups.filter((g) => g.dimension === dimension);
	const full = years.slice(0, -1);
	const recent = full.slice(-RECENT_YEARS);
	const notified = recent.reduce((n, y) => n + y.notify_measured, 0);
	const late = recent.reduce(
		(n, y) => n + Math.round((y.share_notified_after_30_days ?? 0) * y.notify_measured),
		0
	);
	return {
		limit: LIMIT_DAYS,
		years,
		charted: years.filter((y) => y.notices >= MIN_NOTICES),
		minNotices: MIN_NOTICES,
		total: years.reduce((n, y) => n + y.notices, 0),
		firstYear: years[0]?.year ?? null,
		latest: years.at(-1) ?? null,
		recent: {
			from: recent[0]?.year ?? null,
			to: recent.at(-1)?.year ?? null,
			lateShare: notified ? late / notified : null
		},
		industries: by('industry'),
		causes: by('cause'),
		attackTypes: by('attack_type'),
		source: manifest().sources.find((s) => s.id === 'wa-breach-notices') ?? null
	};
};
