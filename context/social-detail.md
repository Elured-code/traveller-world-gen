# social-detail.md — traveller_world_population_detail.py

Read this when working on population detail generation: PCR, urbanisation,
major city counts and populations, or the `PopulationDetail` / `City` dataclasses.

See `context/data-structures.md` for the `World.population_detail` and
`WorldDetail.population_detail` field definitions.

---

## Module overview

`traveller_world_population_detail.py` implements the WBH Social Characteristics
checklist (§2) for population. It is fully independent of the other generation
modules — it imports only from the standard library.

Injectable RNG: module-level `_rng` sentinel (initially `random` the module).
All public functions accept `rng: Optional[random.Random] = None`.

---

## Public API

```python
generate_pcr(
    pop_code: int, size: int, tl: int, government: int,
    trade_codes: list,
    is_tidal_lock: bool = False,
    atm: int = 6,
    rng: Optional[random.Random] = None,
) -> int
    # Roll Population Concentration Rating (0–9).
    # If pop_code < 6 and 1D > pop_code → PCR = 9 immediately (all in one area).
    # Otherwise: 1D + DMs on PCR table.
    # Minimum PCR = 1 when pop_code ≥ 9; else minimum = 0. Maximum = 9.
    # Sets _rng when rng is provided.

generate_urbanisation_pct(
    pcr: int, pop_code: int, size: int, tl: int,
    government: int, law_level: int,
    trade_codes: list, atm: int = 6,
    rng: Optional[random.Random] = None,
) -> int
    # Roll urbanisation % (0–100).
    # 2D + DMs → result → range table → inner dice roll for exact %.
    # Some DMs carry floor/ceiling constraints (themselves rolled).
    # Minimum supersedes conflicting maximum (WBH rule).

generate_population_detail(
    pop_code: int, p_value: int,
    size: int, tl: int, government: int, law_level: int,
    trade_codes: list,
    atm: int = 6,
    is_tidal_lock: bool = False,
    rng: Optional[random.Random] = None,
) -> Optional[PopulationDetail]
    # Returns None when pop_code == 0 (uninhabited).
    # Calls generate_pcr() → generate_urbanisation_pct() → major cities → cities.
    # Builds and returns a PopulationDetail.

attach_population_detail(
    system: TravellerSystem,
    rng: Optional[random.Random] = None,
) -> None
    # Applies generate_population_detail() to system.mainworld when pop > 0.
    # Also applies to each inhabited secondary WorldDetail and moon WorldDetail.
    # Secondary world p_value is rolled on the fly (2D3 procedure).
    # is_tidal_lock is always False for secondaries (no WorldPhysical available).
```

---

## PCR DM table

| Condition | DM |
|---|---|
| Size 1 | +2 |
| Size 2–3 | +1 |
| Twilight zone world (1:1 tidal lock) | +2 |
| Min sustainable TL ≥ 8 | +3 |
| Min sustainable TL 3–7 | +1 |
| Population 8 | −1 |
| Population 9+ | −2 |
| Government 7 | −2 |
| TL 0–1 | −2 |
| TL 2–3 | −1 |
| TL 4–9 | +1 |
| Agricultural | −2 |
| Industrial | +1 |
| Non-Agricultural | −1 |
| Rich | +1 |

Min sustainable TL uses the same table as `traveller_world_detail.py`:
atm 0/1 → 8; atm 2/3 → 5; atm 4/5 → 3; atm 6–9 → 0; atm 10+ → 8.
(The function is duplicated rather than imported to avoid circular dependencies.)

---

## Urbanisation DM table

| Condition | DM | Constraint |
|---|---|---|
| PCR 0–2 | −3+PCR | — |
| PCR 7+ | −6+PCR | — |
| Min sustainable TL 0–3 | −1 | — |
| Size 0 | +2 | — |
| Population 8 | +1 | — |
| Population 9 | +2 | min = 18+1D% |
| Population A+ | +4 | min = 50+1D% |
| Government 0 | −2 | — |
| Law Level 9+ | +1 | — |
| TL 0–2 | −2 | max = 20+1D% |
| TL 3 | −1 | max = 30+1D% |
| TL 4 | +1 | max = 60+1D% |
| TL 5–9 | +2 | max = 90%+1D |
| Agricultural | −2 | max = 90%+1D |
| Non-Agricultural | +2 | — |

The 2D+DM result maps to a range, then inner dice produce the exact %:

| Result | Range formula | % range |
|---|---|---|
| ≤ 0 | — | 0% |
| 1 | 1D | 1–6% |
| 2 | 6 + 1D | 7–12% |
| 3 | 12 + 1D | 13–18% |
| 4 | 18 + 1D | 19–24% |
| 5 | 22 + 1D×2 + D2 | 25–36% |
| 6 | 34 + 1D×2 + D2 | 37–48% |
| 7 | 46 + 1D×2 + D2 | 49–60% |
| 8 | 58 + 1D×2 + D2 | 61–72% |
| 9 | 70 + 1D×2 + D2 | 73–84% |
| 10 | 84 + 1D | 85–90% |
| 11 | 90 + 1D | 91–96% |
| 12 | 96 + D3 | 97–99% |
| 13+ | 100 | ≥99% |

