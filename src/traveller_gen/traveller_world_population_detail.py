"""
traveller_world_population_detail.py
=====================================
Population detail for Traveller mainworlds and secondary worlds, following
the World Builder's Handbook Social Characteristics Checklist (§2).

Implements:
  - Population Concentration Rating (PCR), 0–9
  - Urbanisation percentage
  - Urban population
  - Major city count and total major city population
  - Individual city populations (up to 10, sorted largest first)
  - Population profile string in WBH format P-p-C-%-M

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

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .traveller_world_physical import WorldPhysical

if TYPE_CHECKING:
    from .traveller_system_gen import TravellerSystem

_rng: random.Random = random  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PCR_LABELS: dict[int, str] = {
    0: "Extremely Dispersed",
    1: "Highly Dispersed",
    2: "Moderately Dispersed",
    3: "Partially Dispersed",
    4: "Slightly Dispersed",
    5: "Slightly Concentrated",
    6: "Partially Concentrated",
    7: "Moderately Concentrated",
    8: "Highly Concentrated",
    9: "Extremely Concentrated",
}

# eHex lookup for population code display (codes 0–C are all we need here)
_EHEX = "0123456789ABC"


def _round_sig(n: int, sig: int = 3) -> int:
    """Round n to sig significant figures."""
    if n <= 0:
        return max(0, n)
    magnitude = math.floor(math.log10(n))
    factor = 10 ** (magnitude - sig + 1)
    return int(round(n / factor) * factor)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class City:
    """One major city entry."""
    population: int
    codes: list = field(default_factory=list)   # e.g. ["Cw"] for world capital

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        d: dict = {"population": self.population}
        if self.codes:
            d["codes"] = list(self.codes)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "City":
        """Reconstruct from a dict produced by to_dict()."""
        return cls(
            population=int(d.get("population", 0)),
            codes=list(d.get("codes", [])),
        )


@dataclass
class PopulationDetail:   # pylint: disable=too-many-instance-attributes
    """Full WBH Social Characteristics population profile for one world."""
    total_population: int               # p_value × 10^pop_code
    p_value: int                        # 1–9 (same as population_multiplier)
    pcr: int                            # Population Concentration Rating, 0–9
    pcr_label: str                      # human-readable PCR description
    urbanisation_pct: int               # 0–100
    urban_population: int               # total_population × urbanisation_pct // 100
    major_city_count: int               # 0–31
    major_city_total_population: int    # sum of city populations
    cities: list                        # List[City], up to 10, sorted largest first
    population_profile: str             # "P-p-C-%-M"

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        return {
            "total_population": self.total_population,
            "p_value": self.p_value,
            "pcr": self.pcr,
            "pcr_label": self.pcr_label,
            "urbanisation_pct": self.urbanisation_pct,
            "urban_population": self.urban_population,
            "major_city_count": self.major_city_count,
            "major_city_total_population": self.major_city_total_population,
            "cities": [c.to_dict() for c in self.cities],
            "population_profile": self.population_profile,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PopulationDetail":
        """Reconstruct from a dict produced by to_dict()."""
        return cls(
            total_population=int(d.get("total_population", 0)),
            p_value=int(d.get("p_value", 0)),
            pcr=int(d.get("pcr", 0)),
            pcr_label=str(d.get("pcr_label", "")),
            urbanisation_pct=int(d.get("urbanisation_pct", 0)),
            urban_population=int(d.get("urban_population", 0)),
            major_city_count=int(d.get("major_city_count", 0)),
            major_city_total_population=int(d.get("major_city_total_population", 0)),
            cities=[City.from_dict(c) for c in d.get("cities", [])],
            population_profile=str(d.get("population_profile", "")),
        )


# ---------------------------------------------------------------------------
# Private helpers — PCR
# ---------------------------------------------------------------------------

def _minimal_tl(atm: int) -> int:
    """Return the minimal sustainable TL for an atmosphere code (WBH p.175)."""
    if atm in (0, 1):
        return 8
    if atm in (2, 3):
        return 5
    if atm in (4, 5):
        return 3
    if atm in (6, 7, 8, 9):
        return 0
    return 8   # codes 10+ (A, B, C … hostile)


def _pcr_dms(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-branches
        pop_code: int, size: int, tl: int, government: int,
        trade_codes: list, is_tidal_lock: bool, atm: int) -> int:
    """Accumulate all DMs for the PCR roll (WBH Social Characteristics table)."""
    dm = 0
    if size == 1:
        dm += 2
    elif size in (2, 3):
        dm += 1
    if is_tidal_lock:
        dm += 2
    min_tl = _minimal_tl(atm)
    if min_tl >= 8:
        dm += 3
    elif min_tl >= 3:
        dm += 1
    if pop_code == 8:
        dm -= 1
    elif pop_code >= 9:
        dm -= 2
    if government == 7:
        dm -= 2
    if tl <= 1:
        dm -= 2
    elif tl <= 3:
        dm -= 1
    elif tl <= 9:
        dm += 1
    if "Ag" in trade_codes:
        dm -= 2
    if "In" in trade_codes:
        dm += 1
    if "Na" in trade_codes:
        dm -= 1
    if "Ri" in trade_codes:
        dm += 1
    return dm


def generate_pcr(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        pop_code: int, size: int, tl: int, government: int,
        trade_codes: list, is_tidal_lock: bool = False,
        atm: int = 6,
        rng: Optional[random.Random] = None) -> int:
    """Roll Population Concentration Rating (WBH Social Characteristics).

    For pop_code < 6: if 1D > pop_code → PCR = 9 immediately.
    Otherwise: roll 1D + DMs on PCR table.
    Minimum PCR = 1 when pop_code ≥ 9; else minimum = 0.  Maximum = 9.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    if pop_code < 6 and _rng.randint(1, 6) > pop_code:
        return 9
    dm = _pcr_dms(pop_code, size, tl, government, trade_codes, is_tidal_lock, atm)
    result = _rng.randint(1, 6) + dm
    min_pcr = 1 if pop_code >= 9 else 0
    return max(min_pcr, min(9, result))


