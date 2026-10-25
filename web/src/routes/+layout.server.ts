import { manifest } from '#lib/server/gold.ts';

export const load = () => {
	const { generated_at, schema_version } = manifest();
	return { generatedAt: generated_at, schemaVersion: schema_version };
};
