"""
traveller_orbit_gen.py
======================
Planetary orbit generation for the Traveller RPG
(World Builder's Handbook, Sept 2023 edition).

Implements the world placement procedure from WBH pp.36-51:
  - World counts: gas giants (p.36), belts (p.36), terrestrials (p.37)
  - Minimum Allowable Orbit# (MAO) by star type/class (p.38)
  - Habitable Zone Centre Orbit# (HZCO) via sqrt(luminosity) (p.41)
  - Habitable zone breadth +/-1.0 Orbit# (p.42)
  - Baseline number and baseline Orbit# (Steps 3a/3b/3c, p.44-46)
  - Empty orbits (Step 4, p.47)
  - System spread and orbit slot placement (Steps 5-6, p.48-49)
  - World type placement in order: empty, gas giants, belts, terrestrials (p.51)
  - Mainworld candidate selection (p.51)

Implements anomalous orbits (Step 7, pp.49-50): random, eccentric, inclined,
retrograde, and trojan orbit types.

Implements orbital eccentricity (Step 9, p.27): eccentricity values for worlds,
belts, and companion stars when orbital_eccentricity=True is passed to
generate_orbits().

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
# pylint: disable=too-many-lines

from __future__ import annotations
import json
import math
import random
_rng: random.Random = random  # type: ignore[assignment]
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from .traveller_stellar_gen import Star, StarSystem, _orbit_to_au, ORBIT_AU
if TYPE_CHECKING:
    from .traveller_world_detail import WorldDetail


def roll(n: int, dm: int = 0) -> int:
    """Roll n six-sided dice and return the sum plus dm, minimum 0."""
    return max(0, sum(_rng.randint(1, 6) for _ in range(n)) + dm)


# ---------------------------------------------------------------------------
# MAO table (WBH p.38)
# ---------------------------------------------------------------------------
MAO_TABLE: Dict[Tuple[str, int, str], float] = {
    ("O",0,"Ia"):0.63, ("O",5,"Ia"):0.55,
    ("O",0,"Ib"):0.60, ("O",5,"Ib"):0.50,
    ("O",0,"II"):0.55, ("O",5,"II"):0.45,
    ("O",0,"III"):0.53,("O",5,"III"):0.38,
    ("O",0,"V"):0.50,  ("O",5,"V"):0.30,
    ("O",0,"VI"):0.01, ("O",5,"VI"):0.01,
    ("B",0,"Ia"):0.50, ("B",5,"Ia"):1.67,
    ("B",0,"Ib"):0.35, ("B",5,"Ib"):0.63,
    ("B",0,"II"):0.30, ("B",5,"II"):0.35,
    ("B",0,"III"):0.25,("B",5,"III"):0.15,
    ("B",0,"IV"):0.20, ("B",5,"IV"):0.13,
    ("B",0,"V"):0.18,  ("B",5,"V"):0.09,
    ("B",0,"VI"):0.01, ("B",5,"VI"):0.01,
    ("A",0,"Ia"):3.34, ("A",5,"Ia"):4.17,
    ("A",0,"Ib"):1.40, ("A",5,"Ib"):2.17,
    ("A",0,"II"):0.75, ("A",5,"II"):1.17,
    ("A",0,"III"):0.13,("A",5,"III"):0.13,
    ("A",0,"IV"):0.10, ("A",5,"IV"):0.07,
    ("A",0,"V"):0.06,  ("A",5,"V"):0.05,
    ("F",0,"Ia"):4.42, ("F",5,"Ia"):5.00,
    ("F",0,"Ib"):2.50, ("F",5,"Ib"):3.25,
    ("F",0,"II"):1.33, ("F",5,"II"):1.87,
    ("F",0,"III"):0.13,("F",5,"III"):0.13,
    ("F",0,"IV"):0.07, ("F",5,"IV"):0.06,
    ("F",0,"V"):0.04,  ("F",5,"V"):0.03,
    ("G",0,"Ia"):5.21, ("G",5,"Ia"):5.34,
    ("G",0,"Ib"):3.59, ("G",5,"Ib"):3.84,
    ("G",0,"II"):2.24, ("G",5,"II"):2.67,
    ("G",0,"III"):0.25,("G",5,"III"):0.38,
    ("G",0,"IV"):0.07, ("G",5,"IV"):0.10,
    ("G",0,"V"):0.03,  ("G",5,"V"):0.02,
    ("G",0,"VI"):0.02, ("G",5,"VI"):0.02,
    ("K",0,"Ia"):5.59, ("K",5,"Ia"):6.17,
    ("K",0,"Ib"):4.17, ("K",5,"Ib"):4.84,
    ("K",0,"II"):3.17, ("K",5,"II"):4.00,
    ("K",0,"III"):0.50,("K",5,"III"):1.00,
    ("K",0,"V"):0.02,  ("K",5,"V"):0.02,
    ("K",0,"VI"):0.02, ("K",5,"VI"):0.01,
    ("M",0,"Ia"):6.80, ("M",5,"Ia"):7.20, ("M",9,"Ia"):7.80,
    ("M",0,"Ib"):5.42, ("M",5,"Ib"):6.17, ("M",9,"Ib"):6.59,
    ("M",0,"II"):4.59, ("M",5,"II"):5.30, ("M",9,"II"):5.92,
    ("M",0,"III"):1.68,("M",5,"III"):3.00,("M",9,"III"):4.34,
    ("M",0,"V"):0.02,  ("M",5,"V"):0.01,  ("M",9,"V"):0.01,
    ("M",0,"VI"):0.01, ("M",5,"VI"):0.01, ("M",9,"VI"):0.01,
}


def _interp(
    spectral: str,
    subtype: int,
    lum_class: str,
    table: Dict[Tuple[str, int, str], float],
) -> float:
    anchors = [0,5,9] if spectral == "M" else [0,5]
    for i in range(len(anchors)-1):
        lo, hi = anchors[i], anchors[i+1]
        if lo <= subtype <= hi:
            vlo = table.get((spectral, lo, lum_class))
            vhi = table.get((spectral, hi, lum_class))
            if vlo is not None and vhi is not None:
                return vlo + (vhi - vlo) * (subtype - lo) / (hi - lo)
            break
    for a in [0, 5, 9]:
        v = table.get((spectral, a, lum_class))
        if v is not None:
            return v
    return 0.02


def get_mao(star: Star) -> float:
    """Return the Minimum Allowable Orbit# for this star (WBH p.38)."""
    if star.spectral_type in ("D","BD"):
        return 0.01
    st = star.subtype if star.subtype is not None else 0
    return _interp(star.spectral_type, st, star.lum_class, MAO_TABLE)


