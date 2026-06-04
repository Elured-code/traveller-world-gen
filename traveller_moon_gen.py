"""
traveller_moon_gen.py
=====================
Generates significant moons and rings for every world in a star system,
following the World Builder's Handbook (WBH pp.55-57, 74-77).

Rules implemented
-----------------
Quantity (WBH p.56):
  Planet Size 1-2  : 1D-5
  Planet Size 3-9  : 2D-8
  Planet Size A-F  : 2D-6
  Small GG (GS#)   : 3D-7
  Medium/Large GG  : 4D-6
  DM-1 per dice if orbit# < 1.0 (only condition relevant without
  eccentricity data; other adjacency conditions require star/spread
  context and are omitted as out of scope)
  Negative result  : 0 moons
  Exactly 0        : 1 significant ring (R)

Sizing (WBH p.57):
  Each moon: 1D roll picks a range, second roll gives size
    1-3 → S  (size S, ~600km)
    4-5 → D3-1  (0 = ring R, 1, or 2)
    6   → Terrestrial: Size-1 - 1D  (may give R or S)
          Gas giant: special table below
  Gas Giant Special Moon Sizing (1D):
    1-3 → 1D   (size 1-6)
    4-5 → 2D-2 (size 0-A; 0 = ring R)
    6   → 2D+4 (size 6-G; G = small gas giant)

  Rings: multiple rings on a single planet are collapsed to one
  R0# notation (e.g. R03 = three significant rings).

Output
------
A Moon dataclass holds (size_code, is_ring).
size_code is an integer for numeric sizes, or the string "S" for
size S moons.  Rings are stored as (size_code=0, is_ring=True).

The main entry point `generate_moons(world_detail, orbit_number)`
returns a list of Moon objects sorted: rings first, then S moons,
then numeric sizes ascending.

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

from __future__ import annotations
import math
import random
_rng: random.Random = random  # type: ignore[assignment]
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from traveller_orbit_gen import roll_eccentricity, roll_inclination
if TYPE_CHECKING:
    from traveller_world_detail import WorldDetail


# ---------------------------------------------------------------------------
# Dice helpers
# ---------------------------------------------------------------------------

def _roll(n: int, dm: int = 0) -> int:
    return max(0, sum(_rng.randint(1, 6) for _ in range(n)) + dm)

def _d3() -> int:
    return (_rng.randint(1, 6) + 1) // 2

_EHEX = "0123456789ABCDEFG"
def _ehex(n: int) -> str:
    n = max(0, min(n, len(_EHEX) - 1))
    return _EHEX[n]


# ---------------------------------------------------------------------------
# Orbit placement helpers (WBH pp.74-77)
# ---------------------------------------------------------------------------

_AU_KM = 149_597_870.9  # km per AU (WBH p.74)


def _hill_sphere_au(orbit_au: float, ecc: float,
                    mass_earth: float, star_mass_solar: float) -> float:
    """Hill sphere radius in AU (WBH p.74)."""
    return orbit_au * (1.0 - ecc) * (mass_earth * 3e-6 / (3.0 * star_mass_solar)) ** (1.0 / 3.0)


def _hill_sphere_pd(hill_au: float, diameter_km: float) -> float:
    """Hill sphere radius in planetary diameters (WBH p.74)."""
    return hill_au * _AU_KM / diameter_km


def _hill_moon_limit(hill_pd: float) -> int:
    """Practical outer moon limit = floor(Hill Sphere PD / 2) (WBH p.74)."""
    return math.floor(hill_pd / 2.0)


def _moon_orbit_range(moon_limit: int, n_moons: int) -> int:
    """MOR = Moon Limit − 2; capped at 200 + n_moons when > 200 (WBH p.75)."""
    mor = moon_limit - 2
    if mor <= 0:
        return 0
    if mor > 200:
        mor = min(mor, 200 + n_moons)
    return mor


def _roll_moon_pd(mor: int) -> tuple[float, str]:
    """Roll one moon's orbital PD and range label (WBH pp.75-76).

    Returns (pd, range_name) where range_name is "inner", "middle", or "outer".
    """
    dm = 1 if mor < 60 else 0
    r1 = _rng.randint(1, 6) + dm
    r2d = _roll(2) - 2   # 2D-2
    if r1 <= 3:
        return round(r2d * mor / 60.0 + 2.0, 1), "inner"
    if r1 <= 5:
        return round(r2d * mor / 30.0 + mor / 6.0 + 3.0, 1), "middle"
    return round(r2d * mor / 20.0 + mor / 2.0 + 4.0, 1), "outer"


def _moon_period_hours(orbit_km: float, mass_earth: float) -> float:
    """Moon orbital period in hours using km orbital distance (WBH p.76)."""
    if mass_earth <= 0:
        return 0.0
    return round(math.sqrt(orbit_km ** 3 / mass_earth) / 361730.0, 2)


def _estimate_diameter_km(size_code: int | str, is_gas_giant: bool,
                           gg_diameter: int) -> float:
    """Estimate planet diameter in km from size code (used for secondary worlds)."""
    if is_gas_giant:
        return float(gg_diameter * 12800)
    if size_code == "S":
        return 800.0
    sz = int(size_code)
    return float(max(1, sz) * 1600)


def _estimate_mass_earth(size_code: int | str, is_gas_giant: bool,
                          gg_diameter: int) -> float:
    """Estimate planet mass in Earth masses (used for secondary worlds).

    Terrestrial worlds assume Terran density (mass ∝ diameter³).
    Gas giants use gg_diameter² as a rough estimate; the cube-root in the Hill
    sphere formula absorbs the resulting 2–3× error acceptably.
    """
    if is_gas_giant:
        return float(max(1, gg_diameter) ** 2)
    diam = _estimate_diameter_km(size_code, False, 0)
    return (diam / 12742.0) ** 3


def _assign_sig_moon_orbits(sig_moons: List["Moon"], mor: int,
                             diam_km: float, mass_e: float) -> None:
    """Roll and assign orbit PD/km/range/period to significant moons (WBH pp.75-76)."""
    pd_rolls = [_roll_moon_pd(mor) for _ in range(len(sig_moons))]
    pd_rolls.sort(key=lambda x: x[0])
    for moon, (pd, rng) in zip(sig_moons, pd_rolls):
        moon.orbit_pd           = pd
        moon.orbit_km           = round(pd * diam_km, 1)
        moon.orbit_range        = "excess" if pd > mor + 2 else rng
        moon.orbit_period_hours = _moon_period_hours(moon.orbit_km, mass_e)
    # Collision resolution: push overlapping moons outward by 1 PD
    for i in range(1, len(sig_moons)):
        prev, curr = sig_moons[i - 1], sig_moons[i]
        if curr.orbit_pd is not None and prev.orbit_pd is not None:
            if curr.orbit_pd <= prev.orbit_pd:
                curr.orbit_pd           = prev.orbit_pd + 1.0
                curr.orbit_km           = round(curr.orbit_pd * diam_km, 1)
                curr.orbit_period_hours = _moon_period_hours(curr.orbit_km, mass_e)


def _place_ring(planet_diameter_km: float) -> tuple[float, float]:  # pylint: disable=unused-argument
    """Roll ring centre location and span in PD (WBH p.77)."""
    centre = round(0.4 + _roll(2) / 8.0, 3)
    span   = round(_roll(3) / 100.0 + 0.07, 3)
    # Ensure innermost ring edge is at least 0.55 PD above planet surface (1.05 PD from centre)
    if centre - span / 2.0 < 0.55:
        centre = round(0.55 + span / 2.0, 3)
    return centre, span


# ---------------------------------------------------------------------------
# Moon dataclass
# ---------------------------------------------------------------------------

@dataclass
class Moon:  # pylint: disable=too-many-instance-attributes
    """A single significant moon or ring."""
    size_code: int | str   # int for numeric sizes, "S" for size S, 0 for ring
    is_ring: bool = False
    is_gas_giant_moon: bool = False  # True if moon is itself a small GG
    detail: Optional["WorldDetail"] = None  # full SAH+social, populated later
    ring_count: int = field(default=1, init=False, repr=False)  # collapsed ring count
    # Orbit placement (WBH pp.74-77); populated by generate_moons() when orbit data provided
    orbit_pd: Optional[float] = field(default=None, init=False)
    orbit_km: Optional[float] = field(default=None, init=False)
    orbit_range: Optional[str] = field(default=None, init=False)  # inner/middle/outer/excess
    orbit_period_hours: Optional[float] = field(default=None, init=False)
    ring_centre_pd: Optional[float] = field(default=None, init=False)
    ring_span_pd: Optional[float] = field(default=None, init=False)
    # Eccentricity and inclination (WBH p.76); set by generate_moons() when orbit data provided
    orbit_eccentricity: float = field(default=0.0, init=False)
    orbit_inclination: float = field(default=0.0, init=False)  # >90° implies retrograde
    name: str = field(default="", init=False)  # set by attach_body_names()

    @property
    def size_str(self) -> str:
        """Return the display string for this moon's size code."""
        if self.is_ring:
            return "R"
        if self.size_code == "S":
            return "S"
        return _ehex(int(self.size_code))

    def __repr__(self) -> str:
        if self.is_ring:
            return "Ring"
        return f"Size {self.size_str}"

    def to_dict(self) -> dict:
        """Serialise this moon to a JSON-compatible dict.
        The 'detail' field (WorldDetail) is serialised inline if present.
        """
        d: dict = {
            "size":             self.size_str,
            "is_ring":          self.is_ring,
            "is_gas_giant_moon": self.is_gas_giant_moon,
        }
        if self.is_ring:
            d["ring_count"] = self.ring_count
        if self.orbit_pd is not None:
            d["orbit_pd"]           = self.orbit_pd
            d["orbit_km"]           = self.orbit_km
            d["orbit_range"]        = self.orbit_range
            d["orbit_period_hours"] = self.orbit_period_hours
            if self.orbit_eccentricity > 0:
                d["orbit_eccentricity"] = round(self.orbit_eccentricity, 4)
            if self.orbit_inclination > 0:
                d["orbit_inclination"] = round(self.orbit_inclination, 2)
        if self.is_ring and self.ring_centre_pd is not None:
            d["ring_centre_pd"] = self.ring_centre_pd
            d["ring_span_pd"]   = self.ring_span_pd
        if self.name:
            d["name"] = self.name
        if self.detail is not None:
            d["detail"] = self.detail.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Moon":
        """Reconstruct a Moon from a dict produced by to_dict()."""
        size_raw = str(d["size"])
        if size_raw == "R":
            moon = cls(size_code=0, is_ring=True,
                       is_gas_giant_moon=bool(d.get("is_gas_giant_moon", False)))
            moon.ring_count = int(d.get("ring_count", 1))
            if d.get("ring_centre_pd") is not None:
                moon.ring_centre_pd = float(d["ring_centre_pd"])
                moon.ring_span_pd   = float(d["ring_span_pd"])
        elif size_raw == "S":
            moon = cls(size_code="S",
                       is_gas_giant_moon=bool(d.get("is_gas_giant_moon", False)))
        else:
            moon = cls(size_code=_EHEX.index(size_raw.upper()),
                       is_gas_giant_moon=bool(d.get("is_gas_giant_moon", False)))
        if d.get("orbit_pd") is not None:
            moon.orbit_pd           = float(d["orbit_pd"])
            moon.orbit_km           = (float(d["orbit_km"])
                                       if d.get("orbit_km") is not None else None)
            moon.orbit_range        = (str(d["orbit_range"])
                                       if d.get("orbit_range") is not None else None)
            moon.orbit_period_hours = (float(d["orbit_period_hours"])
                                       if d.get("orbit_period_hours") is not None else None)
            moon.orbit_eccentricity = float(d.get("orbit_eccentricity", 0.0))
            moon.orbit_inclination  = float(d.get("orbit_inclination", 0.0))
        moon.name = str(d.get("name", ""))
        if d.get("detail"):
            from traveller_world_detail import WorldDetail  # pylint: disable=import-outside-toplevel
            moon.detail = WorldDetail.from_dict(d["detail"])
        return moon


