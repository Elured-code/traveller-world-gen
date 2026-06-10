# Understanding `traveller_world_law_detail.py`

A guide for Python beginners. This file takes a world's UWP law level and expands it
into a structured legal profile: what kind of court system the world uses, how
consistently laws are applied across the planet, whether suspects are presumed
innocent, whether the death penalty exists, and how tightly each category of law is
enforced. The result is a `LawDetail` object and two compact profile strings.

---

## What this file does

In Traveller, the UWP law level (0–J) is a single digit that captures overall
restrictiveness. A law-7 world is stricter than a law-3 world, but the digit alone
does not tell you whether the courts are inquisitorial or adversarial, whether
weapons laws are enforced more harshly than privacy laws, or whether a defendant can
expect to be presumed innocent. This file answers those questions by implementing
WBH §3 Social Characteristics (law detail procedures, pp.163–168).

The main public function is `generate_law_detail()`. It runs six steps in order:

1. **Primary judicial system** — 2D with DMs from government code, law level, tech
   level, and government authority code. Result: Inquisitorial (the court investigates
   and prosecutes), Adversarial (prosecution and defence argue before a neutral judge),
   or Tribunal (a panel of judges decides collectively).
2. **Secondary judicial system** — 2D with no extra DMs. The secondary system is used
   for lower courts or specific categories of law.
3. **Law uniformity** — 1D with a DM from government code. Result: Patchy (law
   varies wildly by region), Typical, or Uniform (the same rules apply everywhere).
4. **Presumption of innocence** — 2D − law_level, with a bonus for Adversarial courts.
   If the result is 0 or higher, defendants are presumed innocent until proven guilty.
5. **Death penalty** — 2D with a DM for high law level (and a penalty for law 0,
   though law 0 already returns `None`). Result ≥ 8 means the death penalty exists.
6. **Five law subcategory scores** — each rolled as `law_level + 2D3−4 + DM`, clamped
   to 0–18. The DMs shift individual categories up or down from the base law level:
   Weapons (DM from PCR), Economic (DM from government type), Criminal (DM from
   judicial system), Private (DM from government type), and Personal Rights (DM from
   government type).

The function returns `None` for law level 0 (lawless worlds have nothing to profile).
Secondary world law detail is deferred to issue #135 — only the mainworld is
supported currently. The companion function `attach_law_detail()` handles wiring
this into a live `TravellerSystem`.

Implements WBH §3 Social Characteristics law detail (pp.163–168).

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | `random`, `dataclasses`, plus `TYPE_CHECKING` guard for `TravellerSystem` |
| Module-level `_rng` | Injectable RNG sentinel |
| `_EHEX` | 36-character string used to convert numbers to eHex digits |
| `_JUDICIAL_NAMES`, `_UNIFORMITY_NAMES` | Dicts for human-readable labels |
| Dice helpers | `_to_hex()`, `_roll2d()`, `_roll1d()`, `_roll2d3()` |
| `LawDetail` dataclass | 12 fields + 3 computed properties for human-readable labels |
| Judicial helpers | `_judicial_dm()`, `_judicial_code()` |
| Uniformity helpers | `_uniformity_dm()`, `_uniformity_code()` |
| Subcategory helper | `_subcategory()` — the 2D3−4+base+DM formula |
| `generate_law_detail()` | Main public entry point |
| `attach_law_detail()` | Mainworld-only attachment to a `TravellerSystem` |

---

## Key Python concept: `@property` for computed fields

The `LawDetail` dataclass stores the raw codes (`judicial_primary = "I"`,
`law_uniformity = "P"`, etc.) but also needs to expose human-readable labels for
display. Rather than storing duplicate data, the class uses Python `@property`
decorators to compute the label on demand:

```python
@property
def judicial_primary_label(self) -> str:
    return _JUDICIAL_NAMES.get(self.judicial_primary, "")
```

A `@property` is accessed like a regular attribute (no parentheses), even though it
runs code:

```python
detail.judicial_primary       # → "I"
detail.judicial_primary_label # → "Inquisitorial"
```

The `to_dict()` method includes both the code and the label so that JSON consumers
get both without needing to know the mapping table.

---

## Key Python concept: rolling D3

The game concept of a D3 (a three-sided die, giving 1, 2, or 3) does not exist as a
physical die in most gaming groups — it is simulated by rolling 1D6 and halving,
rounding up. The code does this with integer arithmetic:

```python
def _roll2d3() -> int:
    return sum(_rng.randint(1, 3) for _ in range(2))
```

