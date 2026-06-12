"""
traveller_world_tech_detail.py
================================
Tech level detail for Traveller mainworlds and secondary worlds, following
the World Builder's Handbook Social Characteristics Checklist (§5).

Implements:
  - High / Low common Tech Level range
  - Quality-of-life sub-TLs: Energy, Electronics, Manufacturing, Medical,
    Environmental
  - Transportation sub-TLs: Land, Sea, Air, Space
  - Military sub-TLs: Personal, Heavy
  - Technology profile string in WBH format H-L-QQQQQ-TTTT-MM

Novelty TL is deferred to issue #TBD (WBH §5 procedure not yet transcribed).

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
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from traveller_system_gen import TravellerSystem

_rng: random.Random = random  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EHEX = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Minimum sustainable TL by atmosphere code (WBH §5 Tech Level and Environment
# table).  Multiple factors apply: take the highest minimum.
_TECH_MIN_TL: dict[int, int] = {
    0:  8,   # Vacuum
    1:  8,   # Trace
    2:  5,   # Very Thin Tainted
    3:  5,   # Very Thin
    4:  3,   # Thin Tainted
    5:  0,   # Thin  (no minimum beyond basic life-support)
    6:  0,   # Standard
    7:  3,   # Standard Tainted
    8:  0,   # Dense
    9:  3,   # Dense Tainted
    10: 8,   # Exotic (A)
    11: 9,   # Corrosive (B)
    12: 10,  # Insidious (C)
    13: 5,   # Dense High (D)
    14: 5,   # Thin Low (E)
    15: 8,   # Unusual (F) — at least 8; possibly higher (WBH note)
    16: 14,  # G
    17: 14,  # H
}

# Habitability rating → minimum TL (index = rating, index 8+ → 0)
_HAB_MIN_TL: list[int] = [8, 5, 5, 3, 3, 3, 3, 3, 0, 0]

# TLM table: 2D result → TL modifier.  Missing keys → 0.
_TLM_TABLE: dict[int, int] = {2: -3, 3: -2, 4: -1, 10: 1, 11: 2, 12: 3}

# Medical lower bound by starport quality: starport reflects minimum medical
# support infrastructure available.
_STARPORT_MED_FLOOR: dict[str, int] = {
    "A": 6, "B": 4, "C": 2,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tlm() -> int:
    """Roll 2D and look up the Tech Level Modifier (−3 to +3)."""
    result = _rng.randint(1, 6) + _rng.randint(1, 6)
    return _TLM_TABLE.get(result, 0)


def _ehex(n: int) -> str:
    """Convert a non-negative int to a single eHex character."""
    idx = max(0, min(n, len(_EHEX) - 1))
    return _EHEX[idx]


def _clamp(value: int, lo: int, hi: int) -> int:
    """Clamp value to [lo, hi].  Returns lo when lo > hi (degenerate range)."""
    return max(lo, min(value, hi))


def _min_tl(atmosphere: int, habitability_rating: Optional[int]) -> int:
    """Return the highest applicable minimum TL for this world."""
    atm_min = _TECH_MIN_TL.get(atmosphere, 0)
    if habitability_rating is not None:
        hab_idx = min(habitability_rating, len(_HAB_MIN_TL) - 1)
        hab_min = _HAB_MIN_TL[hab_idx]
        return max(atm_min, hab_min)
    return atm_min


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class TechDetail:  # pylint: disable=too-many-instance-attributes
    """Full WBH tech level profile for one inhabited world."""

    tl_high_common:        int   # = UWP TL
    tl_low_common:         int   # floor of current technology in use
    # Quality-of-life sub-TLs
    tl_energy:             int
    tl_electronics:        int
    tl_manufacturing:      int
    tl_medical:            int
    tl_environmental:      int
    # Transportation sub-TLs
    tl_land:               int
    tl_sea:                int
    tl_air:                int
    tl_space:              int
    # Military sub-TLs
    tl_military_personal:  int
    tl_military_heavy:     int
    # Profile
    technology_profile:    str   # "H-L-QQQQQ-TTTT-MM"

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict."""
        return {
            "tl_high_common":       self.tl_high_common,
            "tl_low_common":        self.tl_low_common,
            "tl_energy":            self.tl_energy,
            "tl_electronics":       self.tl_electronics,
            "tl_manufacturing":     self.tl_manufacturing,
            "tl_medical":           self.tl_medical,
            "tl_environmental":     self.tl_environmental,
            "tl_land":              self.tl_land,
            "tl_sea":               self.tl_sea,
            "tl_air":               self.tl_air,
            "tl_space":             self.tl_space,
            "tl_military_personal": self.tl_military_personal,
            "tl_military_heavy":    self.tl_military_heavy,
            "technology_profile":   self.technology_profile,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TechDetail":
        """Reconstruct from a dict produced by to_dict()."""
        return cls(
            tl_high_common=int(d.get("tl_high_common", 0)),
            tl_low_common=int(d.get("tl_low_common", 0)),
            tl_energy=int(d.get("tl_energy", 0)),
            tl_electronics=int(d.get("tl_electronics", 0)),
            tl_manufacturing=int(d.get("tl_manufacturing", 0)),
            tl_medical=int(d.get("tl_medical", 0)),
            tl_environmental=int(d.get("tl_environmental", 0)),
            tl_land=int(d.get("tl_land", 0)),
            tl_sea=int(d.get("tl_sea", 0)),
            tl_air=int(d.get("tl_air", 0)),
            tl_space=int(d.get("tl_space", 0)),
            tl_military_personal=int(d.get("tl_military_personal", 0)),
            tl_military_heavy=int(d.get("tl_military_heavy", 0)),
            technology_profile=str(d.get("technology_profile", "")),
        )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_tech_detail(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements
        tl: int,
        atmosphere: int,
        hydrographics: int,
        population: int,
        government: int,
        law_level: int,
        starport: str,
        pcr: int = 0,
        habitability_rating: Optional[int] = None,
        trade_codes: Optional[list] = None,
        rng: Optional[random.Random] = None,
) -> Optional[TechDetail]:
    """Generate a full WBH tech level profile for one inhabited world.

    Returns None when ``population == 0`` (uninhabited — no procedures apply).

    Parameters
    ----------
    tl : int
        UWP Tech Level digit (0–F+).
    atmosphere : int
        UWP Atmosphere code.
    hydrographics : int
        UWP Hydrographics code.
    population : int
        UWP Population code.
    government : int
        UWP Government code.
    law_level : int
        UWP Law Level.
    starport : str
        UWP Starport letter (A–E, X).
    pcr : int
        Population Concentration Rating (0–9).  Defaults to 0 when population
        detail has not been generated.
    habitability_rating : Optional[int]
        Habitability rating from WorldPhysical.  Used to determine environment
        minimum TL.  Defaults to None (atmosphere-only minimum used).
    trade_codes : Optional[list]
        Trade code strings (e.g. ["In", "Ag"]).  Used for subcategory DMs.
    rng : Optional[random.Random]
        Injectable RNG.  When provided, replaces the module-level ``_rng``.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    if population == 0:
        return None

    # ------------------------------------------------------------------
    # High / Low common TL
    # ------------------------------------------------------------------
    tl_high = tl

    # Low common TL DMs (WBH §5)
    low_dm = 0
    if 1 <= population <= 5:
        low_dm += 1
    if population >= 9:
        low_dm -= 1
    if government in (0, 6, 13, 14):
        low_dm -= 1
    if government == 5:
        low_dm += 1
    if government == 7:
        low_dm -= 2
    if pcr <= 2:
        low_dm -= 1
    if pcr >= 7:
        low_dm += 1

    min_tech = _min_tl(atmosphere, habitability_rating)
    low_floor = min(tl_high, max(min_tech, tl_high // 2))

    tl_low = _clamp(tl_high + _tlm() + low_dm, low_floor, tl_high)

    # ------------------------------------------------------------------
    # Sub-TL generation helper
    # ------------------------------------------------------------------
    _tc = list(trade_codes or [])

    def _sub_tl(lo: int, hi: int, dm: int = 0, base: Optional[int] = None) -> int:
        raw = (tl_high if base is None else base) + _tlm() + dm
        return max(0, _clamp(raw, lo, hi))

    # ------------------------------------------------------------------
    # Quality-of-life sub-TLs (WBH §5, dependency order)
    # ------------------------------------------------------------------
    # Energy TL: High TL + TLM + DMs, bounds [High TL ÷ 2, High TL × 1.2]
    energy_dm = 0
    if population >= 9:
        energy_dm += 1
    if "In" in _tc:
        energy_dm += 1
    energy_lo = tl_high // 2
    energy_hi = int(tl_high * 1.2)
    tl_energy = _sub_tl(energy_lo, energy_hi, energy_dm)

    # Electronics TL: High TL + TLM + DMs, bounds [Energy TL − 3, Energy TL + 1]
    elec_dm = 0
    if 1 <= population <= 5:
        elec_dm += 1
    if population >= 9:
        elec_dm -= 1
    if "In" in _tc:
        elec_dm += 1
    elec_lo = tl_energy - 3
    elec_hi = tl_energy + 1
    tl_electronics = _sub_tl(elec_lo, elec_hi, elec_dm)

    # Manufacturing TL: High TL + TLM + DMs, bounds [Electronics TL − 2, max(Energy, Electronics)]
    mfg_dm = 0
    if 1 <= population <= 6:
        mfg_dm -= 1
    if population >= 8:
        mfg_dm += 1
    if "In" in _tc:
        mfg_dm += 1
    mfg_lo = tl_electronics - 2
    mfg_hi = max(tl_energy, tl_electronics)
    tl_manufacturing = _sub_tl(mfg_lo, mfg_hi, mfg_dm)

    # Medical TL: Electronics TL + TLM + DMs, bounds [starport floor, Electronics TL]
    med_dm = 0
    if "Ri" in _tc:
        med_dm += 1
    if "Po" in _tc:
        med_dm -= 1
    med_lo = min(_STARPORT_MED_FLOOR.get(starport.upper(), 0), tl_electronics)
    med_hi = tl_electronics
    tl_medical = _sub_tl(med_lo, med_hi, med_dm, base=tl_electronics)

    # Environmental TL: Manufacturing TL + TLM + DMs, bounds [Energy TL − 5, Energy TL]
    env_dm = 0
    if habitability_rating is not None and habitability_rating < 8:
        env_dm += 8 - habitability_rating
    env_lo = tl_energy - 5
    env_hi = tl_energy
    tl_environmental = _sub_tl(env_lo, env_hi, env_dm, base=tl_manufacturing)

    # ------------------------------------------------------------------
    # Transportation sub-TLs
    # ------------------------------------------------------------------
    # Land TL: Energy TL + TLM + DMs, bounds [Electronics TL − 5, Energy TL]
    land_dm = 0
    if hydrographics == 10:
        land_dm -= 1
    if pcr <= 2:
        land_dm += 1
    land_lo = tl_electronics - 5
    land_hi = tl_energy
    tl_land = _sub_tl(land_lo, land_hi, land_dm, base=tl_energy)

    # Sea TL: Energy TL + TLM + DMs, bounds [Electronics TL − 5 (or 0 if hydro=0), Energy TL]
    sea_dm = 0
    if hydrographics == 0:
        sea_dm -= 2
    elif hydrographics == 8:
        sea_dm += 1
    elif hydrographics >= 9:
        sea_dm += 2
    if pcr <= 2:
        sea_dm += 1
    sea_lo = 0 if hydrographics == 0 else tl_electronics - 5
    sea_hi = tl_energy
    tl_sea = _sub_tl(sea_lo, sea_hi, sea_dm, base=tl_energy)

    if atmosphere == 0 and tl_high <= 5:
        tl_air = 0
    else:
        tl_air = _sub_tl(land_lo, land_hi)

    space_base = min(tl_energy, tl_manufacturing)
    space_lo = max(tl_low, space_base - 3)
    space_hi = min(tl_high, space_base)
    tl_space = _sub_tl(space_lo, space_hi)

    # ------------------------------------------------------------------
    # Military sub-TLs
    # ------------------------------------------------------------------
    if law_level == 0:
        tl_military_personal = 0
    else:
        mil_p_lo = max(tl_low, tl_electronics)
        mil_p_hi = min(tl_high, tl_manufacturing)
        tl_military_personal = _sub_tl(mil_p_lo, mil_p_hi)

    tl_military_heavy = _sub_tl(0, tl_manufacturing)

    # ------------------------------------------------------------------
    # Technology profile: H-L-QQQQQ-TTTT-MM
    # ------------------------------------------------------------------
    technology_profile = (
        f"{_ehex(tl_high)}-{_ehex(tl_low)}-"
        f"{_ehex(tl_energy)}{_ehex(tl_electronics)}{_ehex(tl_manufacturing)}"
        f"{_ehex(tl_medical)}{_ehex(tl_environmental)}-"
        f"{_ehex(tl_land)}{_ehex(tl_sea)}{_ehex(tl_air)}{_ehex(tl_space)}-"
        f"{_ehex(tl_military_personal)}{_ehex(tl_military_heavy)}"
    )

    return TechDetail(
        tl_high_common=tl_high,
        tl_low_common=tl_low,
        tl_energy=tl_energy,
        tl_electronics=tl_electronics,
        tl_manufacturing=tl_manufacturing,
        tl_medical=tl_medical,
        tl_environmental=tl_environmental,
        tl_land=tl_land,
        tl_sea=tl_sea,
        tl_air=tl_air,
        tl_space=tl_space,
        tl_military_personal=tl_military_personal,
        tl_military_heavy=tl_military_heavy,
        technology_profile=technology_profile,
    )


# ---------------------------------------------------------------------------
# Attach function
# ---------------------------------------------------------------------------

def _sah_digit(sah: str, idx: int) -> int:
    ch = sah[idx:idx + 1].upper()
    pos = _EHEX.find(ch)
    return pos if pos >= 0 else 0


def _tech_detail_for_det(det: object) -> Optional[TechDetail]:
    """Generate TechDetail for a WorldDetail (secondary world)."""
    pop:   int = getattr(det, "population", 0)
    tl:    int = getattr(det, "tech_level", 0)
    sah_  = getattr(det, "sah", "000")
    atm:   int = _sah_digit(sah_, 1)
    hydro: int = _sah_digit(sah_, 2)
    gov:   int = getattr(det, "government", 0)
    law:   int = getattr(det, "law_level", 0)
    port:  str = getattr(det, "spaceport", "-")
    pop_detail = getattr(det, "population_detail", None)
    pcr: int = pop_detail.pcr if pop_detail is not None else 0
    tc: list = list(getattr(det, "trade_codes", []) or [])
    return generate_tech_detail(
        tl=tl, atmosphere=atm, hydrographics=hydro,
        population=pop, government=gov, law_level=law,
        starport=port, pcr=pcr, trade_codes=tc, rng=None,
    )


def _attach_det_tech(det: object) -> None:
    """Attach tech detail to one WorldDetail and its inhabited moons."""
    det.tech_detail = _tech_detail_for_det(det)  # type: ignore[attr-defined]
    for moon in getattr(det, "moons", []):
        moon_det = getattr(moon, "detail", None)
        if moon_det is not None and getattr(moon_det, "inhabited", False):
            moon_det.tech_detail = _tech_detail_for_det(moon_det)


def attach_tech_detail(
        system: "TravellerSystem",
        rng: Optional[random.Random] = None,
) -> None:
    """Attach tech level detail to mainworld and all inhabited secondaries.

    Calls generate_tech_detail() for system.mainworld when inhabited.
    Also applies to each inhabited secondary WorldDetail and moon WorldDetail.
    Reads habitability_rating from WorldPhysical when available (mainworld only).
    Uses population_detail.pcr when available; falls back to pcr=0.
    No-op when mainworld is uninhabited.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    mw = system.mainworld
    if mw is not None and mw.population > 0:
        pop_det = mw.population_detail  # type: ignore[attr-defined]
        pcr = pop_det.pcr if pop_det is not None else 0
        # Habitability rating only available when full physical detail attached
        hab = None
        phys = getattr(mw, "physical", None)
        if phys is not None and hasattr(phys, "habitability_rating"):
            hab = phys.habitability_rating
        mw.tech_detail = generate_tech_detail(  # type: ignore[attr-defined]
            tl=mw.tech_level,  # type: ignore[attr-defined]
            atmosphere=mw.atmosphere,  # type: ignore[attr-defined]
            hydrographics=mw.hydrographics,  # type: ignore[attr-defined]
            population=mw.population,  # type: ignore[attr-defined]
            government=mw.government,  # type: ignore[attr-defined]
            law_level=mw.law_level,  # type: ignore[attr-defined]
            starport=mw.starport,  # type: ignore[attr-defined]
            pcr=pcr,
            habitability_rating=hab,
            trade_codes=list(mw.trade_codes or []),  # type: ignore[attr-defined]
            rng=None,
        )

    for orbit in system.system_orbits.orbits:
        if orbit.is_mainworld_candidate:
            continue
        det = orbit.detail
        if det is None or not det.inhabited:
            continue
        _attach_det_tech(det)
