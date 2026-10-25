// Rows of the gold export files (see pipelines/sql/gold/ and api/src/ledger_api/models.py).

export interface Manifest {
	dataset: string;
	generated_at: string;
	schema_version: string;
	license: string;
	attribution: string;
	sources: { id: string; description: string; license: string; attribution: string | null }[];
	files: {
		path: string;
		table: string;
		format: 'parquet' | 'csv' | 'json';
		rows: number;
		bytes: number;
		sha256: string;
		iceberg_snapshot_id: number | null;
	}[];
}

export interface GroupSummary {
	vendor_group: 'security_vendors' | 'all_other_vendors';
	kev_count: number;
	ransomware_known: number;
	ransomware_share: number;
	recent_cves: number;
	median_days_to_kev: number | null;
	p25_days_to_kev: number | null;
	p75_days_to_kev: number | null;
	share_within_7_days: number | null;
	time_to_kev_published_since: string;
}

export interface Month {
	month: string;
	kev_added: number;
	security_vendor_kev_added: number;
	security_vendor_share: number;
}

export interface Vendor {
	slug: string;
	name: string;
	is_security_vendor: boolean;
	kev_count: number;
	kev_ransomware_known: number;
	kev_products: number;
	first_kev_date: string | null;
	last_kev_date: string | null;
}

export interface KevEntry {
	cve_id: string;
	vendor_slug: string;
	vendor_name: string;
	is_security_vendor: boolean;
	product_name: string;
	kev_date_added: string;
	kev_ransomware_use: 'known' | 'unknown' | null;
	published: string | null;
	days_to_kev: number | null;
}

export interface UnresolvedName {
	vendor_name: string;
	mentions: number;
	sources: string;
}