# ---------------------------------------------------------------------------
# Private helpers — Urbanisation
# ---------------------------------------------------------------------------

def _urb_pct_from_result(result: int) -> int:  # pylint: disable=too-many-return-statements,too-many-branches
    """Map a 2D+DM result to an exact urbanisation % via inner dice (WBH table)."""
    def d2() -> int:
        return _rng.randint(1, 2)
    def d3() -> int:
        return (_rng.randint(1, 6) + 1) // 2   # ceil(1D/2): 1, 2, or 3

    if result <= 0:
        return 0
    if result == 1:
        return _rng.randint(1, 6)
    if result == 2:
        return 6 + _rng.randint(1, 6)
    if result == 3:
        return 12 + _rng.randint(1, 6)
    if result == 4:
        return 18 + _rng.randint(1, 6)
    if result == 5:
        return 22 + _rng.randint(1, 6) * 2 + d2()
    if result == 6:
        return 34 + _rng.randint(1, 6) * 2 + d2()
    if result == 7:
        return 46 + _rng.randint(1, 6) * 2 + d2()
    if result == 8:
        return 58 + _rng.randint(1, 6) * 2 + d2()
    if result == 9:
        return 70 + _rng.randint(1, 6) * 2 + d2()
    if result == 10:
        return 84 + _rng.randint(1, 6)
    if result == 11:
        return 90 + _rng.randint(1, 6)
    if result == 12:
        return 96 + d3()
    return 100   # 13+


