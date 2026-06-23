# Traveller World Generator — v1.5.29 Release Notes

**2460 tests pass. Pylint 10.00/10.**

Schema maintenance release — adds `culture_detail` object containing 8 WBH
cultural traits, their descriptive labels, and a compressed DXUS-CPEM profile
string. Also introduces T5 Cultural Extension (Cx) conversion for worlds read
from TravellerMap.

---

## Cultural Detail — 8 Traits (Sessions 127–129, issue #99)

Inhabited mainworlds and secondary worlds now receive a full cultural profile
following the World Builder's Handbook Social Characteristics — Culture section.
Culture detail is generated when **Social detail** is enabled (gen-ui Options
checkbox, or `?social_detail=true` on the API).

### The eight cultural traits

Each trait is a 2D roll with DMs drawn from other world characteristics and from
previously-rolled traits in the same culture. All values are in the range 1–35
(minimum 1 enforced even on extreme negative DMs). The roll order is fixed so
that later traits can use earlier ones as DM sources without altering seeds for
the preceding rolls.

| Trait | Roll order | Labels | Key DM sources |
|---|---|---|---|
| **Diversity** | 1st | Monolithic / Homogeneous / Diverse / Multicultural / Balkanised | Population, Government, Law Level, PCR |
| **Xenophilia** | 2nd | Xenophobic / Moderate / Welcoming | Starport class, Population, Government D/E, Law A+, Diversity |
| **Uniqueness** | 3rd | Indistinct / Typical / Distinct / Exotic | Starport (inverted from Xenophilia), Diversity, Xenophilia |
| **Symbology** | 4th | Mundane / Moderate / Prominent / Pervasive | Government D/E, Tech Level (0–1, 2–3, 9–11, 12+), Uniqueness |
| **Cohesion** | 5th | Individualistic / Moderate / Communal / Collectivist | Government (3, C, 5, 6, 9), Law Level, PCR, Diversity |
| **Progressiveness** | 6th | Moribund / Conservative / Moderate / Progressive / Innovative | Population, Government (5, B, D, E), Law Level, Diversity, Xenophilia, Cohesion |
| **Expansionism** | 7th | Insular / Moderate / Expansive / Imperialist | Government A/C+, Diversity, Xenophilia |
| **Militancy** | 8th | Peaceful / Moderate / Aggressive / Militaristic | Government A+, Law Level, Xenophilia, Expansionism |

### Cultural profile string — DXUS-CPEM format

All eight traits are compressed into a 9-character string: four eHex digits, a
literal hyphen separator, then four more eHex digits. Each position encodes one
trait value as a single eHex character (0–9, A–Z):

```
D X U S - C P E M
│ │ │ │   │ │ │ └── Militancy
│ │ │ │   │ │ └──── Expansionism
│ │ │ │   │ └────── Progressiveness
│ │ │ │   └──────── Cohesion
│ │ │ └──────────── Symbology
│ │ └────────────── Uniqueness
│ └──────────────── Xenophilia
└────────────────── Diversity
```

Example: `7567-8432` means Diversity 7 (Diverse), Xenophilia 5 (Moderate),
Uniqueness 6 (Typical), Symbology 7 (Moderate), Cohesion 8 (Moderate),
Progressiveness 4 (Conservative), Expansionism 3 (Insular), Militancy 2 (Peaceful).

### World card display

A new **Culture** section appears in the world card when culture detail has been
generated. It shows the profile string followed by all eight traits with their
values and labels:

```
Cultural profile    7567-8432
Diversity           7 — Diverse
Xenophilia          5 — Moderate
Uniqueness          6 — Typical
Symbology           7 — Moderate
Cohesion            8 — Moderate
Progressiveness     4 — Conservative
Expansionism        3 — Insular
Militancy           2 — Peaceful
```

### Enabling culture detail

**Gen-UI:** Enable the **Social detail** checkbox in the Options dialog. This
checkbox controls all social generation (population detail, government detail,
law detail, tech detail, and culture detail) for the mainworld.

**FastAPI / API:** Add `social_detail=true` to any generation request
(`/api/world`, `/api/system`, `/api/map/system`, etc.).

**Python API:** Pass `want_social_detail=True` in `PipelineOptions` when calling
`run_detail_pipeline()`, or call `attach_culture_detail(system, rng=rng)`
directly after `attach_detail()` has run.

### Secondary worlds

All inhabited secondary worlds and moons also receive culture detail when Social
detail is enabled. Secondary worlds always use the standard dice-roll procedure
(the T5 Cx conversion does not apply). The `starport=""` path is used since
secondary worlds have spaceport codes (Y/H/G/F) rather than the A–X starport
scale.

