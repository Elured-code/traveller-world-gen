# Understanding `traveller_world_tech_detail.py`

A guide for Python beginners. This file takes a world's UWP tech level and expands
it into a structured technological profile: a range from the highest technology in
common use down to the lowest, plus 11 sector-specific sub-TLs covering energy,
electronics, manufacturing, medical care, environmental systems, four transport
modes, and military capability. The result is a `TechDetail` object and a compact
technology profile string.

---

## What this file does

In Traveller, a world's UWP tech level (0–F+) represents the overall sophistication
of its technology. But a single digit conceals variation: a world might have
cutting-edge medical technology while its military hardware is a generation behind,
or its starport might be capable of Jump-3 maintenance while rural settlements still
use TL-5 farming equipment. This file answers those questions by implementing WBH §5
Social Characteristics.

The main public function is `generate_tech_detail()`. It computes the following in
order:

1. **High common TL** — always equal to the UWP TL. This is the most advanced
   technology widely available on the world.
2. **Low common TL** — how far down ordinary people's day-to-day technology falls.
   Computed as `tl_high + TLM_roll + DMs`, clamped to a floor that is the higher of
   `tl_high÷2` or the minimum TL required by the world's atmosphere. Factors like
   small population, low PCR, and certain government types lower the floor; a high
   PCR (concentrated urban population) raises it.
3. **Five quality-of-life sub-TLs** (Energy, Electronics, Manufacturing, Medical,
   Environmental) — each rolled as `base_TL + TLM_roll + DMs`, clamped to bounds
   computed in dependency order. Each sub-TL uses a different base TL: Energy uses
   High TL, Electronics uses Energy TL, Manufacturing uses Electronics TL, Medical
   uses Electronics TL (with a starport-derived floor), and Environmental uses
   Manufacturing TL. Population, trade codes, and habitability rating affect DMs.
4. **Four transportation sub-TLs** (Land, Sea, Air, Space) — Air is forced to 0 if
   atmosphere is 0 and TL ≤ 5. Sea is not forced to 0 on dry worlds — instead,
   Hydrographics 0 applies a DM −2 penalty, reflecting very low capability rather
   than none. Space uses `min(Energy TL, Manufacturing TL)` as both its base and
   upper bound; size, population, and starport class affect DMs.
5. **Two military sub-TLs** (Personal, Heavy) — both use Manufacturing TL as base.
   Personal military is bounded above by Electronics TL; when Law Level is 0
   (weapons freely available), its lower bound is raised to Manufacturing TL rather
   than being forced to zero. Both sub-TLs receive DMs from government code, law
   level, population, and trade codes.
6. **Technology profile string** — formatted as `H-L-QQQQQ-TTTT-MM` using eHex
   digits (see "The technology profile string" section below).

The function returns `None` when `population == 0` (uninhabited worlds have no
technology to profile).

The companion function `attach_tech_detail()` walks a `TravellerSystem` and applies
tech detail to the mainworld and every inhabited secondary world and moon. A separate
helper `_tech_detail_for_det()` handles secondary worlds, where atmosphere and
hydrographics are read from the compact SAH string rather than a full `WorldPhysical`
object.

Implements WBH §5 Social Characteristics (tech level breakdown). Novelty TL is
deferred to issue #137.

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | `random`, `dataclasses`, plus `TYPE_CHECKING` guard for `TravellerSystem` |
| Module-level `_rng` | Injectable RNG sentinel |
| `_TECH_MIN_TL` | Dict: atmosphere code → minimum sustainable TL |
| `_HAB_MIN_TL` | List: habitability rating → minimum TL (index = rating) |
| `_TLM_TABLE` | Dict: 2D result → TL Modifier (−3 to +3); missing keys return 0 |
| `_STARPORT_MED_FLOOR` | Dict: starport letter → medical TL lower bound |
| Helpers | `_tlm()`, `_ehex()`, `_clamp()`, `_min_tl()` |
| `TechDetail` dataclass | 14 fields: two common TLs, 11 sub-TLs, one profile string |
| `generate_tech_detail()` | Main public entry point |
| `_tech_detail_for_det()` | Secondary-world wrapper (reads from SAH string) |
| `_attach_det_tech()` | Attaches tech detail to one WorldDetail and its moons |
| `attach_tech_detail()` | System-wide attachment: mainworld + secondaries + moons |

