// Build-time access to the synced gold export (static/files/). Pages never read anything else.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import type {
	BreachNoticeGroup,
	BreachNoticeYear,
	GroupSignals,
	GroupSummary,
	Incident,
	KevEntry,
	Manifest,
	Month,
	UnresolvedName,
	Vendor,
	VendorCveCount,
	VendorSignals
} from '#lib/types.ts';

const DATA_DIR = join(process.cwd(), 'static', 'files');

function read<T>(file: string): T {
	return JSON.parse(readFileSync(join(DATA_DIR, file), 'utf8')) as T;
}

// Tables newer than the export being built from (the first build after a release) read as
// empty, and the pages leave their sections out.
function readIfPresent<T>(file: string): T[] {
	return existsSync(join(DATA_DIR, file)) ? read<T[]>(file) : [];
}

export const manifest = () => read<Manifest>('datasets.json');
export const summary = () => read<GroupSummary[]>('security_vendor_summary.json');
export const monthly = () => read<Month[]>('security_vendor_kev_monthly.json');
export const vendors = () => read<Vendor[]>('vendors.json');
export const kevEntries = () => read<KevEntry[]>('kev_vendor_products.json');
export const unresolved = () => read<UnresolvedName[]>('unresolved_vendor_names.json');
export const cveCounts = () => read<VendorCveCount[]>('vendor_cve_counts.json');
export const incidents = () => read<Incident[]>('incidents.json');
export const groupSignals = () => readIfPresent<GroupSignals>('security_vendor_signals.json');
export const vendorSignals = () => readIfPresent<VendorSignals>('vendor_signals.json');
export const breachYears = () => readIfPresent<BreachNoticeYear>('breach_notice_yearly.json');
export const breachGroups = () => readIfPresent<BreachNoticeGroup>('breach_notice_groups.json');
