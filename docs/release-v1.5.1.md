# Traveller World Generator — v1.5.1 Release Notes

**Schema update — patch release.**

---

## Tech Level Detail (issue #98, Sessions 104–121)

New `tech_detail` object added to the `World` JSON schema. Implements WBH §5
Social Characteristics tech level breakdown:

- **High / Low common TL** — High = UWP TL; Low = High + TLM roll + DMs,
  bounded to `[TL÷2, TL]`.
- **Quality-of-life sub-TLs** — Energy, Electronics, Manufacturing, Medical,
  Environmental (computed in dependency order; each uses a WBH-specified base TL
  and DMs for population, trade codes, and habitability).
- **Transportation sub-TLs** — Land, Sea, Air, Space; each with WBH-correct
  base TL, bounds, and DMs. Air is forced to 0 when Atmosphere 0 and TL ≤ 5.
  Sea receives DM −2 (not forced to 0) when Hydrographics 0. Space is bounded
  by `min(Energy TL, Manufacturing TL)` with DMs for size, population, and
  starport class.
- **Military sub-TLs** — Personal (base = Manufacturing TL, upper = Electronics
  TL; Law 0 raises floor to Manufacturing TL rather than forcing 0; DMs for
  government and law level) and Heavy (base = Manufacturing TL, bounded by
  Manufacturing TL; DMs for population, government, law, and trade codes).
- **Technology profile string** — format `H-L-QQQQQ-TTTT-MM` (all eHex digits).

Activated by the `social_detail=true` flag on all relevant FastAPI endpoints
(alongside population, government, and law detail). Applies to the mainworld and
all inhabited secondary worlds and moons. `generate_tech_detail()` accepts `size`
and `trade_codes` parameters used by Space and military sub-TL DMs.

Novelty TL deferred to a separate issue. Balkanised worlds (Government 7)
per-nation law/population DM variation deferred.

---

## Schema changes

| Field | Type | Notes |
|---|---|---|
| `tech_detail` | object (optional) | New top-level property on `World`. Contains 13 integer sub-TL fields and `technology_profile` string. |

---

## Test coverage

**2122 tests pass.**

Tests in `tests/test_tech_detail.py`: bounds and DM tests for all 11 sub-TL
categories plus `TestBoundsInvariants` Hypothesis property-based suite.
