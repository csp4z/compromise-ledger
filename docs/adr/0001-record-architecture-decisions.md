# ADR 0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-10-24

## Context

This is a solo-maintained, public project, and its target architecture names many possible
components. Without a written record, components can get added because they were on a diagram
rather than because something needed them. Readers of the repo also need to see *why* the
system looks the way it does.

## Decision

Significant decisions are recorded as ADRs in `docs/adr/`, numbered sequentially, using the
sections Context, Decision, Consequences. These count as significant:

- adding or removing a service, datastore, or framework;
- changing a shared contract (schemas, plugin interfaces, ID scheme);
- making an exception to a hard rule in `CLAUDE.md`.

Accepted ADRs are immutable. A changed decision gets a new ADR that supersedes the old one, and
the old one's status is updated to link to it.

## Consequences

- Every component in the stack can be traced to a documented need.
- A small writing cost per decision, which is intended: it slows down scope creep.