# ---------------------------------------------------------------------------
# Moon quantity (WBH p.56)
# ---------------------------------------------------------------------------

def _moon_quantity(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-branches
        size_code: int | str, orbit_number: float,
        is_gas_giant: bool, gg_category: str,
        star_mao: float = 0.0,
        companion_exclusion_zones: list | None = None,
        is_adjacent_outermost_far: bool = False) -> int:
    """
    Roll for number of significant moons.
    Returns the raw result (negative = 0 moons, 0 = 1 ring).
    WBH p.56: only one DM-1 applies regardless of how many conditions match.
    """
    # Conditions in priority order — first match wins (WBH p.56)
    dm = 0
    if orbit_number < 1.0:
        dm = -1
    elif companion_exclusion_zones:
        for lo, hi in companion_exclusion_zones:
            if lo <= orbit_number <= hi:
                dm = -1
                break
    elif star_mao > 0.0 and abs(orbit_number - star_mao) <= 1.0:
        dm = -1
    elif is_adjacent_outermost_far:
        dm = -1

    if is_gas_giant:
        if gg_category == "S":
            result = _roll(3, dm * 3) - 7   # 3D-7
        else:
            result = _roll(4, dm * 4) - 6   # 4D-6
    else:
        sz = int(size_code) if size_code != "S" else 1
        if sz <= 2:
            result = _rng.randint(1, 6) + dm - 5     # 1D-5
        elif sz <= 9:
            result = _roll(2, dm * 2) - 8              # 2D-8
        else:
            result = _roll(2, dm * 2) - 6              # 2D-6

    return result


