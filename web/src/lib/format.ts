export const REPO_URL = 'https://github.com/csp4z/compromise-ledger';
export const NVD_NOTICE =
	'This product uses data from the NVD API but is not endorsed or certified by the NVD.';

const integer = new Intl.NumberFormat('en-US');

export const count = (n: number) => integer.format(n);
export const percent = (share: number | null, digits = 0) =>
	share === null ? '—' : `${(share * 100).toFixed(digits)}%`;
export const days = (n: number | null) =>
	n === null ? '—' : `${Number.isInteger(n) ? n : n.toFixed(1)} ${n === 1 ? 'day' : 'days'}`;
export const date = (iso: string | null) =>
	iso === null
		? '—'
		: new Date(iso).toLocaleDateString('en-US', {
				year: 'numeric',
				month: 'short',
				day: 'numeric',
				timeZone: 'UTC'
			});
export const bytes = (n: number) =>
	n < 1024 ? `${n} B` : n < 1024 ** 2 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1024 ** 2).toFixed(1)} MB`;
export const nvdUrl = (cve: string) => `https://nvd.nist.gov/vuln/detail/${cve}`;
