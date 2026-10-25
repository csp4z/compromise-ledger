// Copies the gold export into static/files/ and verifies every file against datasets.json, so
// the downloads and the pages built from them are exactly what the manifest describes.
// Source: CL_EXPORTS_DIR, else ../.lake/exports. For a build without local data:
//   CL_EXPORTS_DIR=../tests/sample-exports pnpm build
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';

const source = resolve(process.env.CL_EXPORTS_DIR ?? '../.lake/exports');
const target = resolve('static/files');
const manifestPath = join(source, 'datasets.json');

if (!existsSync(manifestPath)) {
	console.error(`No datasets.json in ${source}. Run \`uv run ledger export\`, or set`);
	console.error('CL_EXPORTS_DIR=../tests/sample-exports to build from the sample.');
	process.exit(1);
}

const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
rmSync(target, { recursive: true, force: true });
mkdirSync(target, { recursive: true });
for (const file of manifest.files) {
	const from = join(source, file.path);
	const digest = createHash('sha256').update(readFileSync(from)).digest('hex');
	if (digest !== file.sha256) {
		console.error(`${file.path}: checksum does not match datasets.json`);
		process.exit(1);
	}
	copyFileSync(from, join(target, file.path));
}
copyFileSync(manifestPath, join(target, 'datasets.json'));
console.log(`Copied ${manifest.files.length} files from ${source} (generated ${manifest.generated_at}).`);