# ---------------------------------------------------------------------------
# Moon sizing (WBH p.57)
# ---------------------------------------------------------------------------

def _size_terrestrial_moon(parent_size: int) -> Moon:
    """
    Size one moon for a terrestrial parent (WBH p.57).

    WBH rule: "Moons may range in size from S to the Size of the parent planet."
    The clamp at the end of each branch enforces this — any roll that would
    exceed the parent size is clamped down to the parent size (twin world).
    The Size 1 planet special case falls out naturally: D3-1 can give 2 which
    would exceed parent_size=1 and is clamped to 1 (twin).

    r=6 branch WBH: "a negative result indicates a Size S moon, a 0 indicates
    a ring." The formula is (parent_size - 1) - 1D. For parent_size=1 the
    result is always ≤ 0 (ring or S). For larger parents it can be positive.
    """
    r = _rng.randint(1, 6)
    if r <= 3:
        return Moon(size_code="S")
    if r <= 5:
        sz = _d3() - 1            # D3-1: 0, 1, or 2
        if sz == 0:
            return Moon(size_code=0, is_ring=True)
        # Clamp: moon cannot exceed parent size (WBH p.57)
        sz = min(sz, parent_size)
        return Moon(size_code=sz)
    # Size = (parent_size - 1) - 1D; negative → S, zero → ring (WBH p.57)
    sz = (parent_size - 1) - _rng.randint(1, 6)
    if sz < 0:
        return Moon(size_code="S")
    if sz == 0:
        return Moon(size_code=0, is_ring=True)
    return Moon(size_code=sz)