def _au_to_orbit(au: float) -> float:
    keys = sorted(ORBIT_AU.keys())
    vals = [ORBIT_AU[k] for k in keys]
    if au <= vals[0]:
        return float(keys[0])
    if au >= vals[-1]:
        return float(keys[-1])
    for i in range(len(vals)-1):
        if vals[i] <= au <= vals[i+1]:
            frac = (au - vals[i]) / (vals[i+1] - vals[i])
            return keys[i] + (keys[i+1] - keys[i]) * frac
    return float(keys[-1])


def get_hzco(star: Star, combined_lum: Optional[float] = None) -> float:
    """Return the Habitable Zone Centre Orbit# for this star (WBH p.42)."""
    lum = combined_lum if combined_lum is not None else star.luminosity
    hzco_au = math.sqrt(max(lum, 1e-10))
    return _au_to_orbit(hzco_au)


def _temp_zone(deviation: float, hzco: float, orbit: float) -> str:  # pylint: disable=unused-argument
    """Map HZ deviation to temperature zone string."""
    if deviation >= 1.0:
        return "frozen"
    if deviation >= 0.2:
        return "cold"
    if deviation >= -0.2:
        return "temperate"
    if deviation >= -1.0:
        return "hot"
    return "boiling"


_GG_EHEX = "0123456789ABCDEFGHIJ"


def _gg_sah_roll(spectral: str, lum_class: str) -> str:
    """Roll gas giant SAH (WBH p.55): GS#, GM#, or GL# with a hex diameter digit."""
    dm = 0
    if spectral == "BD" or lum_class == "VI" or (spectral == "M" and lum_class == "V"):
        dm = -1
    cat = _rng.randint(1, 6) + dm
    if cat <= 2:
        d3a = (_rng.randint(1, 6) + 1) // 2
        d3b = (_rng.randint(1, 6) + 1) // 2
        diameter = d3a + d3b            # 2-6
        return f"GS{_GG_EHEX[min(diameter, len(_GG_EHEX)-1)]}"
    if cat <= 4:
        diameter = _rng.randint(1, 6) + 6  # 7-12
        return f"GM{_GG_EHEX[min(diameter, len(_GG_EHEX)-1)]}"
    # WBH p.55 GL: 2D+6 → 8-18
    diameter = _rng.randint(1, 6) + _rng.randint(1, 6) + 6
    return f"GL{_GG_EHEX[min(diameter, len(_GG_EHEX)-1)]}"


def _roll_gg_mass(gg_category: str) -> float:
    """Roll gas giant mass per WBH third roll table (M⊕).

    GS: 5 × (1D+1)           →  10–35 M⊕
    GM: 20 × (3D−1)           →  40–340 M⊕
    GL: D3 × 50 × (3D+4)      → 350–3,300 M⊕
    """
    if gg_category == "GS":
        return float(5 * (_rng.randint(1, 6) + 1))
    if gg_category == "GM":
        return float(20 * (roll(3) - 1))
    # GL
    return float(_rng.randint(1, 3) * 50 * (roll(3) + 4))


# Eccentricity Values table (WBH p.27): (max_first_roll, base, n_dice, divisor)
# The sentinel value 99 in the last row catches all results of 12+.
_ECC_TABLE = [
    (5,  -0.001, 1, 1000),
    (7,   0.000, 1,  200),
    (9,   0.030, 1,  100),
    (10,  0.050, 1,   20),
    (11,  0.050, 2,   20),
    (99,  0.300, 2,   20),
]

# DMs applied to the first roll of _roll_eccentricity() for anomalous orbit
# types (WBH pp.49-50). Trojan types are absent — no DM specified.
_ANOM_ECC_DM: dict = {
    "random":     2,
    "eccentric":  5,
    "inclined":   2,
    "retrograde": 2,
}


