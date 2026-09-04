# Release v2.1.4 — Star Cluster Member Stars (Session 202)

**Date:** 2026-09-04  
**Branch:** `v2.1`  
**Session:** 202

---

## Summary

Star Cluster systems now display the spectral classes of all other star systems in
the cluster's centre hex. A compliance fix corrects the brown-dwarf fallback per
WBH p.219 when a nested Unusual result occurs inside a cluster.

---

## New features

- **`StarCluster.member_stars`** — `system_count − 1` spectral classifications for the
  other systems in the cluster's centre hex (e.g. `["G9 V", "M5 V", "BD", ...]`).
  Rolled by new `_roll_cluster_member(age_gyr)` using the same Star Type table +
  DM+1 (when age < 0.2 Gyr) as the primary.
- **System card Members row** — displayed below the cluster metadata in the Star
  Cluster section when `member_stars` is non-empty.

---

## Bug fix

- **Nested Unusual → BD (WBH p.219):** `_roll_cluster_member()` previously returned
  `"M"` when the Star Type table roll hit the Special row. Now returns `"BD"` —
  correct per WBH p.219 which specifies a brown dwarf, not re-entry into the
  Unusual column.

---

## Schema changes

| File | Change |
|------|--------|
| `traveller_system_schema.json` | Added `member_stars` (array of strings) to `StarCluster` properties |
| `traveller_system_schema.json` | Added `member_stars` to `StarCluster` required list |

---

## Test coverage

| Suite | Tests |
|-------|-------|
| `tests/test_star_cluster.py` — `TestMemberStars` (new) | 5 |
| Total passing | 3522 |
| Skipped | 5 |
