"""traveller_world_cargo_gen.py — Mainworld cargo manifest (CRB pp.244-245).

Generates available speculative trade goods and purchase prices for a mainworld
based on its trade codes, starport class, and law level.

Licence
-------
MIT Licence — see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .traveller_world_gen import World

# ---------------------------------------------------------------------------
# CRB p.244 — Modified Price table (purchase side).
# Keyed by clamped 3D+DM result.  Supplier broker assumed Broker 2 → DM−2.
# ---------------------------------------------------------------------------
_PURCHASE_PCT: Dict[int, int] = {
    -3: 300, -2: 250, -1: 200,  0: 175,  1: 150,
     2: 135,  3: 125,  4: 120,  5: 115,  6: 110,
     7: 105,  8: 100,  9:  95, 10:  90, 11:  85,
    12:  80, 13:  75, 14:  70, 15:  65, 16:  60,
    17:  55, 18:  50, 19:  45, 20:  40, 21:  35,
    22:  30, 23:  25, 24:  20, 25:  15,
}
_PCT_LO = min(_PURCHASE_PCT)   # −3
_PCT_HI = max(_PURCHASE_PCT)   # 25

_SUPPLIER_BROKER = 2           # assumed Broker 2 (CRB p.244)


def _purchase_pct(roll: int) -> int:
    return _PURCHASE_PCT[max(_PCT_LO, min(_PCT_HI, roll))]


# ---------------------------------------------------------------------------
# Internal trade-good definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _TGDef:  # pylint: disable=too-many-instance-attributes
    """Internal definition of one CRB Table 7-2 trade good."""
    name: str
    tons_n: int                        # number of D6 for tonnage roll
    tons_x: int                        # multiply roll by this (1 = 1D tons)
    base_cr: int                       # base price per ton (Cr)
    avail: Tuple[str, ...]             # trade codes for availability; () = always
    pdms: Tuple[Tuple[str, int], ...]  # (trade_code, DM) purchase DMs
    sdms: Tuple[Tuple[str, int], ...]  # (trade_code, DM) sale DMs (future use)
    illegal_law: Optional[int] = None  # excluded when world.law_level >= this


def _tg(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        name: str, tons_n: int, tons_x: int, base_cr: int,
        avail: Tuple[str, ...],
        pdms: Tuple[Tuple[str, int], ...],
        sdms: Tuple[Tuple[str, int], ...],
        illegal_law: Optional[int] = None) -> _TGDef:
    return _TGDef(name, tons_n, tons_x, base_cr, avail, pdms, sdms, illegal_law)


# ---------------------------------------------------------------------------
# CRB Table 7-2 — Trade Goods (pp.244-245)
# D66 key → trade good definition.
#
# Purchase DM rule (CRB p.244): use only the LARGEST matching DM per column.
# Sale DMs are stored for future sale-price implementation; they are also
# applied negated to the purchase roll: 3D + max_pdm − max_sdm − broker(2).
#
# "Az"/"Rz" sale DMs reference Amber/Red Zone (not trade codes); they are
# stored here for completeness but will not match world.trade_codes and
# therefore never affect the purchase roll.
#
# D66 11-16: Common Goods (avail=()  → always available).
# D66 21-56: Trade Goods (world must have at least one matching trade code).
# D66 61-65: Illegal / black-market goods (illegal_law=0 always excludes).
# D66 66:    Exotics (roleplaying matter; available via random supplier roll).
#
# Values marked "# verify" were read from a photographed page; confirm against
# a physical copy of the CRB before treating as authoritative.
# ---------------------------------------------------------------------------
_TRADE_GOODS: Dict[int, _TGDef] = {
    # -- Common Goods (always available) ------------------------------------
    11: _tg("Common Electronics",          2, 10,    20_000,
            (),
            (("In", 2), ("Ht", 1), ("Ri", 1)),
            (("Ni", 2), ("Lt", 1), ("Po", 1))),
    12: _tg("Common Industrial Goods",     2, 10,    10_000,
            (),
            (("Na", 2), ("Ag", 2), ("In", 5)),
            (("Ni", 3), ("Ag", 3))),
    13: _tg("Common Manufactured Goods",   2, 10,    20_000,
            (),
            (("Na", 2), ("Ag", 2), ("In", 5)),
            (("Na", 3), ("Hi", 2))),
    14: _tg("Common Raw Materials",        2, 20,     5_000,
            (),
            (("Ag", 3), ("Ga", 2)),
            (("In", 2), ("Po", 2))),
    15: _tg("Common Consumables",          2, 20,       500,
            (),
            (("Ag", 3), ("Wa", 2), ("Ga", 1), ("Ic", 1), ("Hi", 1)),
            (("As", 1), ("Ic", 1), ("Hi", 1), ("In", 3), ("Ni", 1))),
    16: _tg("Common Ore",                  2, 20,     1_000,
            (),
            (("As", 4),),
            (("In", 3), ("Ni", 1), ("Hi", 1))),
    # -- Trade Goods --------------------------------------------------------
    21: _tg("Advanced Electronics",        1,  5,   100_000,
            ("In", "Ht"),
            (("In", 2), ("Ht", 3)),
            (("Ni", 1), ("Ri", 1), ("As", 3))),
    22: _tg("Advanced Machine Parts",      1,  5,    75_000,
            ("In", "Ht"),
            (("In", 2), ("Ht", 2)),
            (("As", 2), ("Ni", 2), ("In", 1))),
    23: _tg("Advanced Manufactured Goods", 1,  5,   100_000,
            ("In", "Ht"),
            (("In", 1),),
            (("Hi", 1), ("As", 2), ("Ni", 2), ("In", 1))),
    24: _tg("Advanced Weapons",            1,  5,   150_000,
            ("In", "Ht"),
            (("Ht", 2),),
            (("Po", 1), ("Az", 2), ("Rz", 4))),
    25: _tg("Advanced Vehicles",           1,  5,   180_000,
            ("In", "Ht", "Wa"),
            (("Ht", 2),),
            (("As", 2), ("Ri", 2))),
    26: _tg("Biochemicals",                1,  5,    50_000,
            ("Ag", "Wa"),
            (("Ag", 1), ("Wa", 2), ("De", 2), ("Ic", 1)),
            (("In", 2),)),
    31: _tg("Crystals & Gems",             1,  5,    20_000,
            ("As", "De", "Ic"),
            (("As", 2), ("De", 2)),
            (("In", 3), ("Ri", 2))),
    32: _tg("Cybernetics",                 1,  1,   250_000,
            ("Ht",),
            (("Ht", 2),),
            (("As", 1), ("Ic", 1), ("Ri", 2))),
    33: _tg("Live Animals",                1, 10,    10_000,
            ("Ag", "Ga"),
            (("Ag", 2),),
            (("Lo", 3),)),
    34: _tg("Luxury Consumables",          1, 10,   200_000,  # verify: may be Cr20000
            ("Ag", "Ga", "Wa"),
            (("Ag", 2), ("Wa", 1)),
            (("Ri", 2), ("Hi", 2))),
    35: _tg("Luxury Goods",                1,  1,   200_000,
            ("Hi",),
            (("Hi", 1),),
            (("Ri", 4),)),
    36: _tg("Medical Supplies",            1,  5,    50_000,
            ("Ht", "Hi"),
            (("Ht", 2),),
            (("In", 2), ("Po", 1), ("Ri", 1))),
    41: _tg("Petrochemicals",              1, 10,    10_000,
            ("De", "Fl", "As", "Ic", "Wa"),
            (("De", 2), ("Fl", 1), ("As", 1), ("Ic", 1)),    # verify
            (("In", 2), ("Ag", 1), ("Lt", 2))),               # verify
    42: _tg("Pharmaceuticals",             1,  1,   100_000,
            ("As", "De", "Ic", "Wa"),
            (("As", 3), ("De", 2)),                            # verify
            (("Ri", 2), ("Ni", 1), ("Ht", 1))),               # verify
    43: _tg("Polymers",                    1, 10,     7_000,
            ("In",),
            (("In", 1),),
            (("Ri", 2), ("Ni", 1), ("Ht", 1))),               # verify
    44: _tg("Precious Metals",             1,  1,    50_000,
            ("As", "De", "Ic", "Fl"),
            (("As", 3), ("De", 2), ("Ic", 2), ("Fl", 2)),     # verify
            (("Ri", 3), ("In", 2), ("Ht", 1))),               # verify
    45: _tg("Radioactives",                1,  1, 1_000_000,
            ("As", "De", "Ic", "Lo"),
            (("As", 3), ("De", 2)),                            # verify
            (("In", 3), ("Hi", 2))),                           # verify
    46: _tg("Robots",                      1,  5,   400_000,
            ("In",),
            (("In", 2),),
            (("Ag", 2), ("Na", 2))),                           # verify
    51: _tg("Spices",                      1,  5,     6_000,
            ("Ga", "De", "Wa"),
            (("Ga", 2), ("De", 2)),                            # verify
            (("Hi", 2), ("Ri", 2))),                           # verify
    52: _tg("Textiles",                    1, 20,     3_000,
            ("Ag", "Ni"),
            (("Ag", 3),),
            (("Na", 2), ("Ni", 1))),                           # verify
    53: _tg("Uncommon Ore",                1, 20,     5_000,
            ("As", "Ic"),
            (("As", 4),),
            (("In", 2), ("Ni", 1))),
    54: _tg("Uncommon Raw Materials",      1, 10,    20_000,
            ("Ag", "De", "Ga", "Ic", "Wa"),
            (("Ag", 2), ("De", 1), ("Wa", 1)),                 # verify
            (("In", 2), ("Ag", 1))),                           # verify
    55: _tg("Wood",                        1, 20,     1_000,
            ("Ag", "Ga"),
            (("Ag", 6),),
            (("Na", 2), ("Ht", 1))),                           # verify
    56: _tg("Vehicles",                    1, 10,    15_000,
            ("In", "Ht"),
            (("Ht", 2), ("In", 1)),
            (("Wa", 2), ("Lo", 1))),                           # verify
    # -- Illegal Goods (black-market only; illegal_law=0 always excludes) --
    61: _tg("Illegal Biochemicals",        1,  1,    50_000,
            ("Ag", "Ic"),
            (("Ag", 1), ("Wa", 1), ("Ga", 1)),                 # verify
            (("As", 4), ("Ri", 6), ("Az", 8), ("Rz", 6)),
            illegal_law=0),
    62: _tg("Illegal Cybernetics",         1,  1,   250_000,
            ("As", "De", "Wa"),
            (("As", 2), ("De", 1), ("Wa", 2)),                 # verify
            (("Ri", 6), ("Hi", 4), ("Az", 8), ("Rz", 6)),
            illegal_law=0),
    63: _tg("Illegal Drugs",               1,  1,   100_000,
            ("As", "Ga", "Hi", "Wa"),
            (("As", 2), ("Ga", 1), ("Ic", 2)),                 # verify
            (("Ri", 6), ("Hi", 6), ("Lt", 1)),                 # verify
            illegal_law=0),
    64: _tg("Illegal Luxuries",            1,  1,    50_000,
            ("Ag", "Ga", "Wa"),
            (("Ag", 2), ("Wa", 1)),                            # verify
            (("Ri", 6), ("Hi", 4)),                            # verify
            illegal_law=0),
    65: _tg("Illegal Weapons",             1,  5,   150_000,
            ("In", "Ht"),
            (("Ht", 2),),
            (("Po", 6), ("In", 6), ("Az", 8), ("Rz", 10)),
            illegal_law=0),
    # -- Exotics (roleplaying matter; appears only via random supplier roll) -
    # avail=("__random__",) ensures this never matches real trade codes and
    # therefore never appears in a normal manifest.  When random-roll
    # supplier logic is implemented, D66 66 can be added directly.
    66: _tg("Exotics",                     1,  5,   150_000,  # verify
            ("__random__",),
            (),
            ()),
}


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CargoLot:
    """One available speculative trade-good lot at a source world."""
    d66: int
    trade_good: str
    tons: int
    base_price_cr: int
    purchase_dm: int       # largest purchase DM from matching trade codes
    purchase_price_cr: int

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {
            "d66": self.d66,
            "trade_good": self.trade_good,
            "tons": self.tons,
            "base_price_cr": self.base_price_cr,
            "purchase_dm": self.purchase_dm,
            "purchase_price_cr": self.purchase_price_cr,
        }


@dataclass
class CargoManifest:
    """Available speculative trade lots at a mainworld."""
    world_name: str
    lots: List[CargoLot]
    total_tons: int

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {
            "world_name": self.world_name,
            "lots": [lot.to_dict() for lot in self.lots],
            "total_tons": self.total_tons,
        }

    def to_json(self) -> str:
        """Serialise to a JSON string."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class FreightLots:
    """Count of available lots at each size tier."""
    incidental: int
    minor: int
    major: int

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {
            "incidental": self.incidental,
            "minor": self.minor,
            "major": self.major,
        }


