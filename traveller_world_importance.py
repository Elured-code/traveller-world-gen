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

Implements (Session 132–133, issues #155):
  - WorldImportance dataclass with 8 DM components + labour + infrastructure
  - generate_importance_detail() — importance and labour deterministic;
    infrastructure rolls 0–2 dice depending on population
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
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from traveller_system_gen import TravellerSystem

_rng: random.Random = random  # type: ignore[assignment]


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
    efficiency_factor:     Optional[int]  # −5 to +5 (0 treated as +1); None before attach

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
# Attach helper
# ---------------------------------------------------------------------------

def attach_importance_detail(
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
