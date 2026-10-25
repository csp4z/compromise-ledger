// Build-time access to the synced gold export (static/files/). Pages never read anything else.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { GroupSummary, KevEntry, Manifest, Month, UnresolvedName, Vendor } from '#lib/types.ts';

const DATA_DIR = join(process.cwd(), 'static', 'files');

function read<T>(file: string): T {
	return JSON.parse(readFileSync(join(DATA_DIR, file), 'utf8')) as T;
}

export const manifest = () => read<Manifest>('datasets.json');
export const summary = () => read<GroupSummary[]>('security_vendor_summary.json');
export const monthly = () => read<Month[]>('security_vendor_kev_monthly.json');
export const vendors = () => read<Vendor[]>('vendors.json');
export const kevEntries = () => read<KevEntry[]>('kev_vendor_products.json');
export const unresolved = () => read<UnresolvedName[]>('unresolved_vendor_names.json');
