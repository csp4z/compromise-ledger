import { incidents, manifest } from '#lib/server/gold.ts';
import type { IncidentMonth } from '#lib/types.ts';

// Item 1.05 applied to most companies from this date; the series starts here.
const RULE_START = '2023-12-18';

function months(from: string, to: string): string[] {
	const out: string[] = [];
	const cursor = new Date(`${from.slice(0, 7)}-01T00:00:00Z`);
	const end = new Date(`${to.slice(0, 7)}-01T00:00:00Z`);
	while (cursor <= end) {
		out.push(cursor.toISOString().slice(0, 10));
		cursor.setUTCMonth(cursor.getUTCMonth() + 1);
	}
	return out;
}

export const load = () => {
	const rows = incidents();
	const byMonth = new Map<string, IncidentMonth>(
		months(RULE_START, manifest().generated_at).map((m) => [m, { month: m, material: 0, other: 0 }])
	);
	for (const incident of rows) {
		const month = byMonth.get(`${incident.first_disclosed_on.slice(0, 7)}-01`);
		if (month) month[incident.material ? 'material' : 'other'] += 1;
	}
	return {
		ruleStart: RULE_START,
		incidents: rows,
		months: [...byMonth.values()],
		companies: new Set(rows.map((r) => r.sec_cik)).size,
		material: rows.filter((r) => r.material).length
	};
};