---

## Key Python concept: the TLM table and `.get()` with a default

The Tech Level Modifier (TLM) is a small random adjustment drawn from a 2D table.
Most 2D results give a modifier of 0 — only the extremes (2, 3, 4 and 10, 11, 12)
give non-zero modifiers. The table is stored as a dict with only the non-zero entries:

```python
_TLM_TABLE: dict[int, int] = {2: -3, 3: -2, 4: -1, 10: 1, 11: 2, 12: 3}
```

The lookup uses `.get(result, 0)`:

```python
def _tlm() -> int:
    result = _rng.randint(1, 6) + _rng.randint(1, 6)
    return _TLM_TABLE.get(result, 0)
```

`.get(key, default)` returns `default` when the key is not in the dict. Because
results 5–9 are not listed, they all return 0, which is exactly what the WBH table
specifies. This is more readable than checking every possible value with `if/elif`.

---

## Key Python concept: clamping values with `max()` and `min()`

Most sub-TL calculations end with a clamp: a result that is too low gets raised to a
floor, and a result that is too high gets cut down to a ceiling. The helper function
`_clamp()` does this:

```python
def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(value, hi))
```

`min(value, hi)` ensures the result never exceeds the ceiling. `max(lo, ...)` ensures
it never falls below the floor. The function also handles the degenerate case where
`lo > hi` by returning `lo` (the floor wins).

Inside `generate_tech_detail()`, a local closure called `_sub_tl` uses this pattern:

```python
def _sub_tl(lo: int, hi: int, dm: int = 0, base: Optional[int] = None) -> int:
    raw = (tl_high if base is None else base) + _tlm() + dm
    return max(0, _clamp(raw, lo, hi))
```

The `base` parameter lets each sub-TL roll from a different starting TL (e.g.
Medical rolls from Electronics TL, not High TL). The `dm` parameter applies
DMs for population, trade codes, government, and similar factors. The outer
`max(0, ...)` ensures sub-TLs are never negative even if the clamp produces a
result below zero.

---

## The High and Low common TL in game terms

The **High common TL** is the UWP TL — the best technology a world can reliably
produce and maintain. An Imperial Navy ship can always source TL-12 parts on a
TL-12 world.

The **Low common TL** is the floor of everyday technology: the TL at which ordinary
citizens — farmers, labourers, small-town inhabitants — actually live. On a TL-12
world, that might still be TL-9 or TL-10 outside the major cities.

The Low common TL has a floor set by two constraints:
- It can never be less than half of `tl_high`.
- It can never be less than the minimum TL required to survive the atmosphere (e.g.
  a vacuum world needs at least TL-8 just to keep everyone alive in pressure suits).

The bug note in the brief describes a degenerate case: if `min_tech > tl_high`
(for example, an atmosphere-A world that somehow has TL-0), the calculated floor
would exceed the ceiling, making a valid clamp range impossible. The fix is:

```python
low_floor = min(tl_high, max(min_tech, tl_high // 2))
```

This caps the floor at `tl_high` so the range is always at least `[tl_high, tl_high]`.

---

## The dependency chain for sub-TLs

Sub-TLs are not independent rolls — each sector's technology depends on the ones
that underpin it. The chain runs from most fundamental to most derived:

```
Energy
  └─ Electronics (bounded by Energy ± a few levels)
       └─ Manufacturing (bounded by Electronics)
            ├─ Medical (bounded by Electronics, floored by starport)
            ├─ Environmental (bounded by Energy)
            ├─ Land / Sea / Air (all bounded by Energy)
            │        └─ Space (bounded by Energy and Manufacturing)
            └─ Personal military (bounded by Electronics and Manufacturing)
                 └─ Heavy military (bounded by Manufacturing)
```

