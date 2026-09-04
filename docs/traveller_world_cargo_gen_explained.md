# Understanding `traveller_world_cargo_gen.py`

A guide for Python beginners. This module generates two related but distinct
things that a starship captain cares about at any world: **speculative trade cargo**
(goods you can buy at variable prices hoping to sell them for a profit elsewhere)
and **freight lots** (goods that other people want shipped at a fixed rate).

Implements CRB pp.239 (freight) and pp.244-245 (speculative cargo).

---

## What this file does

- Defines **all 36 D66 trade goods** from CRB Table 7-2, including their
  availability rules, tonnage rolls, base prices, and purchase/sale DMs.
- Generates a **`CargoManifest`** — the list of speculative lots currently
  available at a world, with per-lot purchase prices rolled against the
  world's trade codes.
- Generates a **`FreightManifest`** — the number and total tonnage of
  Incidental, Minor, and Major freight lots waiting to be shipped, plus
  any available mail containers.

---

## How the file is laid out

| Section | What it contains |
|---------|-----------------|
| `_PURCHASE_PCT` | Modified Price table (CRB p.244): roll result → % of base price |
| `_TGDef` / `_TRADE_GOODS` | Internal trade good definitions for all 36 D66 entries |
| `CargoLot`, `CargoManifest` | Output dataclasses for speculative cargo |
| `FreightLots`, `FreightManifest` | Output dataclasses for freight |
| `_FREIGHT_TABLE` | Freight Traffic table: 2D roll → number-of-dice for lot count |
| `_freight_lots_count` | Rolls ndice×D6 given a tier result |
| `generate_cargo_manifest` | Public API — speculative cargo |
| `generate_freight_lots` | Public API — freight lots |

---

## Speculative cargo — how `generate_cargo_manifest` works

### Step 1: Check the starport

A world with **Starport X** has no trade infrastructure. The function immediately
returns an empty manifest without rolling anything.

### Step 2: Filter the trade goods table

For each of the 36 D66 entries the function checks two things:

1. **Illegal?** Goods with `illegal_law=0` (D66 61-65) are excluded from normal
   cargo lists — they require a black-market supplier and are never generated here.

2. **Available?** Common Goods (D66 11-16) have an empty `avail` tuple, meaning
   they are always available at any world with a functioning starport. Trade Goods
   (D66 21-56) are available only when the world has at least one matching trade code
   in the good's `avail` list. For example, Advanced Electronics (D66 21) requires
   the world to have the `In` (Industrial) or `Ht` (High Tech) trade code.

The Exotics entry (D66 66) uses the sentinel code `"__random__"`, which never
matches any real trade code, so it is filtered out automatically until random-supplier
logic is implemented.

### Step 3: Roll tonnage

For each available good, tonnage is `sum(1D × tons_n) × tons_x`. Common Electronics
rolls `2D × 10` — two six-sided dice, then multiply by ten. The spread in lot sizes
means the same good can be a very different proposition depending on the roll.

### Step 4: Roll the purchase price

CRB p.244 uses a *modified price table* driven by a 3D roll plus DMs:

```
roll = 3D + max_purchase_DM − max_sale_DM − broker_skill(2)
```

The key rule: **only the largest matching DM counts**, not the sum of all matching
ones. If a world has both `In` and `Ht` trade codes and a good has DM+2 for `In`
and DM+3 for `Ht`, only the +3 applies.

Sale DMs work the same way — goods that sell well at this world cost more to buy
here (the locals know what they have). The supplier is assumed to have Broker skill
2 (the standard mid-tier trader), applying DM−2.

The roll is clamped to [−3, 25] and looked up in `_PURCHASE_PCT`:

| Roll | % of base | Meaning |
|------|-----------|---------|
| −3   | 300 %     | You're being robbed |
| 0    | 175 %     | Below-average deal |
| 8    | 100 %     | Base price |
| 15   | 65 %      | Good deal |
| 25   | 15 %      | Almost free |

The purchase price in credits is `round(base_cr × pct / 100)`.

---

## Freight lots — how `generate_freight_lots` works

Freight is cargo that already has a destination. As a ship's captain, you
quote a per-ton rate and collect a flat fee; you do not speculate on the price.
The generator tells you how much freight is waiting to be shipped.

### The three tiers