def _urb_dms_and_constraints(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-branches,too-many-statements
        pcr: int, pop_code: int, size: int, tl: int,
        government: int, law_level: int, trade_codes: list,
        atm: int) -> tuple:
    """Return (total_dm, min_pct_or_none, max_pct_or_none) for urbanisation roll.

    min/max constraints are themselves rolled (e.g. 18 + 1D for pop 9).
    A minimum supersedes a conflicting maximum (WBH rule).
    """
    dm = 0
    min_pct: Optional[int] = None
    max_pct: Optional[int] = None

    def _set_min(val: int) -> None:
        nonlocal min_pct
        if min_pct is None or val > min_pct:
            min_pct = val

    def _set_max(val: int) -> None:
        nonlocal max_pct
        if max_pct is None or val < max_pct:
            max_pct = val

    # PCR DMs
    if pcr <= 2:
        dm += -3 + pcr
    elif pcr >= 7:
        dm += -6 + pcr

    # Minimal sustainable TL
    min_tl = _minimal_tl(atm)
    if min_tl <= 3:
        dm -= 1

    # Size 0
    if size == 0:
        dm += 2

    # Population DMs
    if pop_code == 8:
        dm += 1
    elif pop_code == 9:
        dm += 2
        _set_min(18 + _rng.randint(1, 6))
    elif pop_code >= 10:
        dm += 4
        _set_min(50 + _rng.randint(1, 6))

    # Government
    if government == 0:
        dm -= 2

    # Law Level
    if law_level >= 9:
        dm += 1

    # Tech Level — DM + max constraint
    if tl <= 2:
        dm -= 2
        _set_max(20 + _rng.randint(1, 6))
    elif tl == 3:
        dm -= 1
        _set_max(30 + _rng.randint(1, 6))
    elif tl == 4:
        dm += 1
        _set_max(60 + _rng.randint(1, 6))
    elif tl <= 9:
        dm += 2
        _set_max(90 + _rng.randint(1, 6))
    # TL 10+ has no listed DM or max in the table

    # Trade codes
    if "Ag" in trade_codes:
        dm -= 2
        _set_max(90 + _rng.randint(1, 6))
    if "Na" in trade_codes:
        dm += 2

    return dm, min_pct, max_pct


