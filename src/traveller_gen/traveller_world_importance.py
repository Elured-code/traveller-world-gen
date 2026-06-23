"""
traveller_world_importance.py
=================================
World importance, labour, and infrastructure factor calculation for Traveller
mainworlds, following the CRB / WBH Social Characteristics section.

The importance score is a deterministic sum of modifiers derived from starport
class, population code, tech level, trade codes, and base presence.  Labour
factor is also deterministic (Population code − 1, min 0).  Infrastructure
factor adds dice: importance + 1D (pop 4–6) or +2D (pop 7+), with a floor of
None (no infrastructure) when the result would be < 0 or population is 0.

Implements (Sessions 132–133, 135, issues #155, #100):
  - WorldImportance dataclass with 8 DM components + labour + infrastructure
  - generate_importance_detail() — importance and labour deterministic;
    infrastructure rolls 0–2 dice depending on population
  - compute_inequality_rating() — 2D roll + government/law/PCR/IF DMs
  - compute_world_trade_number() — deterministic from population, TL, starport
  - attach_importance_detail() — applies to mainworld only

Licence
-------
MIT Licence — see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.

AI assistance disclosure: developed with Claude (Anthropic).
The human author reviewed, directed, and is responsible for the code.
"""
# pylint: disable=wrong-import-position,import-error,locally-disabled,suppressed-message

import random
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .traveller_system_gen import TravellerSystem

_rng: random.Random = random  # type: ignore[assignment]