def roll_eccentricity(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        orbit_number: float, system_age_gyr: float,
        extra_stars: int = 0,
        is_belt: bool = False,
        is_star: bool = False,
        anomaly_dm: int = 0,
        rng: Optional[random.Random] = None) -> float:
    """Roll orbital eccentricity per WBH p.27 Eccentricity Values table."""
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    dm = 2 if is_star else 0
    dm += extra_stars
    dm += anomaly_dm
    if orbit_number < 1.0 < system_age_gyr:
        dm -= 1
    if is_belt:
        dm += 1
    first = roll(2, dm)
    for max_roll, base, n_dice, divisor in _ECC_TABLE:
        if first <= max_roll:
            second = roll(n_dice) / divisor
            return min(0.999, max(0.0, base + second))
    return 0.0  # unreachable; satisfies type checker


def roll_inclination(rng: Optional[random.Random] = None) -> float:  # pylint: disable=too-many-return-statements
    """Roll orbital inclination per WBH p.28 Inclination table."""
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    first = roll(2)
    if first <= 6:
        return _rng.randint(1, 6) / 2                                    # Very Low: 0.5–3°
    if first == 7:
        return float(_rng.randint(1, 6))                                 # Low: 1–6°
    if first == 8:
        return float(roll(2))                                              # Moderate: 2–12°
    if first == 9:
        return float(roll(2) * 3 + _rng.randint(1, 6))                  # High: 7–42°
    if first == 10:
        return float((_rng.randint(1, 6) + 1) * 5 + _rng.randint(1, 6))  # Very High: 11–41°
    if first == 11:
        return float(roll(3) * 5 - _rng.randint(1, 6))                  # Extreme: 9–89°
    return max(0.0, 180.0 - roll_inclination())                           # Retrograde: 12


@dataclass
class OrbitSlot:  # pylint: disable=too-many-instance-attributes
    """One orbit slot in a star system, with world type and zone data."""

    star_designation: str
    orbit_number: float
    orbit_au: float
    slot_index: int
    world_type: str
    is_habitable_zone: bool
    hz_deviation: float
    temperature_zone: str
    is_mainworld_candidate: bool = False
    notes: str = ""
    canonical_profile: str = ""  # UWP set when mainworld comes from canonical data
    gg_sah: str = ""             # gas giant SAH rolled at orbit gen time (e.g. "GM9")
    anomaly_type: str = ""       # ""|"random"|"eccentric"|"inclined"|"retrograde"
                                 # |"trojan_leading"|"trojan_trailing"
    orbit_period_yr: Optional[float] = field(default=None, init=False)
    eccentricity: float = field(default=0.0, init=False)
    inclination: float = field(default=0.0, init=False)
    gg_mass_earth: Optional[float] = field(default=None, init=False)
    name: str = field(default="", init=False)  # set by attach_body_names()
    detail: Optional["WorldDetail"] = field(default=None, init=False)

    def to_dict(self) -> dict:
        """Serialise this orbit slot to a JSON-compatible dict."""
        d = {
            "star": self.star_designation,
            "orbit_number": round(self.orbit_number, 2),
            "orbit_au": round(self.orbit_au, 3),
            "slot_index": self.slot_index,
            "world_type": self.world_type,
            "is_habitable_zone": self.is_habitable_zone,
            "hz_deviation": round(self.hz_deviation, 2),
            "temperature_zone": self.temperature_zone,
            "is_mainworld_candidate": self.is_mainworld_candidate,
            "notes": self.notes,
        }
        if self.canonical_profile:
            d["canonical_profile"] = self.canonical_profile
        if self.gg_sah:
            d["gg_sah"] = self.gg_sah
        if self.gg_mass_earth is not None:
            d["gg_mass_earth"] = self.gg_mass_earth
        if self.anomaly_type:
            d["anomaly_type"] = self.anomaly_type
        if self.orbit_period_yr is not None:
            d["orbit_period_yr"] = self.orbit_period_yr
        if self.eccentricity > 0:
            d["eccentricity"] = round(self.eccentricity, 4)
            d["orbit_au_min"] = round(self.orbit_au * (1 - self.eccentricity), 3)
            d["orbit_au_max"] = round(self.orbit_au * (1 + self.eccentricity), 3)
        if self.inclination > 0:
            d["inclination"] = round(self.inclination, 2)
        if self.name:
            d["name"] = self.name
        # Include secondary world / satellite detail if attach_detail() has run
        if self.detail is not None:
            d["detail"] = self.detail.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "OrbitSlot":
        """Reconstruct an OrbitSlot from a dict produced by to_dict().

        detail is left as None — WorldDetail reconstruction is out of scope.
        """
        slot = cls(
            star_designation=str(d["star"]),
            orbit_number=float(d["orbit_number"]),
            orbit_au=float(d["orbit_au"]),
            slot_index=int(d["slot_index"]),
            world_type=str(d["world_type"]),
            is_habitable_zone=bool(d.get("is_habitable_zone", False)),
            hz_deviation=float(d.get("hz_deviation", 0.0)),
            temperature_zone=str(d.get("temperature_zone", "temperate")),
            is_mainworld_candidate=bool(d.get("is_mainworld_candidate", False)),
            notes=str(d.get("notes", "")),
            canonical_profile=str(d.get("canonical_profile", "")),
            gg_sah=str(d.get("gg_sah", "")),
            anomaly_type=str(d.get("anomaly_type", "")),
        )
        slot.orbit_period_yr = d.get("orbit_period_yr")
        slot.eccentricity = float(d.get("eccentricity", 0.0))
        slot.inclination = float(d.get("inclination", 0.0))
        slot.gg_mass_earth = float(d["gg_mass_earth"]) if "gg_mass_earth" in d else None
        slot.name = str(d.get("name", ""))
        detail_d = d.get("detail")
        if detail_d:
            from .traveller_world_detail import WorldDetail  # pylint: disable=import-outside-toplevel
            slot.detail = WorldDetail.from_dict(detail_d)
        return slot