D2 = randint(1,2); D3 = ceil(1D/2).

---

## Major city dispatch — 5 cases

| Case | Condition | City count | Total major city pop |
|---|---|---|---|
| 1 | PCR = 0 | 0 | 0 |
| 2 | Pop ≤ 5, PCR = 9 | 1 | Total urban pop |
| 3 | Pop ≤ 5, PCR 1–8 | min(9−PCR, pop_code), min 1 | Total urban pop |
| 4 | Pop ≥ 6, PCR = 9 | max(pop_code − 2D, 1) | Total urban pop |
| 5 | Pop ≥ 6, PCR 1–8 | ceil(2D − PCR + urb_frac × 20 / PCR) | (PCR / (1D + 7)) × urban pop |

Case 5 city count validated: Zed Prime (Pop 7, PCR 3, urb 39%) →
`ceil(7 − 3 + 0.39 × 20 / 3) = ceil(6.6) = 7`.
Result is clamped to [1, 31]; if pop_code < 6, further capped at pop_code.

---

## City population distribution

- **0 cities (PCR 0):** No city list.
- **1 city:** Entire total major city pop.
- **2–3 cities:** Each city gets `(1D+3) × 10%` of the remaining pool; last city gets the remainder. Each city guaranteed ≥ 1% of total.
- **4+ cities (PCR 1–8):** Chunk algorithm —
  1. Base 1% per city.
  2. `remaining = 100 − city_count`; `chunk_pct = PCR` (max); `chunk_count = max(2×city_count, remaining÷chunk_pct)`.
  3. Cycle through cities rolling 1D chunks until pool exhausted.
  4. Held-back % goes to the next city in sequence.
  5. Sort descending; cap display list at 10.

---

## Population profile format

`{pop_hex}-{p_value}-{pcr}-{urbanisation_pct}-{major_city_count}`

Where `pop_hex` is the eHex character for the population code (e.g. `"6"`, `"A"`).
Example: `"6-5-3-39-7"` = Population 6, P=5, PCR 3, 39% urbanised, 7 major cities.

---

## Dataclasses

```python
@dataclass
class City:
    population: int
    codes: list    # e.g. ["Cw"] for world capital; empty by default
    # to_dict() / from_dict()

@dataclass
class PopulationDetail:    # pylint: disable=too-many-instance-attributes
    total_population: int
    p_value: int                      # 1–9
    pcr: int                          # 0–9
    pcr_label: str                    # e.g. "Partially Dispersed"
    urbanisation_pct: int             # 0–100
    urban_population: int
    major_city_count: int             # 0–31
    major_city_total_population: int
    cities: list                      # List[City], up to 10
    population_profile: str           # "P-p-C-%-M"
    # to_dict() / from_dict()
```

---

## City population rounding (Session 101)

`_round_sig(n: int, sig: int = 3) -> int` rounds any positive integer to
`sig` significant figures (default 3). Applied in `generate_population_detail()`
to both `major_city_total_population` and each individual `City.population`
before they are stored. Raw internal values (used for distribution arithmetic)
are not rounded until the final storage step.

The test `test_city_pops_within_total` uses a relative tolerance of 0.5% of the
rounded total (rather than the previous `+1` flat tolerance) because independently
rounded city populations may sum to slightly more than the rounded total.

---

## Integration notes

- `attach_population_detail()` is always a **separate explicit step**. Never
  call it automatically inside `generate_full_system()`.
- For secondary worlds, `p_value` is rolled on the fly using the 2D3 procedure
  (same as `generate_population_multiplier()`). The result may differ from any
  p_value previously recorded for that world.
- `is_tidal_lock` requires `WorldPhysical.tidal_status == "1:1_lock"`, which is
  only available for the mainworld (when physical detail has been generated).
  Secondary worlds always receive `is_tidal_lock=False`.
- The `_minimal_tl()` lookup is duplicated from `traveller_world_detail.py` to
  avoid a circular import chain.

---

## Culture Detail (Session 129–130: `traveller_world_culture_detail.py`)

Cultural trait generation follows the World Builder's Handbook Social
Characteristics Culture section. All 8 traits use 2D + DMs; roll order is
sequential to preserve seed stability across editions. The cultural profile
is the full 9-character DXUS-CPEM format.

### 8 Cultural Traits