@dataclass
class FreightManifest:
    """Available freight lots (fixed-rate cargo) at a mainworld (CRB p.239)."""
    world_name: str
    lots: FreightLots
    total_incidental_tons: int
    total_minor_tons: int
    total_major_tons: int
    mail_containers: int
    total_tons: int

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {
            "world_name": self.world_name,
            "lots": self.lots.to_dict(),
            "total_incidental_tons": self.total_incidental_tons,
            "total_minor_tons": self.total_minor_tons,
            "total_major_tons": self.total_major_tons,
            "mail_containers": self.mail_containers,
            "total_tons": self.total_tons,
        }

    def to_json(self) -> str:
        """Serialise to a JSON string."""
        return json.dumps(self.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# Freight Traffic table (CRB p.239) — 2D roll → number of dice for lot count
# ---------------------------------------------------------------------------

_FREIGHT_TABLE: List[Tuple[int, int]] = [
    (1, 0), (3, 1), (5, 2), (8, 3), (11, 4),
    (14, 5), (16, 6), (17, 7), (18, 8), (19, 9),
]  # (max_roll_inclusive, ndice); roll > 19 → 10 dice


def _freight_lots_count(roll: int, rng) -> int:
    """Roll ndice×D6 to get the number of lots for a freight tier roll result."""
    for threshold, ndice in _FREIGHT_TABLE:
        if roll <= threshold:
            return sum(rng.randint(1, 6) for _ in range(ndice))
    return sum(rng.randint(1, 6) for _ in range(10))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cargo_manifest(
        world: "World",
        rng: Optional[random.Random] = None,
) -> CargoManifest:
    """Generate available speculative trade lots and purchase prices.

    Availability (CRB pp.244-245):
    - Starport X → empty manifest (no trade infrastructure).
    - Common Goods (D66 11-16) are always available.
    - Trade Goods are available when the world has at least one matching
      trade code in the good's availability list.
    - Illegal goods (D66 61-65, illegal_law=0) are excluded; they require
      a black-market supplier.

    Purchase price (CRB p.244):
    - Roll 3D.
    - Add the largest matching purchase DM (not the sum of all matches).
    - Subtract the largest matching sale DM for this world (goods known to
      sell well here cost more to buy here).
    - Subtract supplier broker skill (assumed Broker 2).
    - Clamp result to [−3, 25]; look up percentage of base price.
    """
    _rng = rng if rng is not None else random
    lots: List[CargoLot] = []

    if world.starport == "X":
        return CargoManifest(world_name=world.name, lots=[], total_tons=0)

    codes = set(world.trade_codes)
    law = world.law_level

    for d66, good in sorted(_TRADE_GOODS.items()):
        if good.illegal_law is not None and law >= good.illegal_law:
            continue
        if good.avail and not codes.intersection(good.avail):
            continue

        tons = sum(_rng.randint(1, 6) for _ in range(good.tons_n)) * good.tons_x

        max_pdm = max((dm for code, dm in good.pdms if code in codes), default=0)
        max_sdm = max((dm for code, dm in good.sdms if code in codes), default=0)
        roll = (sum(_rng.randint(1, 6) for _ in range(3))
                + max_pdm - max_sdm - _SUPPLIER_BROKER)
        price = round(good.base_cr * _purchase_pct(roll) / 100)

        lots.append(CargoLot(
            d66=d66,
            trade_good=good.name,
            tons=tons,
            base_price_cr=good.base_cr,
            purchase_dm=max_pdm,
            purchase_price_cr=price,
        ))

    return CargoManifest(
        world_name=world.name,
        lots=lots,
        total_tons=sum(lot.tons for lot in lots),
    )


def generate_freight_lots(  # pylint: disable=too-many-locals
        world: "World",
        rng: Optional[random.Random] = None,
) -> FreightManifest:
    """Generate available freight lots (fixed-rate cargo) at a mainworld.

    Rolls the Freight Traffic table (CRB p.239) three times — once each for
    Incidental (1D tons), Minor (1D×5 tons), and Major (1D×10 tons) lots.
    Per-lot tonnages are rolled and summed at generation time.

    Mail (CRB p.239): a fourth 2D+DMs check with no tier DM; on a result of
    12+ roll 1D containers (each 5 tons, Cr25,000 flat rate).

    Destination-world DM (−1 per parsec beyond first) and Naval/Scout base
    bonuses on mail are deferred — only source-world DMs are applied.
    """
    _rng = rng if rng is not None else random

    # --- World-stat DMs ---
    pop = world.population
    if pop <= 1:
        pop_dm = -4
    elif pop >= 8:
        pop_dm = 4
    elif pop >= 6:
        pop_dm = 2
    else:
        pop_dm = 0

    starport_dm = {"A": 2, "B": 1, "E": -1, "X": -3}.get(world.starport, 0)

    tl = world.tech_level
    tl_dm = -1 if tl <= 6 else (2 if tl >= 9 else 0)

    zone_dm = -2 if world.travel_zone == "Amber" else (
              -6 if world.travel_zone == "Red" else 0)

    base_dm = pop_dm + starport_dm + tl_dm + zone_dm

    def _roll2d() -> int:
        return _rng.randint(1, 6) + _rng.randint(1, 6)

    # --- Lot counts per tier ---
    incidental_count = _freight_lots_count(_roll2d() + base_dm + 2, _rng)
    minor_count      = _freight_lots_count(_roll2d() + base_dm,     _rng)
    major_count      = _freight_lots_count(_roll2d() + base_dm - 4, _rng)

    # --- Roll tonnage for every lot ---
    total_incidental_tons = sum(_rng.randint(1, 6)      for _ in range(incidental_count))
    total_minor_tons      = sum(_rng.randint(1, 6) * 5  for _ in range(minor_count))
    total_major_tons      = sum(_rng.randint(1, 6) * 10 for _ in range(major_count))

    # --- Mail availability: separate 2D + base_dm, no tier DM ---
    mail_containers = _rng.randint(1, 6) if _roll2d() + base_dm >= 12 else 0

    return FreightManifest(
        world_name=world.name,
        lots=FreightLots(
            incidental=incidental_count,
            minor=minor_count,
            major=major_count,
        ),
        total_incidental_tons=total_incidental_tons,
        total_minor_tons=total_minor_tons,
        total_major_tons=total_major_tons,
        mail_containers=mail_containers,
        total_tons=(total_incidental_tons + total_minor_tons + total_major_tons
                    + mail_containers * 5),
    )