Here `randint(1, 3)` gives 1, 2, or 3 with equal probability, so calling it twice
and summing gives a result from 2 to 6. Subtracting 4 centres the range on 0:
`2D3−4` gives −2, −1, 0, +1, or +2, acting as a small random spread around the
base law level for each subcategory.

---

## The judicial system in game terms

The three judicial systems reflect real-world legal traditions:

| Code | Name | What it means in play |
|------|------|-----------------------|
| I | Inquisitorial | The court investigates, prosecutes, and judges. Defendants have few procedural rights. Common on low-TL worlds where legal institutions are primitive. |
| A | Adversarial | Prosecution and defence argue their case to a neutral judge or jury. Standard on most Imperium worlds and high-TL societies. Favours presumption of innocence. |
| T | Tribunal | A panel of judges (often specialists or nobles) deliberates and decides. Common in oligarchies and technocracies. |

The DMs push toward Inquisitorial for religious governments and primitive tech levels
(few formal legal protections), and toward Adversarial for corporate and bureaucratic
governments (which prefer procedural clarity).

---

## The subcategory scores in game terms

A world's overall law level is an average. Different areas of law can be harsher or
more relaxed than the headline figure. The five subcategories are:

| Field | What it covers | Notable DMs |
|-------|---------------|-------------|
| `law_weapons` | Weapons and armour restrictions | PCR ≥ 8: +1 (dense cities = more weapons laws) |
| `law_economic` | Trade, contracts, currency, commerce | Gov 1 (corporation): +2; Gov 2 (democracy): −2 |
| `law_criminal` | Violence, theft, property crime | Inquisitorial primary: +1 |
| `law_private` | Privacy, personal data, surveillance | Gov 3/5/12 (oligarchies): −1 |
| `law_personal_rights` | Freedom of movement, speech, assembly | Gov 1 (corporate): +2; Gov 2 (democracy): −1 |

A world might have overall law level 5 but weapons subcategory 8 (very tight arms
control) and personal rights subcategory 2 (surprisingly permissive about speech) —
giving you material for interesting adventures.

---

## The two profile strings

### Justice profile: `PSU-I-D`

| Position | Meaning | Example values |
|----------|---------|---------------|
| P | Primary judicial code | `I`, `A`, `T` |
| S | Secondary judicial code | `I`, `A`, `T` |
| U | Uniformity code | `P`, `T`, `U` |
| I | Presumption of innocence | `Y` or `N` |
| D | Death penalty | `Y` or `N` |

Example: `AIT-Y-N` — Adversarial primary, Inquisitorial secondary, Typical
uniformity, presumption of innocence yes, no death penalty.

### Law profile: `O-WECPR`

| Position | Meaning |
|----------|---------|
| O | Overall law level (UWP digit, in eHex) |
| W | Weapons subcategory score |
| E | Economic subcategory score |
| C | Criminal subcategory score |
| P | Private subcategory score |
| R | Personal Rights subcategory score |

Example: `7-86755` — overall law 7, with weapons at 8 (stricter), economic at 6,
criminal at 7, private at 5 (more relaxed), personal rights at 5.

---

## The low-floor clamping note

When the atmosphere code requires a very high minimum tech level and the world's
actual TL is below that threshold, the computed `low_floor` could exceed `tl_high`.
If that happened, the clamp `_clamp(value, lo, hi)` would receive a range where
`lo > hi`, which would return `lo` — a value above `tl_high`. The fix used in the
tech detail module (which shares the same logic) is:

```python
low_floor = min(tl_high, max(min_tech, tl_high // 2))
```

Law detail does not compute its own floor, but the subcategory formula is protected
by `max(0, min(18, raw))` at both ends.

---

## Key methods

| Method / function | What it does |
|-------------------|-------------|
| `generate_law_detail(law_level, gov_code, tech_level, pcr, gov_authority_code, rng=None)` | Main entry point: runs all six steps; returns `LawDetail` or `None` for law 0 |
| `attach_law_detail(system, rng=None)` | Attaches law detail to the mainworld only (secondary worlds deferred) |
| `LawDetail.judicial_primary_label` | Property: human-readable label for `judicial_primary` |
| `LawDetail.judicial_secondary_label` | Property: human-readable label for `judicial_secondary` |
| `LawDetail.law_uniformity_label` | Property: human-readable label for `law_uniformity` |
| `LawDetail.to_dict()` | Serialises to a plain dict including computed label fields |
| `LawDetail.from_dict(d)` | Reconstructs from a saved dict |
