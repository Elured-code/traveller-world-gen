"""traveller_world_starport_detail.py — WBH §8 starport detail generation.

Computes detailed starport characteristics for the mainworld: traffic rating,
highport and downport docking capacities, and shipyard build capacity.

Session 137 — Issue #101.

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

import math
import random
from dataclasses import dataclass
from typing import Optional

# pylint: disable=locally-disabled,suppressed-message

_rng: random.Random = random  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Expected Weekly ship traffic — deterministic lookup from traffic_importance
# WBH Starport Traffic table (p.197)
# ---------------------------------------------------------------------------
_EW_TABLE: list[tuple[int, int]] = [
    # (min_importance, expected_weekly)
    (6,  2000),
    (5,  1000),
    (4,   150),
    (3,    30),
    (2,    20),
    (1,    10),
    (0,     5),
    (-1,    3),
    (-2,    2),
    (-3,    1),
]


def _expected_weekly(traffic_importance: int) -> int:
    for min_imp, ew in _EW_TABLE:
        if traffic_importance >= min_imp:
            return ew
    return 0  # uncharted / unexplored


# ---------------------------------------------------------------------------
# Docking capacity formula helpers
# WBH Port Capacity formulas (p.198)
# ---------------------------------------------------------------------------
_HP_BASE: dict[str, int] = {"A": 100_000, "B": 50_000, "C": 20_000, "D": 500,  "E": 400}
_HP_MULT: dict[str, int] = {"A":     500, "B":    500, "C":    200, "D": 100,  "E": 100}


def _round100(x: float) -> int:
    """Round up to the nearest 100 (WBH: 'round results up to the nearest 100')."""
    return max(0, int(math.ceil(x / 100.0)) * 100)


def _capacity_factor(ef: int) -> float:
    """WBH dice factor: (1 + (1D + EF) / 5). Uses module-level _rng."""
    return 1.0 + (_rng.randint(1, 6) + ef) / 5.0


def _compute_highport_capacity(
    starport: str,
    cap_importance: int,
    ew: int,
    pop: int,
    ef: int,
) -> Optional[int]:
    """Highport capacity (tonnes) when a highport is present, classes A–D."""
    base = _HP_BASE.get(starport)
    mult = _HP_MULT.get(starport)
    if base is None or mult is None or starport == "E":
        return None
    raw = base + cap_importance * ew * mult * pop * _capacity_factor(ef)
    return _round100(raw)


def _compute_downport_capacity(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    starport: str,
    has_highport: bool,
    highport_capacity: Optional[int],
    cap_importance: int,
    ew: int,
    pop: int,
    ef: int,
) -> int:
    """Downport capacity (tonnes).

    When a highport is present the downport is 1D × 10% of highport capacity
    (WBH p.198).  When absent the same capacity formula as the class is used.
    Class X worlds have no formal downport (returns 0).
    """
    if starport == "X":
        return 0
    if has_highport and highport_capacity is not None:
        return _round100(_rng.randint(1, 6) * highport_capacity / 10.0)
    base = _HP_BASE.get(starport, 400)
    mult = _HP_MULT.get(starport, 100)
    raw = base + cap_importance * ew * mult * pop * _capacity_factor(ef)
    return _round100(raw)


_LARGEST_PAD: dict[str, int] = {
    "A": 2000, "B": 2000, "C": 1000, "D": 400, "E": 400, "X": 0,
}

# ---------------------------------------------------------------------------
# Shipyard capacity helpers
# WBH Shipyard Build Capacity formulas (p.199)
# ---------------------------------------------------------------------------
_SHIPYARD_DIVISOR: dict[str, float] = {"A": 20_000.0, "B": 100_000.0, "C": 15_000.0}


def _tl_shipyard_dm(tech_level: int) -> int:
    if tech_level >= 15:
        return 4
    if tech_level >= 12:
        return 2
    if tech_level <= 8:
        return -4
    return 0


def _compute_shipyard_capacity(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    starport: str,
    ef: int,
    inf_f: int,
    tech_level: int,
    trade_codes: list,
    total_population: int,
) -> Optional[int]:
    """Shipyard build capacity (tonnes) for classes A, B, C.

    Returns None for class D/E/X, or when a Class C result is zero or negative
    (no functional yard exists per WBH p.199).
    """
    divisor = _SHIPYARD_DIVISOR.get(starport)
    if divisor is None:
        return None

    tl_dm   = _tl_shipyard_dm(tech_level)
    trade_dm = 2 if "In" in trade_codes else (-2 if "Ni" in trade_codes else 0)
    dm = tl_dm + trade_dm

    roll  = _rng.randint(1, 6)
    extra = -3 if starport == "C" else 0
    raw   = (ef + inf_f + roll + extra + dm) * total_population / divisor
    result = _round100(raw)

    if starport == "A":
        if result < 10_000:
            result = 9_000 + _rng.randint(1, 6) * 500
    elif starport == "B":
        if result < 5_000:
            result = 4_000 + (_rng.randint(1, 6) + _rng.randint(1, 6)) * 100
    else:  # C
        if result <= 0:
            return None

    return result


def _compute_annual_output(starport: str, capacity: int, importance: int) -> int:
    """Annual shipyard output (tonnes/year).

    Class C yards produce 10× their capacity (small craft only).
    Class A/B: capacity ÷ importance when importance ≥ 1;
               capacity × (1 − importance) when importance ≤ 0.
    """
    if starport == "C":
        return capacity * 10
    if importance >= 1:
        return max(100, _round100(capacity / importance))
    return _round100(capacity * (1 - importance))


# ---------------------------------------------------------------------------
# Starport profile string
# ---------------------------------------------------------------------------

def _starport_profile(
    starport: str,
    has_highport: bool,
    traffic_importance: int,
) -> str:
    """Build the WBH starport profile string: 'C-HX:DX:±#'."""
    h = "Y" if has_highport else "N"
    d = "N" if starport == "X" else "Y"
    sign = "+" if traffic_importance > 0 else ""
    return f"{starport}-H{h}:D{d}:{sign}{traffic_importance}"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class StarportDetail:  # pylint: disable=too-many-instance-attributes
    """WBH §8 starport detail: traffic, docking capacities, and shipyard.

    Fields
    ------
    traffic_importance     : importance score adjusted for WTN A+ trade hub boost
    expected_weekly        : expected weekly ship arrivals (deterministic lookup)
    has_highport           : True when world.bases contains 'H'
    highport_capacity      : highport total docking (tonnes); None when absent or class E/X
    downport_capacity      : downport total docking (tonnes)
    downport_largest_pad   : largest landing pad (tonnes); class-based
    shipyard_capacity      : shipyard build capacity (tonnes); None for D/E/X
    shipyard_largest_bay   : largest single bay (10% of capacity); None when no shipyard
    shipyard_annual_output : annual ship production (tonnes/year); None when no shipyard
    starport_profile       : WBH profile string, e.g. 'A-HY:DY:+3'
    """

    traffic_importance:     int
    expected_weekly:        int
    has_highport:           bool
    highport_capacity:      Optional[int]
    downport_capacity:      int
    downport_largest_pad:   int
    shipyard_capacity:      Optional[int]
    shipyard_largest_bay:   Optional[int]
    shipyard_annual_output: Optional[int]
    starport_profile:       str

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON output."""
        d: dict = {
            "traffic_importance":   self.traffic_importance,
            "expected_weekly":      self.expected_weekly,
            "has_highport":         self.has_highport,
            "downport_capacity":    self.downport_capacity,
            "downport_largest_pad": self.downport_largest_pad,
            "starport_profile":     self.starport_profile,
        }
        if self.highport_capacity is not None:
            d["highport_capacity"] = self.highport_capacity
        if self.shipyard_capacity is not None:
            d["shipyard_capacity"]      = self.shipyard_capacity
            d["shipyard_largest_bay"]   = self.shipyard_largest_bay
            d["shipyard_annual_output"] = self.shipyard_annual_output
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StarportDetail":
        """Reconstruct from a to_dict() output."""
        hp = d.get("highport_capacity")
        sc = d.get("shipyard_capacity")
        sb = d.get("shipyard_largest_bay")
        so = d.get("shipyard_annual_output")
        return cls(
            traffic_importance     = int(d.get("traffic_importance", 0)),
            expected_weekly        = int(d.get("expected_weekly", 0)),
            has_highport           = bool(d.get("has_highport", False)),
            highport_capacity      = int(hp) if hp is not None else None,
            downport_capacity      = int(d.get("downport_capacity", 0)),
            downport_largest_pad   = int(d.get("downport_largest_pad", 0)),
            shipyard_capacity      = int(sc) if sc is not None else None,
            shipyard_largest_bay   = int(sb) if sb is not None else None,
            shipyard_annual_output = int(so) if so is not None else None,
            starport_profile       = str(d.get("starport_profile", "")),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_starport_detail(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    starport: str,
    has_highport: bool,
    importance: int,
    wtn: int,
    efficiency_factor: int,
    infrastructure_factor: int,
    population: int,
    tech_level: int,
    trade_codes: list,
    total_population: int,
    rng: Optional[random.Random] = None,
) -> StarportDetail:
    """Generate detailed starport characteristics (WBH §8).

    Parameters
    ----------
    starport              : starport class letter A–X
    has_highport          : True when 'H' in world.bases (already rolled)
    importance            : world importance score (signed int)
    wtn                   : World Trade Number eHex int (10 = 'A')
    efficiency_factor     : EF from WorldImportance
    infrastructure_factor : IF from WorldImportance
    population            : population code 0–10
    tech_level            : tech level (0–15+)
    trade_codes           : list of trade code strings
    total_population      : actual population count (used in shipyard formula)
    rng                   : injectable RNG; when provided sets module _rng
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    # Traffic importance: actual importance + WTN A+ trade hub boost (WBH p.197)
    traffic_imp = importance + (1 if wtn >= 10 else 0)
    ew = _expected_weekly(traffic_imp)

    # Capacity formula uses actual importance, minimum 1 (WBH p.198)
    cap_imp = max(1, importance)
    ef      = efficiency_factor or 0
    inf_f   = infrastructure_factor or 0

    # Highport capacity (None when no highport or class E/X)
    highport_cap: Optional[int] = None
    if has_highport:
        highport_cap = _compute_highport_capacity(
            starport, cap_imp, ew, population, ef,
        )

    downport_cap = _compute_downport_capacity(
        starport, has_highport, highport_cap, cap_imp, ew, population, ef,
    )

    ship_cap: Optional[int] = None
    ship_bay: Optional[int] = None
    ship_out: Optional[int] = None
    if starport in ("A", "B", "C"):
        ship_cap = _compute_shipyard_capacity(
            starport, ef, inf_f, tech_level, trade_codes, total_population,
        )
        if ship_cap is not None:
            ship_bay = max(100, _round100(ship_cap / 10.0))
            ship_out = _compute_annual_output(starport, ship_cap, importance)

    return StarportDetail(
        traffic_importance     = traffic_imp,
        expected_weekly        = ew,
        has_highport           = has_highport,
        highport_capacity      = highport_cap,
        downport_capacity      = downport_cap,
        downport_largest_pad   = _LARGEST_PAD.get(starport, 0),
        shipyard_capacity      = ship_cap,
        shipyard_largest_bay   = ship_bay,
        shipyard_annual_output = ship_out,
        starport_profile       = _starport_profile(starport, has_highport, traffic_imp),
    )


def attach_starport_detail(
    system,
    rng: Optional[random.Random] = None,
) -> None:
    """Attach StarportDetail to system.mainworld (WBH §8).

    Requires attach_importance_detail() to have already run.
    No-op when importance_detail is None or mainworld is None.
    """
    world = system.mainworld
    if world is None:
        return
    imp_det = world.importance_detail
    if imp_det is None:
        return

    ef    = imp_det.efficiency_factor    or 0
    inf_f = imp_det.infrastructure_factor or 0
    wtn   = imp_det.world_trade_number   or 0

    # Total world population for shipyard formula
    if world.population_detail is not None:
        twp = world.population_detail.total_population
    elif world.population > 0:
        # Estimate using p_value = 5 (midpoint of 2D procedure)
        twp = 5 * (10 ** world.population)
    else:
        twp = 0

    world.starport_detail = generate_starport_detail(
        starport              = world.starport,
        has_highport          = "H" in world.bases,
        importance            = imp_det.importance,
        wtn                   = wtn,
        efficiency_factor     = ef,
        infrastructure_factor = inf_f,
        population            = world.population,
        tech_level            = world.tech_level,
        trade_codes           = list(world.trade_codes),
        total_population      = twp,
        rng                   = rng,
    )