---

## T5 Cultural Extension (Cx) Conversion (Session 130, issue #150)

When a mainworld is read from TravellerMap, the T5 Cultural Extension (Cx) field
is now extracted and used to derive the first four cultural traits instead of
rolling them with dice. The remaining four traits are still rolled with dice + DMs
using the derived Diversity and Xenophilia values.

### Cx format and conversion rules

TravellerMap returns Cx as four eHex characters (HASS) in parentheses, e.g.
`(7567)`. The conversion rules are (WBH §Cultural Extension Conversion):

| Cx digit | Trait | Conversion |
|---|---|---|
| H (Heterogeneity) | **Diversity** | H, clamped to [max(1, Pop−5), Pop+5] |
| A (Acceptance) | **Xenophilia** | A, clamped to [max(1, Imp+Pop−5), Imp+Pop+5] |
| S (Strangeness) | **Uniqueness** | max(1, ceil(S × 3/2)) |
| S2 (Symbols) | **Symbology** | S2, clamped to [max(1, TL−5), TL+5] |

The TravellerMap Importance Extension (Ix) field — an integer like `+2` or `−1`
— provides the Importance modifier for Xenophilia clamping. Secondary worlds are
never assigned Cx attributes; only mainworlds read from TravellerMap use this path.

### Implementation

- `MapWorldData` gains `cx: str = ""` and `importance: int = 0` fields, populated
  by `fetch_world_data()` from the TravellerMap `"Cx"` and `"Ix"` API fields.
- After `reconstruct_world()` in `generate_system_from_map()`, if `map_data.cx`
  is non-empty, `world.cx` and `world.importance` are stamped as dynamic attributes.
- `attach_culture_detail()` checks for `world.cx` and routes to
  `generate_culture_detail_from_cx()` when present; otherwise uses the standard
  dice-roll path.
- The gen-ui TravellerMap path also checks for `world.cx` when generating culture
  detail for a single-world lookup.

---

## Schema Changes

| Field | Location | Type | Change |
|-------|----------|------|--------|
| `culture_detail` | World | object (optional) | Added — present when Social detail was requested |
| `diversity` | `culture_detail` | integer, min 1 | Added |
| `diversity_label` | `culture_detail` | string enum | Added |
| `xenophilia` | `culture_detail` | integer, min 1 | Added |
| `xenophilia_label` | `culture_detail` | string enum | Added |
| `uniqueness` | `culture_detail` | integer, min 1 | Added |
| `uniqueness_label` | `culture_detail` | string enum | Added |
| `symbology` | `culture_detail` | integer, min 1 | Added |
| `symbology_label` | `culture_detail` | string enum | Added |
| `cohesion` | `culture_detail` | integer, min 1 | Added |
| `cohesion_label` | `culture_detail` | string enum | Added |
| `progressiveness` | `culture_detail` | integer, min 1 | Added |
| `progressiveness_label` | `culture_detail` | string enum | Added |
| `expansionism` | `culture_detail` | integer, min 1 | Added |
| `expansionism_label` | `culture_detail` | string enum | Added |
| `militancy` | `culture_detail` | integer, min 1 | Added |
| `militancy_label` | `culture_detail` | string enum | Added |
| `cultural_profile` | `culture_detail` | string, pattern `^[0-9A-Z]{4}-[0-9A-Z]{4}$` | Added |

---

## Backward Compatibility

When loading a saved world JSON that was generated before culture detail existed,
`CultureDetail.from_dict()` defaults all missing trait values to 1 (Xenophobic /
Indistinct / etc.) and recomputes the `cultural_profile` string from those defaults.
No data is lost; the profile simply reflects the minimum floor.

---

## Tests

**180 tests** in `tests/test_culture_detail.py` covering all 8 standard traits
plus 30 new tests added in Session 130 for the Cx conversion path:

- Standard generation: bounds, DM effects, and label tests for all 8 traits;
  DXUS-CPEM profile string format; `to_dict()` / `from_dict()` round-trip;
  backward-compat defaults for each trait; `attach_culture_detail()` mainworld
  and secondary world wiring; 10 Hypothesis property-based bounds tests.
- Cx conversion: `TestParseCxString` (7 tests), `TestFromCxNoneGuard` (2),
  `TestFromCxDiversityMapping` (4), `TestFromCxXenophiliaMapping` (4),
  `TestFromCxUniquenessMapping` (5), `TestFromCxSymbologyMapping` (4),
  `TestFromCxRolledTraits` (3), `TestAttachCultureDetailCxPath` (2).