@dataclass
class SystemOrbits:  # pylint: disable=too-many-instance-attributes
    """All orbit slots for a star system, with world counts and zone data."""

    stellar_system: StarSystem
    gas_giant_count: int = 0
    belt_count: int = 0
    terrestrial_count: int = 0
    total_worlds: int = 0
    empty_orbits: int = 0
    orbits: List[OrbitSlot] = field(default_factory=list)
    mainworld_orbit: Optional[OrbitSlot] = None
    star_mao: Dict[str, float] = field(default_factory=dict)
    star_hzco: Dict[str, float] = field(default_factory=dict)
    star_hz_inner: Dict[str, float] = field(default_factory=dict)
    star_hz_outer: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise this system's orbits to a JSON-compatible dict."""
        return {
            "gas_giant_count": self.gas_giant_count,
            "belt_count": self.belt_count,
            "terrestrial_count": self.terrestrial_count,
            "total_worlds": self.total_worlds,
            "empty_orbits": self.empty_orbits,
            "star_zones": {
                d: {
                    "mao": round(self.star_mao.get(d,0),2),
                    "hzco": round(self.star_hzco.get(d,0),2),
                    "hz_inner": round(self.star_hz_inner.get(d,0),2),
                    "hz_outer": round(self.star_hz_outer.get(d,0),2),
                } for d in self.star_mao
            },
            "orbits": [o.to_dict() for o in self.orbits],
            "mainworld_orbit": self.mainworld_orbit.to_dict() if self.mainworld_orbit else None,
        }

    def to_json(self, indent=2):
        """Serialise this system's orbits to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: dict, star_system: StarSystem) -> "SystemOrbits":
        """Reconstruct a SystemOrbits from a dict produced by to_dict()."""
        orbits = [OrbitSlot.from_dict(o) for o in d.get("orbits", [])]
        mw_d = d.get("mainworld_orbit")
        mainworld_orbit = OrbitSlot.from_dict(mw_d) if mw_d else None
        zones = d.get("star_zones", {})
        return cls(
            stellar_system=star_system,
            gas_giant_count=int(d.get("gas_giant_count", 0)),
            belt_count=int(d.get("belt_count", 0)),
            terrestrial_count=int(d.get("terrestrial_count", 0)),
            total_worlds=int(d.get("total_worlds", 0)),
            empty_orbits=int(d.get("empty_orbits", 0)),
            orbits=orbits,
            mainworld_orbit=mainworld_orbit,
            star_mao={k: float(v["mao"]) for k, v in zones.items()},
            star_hzco={k: float(v["hzco"]) for k, v in zones.items()},
            star_hz_inner={k: float(v["hz_inner"]) for k, v in zones.items()},
            star_hz_outer={k: float(v["hz_outer"]) for k, v in zones.items()},
        )

    def summary(self) -> str:  # pylint: disable=too-many-locals,too-many-branches
        """
        Human-readable orbital summary.

        If attach_detail() has been called on the parent TravellerSystem,
        each orbit line will include its secondary world profile and any
        significant moons.  Without detail attached, only world type and
        zone are shown.
        """
        lines = ["=" * 88]
        lines.append(
            f"  Orbits: {self.total_worlds} worlds  "
            f"({self.gas_giant_count} GG, {self.belt_count} belts, "
            f"{self.terrestrial_count} terrestrial, {self.empty_orbits} empty slots)"
        )
        lines.append("=" * 88)
        for d, mao in self.star_mao.items():
            hzco = self.star_hzco.get(d, 0)
            inner = self.star_hz_inner.get(d, 0)
            outer = self.star_hz_outer.get(d, 0)
            lines.append(
                f"  Star {d}  MAO={mao:.2f}  HZCO={hzco:.2f}  "
                f"HZ {inner:.2f}–{outer:.2f}"
            )
        lines.append("-" * 88)
        lines.append(
            f"  {'Star':<5} {'#':<4} {'Orbit#':<8} {'AU':<9} "
            f"{'Type':<14} {'Profile':<20} {'Zone':<12} Notes"
        )
        lines.append("  " + "-" * 82)
        for o in self.orbits:
            hz   = "★" if o.is_habitable_zone else " "
            if o.is_mainworld_candidate:
                mw = "  ← mainworld"
            elif o.anomaly_type and o.notes:
                mw = f"  [{o.notes}]"
            else:
                mw = ""
            detail = o.detail
            if o.canonical_profile:
                profile = o.canonical_profile
            elif detail is not None:
                profile = detail.profile
            elif o.world_type == "empty":
                profile = "—"
            else:
                profile = "—"
            lines.append(
                f"  {o.star_designation:<5} {o.slot_index:<4} "
                f"{o.orbit_number:<8.2f} {o.orbit_au:<9.3f} "
                f"{o.world_type:<14} {profile:<20} "
                f"{o.temperature_zone:<12}{hz}{mw}"
            )
            # Moon sub-rows when detail is attached
            if detail is not None:
                for mi, moon in enumerate(detail.moons or [], 1):
                    if moon.is_ring:
                        rc = moon.ring_count
                        mp = f"R{rc:02d}"
                        ms = "ring system"
                    elif moon.detail is not None:
                        mp = moon.detail.profile
                        ms = f"size {moon.size_str}"
                    else:
                        mp = f"size {moon.size_str}"
                        ms = ""
                    lines.append(
                        f"  {'':5} {'':4} {'':8} {'':9} "
                        f"  {'moon '+str(mi):<12} {mp:<20} {'':12}  {ms}"
                    )
        lines.append("=" * 88)
        if self.mainworld_orbit:
            mw = self.mainworld_orbit
            lines.append(
                f"  Mainworld: Star {mw.star_designation}  "
                f"Orbit# {mw.orbit_number:.2f} ({mw.orbit_au:.3f} AU)  "
                f"{mw.temperature_zone.title()}  {mw.world_type}"
            )
            lines.append("=" * 88)
        return "\n".join(lines)


def generate_orbits(system: StarSystem,  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
                    orbital_eccentricity: bool = False,
                    orbital_inclination: bool = False,
                    rng: Optional[random.Random] = None) -> SystemOrbits:
    """Generate all orbit slots for a star system (WBH pp.36-51)."""
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    result = SystemOrbits(stellar_system=system)
    primary_stars = [s for s in system.stars if s.role != "companion"]
    has_companion = any(s.role == "companion" for s in system.stars)
    secondary_count = sum(1 for s in primary_stars if s.role != "primary")
    # World counts (WBH p.36-37)
    if roll(2) <= 9:
        r = roll(2)
        gg = 1 if r<=4 else 2 if r<=6 else 3 if r<=8 else 4 if r<=11 else 5 if r==12 else 6
    else:
        gg = 0
    belts = 0
    if roll(2) >= 8:
        r = roll(2, 1 if gg>0 else 0)
        belts = 1 if r<=6 else 2 if r<=11 else 3
    tp = max(1, roll(2) - 2)
    result.gas_giant_count = gg
    result.belt_count = belts
    result.terrestrial_count = tp
    result.total_worlds = gg + belts + tp

    # Empty orbits (WBH p.47)
    er = roll(2)
    empty = 0 if er<=9 else er-9
    result.empty_orbits = empty

    # MAO and HZCO per star
    star_hzco:  Dict[str, float] = {}
    star_mao:   Dict[str, float] = {}
    star_avail: Dict[str, Tuple[float,float]] = {}
    star_outer: Dict[str, Tuple[float,float]] = {}   # outer zone beyond companion excl.

    for star in primary_stars:
        mao = get_mao(star)
        comp_lum = sum(
            s.luminosity for s in system.stars
            if s.role == "companion" and s.designation.startswith(star.designation)
            and s.designation != star.designation
        )
        hzco = get_hzco(star, star.luminosity + comp_lum)
        star_mao[star.designation] = mao
        star_hzco[star.designation] = hzco

        # Available orbit range — table ends at orbit# 17 (8512 AU)
        max_o = 17.0
        outer_lo = mao   # accumulates max(companion+3) for companions with valid inner zone
        has_outer = False
        if star.role == "primary":
            for other in primary_stars:
                if other.role in ("close","near","far") and other.orbit_number:
                    excl = other.orbit_number - 1.0
                    if excl > mao:
                        max_o = min(max_o, excl)
                        outer_lo = max(outer_lo, other.orbit_number + 3.0)
                        has_outer = True
                    else:
                        # Companion orbit is inside MAO+1: no inner zone exists.
                        # Push MAO past the outer exclusion boundary (WBH: companion+3).
                        mao = max(mao, other.orbit_number + 3.0)
                        star_mao[star.designation] = mao
        elif star.role in ("close","near","far") and star.orbit_number:
            max_o = max(mao+0.1, star.orbit_number - 3.0)
        elif star.role == "companion":
            max_o = 0.65

        if has_outer and outer_lo < 17.0:
            star_outer[star.designation] = (outer_lo, 17.0)

        star_avail[star.designation] = (mao, max_o)
        result.star_mao[star.designation] = mao
        result.star_hzco[star.designation] = hzco
        result.star_hz_inner[star.designation] = max(mao, hzco - 1.0)
        result.star_hz_outer[star.designation] = min(max_o, hzco + 1.0)

    # Allocate worlds to stars proportionally by available orbit range
    if len(primary_stars) == 1:
        alloc = {primary_stars[0].designation: result.total_worlds}
    else:
        def _avail_range(s: Star) -> float:
            des = s.designation
            inner = max(0.0, star_avail[des][1] - star_avail[des][0])
            oz = star_outer.get(des)
            return inner + (max(0.0, oz[1] - oz[0]) if oz else 0.0)

        total_range = sum(_avail_range(s) for s in primary_stars)
        alloc: Dict[str, int] = {}
        remaining = result.total_worlds
        for i, star in enumerate(primary_stars):
            if i == len(primary_stars)-1:
                alloc[star.designation] = remaining
            else:
                star_rng = _avail_range(star)
                n = round(result.total_worlds * star_rng / max(total_range, 0.01))
                n = max(0, min(n, remaining))
                alloc[star.designation] = n
                remaining -= n

    # World type pool
    pool = ["gas_giant"]*gg + ["belt"]*belts + ["terrestrial"]*tp
    _rng.shuffle(pool)
    pool_idx = 0

    for star in primary_stars:
        d = star.designation
        n_worlds_total = alloc.get(d, 0)
        n_empty_here   = empty if star == primary_stars[0] else 0

        # Split worlds between inner zone and outer zone (if one exists)
        if d in star_outer:
            mao_i, max_o_i = star_avail[d]
            mao_o, max_o_o = star_outer[d]
            inner_rng = max(0.0, max_o_i - mao_i)
            outer_rng = max(0.0, max_o_o - mao_o)
            total_rng  = max(inner_rng + outer_rng, 0.01)
            inner_n    = round(n_worlds_total * inner_rng / total_rng)
            inner_n    = max(0, min(inner_n, n_worlds_total))
            outer_n    = n_worlds_total - inner_n
            zones = [
                (mao_i, max_o_i, inner_n, n_empty_here),
                (mao_o, max_o_o, outer_n, 0),
            ]
        else:
            mao_i, max_o_i = star_avail[d]
            zones = [(mao_i, max_o_i, n_worlds_total, n_empty_here)]

        hzco         = star_hzco[d]
        n_total_stars = len(primary_stars)
        slot_counter  = 0  # continuous per-star index across inner/outer zones

        for zone_mao, zone_max_o, zone_n, zone_empty in zones:
            total_slots = zone_n + zone_empty
            if total_slots <= 0:
                continue

            # Baseline number (WBH p.44)
            bn_dm = 0
            if has_companion:
                bn_dm -= 2
            if star.lum_class in ("Ia","Ib","II"):
                bn_dm += 3
            elif star.lum_class == "III":
                bn_dm += 2
            elif star.lum_class == "IV":
                bn_dm += 1
            elif star.lum_class == "VI":
                bn_dm -= 1
            bn_dm -= secondary_count
            tw = result.total_worlds
            if tw < 6:
                bn_dm -= 4
            elif tw <= 9:
                bn_dm -= 3
            elif tw <= 12:
                bn_dm -= 2
            elif tw <= 15:
                bn_dm -= 1
            elif tw >= 18:
                bn_dm += 1
            baseline_num = max(0, roll(2, bn_dm))

            # Baseline Orbit# (WBH p.44-46)
            vs = 0.1 if hzco >= 1.0 else 0.01
            if 1 <= baseline_num <= total_slots:
                # Step 3a: baseline world is in the habitable zone
                var = (roll(2)-7) * vs
                baseline_orbit = max(zone_mao, hzco + var)
            elif baseline_num < 1:
                # Step 3b: cold system — all worlds are beyond the HZCO.
                # WBH p.45: Baseline Orbit# = HZCO − baseline_number + Total Worlds + (2D-7)/10
                # baseline_number is ≤0 so subtracting it adds its absolute value.
                # Total Worlds is added as whole Orbit#s (no 0.1 multiplier) to push
                # the baseline — and therefore the innermost world — well outside the HZ.
                anchor = max(zone_mao, hzco)
                if anchor >= 1.0:
                    var = (roll(2)-7) / 10.0
                    # FIX: add total_worlds as whole Orbit#s, not total_slots*0.1
                    baseline_orbit = anchor + abs(baseline_num) + zone_n + var
                else:
                    # Sub-Orbit#1 HZCO: use 1/10 scaling throughout (WBH p.45)
                    var = (roll(2)-2) / 100.0
                    baseline_orbit = anchor + abs(baseline_num)/10.0 + zone_n/10.0 + var
                baseline_orbit = max(zone_mao, baseline_orbit)
                baseline_num = 1
            else:
                # Step 3c: hot system — all worlds are inside the HZCO
                inner = hzco - baseline_num + total_slots
                if inner < 1.0 or hzco < 1.0:
                    var = (roll(2)-7) / 100.0
                    baseline_orbit = hzco - baseline_num/10.0 + total_slots/10.0 + var
                else:
                    var = (roll(2)-7) * vs
                    baseline_orbit = inner + var
                baseline_orbit = max(zone_mao, min(baseline_orbit, hzco - 0.01))
                baseline_num = total_slots

            baseline_orbit = max(zone_mao, min(baseline_orbit, zone_max_o - 0.01))

            # Spread (WBH p.48)
            # Formula: Spread = (Baseline Orbit# - MAO) / Baseline Number
            spread = (baseline_orbit - zone_mao) / max(1, baseline_num)
            # Maximum Spread = Primary's Available Orbits / (All Slots + Total Stars)
            # Denominator uses total_slots (worlds + empty) so every slot gets a
            # spread unit, preventing outer slots from piling up at the ceiling.
            avail = zone_max_o - zone_mao
            max_spread = avail / max(total_slots + n_total_stars, 1)
            # Minimum spread: when baseline_num is large the formula above collapses
            # to HZCO/total_slots (~0.4 for a G star with 8 worlds), pinning all
            # slots near the inner system.  Enforce a floor so worlds span at least
            # half the available range.
            min_spread = avail / max(total_slots * 2, 1)
            spread = max(min_spread, min(spread, max_spread))
            spread = min(spread, max_spread)
            spread = max(0.01, spread)

            # Place slots (WBH p.48-49)
            # Inner Slot Orbit# = (MAO + Spread) + (2D-7) × Spread/10
            # Each subsequent slot: Previous + Spread + (2D-7) × Spread/10
            slots: List[float] = []
            current = zone_mao + spread + (roll(2)-7)*0.1*spread
            current = max(zone_mao, current)
            for _ in range(total_slots):
                current = max(zone_mao, min(current, zone_max_o))
                # Additive gap check (was multiplicative `* 1.1`, which triggered
                # constantly once orbit# exceeded spread/0.1 and halved every step).
                if slots and current - slots[-1] < spread * 0.4:
                    current = min(slots[-1] + spread * 0.5, zone_max_o)
                # Stop if we cannot advance past the last slot (at ceiling)
                if slots and round(current, 2) == round(slots[-1], 2):
                    break
                slots.append(round(current, 2))
                current += spread + (roll(2)-7)*0.1*spread

            # Assign world types — pool_idx shared across all zones
            empty_set = set(_rng.sample(range(len(slots)), min(zone_empty, len(slots))))
            for si, on in enumerate(slots):
                au = _orbit_to_au(on)
                dev = on - hzco
                in_hz = abs(dev) <= 1.0
                tz = _temp_zone(dev, hzco, on)
                if si in empty_set:
                    wtype = "empty"
                elif pool_idx < len(pool):
                    wtype = pool[pool_idx]
                    pool_idx += 1
                else:
                    wtype = "terrestrial"
                slot_gg_sah = (
                    _gg_sah_roll(star.spectral_type, star.lum_class)
                    if wtype == "gas_giant" else ""
                )
                slot_gg_mass = (
                    _roll_gg_mass(slot_gg_sah[:2])
                    if slot_gg_sah else None
                )
                slot_counter += 1
                result.orbits.append(OrbitSlot(
                    star_designation=d, orbit_number=on, orbit_au=au,
                    slot_index=slot_counter, world_type=wtype,
                    is_habitable_zone=in_hz, hz_deviation=round(dev,3),
                    temperature_zone=tz, gg_sah=slot_gg_sah,
                ))
                result.orbits[-1].gg_mass_earth = slot_gg_mass

    result.orbits.sort(key=lambda o: (o.star_designation, o.orbit_au))

    # Recount from what was actually placed — early breaks or pool exhaustion
    # can leave metadata counts from the initial dice rolls out of sync.
    result.gas_giant_count   = sum(1 for o in result.orbits if o.world_type == "gas_giant")
    result.belt_count        = sum(1 for o in result.orbits if o.world_type == "belt")
    result.terrestrial_count = sum(1 for o in result.orbits if o.world_type == "terrestrial")
    result.total_worlds      = (result.gas_giant_count
                                + result.belt_count
                                + result.terrestrial_count)

    # ── Step 7: Anomalous orbits (WBH pp.49-50) ─────────────────────────────
    # Roll 2D: ≤9 → 0, 10 → 1, 11 → 2, 12 → 3 anomalous orbits.
    # Each anomalous orbit adds 1 terrestrial (or belt when tp already at 13).
    anom_count = max(0, roll(2) - 9)
    if anom_count > 0:
        eligible = [
            s for s in primary_stars
            if star_avail.get(s.designation, (0.0, 0.0))[1]
               > star_avail.get(s.designation, (0.0, 0.0))[0]
        ]
        for _ in range(anom_count):
            if not eligible:
                break
            anom_star = _rng.choice(eligible) if len(eligible) > 1 else eligible[0]
            anom_d = anom_star.designation
            a_hzco = star_hzco.get(anom_d, 0.0)

            anom_wtype = "belt" if result.terrestrial_count >= 13 else "terrestrial"

            atype_r = roll(2)
            if atype_r <= 7:
                anom_type = "random"
            elif atype_r == 8:
                anom_type = "eccentric"
            elif atype_r == 9:
                anom_type = "inclined"
            elif atype_r <= 11:
                anom_type = "retrograde"
            else:
                anom_type = "trojan"

            anom_on    = None
            anom_notes = ""

            if anom_type == "trojan":
                host_slots = [
                    o for o in result.orbits
                    if o.star_designation == anom_d and o.world_type != "empty"
                ]
                if not host_slots:
                    anom_type = "random"
                else:
                    host = _rng.choice(host_slots)
                    anom_on = host.orbit_number
                    pos = "leading" if roll(1) <= 3 else "trailing"
                    anom_type = f"trojan_{pos}"
                    anom_notes = f"Trojan {pos} (L{'4' if pos == 'leading' else '5'})"

            if anom_on is None:
                # 2D-2 + d10 fractional, clamped within the star's valid zone.
                # Use star_avail / star_outer to respect companion exclusion bands.
                # Add ±0.01 clearance so the orbit never lands exactly on a zone
                # boundary (which coincides with the exclusion band edge).
                z_lo, z_hi = star_avail[anom_d]
                oz = star_outer.get(anom_d)
                if oz and roll(1) >= 4:   # 50/50 inner vs outer zone
                    z_lo, z_hi = oz
                z_lo = z_lo + 0.01
                z_hi = min(z_hi, 20.0) - 0.01
                if z_lo > z_hi:
                    z_lo = z_hi = round((z_lo + z_hi) / 2.0, 2)
                existing = {
                    round(o.orbit_number, 2)
                    for o in result.orbits if o.star_designation == anom_d
                }
                candidate = z_lo
                for _attempt in range(4):
                    candidate = max(
                        z_lo,
                        min(roll(2, -2) + _rng.randint(0, 9) / 10.0, z_hi),
                    )
                    if round(candidate, 2) not in existing:
                        break
                    adj = roll(1) * _rng.choice((-1, 1))
                    candidate = max(z_lo, min(candidate + adj, z_hi))
                anom_on = round(candidate, 2)

            if anom_type == "inclined":
                inc_deg = (roll(1, 2)) * 10 + _rng.randint(0, 9)
                anom_notes = f"Inclined {inc_deg}°"
            elif anom_type == "retrograde":
                anom_notes = "Retrograde"
            elif anom_type == "eccentric":
                anom_notes = "Eccentric"
            elif anom_type == "random":
                anom_notes = "Random orbit"

            anom_au  = _orbit_to_au(anom_on)
            anom_dev = round(anom_on - a_hzco, 3)

            result.orbits.append(OrbitSlot(
                star_designation=anom_d,
                orbit_number=anom_on,
                orbit_au=anom_au,
                slot_index=0,
                world_type=anom_wtype,
                is_habitable_zone=abs(anom_dev) <= 1.0,
                hz_deviation=anom_dev,
                temperature_zone=_temp_zone(anom_dev, a_hzco, anom_on),
                anomaly_type=anom_type,
                notes=anom_notes,
            ))
            if anom_wtype == "belt":
                result.belt_count += 1
            else:
                result.terrestrial_count += 1
            result.total_worlds += 1

        result.orbits.sort(key=lambda o: (o.star_designation, o.orbit_au))

    # Mainworld selection (WBH p.51)
    candidates = [o for o in result.orbits if o.world_type != "empty"]
    if candidates:
        pd = system.primary.designation

        def score(o):
            ts = 0 if o.world_type == "terrestrial" else 2
            hs = 0 if o.is_habitable_zone else 5
            tp_s = {"temperate":0,"cold":1,"hot":1,"frozen":3,"boiling":4}.get(o.temperature_zone,5)
            ps = 0 if o.star_designation == pd else 1
            return (ts+hs+tp_s+ps, abs(o.hz_deviation))

        best = min(candidates, key=score)
        best.is_mainworld_candidate = True
        result.mainworld_orbit = best
        notes = []
        if best.is_habitable_zone:
            notes.append("in HZ")
        if best.hz_deviation < -0.5:
            notes.append("warm side")
        elif best.hz_deviation > 0.5:
            notes.append("cool side")
        best.notes = ", ".join(notes)

    # Compute world orbital periods: P (yr) = sqrt(AU³ / M_central)
    # M_central = designated star mass + companions whose orbit_au < world orbit_au.
    # Planet mass correction (WBH: mE × 0.000003) is negligible for standard worlds
    # and is omitted here.
    _stars_by_d = {s.designation: s for s in system.stars}
    _comp_by_parent: Dict[str, List[Star]] = {}
    for _s in system.stars:
        if _s.role == "companion":
            _comp_by_parent.setdefault(_s.designation[:-1], []).append(_s)

    for o in result.orbits:
        _star = _stars_by_d.get(o.star_designation)
        if _star is None or o.orbit_au <= 0:
            continue
        _mc = _star.mass
        for _comp in _comp_by_parent.get(o.star_designation, []):
            if _comp.orbit_au is not None and _comp.orbit_au < o.orbit_au:
                _mc += _comp.mass
        if _mc > 0:
            o.orbit_period_yr = round(math.sqrt(o.orbit_au ** 3 / _mc), 4)

    # ── Orbital eccentricity (WBH p.27) — only when flag is set ──────────────
    if orbital_eccentricity:
        age = system.stars[0].age_gyr or 0.0
        primary_desig = system.stars[0].designation

        for o in result.orbits:
            if o.world_type == "empty":
                continue
            extra = sum(
                1 for s in system.stars
                if s.role in ("close", "near", "far")
                and s.orbit_number is not None
                and o.star_designation == primary_desig
                and s.orbit_number < o.orbit_number
            )
            o.eccentricity = roll_eccentricity(
                o.orbit_number, age,
                extra_stars=extra,
                is_belt=(o.world_type == "belt"),
                anomaly_dm=_ANOM_ECC_DM.get(o.anomaly_type, 0),
            )

        for s in system.stars:
            if s.role in ("close", "near", "far") and s.orbit_number is not None:
                s.orbit_eccentricity = roll_eccentricity(
                    s.orbit_number, age, is_star=True
                )

    # ── Orbital inclination (WBH p.28) — only when flag is set ──────────────
    if orbital_inclination:
        for o in result.orbits:
            if o.world_type == "empty":
                continue
            if o.anomaly_type == "inclined":
                continue  # angle already stored in notes
            o.inclination = roll_inclination()

        for s in system.stars:
            if s.role in ("close", "near", "far") and s.orbit_number is not None:
                s.orbit_inclination = roll_inclination()

    return result


def generate_full_system(seed=None, orbital_eccentricity: bool = False,
                         orbital_inclination: bool = False):
    """Generate a stellar system with orbits, optionally seeding the RNG."""
    from .traveller_stellar_gen import generate_stellar_data  # pylint: disable=import-outside-toplevel
    rng = random.Random(seed) if seed is not None else None
    system = generate_stellar_data(rng=rng)
    orbits = generate_orbits(system, rng=rng, orbital_eccentricity=orbital_eccentricity,
                             orbital_inclination=orbital_inclination)
    return system, orbits


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _system, _orbits = generate_full_system(args.seed)
    if args.json:
        data = _system.to_dict()
        data["orbits"] = _orbits.to_dict()
        print(json.dumps(data, indent=2))
    else:
        print(_system.summary())
        print(_orbits.summary())