| Trait | Range | Labels | DM Sources |
|---|---|---|---|
| **Diversity** | 1–35 | Monolithic / Homogeneous / Diverse / Multicultural / Balkanised | Population, Government (3, 7, D–F), Law, PCR |
| **Xenophilia** | 1–35 | Xenophobic / Moderate / Welcoming | Population, Government (D, E), Law (A+), Starport (A–X, inverted), Diversity feedback |
| **Uniqueness** | 1–35 | Indistinct / Typical / Distinct / Exotic | Starport (inverted), Diversity feedback, Xenophilia feedback |
| **Symbology** | 1–35 | Mundane / Moderate / Prominent / Pervasive | Government (D, E), Tech Level (0–1, 2–3, 9–11, 12+), Uniqueness feedback |
| **Cohesion** | 1–35 | Individualistic / Moderate / Communal / Collectivist | Government (3, C, 5, 6, 9), Law (0–2, A+), PCR (0–3, 7+), Diversity feedback |
| **Progressiveness** | 1–35 | Moribund / Conservative / Moderate / Progressive / Innovative | Population (6–8, 9+), Government (5, B, D–E), Law (9–B, C+), Diversity, Xenophilia, Cohesion feedback |
| **Expansionism** | 1–35 | Insular / Moderate / Expansive / Imperialist | Government (A, C+), Diversity (1–3, C+), Xenophilia (1–5, 9+) |
| **Militancy** | 1–35 | Peaceful / Moderate / Aggressive / Militaristic | Government (A+), Law (9–B, C+), Xenophilia, Expansionism feedback |

### Public API

```python
generate_culture_detail(
    population: int, government: int, law_level: int,
    pcr: int = 0, starport: str = "", tech_level: int = 0,
    rng: Optional[random.Random] = None,
) -> Optional[CultureDetail]
    # Roll all 8 traits with 2D + DMs. Returns None for uninhabited (pop=0).
    # Sets _rng when rng is provided. All traits have min value 1.

generate_culture_detail_from_cx(
    cx: str, population: int, importance: int,
    government: int, law_level: int,
    pcr: int = 0, starport: str = "", tech_level: int = 0,
    rng: Optional[random.Random] = None,
) -> Optional[CultureDetail]
    # Generate culture detail from T5 Cultural Extension (Cx) string.
    # DXUS traits (Diversity, Xenophilia, Uniqueness, Symbology) are derived
    # from the Cx HASS code with clamping; CPEM traits are rolled with dice+DMs.
    # See "T5 Cx Conversion" section below for mapping rules.
    # Returns None for uninhabited (pop=0).

attach_culture_detail(
    system: TravellerSystem, rng: Optional[random.Random] = None,
) -> None
    # Applies culture detail to system.mainworld when pop > 0.
    # Routes to generate_culture_detail_from_cx() if world.cx is present;
    # otherwise uses generate_culture_detail().
    # Also applies to each inhabited secondary WorldDetail and moon WorldDetail
    # (always uses standard generation for secondaries; cx is not stamped on them).
```

### T5 Cultural Extension Conversion (Session 130)

When reading a mainworld from TravellerMap, the Cx field (4 eHex chars: HASS)
is available and may be converted to the first four cultural traits. The
`world.cx` and `world.importance` attributes are stamped dynamically after
`reconstruct_world()` in `generate_system_from_map()`.

**Conversion rules (WBH §):**

```
H (Heterogeneity)  → Diversity  = H,     clamped to [max(1, Pop−5), Pop+5]
A (Acceptance)     → Xenophilia = A,     clamped to [max(1, Imp+Pop−5), Imp+Pop+5]
S (Strangeness)    → Uniqueness = max(1, ceil(S × 3/2))
S2 (Symbols)       → Symbology  = S2,    clamped to [max(1, TL−5), TL+5]
```

The remaining four traits (Cohesion, Progressiveness, Expansionism, Militancy)
are always rolled with dice + DMs using the derived Diversity and Xenophilia
values.

### Dataclass

```python
@dataclass
class CultureDetail:  # pylint: disable=too-many-instance-attributes
    diversity: int
    diversity_label: str
    xenophilia: int
    xenophilia_label: str
    uniqueness: int
    uniqueness_label: str
    symbology: int
    symbology_label: str
    cohesion: int
    cohesion_label: str
    progressiveness: int
    progressiveness_label: str
    expansionism: int
    expansionism_label: str
    militancy: int
    militancy_label: str
    cultural_profile: str        # DXUS-CPEM format: 9 chars, hyphen at position 4

    # to_dict() / from_dict() — backward-compat defaults missing traits to 1
```

### Integration notes

- `attach_culture_detail()` is always a **separate explicit step**. Never
  call it automatically inside `generate_full_system()` or inside
  `attach_detail()` — it is wired into `run_detail_pipeline()` only.
- When `world.cx` is present (from TravellerMap), culture detail uses the
  Cx-derived mapping for DXUS. The `world.importance` attribute (Ix field)
  is used as the Importance modifier for Xenophilia clamping.
- Secondary worlds never receive `cx` attributes (only read from TravellerMap
  mainworld). They always use standard `generate_culture_detail()`.
- All trait values have min 1 even with extreme negative DMs (enforced by
  `max(1, roll + dm)`).
