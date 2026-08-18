# Traveller World Generator — v2.0.2 Release Notes

**3124 tests pass (5 skipped). Pylint 10.00/10.**

Feature release implementing issue #160: city spaceport generation for mainworld
major cities (WBH §8 p.196).

---

## New Feature — City Spaceports (Issue #160)

Major cities on the mainworld may now have their own spaceport facility.
Each city rolls 1D + population DM on the WBH p.195 spaceport class table:

- Cities with population ≥ 1,000,000 receive DM +2.
- Cities with population < 1,000,000 receive DM 0.
- Result ≤ 2 → Class Y (no facility; excluded from output).
- Result 3 → Class H (cleared landing area).
- Result 4–5 → Class G (basic facility).
- Result ≥ 6 → Class F (good facility).

City spaceports are generated automatically by `attach_starport_detail()` when
`population_detail` is already attached. They appear in the world card as detail
rows under the starport inner-card.

---

## Schema Changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `city_spaceports` | `starport_detail` | array (optional) | Added. Present only when at least one city rolls a non-Y result. Absent otherwise. |
| `city_spaceports[*].city_rank` | `city_spaceports` items | integer (≥ 1) | Added, required. 1 = largest city. |
| `city_spaceports[*].city_population` | `city_spaceports` items | integer (≥ 0) | Added, required. |
| `city_spaceports[*].spaceport_class` | `city_spaceports` items | string enum (F/G/H) | Added, required. Y results are excluded from the array. |

---

## Backward Compatibility

`StarportDetail.from_dict()` defaults `city_spaceports` to `[]` when the key
is absent, so JSON produced by v2.0.1 loads without error.

---

## Tests

3124 tests pass (5 skipped). 12 new tests in `TestCitySpaceports` covering:
DM helper, empty-cities edge case, Y-exclusion, class assignment, city rank
ordering, serialisation round-trip, and `attach_starport_detail()` integration.
