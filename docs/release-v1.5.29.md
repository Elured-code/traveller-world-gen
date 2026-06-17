# Traveller World Generator — v1.5.29 Release Notes

**2460 tests pass. Pylint 10.00/10.**

Schema maintenance release — adds `culture_detail` object with 8 cultural traits
and introduces T5 Cultural Extension (Cx) conversion for TravellerMap-sourced worlds.

---

## T5 Cultural Extension (Cx) Conversion (Session 130, issue #150)

When reading a mainworld from TravellerMap, the T5 Cultural Extension (Cx) field
is now extracted and converted to the first four cultural traits (Diversity,
Xenophilia, Uniqueness, Symbology) per World Builder's Handbook rules. The
remaining four traits (Cohesion, Progressiveness, Expansionism, Militancy) are
rolled with dice + DMs using the derived cultural values.

**Conversion rules (WBH):**

- **Diversity** ← H (Heterogeneity), clamped to [max(1, Pop−5), Pop+5]
- **Xenophilia** ← A (Acceptance), clamped to [max(1, Imp+Pop−5), Imp+Pop+5]
- **Uniqueness** ← max(1, ceil(S × 3/2)), where S is Strangeness (0–10)
- **Symbology** ← S2 (Symbols), clamped to [max(1, TL−5), TL+5]

The Importance (Ix) field from TravellerMap is used as the modifier for Xenophilia
clamping. Secondary worlds never receive Cx attributes (conversion applies only to
mainworlds read from TravellerMap).

### Implementation

- `MapWorldData` adds `cx: str = ""` and `importance: int = 0` fields
- `fetch_world_data()` extracts `"Cx"` and `"Ix"` from TravellerMap API
- `generate_system_from_map()` stamps `world.cx` and `world.importance` after
  `reconstruct_world()` if Cx is present
- `generate_culture_detail_from_cx()` performs the conversion and rolls remaining
  four traits
- `attach_culture_detail()` routes to `generate_culture_detail_from_cx()` when
  `world.cx` is present; otherwise uses standard generation

### Schema changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `culture_detail` | World | object | Added (all 8 cultural traits + labels + profile) |
| `diversity`, `diversity_label` | `culture_detail` | integer [1–35], string | Added |
| `xenophilia`, `xenophilia_label` | `culture_detail` | integer [1–35], string | Added |
| `uniqueness`, `uniqueness_label` | `culture_detail` | integer [1–35], string | Added |
| `symbology`, `symbology_label` | `culture_detail` | integer [1–35], string | Added |
| `cohesion`, `cohesion_label` | `culture_detail` | integer [1–35], string | Added |
| `progressiveness`, `progressiveness_label` | `culture_detail` | integer [1–35], string | Added |
| `expansionism`, `expansionism_label` | `culture_detail` | integer [1–35], string | Added |
| `militancy`, `militancy_label` | `culture_detail` | integer [1–35], string | Added |
| `cultural_profile` | `culture_detail` | string (regex) | Added (DXUS-CPEM format) |

---

## Tests

30 new tests added to `tests/test_culture_detail.py`:

- `TestParseCxString` (7 tests) — Cx string parsing with various formats
- `TestFromCxNoneGuard` (2 tests) — None guard for uninhabited worlds
- `TestFromCxDiversityMapping` (4 tests) — Diversity derivation and clamping
- `TestFromCxXenophiliaMapping` (4 tests) — Xenophilia derivation and clamping
- `TestFromCxUniquenessMapping` (5 tests) — Strangeness-to-Uniqueness scaling
- `TestFromCxSymbologyMapping` (4 tests) — Symbology derivation and clamping
- `TestFromCxRolledTraits` (3 tests) — Rolled trait minimums and profile format
- `TestAttachCultureDetailCxPath` (2 tests) — Routing decision in attach_culture_detail

---

## Backward Compatibility

All fields in `CultureDetail.from_dict()` default to 1 when absent (for old saved data).
The `cultural_profile` string is recomputed if missing.
