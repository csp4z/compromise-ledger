# ADR 0005: SvelteKit, prerendered from the gold exports

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

The Phase 1a site is a handful of pages (dashboard, downloads, method) whose data changes once a
day. ADR 0002 calls for a static-first frontend behind Caddy, with FastAPI for lookups. The
candidates were Next.js and SvelteKit, or no framework at all.

- **Next.js** is the most widely known, but leans toward a Node server and hosted features;
  static export works with limits, and bundles are larger.
- **No framework** (static HTML plus Vite) has the fewest dependencies, but Phase 1b and 2 add
  timeline and profile pages, and hand-written pages scale poorly.
- **SvelteKit** with `adapter-static` prerenders every page to HTML at build time, ships little
  JavaScript, and can still hydrate interactive charts.

## Decision

- `/web` is SvelteKit (Svelte 5, TypeScript) with `adapter-static`. Every page is prerendered.
- Pages read the **gold export files** (`datasets.json` and the JSON exports) at build time.
  The site never reads silver or the lakehouse, and needs no server at runtime.
- The export files are copied into the build, so the download links and the site always come
  from the same export, and the manifest's checksums match what is served.
- Charts use **Observable Plot** (ISC), rendered in the browser from the prerendered data.
- Dependencies are managed with pnpm, with the same 14-day minimum release age as Python.

## Consequences

- The daily job rebuilds the site after exporting. A static host (Caddy) serves it; no Node
  process runs in production.
- Lookups that don't fit a prerendered page go to the read-only API.
- The site's numbers come from gold tables, so they match the downloads and the API.
