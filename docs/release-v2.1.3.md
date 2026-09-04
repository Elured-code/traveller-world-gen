# Release v2.1.3 — Star Cluster Metadata (Issue #182)

**Date:** 2026-09-03  
**Branch:** `v2.1`  
**Session:** 201

---

## Summary

Full Star Cluster metadata generation for Peculiar environment: Star Cluster systems
(Worlds Beyond the Horizon p.219). The `StarSystem` JSON output now includes a
`star_cluster` object when the primary is a Star Cluster environment type.

---

## New features

- **`StarCluster` dataclass** — age, extent (single/multi-hex), hex diameter, system count,
  merged-star flag, and jump restriction string.
- **Merged-star orbit DMs** — when the primary star has already evolved off the main
  sequence (`merged_star=True`), `generate_orbits()` applies reduced world counts and
  eccentricity DM+2 (disrupted planetary system).
- **System card Star Cluster section** — Age / Extent / Hex Ø / Systems / Merged Star /
  Jump Restriction table in both `system_card.html` and the Azure-synced template copy.

---

## Schema changes

| File | Change |
|------|--------|
| `traveller_system_schema.json` | Added `StarCluster` `$def` with 6 required fields (`age_gyr`, `single_hex`, `hex_diameter`, `system_count`, `merged_star`, `jump_restriction`) |
| `traveller_system_schema.json` | Added `star_cluster` optional property on the root `StarSystem` object (`$ref: "#/$defs/StarCluster"`) |

---

## Test coverage

| Suite | Tests |
|-------|-------|
| `tests/test_star_cluster.py` (new) | 25 |
| Total passing | 3517 |
| Skipped | 5 |