For example, you cannot have high-tech electronics without a decent energy
infrastructure to power them. And you cannot have sophisticated medical equipment
without the electronics to run the diagnostics.

---

## Special zero-forcing and floor-raising rules

Some sub-TLs have conditions that force them to zero or raise their lower bound:

| Sub-TL | Condition | Effect | Why |
|--------|-----------|--------|-----|
| Air | `atmosphere == 0` and `tl_high <= 5` | Forced to 0 | No air, no aeroplanes; high TL allows spacecraft that count as air-capable |
| Personal military | `law_level == 0` | Lower bound raised to `min(Manufacturing TL, Electronics TL)` | Weapons freely available → locally-made weapons are at least manufacturing-grade |

Sea transport is **not** forced to zero on dry worlds (Hydrographics 0). Instead,
Hydrographics 0 applies a DM −2 to the Sea TL roll, reflecting minimal maritime
capability rather than none (some worlds have other liquids, or subsurface oceans).

---

## The technology profile string

The profile string is formatted as `H-L-QQQQQ-TTTT-MM` where each character is a
single eHex digit (0–9, then A–Z for values 10–35):

| Group | Positions | What it covers |
|-------|-----------|---------------|
| H | 1 digit | High common TL |
| L | 1 digit | Low common TL |
| QQQQQ | 5 digits | Quality: Energy, Electronics, Manufacturing, Medical, Environmental |
| TTTT | 4 digits | Transport: Land, Sea, Air, Space |
| MM | 2 digits | Military: Personal, Heavy |

Example: `C-9-A9A87-9079-95`

- High TL: C (=12), Low TL: 9
- Energy: A (=10), Electronics: 9, Manufacturing: A (=10), Medical: 8, Environmental: 7
- Land: 9, Sea: 0 (dry world), Air: 7, Space: 9
- Personal military: 9, Heavy military: 5

---

## Key methods

| Method / function | What it does |
|-------------------|-------------|
| `generate_tech_detail(tl, atmosphere, hydrographics, population, government, law_level, starport, size=0, pcr=0, habitability_rating=None, trade_codes=None, rng=None)` | Main entry point: computes all 13 TL values and the profile string; returns `TechDetail` or `None` for pop 0 |
| `attach_tech_detail(system, rng=None)` | Walks the system, attaching tech detail to the mainworld and all inhabited secondaries and moons |
| `TechDetail.to_dict()` | Serialises all 14 fields to a JSON-compatible dict |
| `TechDetail.from_dict(d)` | Reconstructs from a saved dict |

### DM summary

Each sub-TL's DMs in brief:

| Sub-TL | Base | DMs |
|--------|------|-----|
| Energy | High TL | Pop 9+ +1; Industrial +1 |
| Electronics | Energy TL | Pop 1–5 +1; Pop 9+ −1; Industrial +1 |
| Manufacturing | Electronics TL | Pop 1–6 −1; Pop 8+ +1; Industrial +1 |
| Medical | Electronics TL | Rich +1; Poor −1; starport floor (A→6, B→4, C→2) |
| Environmental | Manufacturing TL | Habitability < 8: +(8 − habitability) |
| Land | Energy TL | Hydro 10 −1; PCR ≤ 2 +1 |
| Sea | Energy TL | Hydro 0 −2; Hydro 8 +1; Hydro 9+ +2; PCR ≤ 2 +1 |
| Air | Energy TL | Atm 0/1/2/3/E at TL 0–7 −2; Atm 4/5 at TL 0–7 −1; Atm 8/9 at TL 0–7 +1 |
| Space | Manufacturing TL | Size 0–1 +2; Pop 1–5 −1; Pop 9+ +1; Starport A +2; Starport B +1 |
| Personal military | Manufacturing TL | Gov 0 or 7 +2; Law 0 or D+ +2; Law 1–4 or 9–C +1 |
| Heavy military | Manufacturing TL | Pop 1–6 −1; Pop 8+ +1; Gov 7/A/B/F +2; Law D+ +2; Industrial +1 |
