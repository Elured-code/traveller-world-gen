# Traveller World Generator — v1.5.1 Release Notes

**Schema update — patch release.**

---

## Tech Level Detail (issue #98)

New `tech_detail` object added to the `World` JSON schema. Implements WBH §5
Social Characteristics tech level breakdown:

- **High / Low common TL** — High = UWP TL; Low = High + TLM roll + DMs,
  bounded to `[TL÷2, TL]`.
- **Quality-of-life sub-TLs** — Energy, Electronics, Manufacturing, Medical,
  Environmental (computed in dependency order; each bounded relative to its
  predecessor).
- **Transportation sub-TLs** — Land, Sea (0 when Hydrographics 0), Air (0 when
  Atmosphere 0 and TL ≤ 5), Space.
- **Military sub-TLs** — Personal (0 when Law Level 0), Heavy.
- **Technology profile string** — format `H-L-QQQQQ-TTTT-MM` (all eHex digits).

Activated by the `social_detail=true` flag on all relevant FastAPI endpoints
(alongside population, government, and law detail). Applies to the mainworld and
all inhabited secondary worlds and moons.

Novelty TL deferred to a separate issue.

---

## Schema changes

| Field | Type | Notes |
|---|---|---|
| `tech_detail` | object (optional) | New top-level property on `World`. Contains 13 integer sub-TL fields and `technology_profile` string. |

---

## Test coverage

Tests added in `tests/test_tech_detail.py`.