_EHEX = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _ehex(n: int) -> str:
    """Convert a non-negative int to a single eHex character (0–Z)."""
    return _EHEX[max(0, min(n, len(_EHEX) - 1))]


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class WorldImportance:  # pylint: disable=too-many-instance-attributes
    """Traveller world importance score with per-condition DM breakdown,
    plus derived labour factor, infrastructure factor, and efficiency factor."""

    importance:            int            # total signed importance score
    starport_dm:           int            # −1, 0, or +1
    population_dm:         int            # −1, 0, or +1
    tech_dm:               int            # −1, 0, +1, or +2
    agricultural_dm:       int            # 0 or +1
    industrial_dm:         int            # 0 or +1
    rich_dm:               int            # 0 or +1
    base_dm:               int            # 0 or +1  (two or more non-corsair bases)
    waystation_dm:         int            # 0 or +1  (X-Boat waystation, base code "W")
    labour_factor:         int            # Population code − 1, min 0; 0 when pop ≤ 1
    infrastructure_factor: Optional[int]  # importance + pop DMs; None when no infrastructure
    efficiency_factor:     Optional[int]   # −5 to +5 (0 treated as +1); None before attach
    resource_units:        Optional[int]   # RF × LF × IF × EF (zeros → 1); None before attach
    gwp_base:              Optional[int]   # IF_adj + min(RF_adj, IF_adj); None before attach
    gwp_per_capita:        Optional[int]   # GWP per capita in Cr; None before attach
    gwp_total_mcr:         Optional[float] # total GWP in MCr; None before attach
    development_score:     Optional[float]  # (GWP_pc/1000)×(1−IR/100); None before attach
    economics_profile:     Optional[str]   # e.g. "765+2" — RF/LF/IF eHex + EF signed
    inequality_rating:     Optional[int]   = field(default=None)  # 0–100; 50=neutral; dice roll
    world_trade_number:    Optional[int]   = field(default=None)  # eHex int; deterministic

    @property
    def importance_str(self) -> str:
        """Return the importance score as a signed string: '+2', '0', '−2'."""
        if self.importance > 0:
            return f"+{self.importance}"
        if self.importance < 0:
            return f"−{abs(self.importance)}"  # minus sign U+2212
        return "0"

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON output."""
        d: dict = {
            "importance":      self.importance,
            "starport_dm":     self.starport_dm,
            "population_dm":   self.population_dm,
            "tech_dm":         self.tech_dm,
            "agricultural_dm": self.agricultural_dm,
            "industrial_dm":   self.industrial_dm,
            "rich_dm":         self.rich_dm,
            "base_dm":         self.base_dm,
            "waystation_dm":   self.waystation_dm,
            "labour_factor":   self.labour_factor,
        }
        if self.infrastructure_factor is not None:
            d["infrastructure_factor"] = self.infrastructure_factor
        if self.efficiency_factor is not None:
            d["efficiency_factor"] = self.efficiency_factor
        if self.resource_units is not None:
            d["resource_units"] = self.resource_units
        if self.gwp_base is not None:
            d["gwp_base"] = self.gwp_base
        if self.gwp_per_capita is not None:
            d["gwp_per_capita"] = self.gwp_per_capita
        if self.gwp_total_mcr is not None:
            d["gwp_total_mcr"] = self.gwp_total_mcr
        if self.development_score is not None:
            d["development_score"] = self.development_score
        if self.economics_profile is not None:
            d["economics_profile"] = self.economics_profile
        if self.inequality_rating is not None:
            d["inequality_rating"] = self.inequality_rating
        if self.world_trade_number is not None:
            d["world_trade_number"] = self.world_trade_number
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "WorldImportance":
        """Reconstruct from a to_dict() output (backward-compat: missing fields default to 0)."""
        return cls(
            importance=            int(d.get("importance",      0)),
            starport_dm=           int(d.get("starport_dm",     0)),
            population_dm=         int(d.get("population_dm",   0)),
            tech_dm=               int(d.get("tech_dm",         0)),
            agricultural_dm=       int(d.get("agricultural_dm", 0)),
            industrial_dm=         int(d.get("industrial_dm",   0)),
            rich_dm=               int(d.get("rich_dm",         0)),
            base_dm=               int(d.get("base_dm",         0)),
            waystation_dm=         int(d.get("waystation_dm",   0)),
            labour_factor=         int(d.get("labour_factor",   0)),
            infrastructure_factor= (
                int(d["infrastructure_factor"])
                if d.get("infrastructure_factor") is not None else None
            ),
            efficiency_factor= (
                int(d["efficiency_factor"])
                if d.get("efficiency_factor") is not None else None
            ),
            resource_units= (
                int(d["resource_units"])
                if d.get("resource_units") is not None else None
            ),
            gwp_base= (
                int(d["gwp_base"])
                if d.get("gwp_base") is not None else None
            ),
            gwp_per_capita= (
                int(d["gwp_per_capita"])
                if d.get("gwp_per_capita") is not None else None
            ),
            gwp_total_mcr= (
                float(d["gwp_total_mcr"])
                if d.get("gwp_total_mcr") is not None else None
            ),
            development_score= (
                float(d["development_score"])
                if d.get("development_score") is not None else None
            ),
            economics_profile=d.get("economics_profile"),
            inequality_rating=(
                int(d["inequality_rating"])
                if d.get("inequality_rating") is not None else None
            ),
            world_trade_number=(
                int(d["world_trade_number"])
                if d.get("world_trade_number") is not None else None
            ),
        )


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------

def generate_importance_detail(  # pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments,too-many-branches
    starport: str,
    population: int,
    tech_level: int,
    trade_codes: list,
    bases: list,
    rng: Optional[random.Random] = None,
) -> WorldImportance:
    """Calculate world importance, labour factor, and infrastructure factor.

    Parameters
    ----------
    starport:    UWP starport code letter ("A"–"X")
    population:  UWP population digit (0–15)
    tech_level:  UWP tech level digit (0–33)
    trade_codes: list of trade code strings, e.g. ["Ag", "Ni", "Ri"]
    bases:       list of base code letters, e.g. ["N", "S"]
    rng:         injectable RNG; infrastructure factor rolls 1D or 2D
    """
    r = rng if rng is not None else _rng

    # Starport DM
    if starport in ("A", "B"):
        starport_dm = 1
    elif starport in ("D", "E", "X"):
        starport_dm = -1
    else:
        starport_dm = 0

    # Population DM
    if population <= 6:
        population_dm = -1
    elif population >= 9:
        population_dm = 1
    else:
        population_dm = 0

    # Tech level DM (TL 9 is a dead zone — no modifier)
    if tech_level >= 16:      # G+ in eHex
        tech_dm = 2
    elif tech_level >= 10:    # A–F in eHex
        tech_dm = 1
    elif tech_level <= 8:     # 0–8
        tech_dm = -1
    else:                     # 9
        tech_dm = 0

    # Trade code DMs
    agricultural_dm = 1 if "Ag" in trade_codes else 0
    industrial_dm   = 1 if "In" in trade_codes else 0
    rich_dm         = 1 if "Ri" in trade_codes else 0

    # Base DM — two or more bases present, excluding Corsair ("C")
    non_corsair_count = sum(1 for b in bases if b != "C")
    base_dm = 1 if non_corsair_count >= 2 else 0

    # X-Boat waystation DM (base code "W")
    waystation_dm = 1 if "W" in bases else 0

    importance = (
        starport_dm + population_dm + tech_dm
        + agricultural_dm + industrial_dm + rich_dm
        + base_dm + waystation_dm
    )

    # Labour factor: Population code − 1, minimum 0; 0 for pop 0 or 1
    labour_factor = max(0, population - 1)

    # Infrastructure factor: importance + population DMs (1D for 4–6, 2D for 7+)
    # None when population is 0 or when the calculated result is negative
    if population == 0:
        infrastructure_factor: Optional[int] = None
    else:
        if population >= 7:
            infra_dm = r.randint(1, 6) + r.randint(1, 6)
        elif population >= 4:
            infra_dm = r.randint(1, 6)
        else:
            infra_dm = 0
        raw = importance + infra_dm
        infrastructure_factor = raw if raw >= 0 else None

    return WorldImportance(
        importance=importance,
        starport_dm=starport_dm,
        population_dm=population_dm,
        tech_dm=tech_dm,
        agricultural_dm=agricultural_dm,
        industrial_dm=industrial_dm,
        rich_dm=rich_dm,
        base_dm=base_dm,
        waystation_dm=waystation_dm,
        labour_factor=labour_factor,
        infrastructure_factor=infrastructure_factor,
        efficiency_factor=None,
        resource_units=None,
        gwp_base=None,
        gwp_per_capita=None,
        gwp_total_mcr=None,
        development_score=None,
        economics_profile=None,
    )


# ---------------------------------------------------------------------------
# Efficiency factor
# ---------------------------------------------------------------------------

# Governments that penalise efficiency (DM-1)
_EF_GOV_MINUS = frozenset({0, 3, 6, 9, 11, 12, 15})  # 0,3,6,9,B,C,F
# Governments that boost efficiency (DM+1)
_EF_GOV_PLUS  = frozenset({1, 2, 4, 5, 8})            # 1,2,4,5,8


def compute_efficiency_factor(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-branches
    population: int,
    government: int,
    law_level: int,
    pcr: int,
    progressiveness: int,
    expansionism: int,
    rng: Optional[random.Random] = None,
) -> int:
    """Compute the world efficiency factor (WBH p.131).

    Returns an integer in [-5, +5]; 0 is always converted to +1.
    Population 0 always returns -5 (no inhabitants, no efficiency).

    Parameters
    ----------
    population:     UWP population code (0–15)
    government:     UWP government code (0–15)
    law_level:      UWP law level code (0–15)
    pcr:            Population Concentration Rating from population_detail
    progressiveness: CultureDetail progressiveness trait (raw, 1–35)
    expansionism:   CultureDetail expansionism trait (raw, 1–35)
    rng:            injectable RNG for the base dice roll
    """
    if population == 0:
        return -5

    r = rng if rng is not None else _rng

    # Base roll: 2D3-4 for pop 7+, 2D6-7 for pop 1-6
    if population >= 7:
        base = r.randint(1, 3) + r.randint(1, 3) - 4
    else:
        base = r.randint(1, 6) + r.randint(1, 6) - 7

    dm = 0
    if government in _EF_GOV_MINUS:
        dm -= 1
    if government in _EF_GOV_PLUS:
        dm += 1

    if law_level <= 4:
        dm += 1
    if law_level >= 10:      # A+
        dm -= 1

    if pcr <= 3:
        dm -= 1
    if pcr >= 8:
        dm += 1

    if 1 <= progressiveness <= 3:
        dm -= 1
    if progressiveness >= 9:
        dm += 1

    if 1 <= expansionism <= 3:
        dm -= 1
    if expansionism >= 9:
        dm += 1

    result = max(-5, min(5, base + dm))
    return result if result != 0 else 1


# ---------------------------------------------------------------------------
# Resource units
# ---------------------------------------------------------------------------

def compute_resource_units(
    resource_factor: Optional[int],
    labour_factor: int,
    infrastructure_factor: Optional[int],
    efficiency_factor: int,
) -> int:
    """Compute system resource units (WBH p.131).

    RU = Resource Factor × Labour Factor × Infrastructure Factor × Efficiency Factor.
    Any factor with value 0 (or absent for infrastructure) is treated as 1.
    Only efficiency factor can produce a negative RU.
    """
    rf  = resource_factor   if (resource_factor  is not None and resource_factor  != 0) else 1
    lf  = labour_factor     if labour_factor     != 0 else 1
    inf = infrastructure_factor if (infrastructure_factor is not None and
                                    infrastructure_factor != 0) else 1
    return rf * lf * inf * efficiency_factor


# ---------------------------------------------------------------------------
# Gross World Product
# ---------------------------------------------------------------------------

_GWP_PORT_MODS: dict[str, float] = {
    "A": 1.5, "B": 1.2, "C": 1.0, "D": 0.8, "E": 0.5,
    "F": 0.9, "G": 0.7, "H": 0.4, "Y": 0.2, "X": 0.2,
}

_GWP_GOV_MODS: dict[int, float] = {
    0: 1.0, 1: 1.5, 2: 1.2, 3: 0.8,  4: 1.2, 5: 1.3,
    6: 0.6, 7: 1.0, 8: 0.9, 9: 0.8, 10: 1.0, 11: 0.7,
    12: 1.0, 13: 0.6, 14: 0.5, 15: 0.8,
}

_GWP_TC_MODS: dict[str, float] = {
    "Ag": 0.9, "As": 1.2, "Ga": 1.2, "In": 1.1,
    "Na": 0.9, "Ni": 0.9, "Po": 0.8, "Ri": 1.2,
}


def compute_gwp_base(
    infrastructure_factor: Optional[int],
    resource_factor: Optional[int],
) -> int:
    """Compute the GWP base value (WBH p.132).

    Base Value = IF_adj + min(RF_adj, IF_adj).
    Each factor is treated as ≥ 1 when population > 0 (assumed by caller).
    RF is capped at IF so the upper bound is 2 × IF and lower bound is 2.
    """
    inf_adj = max(1, infrastructure_factor) if infrastructure_factor is not None else 1
    rf_adj  = max(1, resource_factor)       if resource_factor       is not None else 1
    return inf_adj + min(rf_adj, inf_adj)


def compute_gwp(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    population: int,
    starport: str,
    tech_level: int,
    government: int,
    trade_codes: list,
    gwp_base: int,
    efficiency_factor: int,
) -> tuple[int, float]:
    """Compute GWP per capita (Cr) and total GWP (MCr) (WBH p.132).

    Returns (gwp_per_capita_cr, gwp_total_mcr).
    Population 0 returns (0, 0.0).

    Total Modifiers = TL Modifier × Port Modifier × Government Modifier
                    × Trade Code Modifiers (each applicable TC applied separately).

    Positive EF: GWP_pc = Cr1000 × Base × Total_Mods × EF
    Negative EF: GWP_pc = Cr1000 × Base × Total_Mods / -(EF − 1)
    """
    if population == 0:
        return (0, 0.0)

    tl_mod   = max(0.05, tech_level / 10.0)
    port_mod = _GWP_PORT_MODS.get(starport, 1.0)
    gov_mod  = _GWP_GOV_MODS.get(government, 1.0)

    tc_mod = 1.0
    for tc in trade_codes:
        if tc in _GWP_TC_MODS:
            tc_mod *= _GWP_TC_MODS[tc]

    total_mods = tl_mod * port_mod * gov_mod * tc_mod

    if efficiency_factor > 0:
        gwp_pc = 1000.0 * gwp_base * total_mods * efficiency_factor
    else:
        gwp_pc = 1000.0 * gwp_base * total_mods / (1 - efficiency_factor)

    gwp_per_capita = round(gwp_pc)
    gwp_total_mcr  = round(gwp_per_capita * (10 ** population) / 1_000_000, 2)
    return (gwp_per_capita, gwp_total_mcr)


# ---------------------------------------------------------------------------
# Development score
# ---------------------------------------------------------------------------

def compute_development_score(gwp_per_capita: int, inequality_rating: int = 0) -> float:
    """Compute the IISS development score (WBH p.132).

    Development Score = (GWP per capita / 1000) × (1 − Inequality Rating / 100)

    When inequality_rating is 0 (not yet computed) the score equals GWP_pc / 1000.
    The result is rounded to 2 decimal places.
    """
    return round((gwp_per_capita / 1000.0) * (1 - inequality_rating / 100.0), 2)


# ---------------------------------------------------------------------------
# Inequality rating
# ---------------------------------------------------------------------------

_IR_GOV_PLUS10  = frozenset({6, 11, 15})      # gov 6, B, F
_IR_GOV_PLUS5   = frozenset({0, 1, 3, 9, 12}) # gov 0, 1, 3, 9, C
_IR_GOV_MINUS5  = frozenset({4, 8})            # gov 4, 8
_IR_GOV_MINUS10 = frozenset({2})               # gov 2


def compute_inequality_rating(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    efficiency_factor: int,
    government: int,
    law_level: int,
    pcr: int,
    infrastructure_factor: Optional[int],
    rng: Optional[random.Random] = None,
) -> int:
    """Compute the world inequality rating (WBH Social Characteristics).

    Inequality Rating = 50 − (EF × 5) + (2D−7) × 2 + DMs
    Result clamped to [0, 100].  50 = perfectly equal baseline.
    Higher values → more unequal distribution of wealth.
    """
    r = rng if rng is not None else _rng
    roll = (r.randint(1, 6) + r.randint(1, 6) - 7) * 2

    dm = 0
    if government in _IR_GOV_PLUS10:
        dm += 10
    elif government in _IR_GOV_PLUS5:
        dm += 5
    elif government in _IR_GOV_MINUS5:
        dm -= 5
    elif government in _IR_GOV_MINUS10:
        dm -= 10

    if law_level >= 9:
        dm += law_level - 8

    dm += pcr

    if infrastructure_factor is not None:
        dm -= infrastructure_factor

    return max(0, min(100, 50 - efficiency_factor * 5 + roll + dm))


# ---------------------------------------------------------------------------
# World Trade Number
# ---------------------------------------------------------------------------

# Base WTN TL DM thresholds
def _wtn_tl_dm(tech_level: int) -> int:
    if tech_level <= 1:
        return -1
    if tech_level <= 4:
        return 0
    if tech_level <= 8:
        return 1
    if tech_level <= 14:
        return 2
    return 3


def _wtn_row(base_wtn: int) -> int:
    """Return the 0-based row index into _WTN_PORT_TABLE for a given base WTN."""
    bands = (1, 3, 5, 7, 9, 11, 13)
    for idx, ceiling in enumerate(bands):
        if base_wtn <= ceiling:
            return idx
    return 7


# WTN starport modifier table indexed by [row][starport_class].
# Rows correspond to base WTN bands: 0-1, 2-3, 4-5, 6-7, 8-9, 10-11, 12-13, 14+.
_WTN_PORT_TABLE: list[dict[str, int]] = [
    {"A": 3, "B": 2, "C": 2, "D":  1, "E":  1, "X":   0},  # 0–1
    {"A": 2, "B": 2, "C": 1, "D":  1, "E":  0, "X":  -5},  # 2–3
    {"A": 2, "B": 1, "C": 1, "D":  0, "E":  0, "X":  -5},  # 4–5
    {"A": 1, "B": 1, "C": 0, "D":  0, "E": -1, "X":  -6},  # 6–7
    {"A": 1, "B": 0, "C": 0, "D": -1, "E": -2, "X":  -7},  # 8–9
    {"A": 0, "B": 0, "C":-1, "D": -2, "E": -3, "X":  -8},  # 10–11
    {"A": 0, "B":-1, "C":-2, "D": -3, "E": -4, "X":  -9},  # 12–13
    {"A": 0, "B":-2, "C":-3, "D": -4, "E": -5, "X": -10},  # 14+
]


def compute_world_trade_number(population: int, tech_level: int, starport: str) -> int:
    """Compute the World Trade Number (WBH Social Characteristics).

    WTN = Population code + TL DM + Starport DM, minimum 0.
    Stored as a plain integer; callers display it as eHex.
    """
    base = population + _wtn_tl_dm(tech_level)
    port_dm = _WTN_PORT_TABLE[_wtn_row(base)].get(starport, 0)
    return max(0, base + port_dm)


# ---------------------------------------------------------------------------
# Economics profile string
# ---------------------------------------------------------------------------

def compute_economics_profile(
    resource_factor: Optional[int],
    labour_factor: int,
    infrastructure_factor: Optional[int],
    efficiency_factor: int,
) -> str:
    """Build the economics profile string (WBH Social Characteristics).

    Format: RF LF IF EF — e.g. "765+2" or "A90-3".
    RF, LF, IF are single eHex characters; IF is '0' when absent.
    EF is a signed decimal (+1…+5 or -1…-5; never 0 by rule).
    """
    rf_char  = _ehex(resource_factor   if resource_factor   is not None else 0)
    lf_char  = _ehex(labour_factor)
    if_char  = _ehex(infrastructure_factor) if infrastructure_factor is not None else "0"
    ef_str   = f"+{efficiency_factor}" if efficiency_factor > 0 else str(efficiency_factor)
    return f"{rf_char}{lf_char}{if_char}{ef_str}"


# ---------------------------------------------------------------------------
# Attach helper
# ---------------------------------------------------------------------------

def attach_importance_detail(  # pylint: disable=too-many-locals
    system: "TravellerSystem",
    rng: Optional[random.Random] = None,
) -> None:
    """Compute and attach importance_detail to the system mainworld.

    Applies only to the mainworld (importance is a mainworld concept).
    Skips if mainworld is None or population is 0 (uninhabited).
    Infrastructure factor rolls 1D or 2D depending on population.
    Efficiency factor requires government, law_level, and optionally
    population_detail.pcr and culture_detail traits.
    """
    world = system.mainworld
    if world is None or world.population == 0:
        return

    world.importance_detail = generate_importance_detail(  # type: ignore[attr-defined]
        starport=world.starport,
        population=world.population,
        tech_level=world.tech_level,
        trade_codes=world.trade_codes,
        bases=world.bases,
        rng=rng,
    )

    pop_det = getattr(world, "population_detail", None)
    cult_det = getattr(world, "culture_detail", None)
    pcr           = pop_det.pcr           if pop_det  is not None else 0
    progressiveness = cult_det.progressiveness if cult_det is not None else 0
    expansionism    = cult_det.expansionism    if cult_det is not None else 0

    ef = compute_efficiency_factor(
        population=world.population,
        government=world.government,
        law_level=world.law_level,
        pcr=pcr,
        progressiveness=progressiveness,
        expansionism=expansionism,
        rng=rng,
    )
    world.importance_detail.efficiency_factor = ef  # type: ignore[attr-defined]

    phys = getattr(world, "size_detail", None)
    resource_factor = getattr(phys, "resource_factor", None) if phys is not None else None
    wi = world.importance_detail  # type: ignore[attr-defined]
    wi.resource_units = compute_resource_units(  # type: ignore[attr-defined]
        resource_factor=resource_factor,
        labour_factor=wi.labour_factor,
        infrastructure_factor=wi.infrastructure_factor,
        efficiency_factor=ef,
    )

    gwp_base = compute_gwp_base(
        infrastructure_factor=wi.infrastructure_factor,
        resource_factor=resource_factor,
    )
    wi.gwp_base = gwp_base  # type: ignore[attr-defined]
    gwp_pc, gwp_mcr = compute_gwp(
        population=world.population,
        starport=world.starport,
        tech_level=world.tech_level,
        government=world.government,
        trade_codes=world.trade_codes,
        gwp_base=gwp_base,
        efficiency_factor=ef,
    )
    wi.gwp_per_capita = gwp_pc   # type: ignore[attr-defined]
    wi.gwp_total_mcr  = gwp_mcr  # type: ignore[attr-defined]

    wi.economics_profile = compute_economics_profile(  # type: ignore[attr-defined]
        resource_factor=resource_factor,
        labour_factor=wi.labour_factor,
        infrastructure_factor=wi.infrastructure_factor,
        efficiency_factor=ef,
    )

    ir = compute_inequality_rating(
        efficiency_factor=ef,
        government=world.government,
        law_level=world.law_level,
        pcr=pcr,
        infrastructure_factor=wi.infrastructure_factor,
        rng=rng,
    )
    wi.inequality_rating = ir  # type: ignore[attr-defined]
    wi.development_score = compute_development_score(  # type: ignore[attr-defined]
        gwp_pc, inequality_rating=ir,
    )
    wi.world_trade_number = compute_world_trade_number(  # type: ignore[attr-defined]
        population=world.population,
        tech_level=world.tech_level,
        starport=world.starport,
    )
