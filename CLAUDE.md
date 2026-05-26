# CLAUDE.md — Traveller World & System Generator

**Last updated:** 2026-05-26 (Session 73)  
**Branch:** `v1.4.0` · **Main:** `main`  
**Virtual environment:** `.venv` (Python 3.11, includes PySide6)

This file is a router. Read `context/common.md` first on every session, then
read only the context files listed below for the specific task at hand.

---

## Always read first

- [`context/common.md`](context/common.md) — repo layout, code quality, tests, licence, CI

---

## Routing table

| Task | Read these files |
|------|-----------------|
| Any task involving data structures, type signatures, or dataclasses | [`context/data-structures.md`](context/data-structures.md) |
| Understanding the generation pipeline, entry points, or RNG/seed behaviour | [`context/generation-pipeline.md`](context/generation-pipeline.md) |
| `traveller_stellar_gen.py` or `traveller_orbit_gen.py` | [`context/stellar-orbit.md`](context/stellar-orbit.md) + [`context/data-structures.md`](context/data-structures.md) |
| `traveller_system_gen.py`, `traveller_world_gen.py`, `traveller_world_physical.py`, or `traveller_hydro_detail.py` | [`context/system-world.md`](context/system-world.md) + [`context/data-structures.md`](context/data-structures.md) + [`context/generation-pipeline.md`](context/generation-pipeline.md) |
| `traveller_world_detail.py`, `traveller_moon_gen.py`, or `traveller_belt_physical.py` | [`context/detail-moon.md`](context/detail-moon.md) + [`context/data-structures.md`](context/data-structures.md) |
| `traveller_map_fetch.py` | [`context/map-fetch.md`](context/map-fetch.md) + [`context/generation-pipeline.md`](context/generation-pipeline.md) |
| `function_app.py` or `shared/helpers.py` | [`context/api-layer.md`](context/api-layer.md) |
| `system_map.py` | [`context/system-map.md`](context/system-map.md) + [`context/data-structures.md`](context/data-structures.md) |
| `gen-ui/app.py` | [`context/gen-ui.md`](context/gen-ui.md) + [`context/data-structures.md`](context/data-structures.md) |
| Bug investigation or compliance review | [`context/compliance-audit.md`](context/compliance-audit.md) + relevant module file(s) above |
| Implementing a deferred feature | [`context/deferred-features.md`](context/deferred-features.md) + relevant module file(s) above |
| Any work touching temperature, HZ, or orbital position | Also read [`context/data-structures.md`](context/data-structures.md) (HZ sign convention + Orbit# vs AU table) |

---

## Always-needed facts (no file read required)

- **Pylint:** `.venv/bin/pylint <file>` — target **10.00/10 per file**
- **Tests:** `.venv/bin/pytest tests/ -q` — **1450 tests**, all must pass
- **RNG:** Global shared state; seed set once in `generate_full_system()`.
  Adding any dice roll anywhere shifts all subsequent results for that seed.
- **`attach_detail()` is always a separate explicit step.** Never call it
  automatically inside `generate_full_system()`.
- **New dice rolls belong at the end of the pipeline** to minimise seed disruption.

---

## Update rules

After any session in which code, APIs, tests, or documented behaviour change:

1. Add one row to [`context/session-history.md`](context/session-history.md).
2. Update **Last updated** and session number at the top of this file.
3. Update the specific context file(s) whose content changed:

| What changed | Update which file |
|---|---|
| Data structure field added/removed/renamed | `context/data-structures.md` |
| New API endpoint or error code | `context/api-layer.md` |
| Helpers.py function added or signature changed | `context/api-layer.md` |
| Compliance bug found and fixed | `context/compliance-audit.md` |
| Deferred feature implemented | Remove row from `context/deferred-features.md` |
| New deferred feature identified | Add row to `context/deferred-features.md` |
| Module API or public function changed | The matching module context file |
| New module created | New `context/<name>.md` + add row to routing table above |
| Pipeline entry point added or changed | `context/generation-pipeline.md` |
| Gen-UI widget or interaction changed | `context/gen-ui.md` |
| SVG map generation changed | `context/system-map.md` |
| TravellerMap fetch behaviour changed | `context/map-fetch.md` |
| Pylint suppression pattern added | `context/common.md` |

4. Update `RELEASE-NOTES.md` with a summary of new features, bug fixes, and test
   count changes. Add a new version section when shipping to `main`; append to the
   current draft section otherwise.
5. Do **not** delete compliance audit entries.  
6. Do **not** modify `docs/developer-guide.md` via this workflow — it is
   human-facing documentation maintained separately from the AI context layer.
