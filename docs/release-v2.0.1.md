# Traveller World Generator — v2.0.1 Release Notes

**3112 tests pass. Pylint 10.00/10.**

Maintenance release. Updates the JSON schema to describe Balkanised world
government, law, culture, and military detail added in sessions 183–185.

---

## Schema Changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `balkanised_detail` | `World` top-level | object | Added, optional. Present only for government code 7 worlds when government detail has been attached. `government_detail` is absent when this is present. |
| `balkanised_detail.nation_count` | `balkanised_detail` | integer (2–4) | Added, required. Number of nations in this Balkanised world. |
| `balkanised_detail.ruling_nation_numeral` | `balkanised_detail` | string (const `"I"`) | Added, required. Roman numeral of the dominant nation. |
| `balkanised_detail.nations` | `balkanised_detail` | array (2–4 items) | Added, required. One object per nation. |
| `nations[*].numeral` | `balkanised_detail.nations` | string | Added, required. Roman numeral; `"I"` = ruling (highest strength) nation. |
| `nations[*].government_type` | `balkanised_detail.nations` | integer (0–15) | Added, required. |
| `nations[*].government_name` | `balkanised_detail.nations` | string | Added, required. |
| `nations[*].strength_code` | `balkanised_detail.nations` | string enum (O/F/M/N/S/P) | Added, required. |
| `nations[*].strength_label` | `balkanised_detail.nations` | string | Added, required. |
| `nations[*].centralisation_code` | `balkanised_detail.nations` | string enum (C/F/U) | Added, required. |
| `nations[*].centralisation` | `balkanised_detail.nations` | string | Added, required. |
| `nations[*].authority_code` | `balkanised_detail.nations` | string enum (L/E/J/B) | Added, required. |
| `nations[*].authority` | `balkanised_detail.nations` | string | Added, required. |
| `nations[*].structure_code` | `balkanised_detail.nations` | string | Added, required. |
| `nations[*].structure` | `balkanised_detail.nations` | string | Added, required. |
| `nations[*].nation_profile` | `balkanised_detail.nations` | string | Added, required. WBH government profile string, e.g. `"4-FES"`. |
| `nations[*].law_level` | `balkanised_detail.nations` | integer (0–9) | Added, required. Per-nation law level (2D−7+gov_code, clamped 0–9). |
| `nations[*].law_detail` | `balkanised_detail.nations` | object | Added, optional. Present when law detail has been attached. |
| `nations[*].culture_detail` | `balkanised_detail.nations` | object | Added, optional. Present when culture detail has been attached. |
| `nations[*].military_detail` | `balkanised_detail.nations` | object | Added, optional. Present when social/military detail has been attached. |

---

## Backward Compatibility

`World.from_dict()` defaults `balkanised_detail` to `None` when absent, so
JSON produced by v2.0.0 loads without error.

---

## Tests

3112 tests pass. No new tests in this maintenance release; the Balkanised
world test suite (44 tests across `TestBalkanisedDetail` and
`TestClass4FormBalkanised`) shipped with the underlying feature sessions.
