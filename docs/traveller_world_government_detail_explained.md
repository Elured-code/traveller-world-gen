# Understanding `traveller_world_government_detail.py`

A guide for Python beginners. This file takes a world's UWP government code and
fleshes it out into a structured political profile: how centralised the government
is, which branch holds supreme authority, how the ruling body is organised, and what
factions are competing for power. The result is a `GovernmentDetail` object and a
compact government profile string.

---

## What this file does

In Traveller, a world's UWP gives you a single-digit government code (0–F). A code
of 5 tells you it is a Feudal Technocracy, but not whether power is held by a
parliament, a council, or a single ruler — or how many rebel factions are quietly
undermining it. This file answers those questions by implementing WBH §3 Social
Characteristics.

The main public function is `generate_government_detail()`. It runs three steps in
order:

1. **Step 1 — Degree of Centralisation**: Roll 2D with DMs from the government code
   and PCR. Result: Confederal (power shared between semi-autonomous regions),
   Federal (a central government with limited regional autonomy), or Unitary (full
   central control). This is the "C" position in the profile string.
2. **Step 2 — Primary Authority**: Roll 2D with DMs from the government code and the
   centralisation result. Result: Legislative (laws made by an assembly), Executive
   (a strong executive commands), Judicial (courts hold supreme authority), or
   Balanced (three separate branches share power equally). This is the "A" position.
3. **Step 3 — Government Structure**: The way the ruling body is actually organised.
   Demos (direct popular participation), Single Council, Multiple Councils, or Ruler.
   If authority is Balanced, three separate structure rolls are made — one for each
   branch. This is the "S" position (or "B-LS-ES-JS" for Balanced).

After the three steps, factions are generated. A D3+DM roll determines how many
significant challengers exist. For each faction, the code rolls a government type
(the kind of government the faction would prefer), a strength (from Obscure to
Overwhelming), and a relationship to the ruling body (from Alliance to Total War).

The function returns `None` for government code 0 (no government — procedures do
not apply) and for code 7 (Balkanisation — deferred to issue #130, because a
balkanised world needs its own separate per-polity treatment).

The companion function `attach_government_detail()` walks a `TravellerSystem` and
applies government detail to the mainworld and every inhabited secondary world.

Implements WBH §3 Social Characteristics (Centralisation, Authority, Structure,
Factions).

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| Imports | `random`, `dataclasses`, plus `TYPE_CHECKING` guard for `TravellerSystem` |
| Module-level `_rng` | Injectable RNG sentinel |
| `_GOV_NAMES` | Dict mapping government codes 0–F to human-readable names |
| `_AUTHORITY_NAMES`, `_STRUCTURE_NAMES` | Short display name dicts |
| `_STRUCT_TABLE` | 11-entry list: maps a 2D result to a structure code |
| `_AUTHORITY_TABLE` | Dict for mid-range authority results (edges handled separately) |
| `_FACTION_STRENGTH` | 11-entry list of (code, label) tuples, indexed by 2D result |
| `_FACTION_RELATIONSHIP` | Dict mapping 0–9 to (code, label) for faction stance |
| `Faction` dataclass | One challenger faction with type, strength, and relationship |
| `GovernmentDetail` dataclass | The full 13-field political profile for one world |
| Centralisation helpers | `_centralisation_dm()`, `generate_centralisation()` |
| Authority helpers | `_authority_dm()`, `generate_authority()` |
| Structure helpers | `_struct_from_table()`, `_roll_one_structure()` |
| Faction helpers | `_d3()`, `_faction_count_dm()`, `_roll_faction_gov()`, etc. |
| `generate_government_detail()` | Main public entry point |
| `attach_government_detail()` | System-wide attachment |

---

## Key Python concept: dict lookup tables

Many rules in this file are expressed as Python dicts that map a numeric or string
key to a result. For example:

```python
_AUTHORITY_TABLE: dict[int, str] = {
    5: "E", 6: "J", 7: "B", 8: "L", 9: "B", 10: "E", 11: "J"
}
```

When the 2D+DM result falls between 5 and 11, the code does:

```python
code = _AUTHORITY_TABLE.get(result, "L")
```

The `.get(key, default)` form returns `"L"` if the key is not present, which handles
the edge cases (result ≤ 4 → Legislative, result ≥ 12 → Executive) that are
separately checked with `if` statements before this line. Using a dict here is
cleaner than a long chain of `if/elif` because the mapping is a data relationship,
not program logic.

The `_FACTION_STRENGTH` and `_FACTION_RELATIONSHIP` tables use lists instead of
dicts because the keys are a contiguous range starting at a known offset:

```python
_FACTION_STRENGTH: list[tuple[str, str]] = [
    ("O", "Obscure group"),    # 2D=2 → index 0
    ("O", "Obscure group"),    # 2D=3 → index 1
    ("F", "Fringe group"),     # 2D=4 → index 2
    ...
]
# Usage: _FACTION_STRENGTH[result - 2]
```