def generate_urbanisation_pct(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        pcr: int, pop_code: int, size: int, tl: int,
        government: int, law_level: int,
        trade_codes: list, atm: int = 6,
        rng: Optional[random.Random] = None) -> int:
    """Roll urbanisation % (WBH Social Characteristics table).

    Returns an integer 0–100.  Minimum supersedes conflicting maximum.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    dm, min_pct, max_pct = _urb_dms_and_constraints(
        pcr, pop_code, size, tl, government, law_level, trade_codes, atm)
    result = _rng.randint(1, 6) + _rng.randint(1, 6) + dm
    pct = _urb_pct_from_result(result)
    pct = max(0, min(100, pct))
    if max_pct is not None:
        pct = min(pct, max(0, max_pct), 100)
    if min_pct is not None:
        pct = max(pct, min(min_pct, 100), 0)
    return pct


# ---------------------------------------------------------------------------
# Private helpers — Major cities
# ---------------------------------------------------------------------------

def _total_world_population(pop_code: int, p_value: int) -> int:
    """Compute total world population: p_value × 10^pop_code."""
    if pop_code == 0:
        return 0
    return p_value * (10 ** pop_code)


def _major_cities_and_total_pop(  # pylint: disable=too-many-return-statements
        pop_code: int, pcr: int,
        urbanisation_pct: int, urban_pop: int) -> tuple:
    """Return (city_count, total_major_city_pop) using the 5-case WBH procedure."""
    # Case 1: PCR = 0 — no major cities
    if pcr == 0:
        return 0, 0

    # Case 2: Pop ≤ 5, PCR = 9 — single concentrated city
    if pop_code <= 5 and pcr == 9:
        return 1, urban_pop

    # Case 3: Pop ≤ 5, PCR 1–8
    if pop_code <= 5:
        count = min(9 - pcr, pop_code)
        count = max(1, count)
        return count, urban_pop

    # Case 4: Pop ≥ 6, PCR = 9
    if pcr == 9:
        count = max(1, pop_code - (_rng.randint(1, 6) + _rng.randint(1, 6)))
        return count, urban_pop

    # Case 5: Pop ≥ 6, PCR 1–8
    urb_frac = urbanisation_pct / 100.0
    raw = _rng.randint(1, 6) + _rng.randint(1, 6) - pcr + urb_frac * 20.0 / pcr
    count = max(1, math.ceil(raw))
    count = min(count, 31)
    if pop_code < 6:
        count = min(count, pop_code)
    total_pop = int(pcr / (_rng.randint(1, 6) + 7) * urban_pop)
    total_pop = max(1, total_pop)
    return count, total_pop


def _distribute_city_populations(  # pylint: disable=too-many-branches,too-many-locals
        city_count: int, total_major_city_pop: int, pcr: int) -> list:
    """Allocate populations to cities using the WBH chunk algorithm.

    Returns a list of city populations (integers), sorted largest first.
    Each city receives at least 1% of total_major_city_pop.
    """
    if city_count <= 0 or total_major_city_pop <= 0:
        return []
    if city_count == 1:
        return [total_major_city_pop]

    # 2-3 cities: proportional split with (1D+3)×10% method
    if city_count <= 3:
        pops = []
        remaining_pop = total_major_city_pop
        one_pct = max(1, total_major_city_pop // 100)
        for i in range(city_count):
            is_last = i == city_count - 1
            if is_last:
                pops.append(max(one_pct, remaining_pop))
            else:
                share_pct = (_rng.randint(1, 6) + 3) * 10
                share_pct = min(share_pct, 90)
                this_pop = max(one_pct, int(remaining_pop * share_pct / 100))
                # leave at least 1% for each remaining city
                max_take = remaining_pop - one_pct * (city_count - i - 1)
                this_pop = min(this_pop, max(one_pct, max_take))
                pops.append(this_pop)
                remaining_pop -= this_pop
        return sorted(pops, reverse=True)

    # 4+ cities: chunk allocation algorithm
    # Each city gets 1% base; remaining pool split into PCR-sized chunks
    remaining_pct = 100 - city_count     # percent pool (each city has 1% base)
    max_chunk_pct = max(1, pcr)
    min_chunk_count = 2 * city_count
    raw_chunks = remaining_pct // max_chunk_pct if max_chunk_pct > 0 else min_chunk_count
    chunk_count = max(min_chunk_count, raw_chunks)
    chunk_pct = remaining_pct // chunk_count if chunk_count > 0 else 1
    chunk_pct = max(1, chunk_pct)
    chunk_count = remaining_pct // chunk_pct
    held_back_pct = remaining_pct - chunk_count * chunk_pct

    # Allocate chunks to cities by cycling, rolling 1D each time
    chunk_allocations = [0] * city_count
    chunks_left = chunk_count
    city_idx = 0
    while chunks_left > 0:
        take = min(_rng.randint(1, 6), chunks_left)
        chunk_allocations[city_idx] += take
        chunks_left -= take
        city_idx = (city_idx + 1) % city_count

    # Convert to populations
    one_pct_pop = max(1, total_major_city_pop // 100)
    pops = []
    for i, alloc in enumerate(chunk_allocations):
        pct = 1 + alloc * chunk_pct
        if i == city_idx:
            pct += held_back_pct
        pops.append(max(one_pct_pop, int(total_major_city_pop * pct // 100)))

    return sorted(pops, reverse=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_population_detail(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        pop_code: int, p_value: int,
        size: int, tl: int, government: int, law_level: int,
        trade_codes: list,
        atm: int = 6,
        is_tidal_lock: bool = False,
        rng: Optional[random.Random] = None) -> Optional[PopulationDetail]:
    """Generate a full WBH population profile for one inhabited world.

    Returns None when pop_code == 0 (uninhabited).

    Parameters
    ----------
    pop_code : int
        UWP population code (0–10+).
    p_value : int
        Population P-digit / multiplier (1–9); same as population_multiplier.
    size, tl, government, law_level : int
        Standard UWP codes used for DM lookups.
    trade_codes : list[str]
        World trade codes (e.g. ["Ag", "Ni"]).
    atm : int
        Atmosphere code; used for minimal sustainable TL checks.
    is_tidal_lock : bool
        True when the world has a 1:1 tidal lock (adds PCR DM+2).
    rng : random.Random, optional
        Injectable RNG; writes to module-level sentinel when provided.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng
    if pop_code == 0:
        return None

    total_pop = _total_world_population(pop_code, p_value)

    pcr = generate_pcr(pop_code, size, tl, government, trade_codes, is_tidal_lock, atm)
    pcr_label = _PCR_LABELS[pcr]

    urb_pct = generate_urbanisation_pct(
        pcr, pop_code, size, tl, government, law_level, trade_codes, atm)
    urban_pop = total_pop * urb_pct // 100

    city_count, total_major_city_pop = _major_cities_and_total_pop(
        pop_code, pcr, urb_pct, urban_pop)

    raw_pops = _distribute_city_populations(city_count, total_major_city_pop, pcr)
    total_major_city_pop = _round_sig(total_major_city_pop)
    # Cap display list at 10; keep all for city_count accuracy
    detailed_cities = [City(population=_round_sig(p)) for p in raw_pops[:10]]

    pop_hex = _EHEX[pop_code] if pop_code < len(_EHEX) else str(pop_code)
    profile = f"{pop_hex}-{p_value}-{pcr}-{urb_pct}-{city_count}"

    return PopulationDetail(
        total_population=total_pop,
        p_value=p_value,
        pcr=pcr,
        pcr_label=pcr_label,
        urbanisation_pct=urb_pct,
        urban_population=urban_pop,
        major_city_count=city_count,
        major_city_total_population=total_major_city_pop,
        cities=detailed_cities,
        population_profile=profile,
    )