def _size_gg_moon(gg_diameter: int) -> Moon:
    """Size one moon for a gas giant parent."""
    r = _rng.randint(1, 6)
    if r <= 3:
        return Moon(size_code="S")
    if r <= 5:
        sz = _d3() - 1
        if sz == 0:
            return Moon(size_code=0, is_ring=True)
        return Moon(size_code=sz)
    # Gas Giant Special Moon Sizing
    r2 = _rng.randint(1, 6)
    if r2 <= 3:
        sz = _rng.randint(1, 6)             # 1D → 1-6
    elif r2 <= 5:
        sz = max(0, _roll(2) - 2)             # 2D-2 → 0-A
    else:
        sz = _roll(2, 4)                      # 2D+4 → 6-G
        if sz >= 16:
            # Size G = this moon is a small gas giant
            gg_sz = _d3() + _d3()             # D3+D3 for GS diameter
            return Moon(size_code=gg_sz, is_gas_giant_moon=True)
    if sz == 0:
        return Moon(size_code=0, is_ring=True)
    # Clamp moon to be smaller than parent
    sz = min(sz, gg_diameter - 1)
    return Moon(size_code=max(1, sz))


# ---------------------------------------------------------------------------
# Twin/near-twin check (WBH p.57)
# ---------------------------------------------------------------------------

def _twin_check(moon: Moon, parent_size: int) -> Moon:
    """
    If a terrestrial moon's size is exactly parent_size - 2, roll 2D:
      2  → size becomes parent_size - 1
      12 → size becomes parent_size (twin world)
      else → unchanged
    """
    if moon.is_ring or moon.size_code == "S":
        return moon
    sz = int(moon.size_code)
    if sz == parent_size - 2:
        r = _roll(2)
        if r == 2:
            return Moon(size_code=parent_size - 1)
        if r == 12:
            return Moon(size_code=parent_size)
    return moon


