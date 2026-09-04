# Traveller World Generator — v2.0.3 Release Notes

**3179 tests pass (5 skipped). Pylint 10.00/10.**

Feature release implementing issue #44: atmospheric gas retention check using
actual escape velocity and mean temperature (WBH p.87–88).

---

## New Feature — Atmospheric Gas Retention Filter (Issue #44)

Exotic (A), Corrosive (B), and Insidious (C) atmosphere gas mixes are now
filtered against the world's gravitational escape velocity and mean temperature
using the WBH p.87–88 retention formula:

```
world_escape_value = v_e² × 8 / T_K
```

A gas component is retained when its escape value (derived from molar mass)
is less than or equal to the world escape value. Light gases like hydrogen and
helium are removed from the gas mix on small or warm worlds; heavy gases like
carbon dioxide, sulphur dioxide, and krypton are retained even on smaller bodies.

The filter runs after `generate_advanced_mean_temperature()` in the mainworld
physical attachment pipeline, so it uses the full physics-based temperature
rather than a category heuristic.

---

## New Feature — Precise Temperature K for Gas Mix Table DMs (Issue #44 Stage 1)

Gas mix sub-range DMs now use the actual mean temperature in Kelvin rather
than a hardcoded category estimate:

- **Frozen Deep (hz_deviation ≥ 3.01):** DM+3 is now applied only when
  `70 ≤ T_K ≤ 100`, matching the WBH table band exactly.
- **Boiling very-hot (hz_deviation ≤ −2.01):** the ≥ 700 K threshold is
  evaluated against the computed temperature rather than the midpoint estimate.

`compute_basic_temperature_k(hz_deviation, atmosphere)` is a new dice-free
function that returns the deterministic mean temperature in K for use at
gas-mix generation time (before `WorldPhysical` is available). Returns `None`
for extreme cold edge cases that would require a dice roll, preserving the
existing fallback heuristic.

---

## Schema Changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `gas_retention_applied` | `atmosphere.detail` | boolean (optional) | Added. Present and `true` only when one or more gas-mix components were removed by the retention filter. Absent otherwise. |

---

## Backward Compatibility

`AtmosphereDetail.from_dict()` defaults `gas_retention_applied` to `False`
when the key is absent, so JSON produced by v2.0.2 loads without error.

---

## Tests

3179 tests pass (5 skipped). New tests:

- `tests/test_gas_mix_temperature_k.py` — 27 tests: `compute_basic_temperature_k`,
  `_select_gas_mix_table` Frozen Deep DM, other temperature zones unaffected,
  `generate_gas_mix` temperature_k parameter.
- `tests/test_gas_retention_filter.py` — 21 tests: `_world_escape_value` formula,
  `_GAS_ESCAPE_VALUES` completeness, no-op cases, light gas removal, heavy gas
  retention, unknown gas name (conservative keep), serialisation roundtrip.
