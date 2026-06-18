"""
traveller_world_importance.py
=================================
World importance calculation for Traveller mainworlds, following the
Traveller Core Rulebook Social Characteristics — Importance section.

The importance score is a deterministic sum of modifiers derived from
starport class, population code, tech level, trade codes, and base
presence. No dice are rolled. Adding this module to the social detail
pipeline has zero effect on RNG state for any other generated value.

Implements (Session 132, issue #155):
  - WorldImportance dataclass with 8 DM components
  - generate_importance_detail() — deterministic calculation
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

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from traveller_system_gen import TravellerSystem


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class WorldImportance:  # pylint: disable=too-many-instance-attributes
    """Traveller world importance score with per-condition DM breakdown."""

    importance:      int   # total signed score
    starport_dm:     int   # −1, 0, or +1
    population_dm:   int   # −1, 0, or +1
    tech_dm:         int   # −1, 0, +1, or +2
    agricultural_dm: int   # 0 or +1
    industrial_dm:   int   # 0 or +1
    rich_dm:         int   # 0 or +1
    base_dm:         int   # 0 or +1  (two or more non-corsair bases)
    waystation_dm:   int   # 0 or +1  (X-Boat waystation, base code "W")

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
        return {
            "importance":      self.importance,
            "starport_dm":     self.starport_dm,
            "population_dm":   self.population_dm,
            "tech_dm":         self.tech_dm,
            "agricultural_dm": self.agricultural_dm,
            "industrial_dm":   self.industrial_dm,
            "rich_dm":         self.rich_dm,
            "base_dm":         self.base_dm,
            "waystation_dm":   self.waystation_dm,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WorldImportance":
        """Reconstruct from a to_dict() output (backward-compat: missing DMs default to 0)."""
        return cls(
            importance=      int(d.get("importance",      0)),
            starport_dm=     int(d.get("starport_dm",     0)),
            population_dm=   int(d.get("population_dm",   0)),
            tech_dm=         int(d.get("tech_dm",         0)),
            agricultural_dm= int(d.get("agricultural_dm", 0)),
            industrial_dm=   int(d.get("industrial_dm",   0)),
            rich_dm=         int(d.get("rich_dm",         0)),
            base_dm=         int(d.get("base_dm",         0)),
            waystation_dm=   int(d.get("waystation_dm",   0)),
        )


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------

def generate_importance_detail(
    starport: str,
    population: int,
    tech_level: int,
    trade_codes: list,
    bases: list,
) -> WorldImportance:
    """Calculate world importance from UWP components.

    No dice are rolled — the result is fully deterministic given the inputs.

    Parameters
    ----------
    starport:    UWP starport code letter ("A"–"X")
    population:  UWP population digit (0–15)
    tech_level:  UWP tech level digit (0–33)
    trade_codes: list of trade code strings, e.g. ["Ag", "Ni", "Ri"]
    bases:       list of base code letters, e.g. ["N", "S"]
    """
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
    )


# ---------------------------------------------------------------------------
# Attach helper
# ---------------------------------------------------------------------------

def attach_importance_detail(system: "TravellerSystem") -> None:
    """Compute and attach importance_detail to the system mainworld.

    Applies only to the mainworld (importance is a mainworld concept).
    Skips if mainworld is None or population is 0 (uninhabited).
    No RNG used — safe to call at any point in the pipeline.
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
    )