# ---------------------------------------------------------------------------
# Ring consolidation
# ---------------------------------------------------------------------------

def _consolidate(moons: List[Moon]) -> List[Moon]:
    """
    Collapse multiple rings into a single R0# entry.
    Returns list with at most one ring entry (R0N).
    """
    rings = [m for m in moons if m.is_ring]
    others = [m for m in moons if not m.is_ring]
    if not rings:
        return others
    # Represent all rings as a single Moon with ring_count attribute
    ring_entry = Moon(size_code=0, is_ring=True)
    ring_entry.ring_count = len(rings)
    return [ring_entry] + others


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def place_moon_orbit(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    moon: Moon,
    parent_diameter_km: float,
    parent_mass_earth: float,
    parent_orbit_au: float,
    star_mass_solar: float,
    parent_ecc: float = 0.0,
) -> None:
    """Place a single moon's orbit around a parent body (mutates moon in-place).

    Sets orbit_pd, orbit_km, orbit_range, orbit_period_hours, orbit_eccentricity,
    and orbit_inclination using the same Hill sphere / MOR / PD-roll procedure as
    generate_moons().  No-op when parent data is zero or Moon Limit < 2 (no stable
    significant-moon orbit possible).
    """
    if parent_orbit_au <= 0.0 or star_mass_solar <= 0.0 or parent_diameter_km <= 0.0:
        return
    hill_au = _hill_sphere_au(parent_orbit_au, parent_ecc, parent_mass_earth, star_mass_solar)
    hill_pd = _hill_sphere_pd(hill_au, parent_diameter_km)
    ml      = _hill_moon_limit(hill_pd)
    if ml < 2:
        return
    mor = _moon_orbit_range(ml, 1)
    if mor <= 0:
        return
    pd, rng = _roll_moon_pd(mor)
    moon.orbit_pd           = pd
    moon.orbit_km           = round(pd * parent_diameter_km, 1)
    moon.orbit_range        = "excess" if pd > mor + 2 else rng
    moon.orbit_period_hours = _moon_period_hours(moon.orbit_km, parent_mass_earth)
    moon.orbit_eccentricity = roll_eccentricity(orbit_number=2.0, system_age_gyr=0.0, rng=_rng)
    moon.orbit_inclination  = roll_inclination(rng=_rng)