def attach_population_detail(
        system: "TravellerSystem",
        rng: Optional[random.Random] = None) -> None:
    """Attach population detail to mainworld and all inhabited secondaries.

    Calls generate_population_detail() for system.mainworld when inhabited,
    and for each inhabited secondary WorldDetail and moon WorldDetail in the
    system orbits.  Results are attached as .population_detail on each object.

    Secondary worlds lack WorldPhysical data, so is_tidal_lock is always False
    for them; atmosphere is derived from the WorldDetail SAH string.
    """
    global _rng  # pylint: disable=global-statement
    if rng is not None:
        _rng = rng

    mw = system.mainworld
    if mw is not None and mw.population > 0:
        tidal_lock = False
        if (isinstance(mw.size_detail, WorldPhysical)
                and mw.size_detail.tidal_status == "1:1_lock"):
            tidal_lock = True
        mw.population_detail = generate_population_detail(
            mw.population, mw.population_multiplier,
            mw.size, mw.tech_level, mw.government,
            mw.law_level, mw.trade_codes,
            atm=mw.atmosphere,
            is_tidal_lock=tidal_lock,
            rng=None,   # _rng already set above
        )

    for orbit in system.system_orbits.orbits:
        if orbit.is_mainworld_candidate:
            continue
        det = orbit.detail
        if det is None or not det.inhabited:
            continue
        _attach_detail_population(det)


def _gen_p_value() -> int:
    """Roll a population P-value (1–9) for a secondary world."""
    def d3() -> int:
        return (_rng.randint(1, 6) + 1) // 2
    offset_map = {1: 0, 2: 3, 3: 6}
    return offset_map[d3()] + d3()


_EHEX_FULL = "0123456789ABCDEFGHIJ"


def _ehex_int(ch: str) -> int:
    """Convert one eHex character to int; returns 0 for 'S' or unknown."""
    idx = _EHEX_FULL.find(ch.upper())
    return max(0, idx)


def _pop_detail_for_det(det: object) -> Optional[PopulationDetail]:  # type: ignore[type-arg]
    """Generate PopulationDetail for a WorldDetail object (secondary world)."""
    pop_code: int = getattr(det, "population", 0)
    if pop_code == 0:
        return None
    sah: str = getattr(det, "sah", "000")
    size_ch = sah[0] if len(sah) > 0 else "0"
    atm_ch  = sah[1] if len(sah) > 1 else "0"
    size = 1 if size_ch == "S" else _ehex_int(size_ch)
    atm  = _ehex_int(atm_ch)
    p_value = _gen_p_value()
    return generate_population_detail(
        pop_code, p_value,
        size=size,
        tl=getattr(det, "tech_level", 0),
        government=getattr(det, "government", 0),
        law_level=getattr(det, "law_level", 0),
        trade_codes=getattr(det, "trade_codes", []),
        atm=atm,
        rng=None,   # _rng already set by attach_population_detail
    )


def _attach_detail_population(det: object) -> None:  # type: ignore[type-arg]
    """Attach population detail to one WorldDetail and its inhabited moons."""
    det.population_detail = _pop_detail_for_det(det)  # type: ignore[attr-defined]
    for moon in getattr(det, "moons", []):
        moon_det = getattr(moon, "detail", None)
        if moon_det is not None and getattr(moon_det, "inhabited", False):
            moon_det.population_detail = _pop_detail_for_det(moon_det)
