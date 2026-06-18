# Traveller World Generator — v1.5.32 Release Notes

**2613 tests pass. Pylint 10.00/10.**

Schema maintenance release — adds economic characteristic fields to
`importance_detail` and `resource_factor` to the world top-level object.

---

## Economic Characteristics (Issue #100)

Full WBH economic profile per inhabited mainworld. `WorldImportance` gains nine
new fields computed by `attach_importance_detail()`:

| Field | Description |
|-------|-------------|
| `labour_factor` | Population code − 1, clamped ≥ 0 |
| `infrastructure_factor` | Importance + population DMs; `null` for no infrastructure |
| `efficiency_factor` | Die-rolled −5 to +5; pop 0 fixed at −5 |
| `resource_units` | RF × LF × IF × EF (zeros treated as 1) |
| `gwp_base` | IF_adj + min(RF_adj, IF_adj) |
| `gwp_per_capita` | GWP per capita in Credits |
| `gwp_total_mcr` | Total GWP in MCr |
| `development_score` | (GWP_pc / 1000) × (1 − IR/100) |
| `economics_profile` | Compact string e.g. `"765+2"` |

`resource_factor` added to `WorldPhysical` and exposed as a top-level key in
`World.to_dict()`: resource_rating adjusted by TL and trade-code DMs, clamped
to [0, 12].

---

## Schema Changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `labour_factor` | `importance_detail` | integer, min 0 | Added |
| `infrastructure_factor` | `importance_detail` | integer or null | Added |
| `efficiency_factor` | `importance_detail` | integer −5 to +5 | Added |
| `resource_units` | `importance_detail` | integer | Added |
| `gwp_base` | `importance_detail` | integer, min 0 | Added |
| `gwp_per_capita` | `importance_detail` | integer, min 0 | Added |
| `gwp_total_mcr` | `importance_detail` | number | Added |
| `development_score` | `importance_detail` | number | Added |
| `economics_profile` | `importance_detail` | string | Added |
| `resource_factor` | world top-level | integer or null | Added |

---

## Backward Compatibility

`WorldImportance.from_dict()` defaults all new fields to `None` when absent, so
world JSON saved before v1.5.32 loads without error.

---

## Tests

68 new tests across `TestLabourFactor`, `TestInfrastructureFactor`,
`TestEfficiencyFactor`, `TestResourceUnits`, `TestGwpBase`, `TestComputeGwp`,
`TestDevelopmentScore`, and `TestEconomicsProfile`. 2613 tests pass.