Subtracting 2 converts a dice result (minimum 2 on 2D) to a zero-based list index.

---

## Key Python concept: the `@dataclass` decorator and `field(default_factory=list)`

`Faction` and `GovernmentDetail` both use `@dataclass`. `GovernmentDetail` has a
`factions` field that holds a list of `Faction` objects:

```python
@dataclass
class GovernmentDetail:
    ...
    factions: list = field(default_factory=list)
```

The `field(default_factory=list)` idiom creates a fresh empty list for each new
`GovernmentDetail` instance. If you wrote `factions: list = []` instead, every
instance of the class would share the same list object, which would cause bugs when
one world's factions accidentally appeared on another world.

---

## The three-step procedure in game terms

### Step 1: Centralisation

Think of this as "how much does the central government actually control its
territory?" A **Confederal** government has member states that can override it.
A **Federal** government is dominant but leaves some matters to regions.
A **Unitary** government has complete authority everywhere on the world.

Authoritarian government types (codes 10+) push toward Unitary; democratic or
distributed types (codes 2–5) push toward Confederal. A high PCR (lots of people in
cities) also pushes toward Unitary — urban populations are easier to centralise.

### Step 2: Authority

Which branch of government is supreme? This is strongly influenced by the government
code. Religious governments (codes 13, 14) almost always end up Executive (the
theocrat rules by decree). Participating Democracies (code 2) strongly favour
Legislative (the assembly decides). A Judicial authority is rare — this is a world
where the courts have grown powerful enough to override both parliament and executive.
Balanced is the most complex result: no branch dominates.

### Step 3: Structure

How is the ruling body physically organised? **Demos** means the population
participates directly (referenda, direct democracy). **Single Council** is a unified
body like a cabinet or senate. **Multiple Councils** represents a bicameral or
multi-chamber arrangement. **Ruler** is a single person who holds authority.

When authority is Balanced, each branch rolls independently, so you might end up with
a Legislative Demos + Executive Single Council + Judicial Ruler — a rich basis for
roleplaying the political tensions.

---

## Factions in game terms

Factions represent internal political challengers to the ruling government. The
ruling government itself is Faction I (not listed — it is the world's official UWP
government code). The code generates challenger factions starting from Faction II.

A D3+DM roll sets the count. Government codes 0 and 7 get DM+1 (anarchies and
balkanised worlds have many competing factions by nature); authoritarian governments
(code 10+) get DM−1 (they tend to suppress opposition). A result of 1 or less means
no significant challengers.

For each challenger, three rolls determine its character:

| Roll | What it gives |
|------|--------------|
| 2D + pop_code − 7 | Government type the faction wants (clamped away from 7) |
| 2D | Strength: Obscure / Fringe / Minor / Notable / Significant / Overwhelming |
| 1D + DMs | Relationship: Alliance through Total War |

The relationship DMs reward similarity: a faction that wants the same kind of
government as the current rulers gets DM−1 (they compete cooperatively), while all
factions receive DM+1 to push their relationship toward tension rather than harmony.

---

## The government profile string

The profile string packages the political structure into a compact notation:

| Format | Meaning | Example |
|--------|---------|---------|
| `G-CAS` | Non-Balanced authority | `5-FES` = gov 5, Federal, Executive, Single Council |
| `G-CB-LS-ES-JS` | Balanced authority, one structure per branch | `4-FB-LM-ES-JR` |

Where G is the government code in eHex, C is centralisation (C/F/U), A is authority
(L/E/J/B), and S is structure (D/S/M/R). For Balanced authority, the three branch
structures are prefixed with L (Legislative), E (Executive), J (Judicial).

---

## Key methods

| Method / function | What it does |
|-------------------|-------------|
| `generate_centralisation(gov_code, pcr, rng=None)` | Step 1: rolls Confederal/Federal/Unitary; returns (code, label) |
| `generate_authority(gov_code, centralisation_code, rng=None)` | Step 2: rolls Legislative/Executive/Judicial/Balanced; returns (code, label) |
| `generate_factions(gov_code, pop_code, rng=None)` | Rolls faction count, type, strength, and relationship; returns `list[Faction]` |
| `generate_government_detail(gov_code, pop_code, pcr=0, rng=None)` | Main entry point: runs all three steps and factions; returns `GovernmentDetail` or `None` |
| `attach_government_detail(system, rng=None)` | Walks the system, attaching government detail to all inhabited worlds |
| `GovernmentDetail.to_dict()` | Serialises to a plain dict for JSON output |
| `GovernmentDetail.from_dict(d)` | Reconstructs from a saved dict |
| `Faction.to_dict()` | Serialises one faction |
| `Faction.from_dict(d)` | Reconstructs one faction |