| Tier | Tonnage per lot | Tier DM |
|------|-----------------|---------|
| Incidental | 1D tons | +2 |
| Minor | 1D×5 tons | 0 |
| Major | 1D×10 tons | −4 |

Small (incidental) lots are abundant; large (major) lots are rare — hence the
tier DMs that bias each roll.

### Step 1: Compute base DM

The base DM is the sum of four world-stat adjustments:

| Factor | DM |
|--------|----|
| Population ≤ 1 | −4 |
| Population 2–5 | 0 |
| Population 6–7 | +2 |
| Population ≥ 8 | +4 |
| Starport A | +2 |
| Starport B | +1 |
| Starport C, D | 0 |
| Starport E | −1 |
| Starport X | −3 |
| TL ≤ 6 | −1 |
| TL 7–8 | 0 |
| TL ≥ 9 | +2 |
| Travel Zone Amber | −2 |
| Travel Zone Red | −6 |

### Step 2: Roll tier counts via the Freight Traffic table

For each tier, roll 2D + base_dm + tier_dm, then look up the result in the
Freight Traffic table to get a number of dice (0–10):

| Roll result | Dice to roll |
|-------------|-------------|
| ≤ 1 | 0 (no lots) |
| 2–3 | 1D |
| 4–5 | 2D |
| 6–8 | 3D |
| 9–11 | 4D |
| 12–14 | 5D |
| 15–16 | 6D |
| 17 | 7D |
| 18 | 8D |
| 19 | 9D |
| ≥ 20 | 10D |

Roll the indicated number of D6 — the result is the number of lots in that tier.

### Step 3: Roll total tonnage per tier

Each lot is rolled separately: 1D for incidental, 1D×5 for minor, 1D×10 for major.
The totals for each tier are summed. The generator rolls these at generation time —
`total_incidental_tons` is the combined tonnage of all incidental lots, not a
per-lot list.

### Step 4: Check for mail

A separate 2D + base_dm roll (no tier DM) of 12 or higher means mail is available.
Roll 1D for the number of containers (each container is 5 tons, flat rate Cr25,000).
Destination-world range penalties and Naval/Scout base bonuses are deferred to the
time of booking a specific destination.

---

## Key methods table

| Function / class | Purpose |
|-----------------|---------|
| `generate_cargo_manifest(world, rng=None)` | Returns `CargoManifest` of speculative trade lots |
| `generate_freight_lots(world, rng=None)` | Returns `FreightManifest` of freight lot counts and tonnages |
| `CargoLot` | One D66 entry: `d66`, `trade_good`, `tons`, `base_price_cr`, `purchase_dm`, `purchase_price_cr` |
| `CargoManifest` | `world_name`, `lots: List[CargoLot]`, `total_tons`; `.to_dict()` / `.to_json()` |
| `FreightLots` | `incidental`, `minor`, `major` (lot counts per tier); `.to_dict()` |
| `FreightManifest` | `world_name`, `lots`, `total_incidental_tons`, `total_minor_tons`, `total_major_tons`, `mail_containers`, `total_tons`; `.to_dict()` / `.to_json()` |
| `_freight_lots_count(roll, rng)` | Looks up `_FREIGHT_TABLE` and rolls ndice×D6 |

---

## RNG behaviour

Both public functions accept an optional `rng: Optional[random.Random]`. When
provided, all dice rolls use that instance. When omitted, the module-level `_rng`
sentinel (which defaults to the global `random` module) is used — the same pattern
used throughout the codebase.

Because neither function writes back to `_rng` (unlike module-level generators
such as `generate_world`), the `rng` argument is purely for callers that want
deterministic output. Passing `random.Random(seed)` always gives the same manifest
for the same world and seed.

---

## Why speculative cargo and freight are separate

They model different activities:

- **Speculative cargo** requires the captain to risk money: buy goods here at an
  uncertain price and hope to sell them at a profit elsewhere. The generator rolls
  what is available and how much it costs; the sale price is rolled at the destination.
- **Freight** is a fee-for-service contract: someone else owns the cargo, the captain
  just moves it. The generator tells you how much is waiting to be picked up.

CRB treats them in different chapters for the same reason. In the code, both live
in `traveller_world_cargo_gen.py` because they share the same `World` input and
the same RNG threading pattern.

---

## Source notes

Values in the trade goods table marked `# verify` were read from a photographed
copy of the CRB. Confirm against a physical copy before treating them as
authoritative. All unmarked values match the published table.
