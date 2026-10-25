import { manifest, unresolved } from '#lib/server/gold.ts';

export const load = () => ({ manifest: manifest(), unresolved: unresolved() });