def generate_moons(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements
    size_code: int | str,
    orbit_number: float,
    is_gas_giant: bool = False,
    gg_category: str = "M",   # "S", "M", or "L"
    gg_diameter: int = 8,
    planet_diameter_km: float = 0.0,
    planet_mass_earth: float = 0.0,
    orbit_au: float = 0.0,
    star_mass_solar: float = 0.0,
    planet_ecc: float = 0.0,
    star_mao: float = 0.0,
    companion_exclusion_zones: list | None = None,
    is_adjacent_outermost_far: bool = False,
    rng: Optional[random.Random] = None,
) -> List[Moon]:
    """
    Generate all significant moons for a world.

    Parameters
    ----------
    size_code          : planet size (int 1-F, or "S" for size S terrestrial)
    orbit_number       : orbital Orbit# (used for DM check)
    is_gas_giant       : True if this is a gas giant
    gg_category        : "S", "M", or "L" — gas giant size category
    gg_diameter        : gas giant diameter in Terran diameters (for clamping)
    planet_diameter_km : planet diameter in km; 0 = estimate from size_code
    planet_mass_earth  : planet mass in Earth masses; 0 = estimate from size_code
    orbit_au           : planet orbit in AU; 0 = skip orbit placement
    star_mass_solar    : combined host-star mass in solar masses; 0 = skip orbit placement
    planet_ecc         : planet orbital eccentricity (for Hill sphere)

    Returns
    -------
    List of Moon objects, rings first then by size.
    Orbit fields (orbit_pd, orbit_km, …) are set when orbit_au and
    star_mass_solar are non-zero; otherwise they remain None.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    # Belts (size 0) are diffuse debris fields, not solid bodies.
    # The WBH moon rules apply to planets (solid bodies ≥ size S).
    # A belt cannot gravitationally retain significant moons.
    if not is_gas_giant and size_code != "S" and int(size_code) == 0:
        return []

    raw = _moon_quantity(size_code, orbit_number, is_gas_giant, gg_category,
                         star_mao=star_mao,
                         companion_exclusion_zones=companion_exclusion_zones,
                         is_adjacent_outermost_far=is_adjacent_outermost_far)

    moons: List[Moon] = []
    if raw < 0:
        pass  # no moons; moons stays []
    elif raw == 0:
        ring = Moon(size_code=0, is_ring=True)
        ring.ring_count = 1
        moons = [ring]
    else:
        for _ in range(raw):
            if is_gas_giant:
                m = _size_gg_moon(gg_diameter)
            else:
                sz = int(size_code) if size_code != "S" else 1
                m = _size_terrestrial_moon(sz)
                m = _twin_check(m, sz)
            moons.append(m)

    moons = _consolidate(moons)

    # Sort: rings first, then S, then numeric ascending
    def sort_key(m: Moon) -> tuple[int, int]:
        if m.is_ring:
            return (0, 0)
        if m.size_code == "S":
            return (1, 0)
        return (2, int(m.size_code))

    moons = sorted(moons, key=sort_key)

    # ── Orbit placement (WBH pp.74–77) ──────────────────────────────────────
    if orbit_au > 0.0 and star_mass_solar > 0.0:
        diam_km = planet_diameter_km or _estimate_diameter_km(size_code, is_gas_giant, gg_diameter)
        mass_e  = planet_mass_earth  or _estimate_mass_earth(size_code, is_gas_giant, gg_diameter)

        hill_au = _hill_sphere_au(orbit_au, planet_ecc, mass_e, star_mass_solar)
        hill_pd = _hill_sphere_pd(hill_au, diam_km)
        ml      = _hill_moon_limit(hill_pd)   # integer PD outer limit

        sig_moons = [m for m in moons if not m.is_ring]
        rings     = [m for m in moons if m.is_ring]

        # Moon removal (WBH p.75)
        if ml < 1:
            # Hill sphere too small for anything
            moons = []
        elif ml < 2:
            # Below the Roche limit — no significant moons; keep/create one ring
            if rings:
                moons = rings[:1]
            elif sig_moons:
                ring = Moon(size_code=0, is_ring=True)
                ring.ring_count = 1
                moons = [ring]
            else:
                moons = []
        else:
            # Normal orbit placement
            n_sig = len(sig_moons)
            mor   = _moon_orbit_range(ml, n_sig)

            if mor > 0 and n_sig > 0:
                _assign_sig_moon_orbits(sig_moons, mor, diam_km, mass_e)

            # Ring placement (WBH p.77)
            for ring in rings:
                ring.ring_centre_pd, ring.ring_span_pd = _place_ring(diam_km)

            # Eccentricity and inclination (WBH p.76)
            for m in sig_moons:
                m.orbit_eccentricity = roll_eccentricity(
                    orbit_number=2.0, system_age_gyr=0.0, rng=_rng,
                )
                m.orbit_inclination = roll_inclination(rng=_rng)

            # Perigee Roche limit check: r(perigee) = orbit_pd × (1 − e).
            # If perigee < 2 PD the moon will be tidally disrupted at closest
            # approach and must be converted to ring material.
            roche_victims = [
                m for m in sig_moons
                if m.orbit_pd is not None and m.orbit_pd * (1.0 - m.orbit_eccentricity) < 2.0
            ]
            if roche_victims:
                for m in roche_victims:
                    moons.remove(m)
                sig_moons = [m for m in sig_moons if m not in roche_victims]
                if rings:
                    rings[0].ring_count += len(roche_victims)
                else:
                    new_ring = Moon(size_code=0, is_ring=True)
                    new_ring.ring_count = len(roche_victims)
                    rings.append(new_ring)
                    moons.append(new_ring)

            moons = sorted(moons, key=sort_key)

    return moons


def moons_str(moons: List[Moon]) -> str:
    """Compact string representation of a moon list, e.g. 'R03, S, S, 2, 5'."""
    if not moons:
        return "—"
    parts = []
    for m in moons:
        if m.is_ring:
            count = m.ring_count
            parts.append(f"R{count:02d}")
        elif m.is_gas_giant_moon:
            parts.append(f"GS{_ehex(int(m.size_code))}")
        elif m.size_code == "S":
            parts.append("S")
        else:
            parts.append(_ehex(int(m.size_code)))
    return ", ".join(parts)
