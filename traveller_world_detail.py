"""
traveller_world_detail.py
=========================
Generates SAH/UWP profiles for every significant body in a star system
other than the designated mainworld, following the World Builder's Handbook
(WBH) and Traveller 2022 Core Rulebook (CRB).

Secondary worlds CAN be inhabited (WBH pp.155-180). The rules in full:

Physical characteristics (WBH pp.53-55)
----------------------------------------
Terrestrial worlds:
  - Size: two-stage roll — 1D picks range, second roll gives final Size:
      1-2 → 1D   (range 1-6)
      3-4 → 2D   (range 2-C)
      5-6 → 2D+3 (range 5-F)
  - Atmosphere: 2D-7 + Size (same CRB formula as mainworld)
  - Temperature: derived from orbital HZ deviation (WBH p.46-47)
  - Hydrographics: 2D-7 + Atmosphere + temperature DMs (same CRB formula)

Gas giants (WBH p.55):
  - Category: 1D+DM → Small (GS), Medium (GM), Large (GL)
    DM-1 if primary is M-type V, any Class VI, or brown dwarf
  - Diameter encoded as eHex: GS=D3+D3(2-6), GM=1D+6(7-12), GL=2D+6(8-18)
  - Recorded as e.g. GS4, GM9, GLE

Planetoid belts: always SAH = 000

Social characteristics (WBH pp.155-180)
-----------------------------------------
Population:
  - Maximum secondary world Population = mainworld Population - 1D
  - If max ≤ 0: no secondary populations exist in this system
  - Each terrestrial world independently rolls 1D; pop exists on 1-4,
    capped at the system maximum (WBH p.155 guidance)
  - Gas giants are never inhabited (their moons can be, but we do not
    model moons here); belts can have populations but we treat them
    as uninhabited at this level of detail

Government (WBH p.161-162):
  - Dependent worlds (Gov 6): roll 1D on Secondary World Government table
  - Independent worlds: roll 2D-7 + Population (same as mainworld)
  - Simplified: we treat all secondary worlds as dependent (Gov 6)
    with the simplified government table, which is the most common case

Law Level:
  - For captive (Gov 6) worlds: 1D roll determines relationship to mainworld
  - For others: 2D-7 + Government, same as mainworld

Tech Level (WBH p.180):
  - Secondary world TL = higher of (mainworld TL - 1) or minimal
    sustainable TL
  - Minimal sustainable TL by atmosphere code:
      Atm 0,1: TL 8 (vacc suits / hostile env gear)
      Atm 2,3: TL 5 (filter mask + cold gear)
      Atm 4,5: TL 3 (filter mask)
      Atm 6,7: TL 0 (no special equipment)
      Atm 8,9: TL 0 (no special equipment)
      Atm A+:  TL 8 (hostile environment)
  - If minimal TL > mainworld TL: world is uninhabited
  - Secondary world TL = min(mainworld TL - 1, max(minimal_TL, ...))

Spaceport (WBH p.195):
  - Inhabited secondary worlds roll 1D + population DM:
      Pop 6+ → DM+2, Pop 1 → DM-1, Pop 0 → DM-3
      2-  → Y (no spaceport)
      3   → H (primitive installation)
      4-5 → G (basic facility)
      6   → F (good facility)
      7   → F (refined fuel, overhaul)
      8+  → F (possible shipyard)
  - Spaceport class F is equivalent to starport class C for refuelling.
  - Non-starport spaceport codes (Y/H/G/F) appear in the profile in place
    of the starport code; a world with no population gets '-' in that slot.

Output
------
For uninhabited worlds: a 3-char SAH string  e.g. "473", "GS4", "000"
For inhabited worlds: a 7-char profile  e.g. "F473510" (spaceport+SAH+PGL)
  where PGL = Population, Government, Law Level (one digit each)
  Tech Level is stored as a field but not in the primary profile string,
  consistent with the IISS survey form's separation of UWP data.

The full profile is stored on the OrbitSlot as:
  orbit.sah        — always set (3-char physical profile)
  orbit.population — int 0-C (0 if uninhabited)
  orbit.government — int 0-F (0 if uninhabited)
  orbit.law_level  — int 0-9 (0 if uninhabited)
  orbit.tech_level — int (0 if uninhabited)
  orbit.spaceport  — str  ('-' if uninhabited)
  orbit.profile    — full display string

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

import random

from traveller_orbit_gen import OrbitSlot, SystemOrbits
from traveller_system_gen import TravellerSystem, generate_temperature_from_orbit
from traveller_world_gen import (
    assign_trade_codes,
    generate_atmosphere,
    generate_nhz_atmosphere,
    generate_hydrographics,
    to_hex,
)
from traveller_moon_gen import generate_moons, moons_str, Moon
from traveller_belt_physical import generate_belt_physical, BeltPhysical


# ---------------------------------------------------------------------------
# Dice helpers
# ---------------------------------------------------------------------------

def _roll(n: int, dm: int = 0) -> int:
    return max(0, sum(random.randint(1, 6) for _ in range(n)) + dm)

def _d3() -> int:
    return (random.randint(1, 6) + 1) // 2

_EHEX = "0123456789ABCDEFGHIJ"

def _ehex(n: int) -> str:
    """Encode integer 0-19 as a single eHex character."""
    n = max(0, min(n, len(_EHEX) - 1))
    return _EHEX[n]

def _ehex_to_int(ch: str) -> int:
    """Decode a single eHex character to int; unknown chars return 0."""
    idx = _EHEX.find(ch.upper())
    return idx if idx >= 0 else 0


# ---------------------------------------------------------------------------
# Minimal sustainable Tech Level by atmosphere (WBH p.173)
# ---------------------------------------------------------------------------

def _minimal_tl(atmosphere: int) -> int:
    """
    Minimum TL needed to sustain a population on a world with the given
    atmosphere code (WBH p.173 — Tech Level and Environment table).
    """
    if atmosphere in (0, 1):
        return 8    # vacuum / trace — vacc suits required
    if atmosphere in (2, 3):
        return 5    # very thin / tainted — filter + cold gear
    if atmosphere in (4, 5):
        return 3    # thin — filter mask
    if atmosphere <= 9:
        return 0    # standard / dense — no special gear
    return 8        # A+ exotic / corrosive / insidious — hostile env suits


# ---------------------------------------------------------------------------
# Physical characteristics
# ---------------------------------------------------------------------------

def _terrestrial_size() -> int:
    """Two-stage terrestrial world size roll (WBH p.53-54)."""
    r = random.randint(1, 6)
    if r <= 2:
        return random.randint(1, 6)   # 1-6
    if r <= 4:
        return _roll(2)               # 2-12 (C)
    return _roll(2, 3)                # 5-15 (F)


def _gg_dm(star_spectral: str, star_lum_class: str) -> int:
    """DM for gas giant size category roll (WBH p.55)."""
    if star_spectral == "BD":
        return -1
    if star_spectral == "M" and star_lum_class == "V":
        return -1
    if star_lum_class == "VI":
        return -1
    return 0


def _gas_giant_sah(star_spectral: str, star_lum_class: str) -> str:
    """Generate gas giant SAH string: GS#, GM#, or GL# (WBH p.55)."""
    cat = random.randint(1, 6) + _gg_dm(star_spectral, star_lum_class)
    if cat <= 2:
        return f"GS{_ehex(_d3() + _d3())}"         # 2-6
    if cat <= 4:
        return f"GM{_ehex(random.randint(1,6) + 6)}" # 7-12
    return f"GL{_ehex(_roll(2, 6))}"             # 8-18


def _terrestrial_sah(
    orbit: OrbitSlot,
    hzco: float,
    nhz_atmospheres: bool = False,
) -> tuple[int, int, int]:
    """
    Generate (size, atmosphere, hydrographics) for a terrestrial world.
    Temperature is derived from orbital position for physical consistency.
    Returns (size, atmosphere, hydrographics) as integers.
    """
    size = _terrestrial_size()
    if nhz_atmospheres and abs(orbit.hz_deviation) > 1.0:
        atmosphere, _ = generate_nhz_atmosphere(size, orbit.hz_deviation)
    else:
        atmosphere = generate_atmosphere(min(size, 9))
    temperature = generate_temperature_from_orbit(
        atmosphere=atmosphere,
        hz_deviation=orbit.hz_deviation,
        hzco=hzco,
        orbit=orbit.orbit_number,
    )
    hydrographics = generate_hydrographics(size, atmosphere, temperature)
    return size, atmosphere, hydrographics


# ---------------------------------------------------------------------------
# Social characteristics
# ---------------------------------------------------------------------------

def _secondary_population(max_pop: int) -> int:
    """
    Roll to see if this secondary world has a population and what it is.
    Returns population code 0 (uninhabited) or 1-max_pop.
    Per WBH p.155: check each body; Referee may use 1D result of 5-6 = no pop.
    We use: 1-4 on 1D → has population; 5-6 → uninhabited.
    """
    if max_pop <= 0:
        return 0
    if random.randint(1, 6) >= 5:
        return 0
    return random.randint(1, max_pop)


def _secondary_government(mainworld_pop: int, mainworld_gov: int) -> int:
    """
    Government code for a dependent secondary world (WBH p.161-162).
    We use Case 1 (captive/dependent), which is the most common case.
    Secondary World Government table (1D):
      1 → 0, 2 → 1, 3 → 2, 4 → 3, 5+ → 6
    DMs: Mainworld Gov 0 → DM-2; Mainworld Gov 6 → DM + mainworld pop
    """
    r = random.randint(1, 6)
    if mainworld_gov == 0:
        r = max(1, r - 2)
    elif mainworld_gov == 6:
        r += mainworld_pop
    if r <= 1:
        return 0
    if r <= 2:
        return 1
    if r <= 3:
        return 2
    if r <= 4:
        return 3
    return 6


def _secondary_law_level(government: int, mainworld_law: int) -> int:
    """
    Law Level for a secondary world (WBH p.171).
    For captive governments (6): 1D determines relationship to mainworld.
    For others: standard 2D-7 + Government.
    """
    if government == 6:
        r = random.randint(1, 6)
        if r <= 2:
            return max(0, _roll(2, -7 + 6))       # rerolled for Gov 6
        if r <= 4:
            return mainworld_law                    # equal to mainworld
        if r == 5:
            return mainworld_law + 1                # mainworld + 1
        return mainworld_law + random.randint(1, 6)
    return max(0, _roll(2, -7 + government))


def _secondary_tech_level(atmosphere: int, mainworld_tl: int) -> int:
    """
    Tech Level for a secondary world (WBH p.180).
    = higher of (mainworld TL - 1) or minimal sustainable TL.
    """
    min_tl = _minimal_tl(atmosphere)
    return max(mainworld_tl - 1, min_tl)


def _spaceport(population: int) -> str:
    """
    Spaceport class for an inhabited secondary world (WBH p.195).
    Returns Y/H/G/F (not the full starport A-X scale).
    """
    dm = 0
    if population >= 6:
        dm = 2
    elif population == 1:
        dm = -1
    r = random.randint(1, 6) + dm
    if r <= 2:
        return "Y"
    if r == 3:
        return "H"
    if r <= 5:
        return "G"
    return "F"


# ---------------------------------------------------------------------------
# WorldDetail dataclass attached to each OrbitSlot
# ---------------------------------------------------------------------------

class WorldDetail:  # pylint: disable=too-many-instance-attributes
    """Physical and social details for one orbit slot."""

    __slots__ = ("sah", "population", "government", "law_level",
                 "tech_level", "spaceport", "moons", "trade_codes", "physical")

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
            self, sah: str, population: int = 0, government: int = 0,
            law_level: int = 0, tech_level: int = 0, spaceport: str = "-",
            moons: list[Moon] | None = None):
        self.sah        = sah
        self.population = population
        self.government = government
        self.law_level  = law_level
        self.tech_level = tech_level
        self.spaceport  = spaceport
        self.moons      = moons if moons is not None else []
        self.physical: BeltPhysical | None = None
        # Gas giants and rings carry no trade codes
        if (len(sah) == 3 and sah[0] == "G" and sah[1] in ("S", "M", "L")) \
                or (len(sah) >= 1 and sah[0] == "R"):
            self.trade_codes: list[str] = []
        else:
            # "S" (sub-planetary) is not a size-0 asteroid; treat as 1
            sz_ch = sah[0] if len(sah) > 0 else "0"
            sz   = 1 if sz_ch == "S" else _ehex_to_int(sz_ch)
            atm  = _ehex_to_int(sah[1]) if len(sah) > 1 else 0
            hyd  = _ehex_to_int(sah[2]) if len(sah) > 2 else 0
            self.trade_codes = assign_trade_codes(
                sz, atm, hyd, population, government, law_level, tech_level,
            )

    @property
    def inhabited(self) -> bool:
        """True if this world has a non-zero population."""
        return self.population > 0

    @property
    def is_gas_giant(self) -> bool:
        """True if this world is a gas giant (SAH starts with GS/GM/GL)."""
        return (len(self.sah) == 3
                and self.sah[0] == "G"
                and self.sah[1] in ("S", "M", "L"))

    @property
    def profile(self) -> str:
        """
        Short display profile:
          Gas giants: size code only, no spaceport or social codes
            e.g. "GS4"  "GM9"  "GLB"
          Uninhabited terrestrial/belt: 'Y' + SAH + '000' + TL
            e.g. "Y473000-0"  "Y000000-0"
          Inhabited terrestrial: spaceport + SAH + PGL + TL
            e.g. "F473510-7"
        Terrestrial worlds use no dash between SAH and social codes.
        Belts retain the Y prefix and social codes for consistency.
        """
        if self.is_gas_giant:
            return self.sah
        if not self.inhabited:
            return f"Y{self.sah}000-0"
        return (f"{self.spaceport}{self.sah}"
                f"{to_hex(self.population)}{to_hex(self.government)}"
                f"{to_hex(self.law_level)}"
                f"-{to_hex(self.tech_level)}")

    def to_dict(self) -> dict:
        """Serialise this WorldDetail to a JSON-compatible dict."""
        return {
            "sah":         self.sah,
            "population":  self.population,
            "government":  self.government,
            "law_level":   self.law_level,
            "tech_level":  self.tech_level,
            "spaceport":   self.spaceport,
            "inhabited":   self.inhabited,
            "profile":     self.profile,
            "trade_codes": self.trade_codes,
            "moons_str":   moons_str(self.moons),
            "moons":       [m.to_dict() for m in self.moons],
            "physical":    self.physical.to_dict() if self.physical is not None else None,
        }



def _moon_adjacency_context(
        orbit_number: float,
        star_designation: str,
        system_orbits: SystemOrbits,
        stellar_system,
) -> dict:
    """
    Build the three adjacency DM keyword args for generate_moons() (WBH p.56).

    Returns a dict with keys star_mao, companion_exclusion_zones,
    is_adjacent_outermost_far — unpack directly into generate_moons(**ctx).
    """
    # Condition: adjacent to a companion's exclusion zone
    zones = []
    for star in stellar_system.stars:
        if star.designation == star_designation:
            continue
        role = getattr(star, "role", "")
        if role in ("Close", "Near", "Far"):
            lo = star.orbit_number - 1.0
            hi = star.orbit_number + 3.0
            zones.append((lo, hi))

    # Condition: adjacent to the host star's MAO boundary
    mao = system_orbits.star_mao.get(star_designation, 0.0)

    # Condition: adjacent to outermost slot of any Far star
    far_stars = [s for s in stellar_system.stars if getattr(s, "role", "") == "Far"]
    is_adj_far = False
    if far_stars:
        far_desig = far_stars[-1].designation
        far_orbit_numbers = [
            o.orbit_number for o in system_orbits.orbits
            if o.star_designation == far_desig
        ]
        if far_orbit_numbers:
            outermost = max(far_orbit_numbers)
            is_adj_far = abs(orbit_number - outermost) <= 1.0

    return {
        "star_mao": mao,
        "companion_exclusion_zones": zones or None,
        "is_adjacent_outermost_far": is_adj_far,
    }


def _moons_for(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        detail: WorldDetail, orbit_number: float,
        orbit_au: float = 0.0,
        planet_ecc: float = 0.0,
        star_mass_solar: float = 0.0,
        adjacency_ctx: dict | None = None) -> list:
    """Generate moons for a WorldDetail based on its SAH and orbital context."""
    sah = detail.sah
    ctx = adjacency_ctx or {}
    if sah == "000":                      # belt — no moons
        return []
    if detail.is_gas_giant:
        cat = sah[1]                      # S, M, or L
        diam_hex = sah[2]
        diam = _EHEX.index(diam_hex) if diam_hex in _EHEX else 8
        return generate_moons(
            size_code=diam, orbit_number=orbit_number,
            is_gas_giant=True, gg_category=cat, gg_diameter=diam,
            orbit_au=orbit_au, star_mass_solar=star_mass_solar, planet_ecc=planet_ecc,
            **ctx,
        )
    # Terrestrial
    try:
        sz = int(sah[0], 16)
    except ValueError:
        sz = 1
    return generate_moons(
        size_code=sz, orbit_number=orbit_number,
        orbit_au=orbit_au, star_mass_solar=star_mass_solar, planet_ecc=planet_ecc,
        **ctx,
    )


def _moon_detail(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-return-statements
    moon: Moon,
    hz_deviation: float,
    hzco: float,
    orbit_number: float,
    mw_pop: int,
    mw_gov: int,
    mw_law: int,
    mw_tl: int,
    max_secondary_pop: int,
    nhz_atmospheres: bool = False,
) -> "WorldDetail":
    """
    Generate full WorldDetail for a significant moon (WBH pp.57, 78-99, 155-180).

    Temperature is determined by the *parent planet's* orbital position,
    since the moon shares that distance from the star (WBH p.108 example).

    Physical rules:
      Ring (is_ring=True)    : SAH = "R00", always uninhabited
      Size S                 : SAH = "S00", atm/hydro auto-0 (too small)
      Size 0-1 (numeric)     : SAH = "{size}00", atm/hydro auto-0
      Size 2+ (numeric)      : generate_atmosphere(size), generate_hydrographics()
                               using parent orbit temperature
      Gas giant moon         : SAH = GS{diam}, always uninhabited (gas giant)
    Social:
      Same pipeline as orbital secondary worlds — population roll, TL viability
      check, government, law, tech level, spaceport.
    """
    # ── Physical ──────────────────────────────────────────────────────────
    if moon.is_ring:
        return WorldDetail(sah="R00")

    if moon.is_gas_giant_moon:
        # Moon is itself a small gas giant — no atmosphere/hydro/social
        diam = int(moon.size_code) if not isinstance(moon.size_code, str) else 2
        sah = f"GS{_ehex(diam)}"
        return WorldDetail(sah=sah)

    if moon.size_code == "S":
        return WorldDetail(sah="S00")

    sz = int(moon.size_code)

    if sz <= 1:
        # Size 0-1: auto vacuum, no hydrographics
        sah = f"{to_hex(sz)}00"
        # Still check for (very minimal) population — vacuum requires TL 8
        pop = _secondary_population(max_secondary_pop)
        if pop > 0 and _minimal_tl(0) > mw_tl:
            pop = 0
        if pop == 0:
            return WorldDetail(sah=sah)
        gov  = _secondary_government(mw_pop, mw_gov)
        law  = _secondary_law_level(gov, mw_law)
        tl   = _secondary_tech_level(0, mw_tl)
        port = _spaceport(pop)
        return WorldDetail(sah=sah, population=pop, government=gov,
                           law_level=law, tech_level=tl, spaceport=port)

    # Size 2+: generate atmosphere and hydrographics
    if nhz_atmospheres and abs(hz_deviation) > 1.0:
        atmosphere, _ = generate_nhz_atmosphere(sz, hz_deviation)
    else:
        atmosphere = generate_atmosphere(min(sz, 9))
    temperature = generate_temperature_from_orbit(
        atmosphere=atmosphere,
        hz_deviation=hz_deviation,
        hzco=hzco,
        orbit=orbit_number,
    )
    hydrographics = generate_hydrographics(sz, atmosphere, temperature)
    sah = f"{to_hex(sz)}{to_hex(atmosphere)}{to_hex(hydrographics)}"

    # ── Social ────────────────────────────────────────────────────────────
    pop = _secondary_population(max_secondary_pop)
    min_tl = _minimal_tl(atmosphere)
    if pop > 0 and min_tl > mw_tl:
        pop = 0
    if pop == 0:
        return WorldDetail(sah=sah)
    gov  = _secondary_government(mw_pop, mw_gov)
    law  = _secondary_law_level(gov, mw_law)
    tl   = _secondary_tech_level(atmosphere, mw_tl)
    port = _spaceport(pop)
    return WorldDetail(sah=sah, population=pop, government=gov,
                       law_level=law, tech_level=tl, spaceport=port)

# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

def generate_system_detail(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    system: TravellerSystem,
    nhz_atmospheres: bool = False,
) -> dict[str, WorldDetail]:
    """
    Generate WorldDetail for every non-mainworld, non-empty orbit slot.

    Returns a dict mapping "{star_designation}-{slot_index}" → WorldDetail.
    """
    orbits: SystemOrbits = system.system_orbits
    mainworld = system.mainworld

    # Determine system-wide secondary population cap (WBH p.155)
    mw_pop  = mainworld.population if mainworld else 0
    mw_gov  = mainworld.government if mainworld else 0
    mw_law  = mainworld.law_level  if mainworld else 0
    mw_tl   = mainworld.tech_level if mainworld else 0

    max_secondary_pop = max(0, mw_pop - random.randint(1, 6))

    primary = system.stellar_system.primary

    # Belt physical: precompute per-star orbit generation spreads (WBH p.131).
    # Spread = (max Orbit# − MAO) / n_orbits — the per-slot step used in orbit
    # placement; this is what WBH calls "system orbit spread" in the span formula.
    non_empty = [o for o in orbits.orbits if o.world_type != "empty"]
    outermost_au = max((o.orbit_au for o in non_empty), default=0.0)
    star_orbit_spreads: dict[str, float] = {}
    for _desig in {o.star_designation for o in non_empty}:
        _star_ne = [o for o in non_empty if o.star_designation == _desig]
        _mao = orbits.star_mao.get(_desig, 0.0)
        _max_orb = max(o.orbit_number for o in _star_ne)
        star_orbit_spreads[_desig] = (
            (_max_orb - _mao) / len(_star_ne) if _star_ne else 0.0
        )
    is_exploited = (mainworld is not None
                    and "In" in mainworld.trade_codes
                    and mainworld.tech_level >= 8)

    result: dict[str, WorldDetail] = {}

    for orbit in orbits.orbits:
        if orbit.is_mainworld_candidate:
            continue
        if orbit.world_type == "empty":
            continue

        key  = f"{orbit.star_designation}-{orbit.slot_index}"
        hzco = orbits.star_hzco.get(orbit.star_designation, 1.0)

        host = next(
            (s for s in system.stellar_system.stars
             if s.designation == orbit.star_designation),
            primary,
        )

        if orbit.world_type == "belt":
            # Belts can be inhabited (WBH p.163 — Mining Facility classification).
            # Physical profile is always 000; social codes follow the same
            # procedure as terrestrials but using atmosphere 0 (vacuum), which
            # requires TL 8 to sustain — so belts are only inhabited when the
            # mainworld TL is high enough.
            belt_atm = 0
            pop = _secondary_population(max_secondary_pop)
            if pop > 0 and _minimal_tl(belt_atm) > mw_tl:
                pop = 0
            if pop == 0:
                result[key] = WorldDetail(sah="000")
            else:
                gov  = _secondary_government(mw_pop, mw_gov)
                law  = _secondary_law_level(gov, mw_law)
                tl   = _secondary_tech_level(belt_atm, mw_tl)
                port = _spaceport(pop)
                result[key] = WorldDetail(
                    sah="000", population=pop, government=gov,
                    law_level=law, tech_level=tl, spaceport=port,
                )
            # Belt physical detail (WBH pp.131-133)
            same_star_outward = sorted(
                [o for o in orbits.orbits
                 if o.star_designation == orbit.star_designation
                 and o.orbit_au > orbit.orbit_au
                 and o.world_type != "empty"],
                key=lambda o: o.orbit_au,
            )
            next_is_gg = bool(same_star_outward
                              and same_star_outward[0].world_type == "gas_giant")
            result[key].physical = generate_belt_physical(
                orbit_au=orbit.orbit_au,
                hz_deviation=orbit.hz_deviation,
                age_gyr=primary.age_gyr or 0.0,
                orbit_spread=star_orbit_spreads.get(orbit.star_designation, 0.0),
                next_is_gas_giant=next_is_gg,
                is_outermost=orbit.orbit_au >= outermost_au,
                is_exploited=is_exploited,
            )

        elif orbit.world_type == "gas_giant":
            # Gas giants: never directly inhabited (moons are out of scope).
            # Reuse the SAH rolled at orbit-gen time if available so the
            # diameter seen here matches the mainworld satellite size constraint.
            sah = (orbit.gg_sah if orbit.gg_sah
                   else _gas_giant_sah(host.spectral_type, host.lum_class))
            result[key] = WorldDetail(sah=sah)

        else:
            # Terrestrial world
            size, atm, hydro = _terrestrial_sah(orbit, hzco, nhz_atmospheres)
            sah = f"{to_hex(size)}{to_hex(atm)}{to_hex(hydro)}"

            # Check for population
            pop = _secondary_population(max_secondary_pop)

            # Check TL viability — if min sustainable TL > mainworld TL,
            # this world cannot be inhabited
            min_tl = _minimal_tl(atm)
            if pop > 0 and min_tl > mw_tl:
                pop = 0   # too hostile given available technology

            if pop == 0:
                result[key] = WorldDetail(sah=sah)
            else:
                gov  = _secondary_government(mw_pop, mw_gov)
                law  = _secondary_law_level(gov, mw_law)
                tl   = _secondary_tech_level(atm, mw_tl)
                port = _spaceport(pop)
                result[key] = WorldDetail(
                    sah=sah, population=pop, government=gov,
                    law_level=law, tech_level=tl, spaceport=port,
                )

    # Attach moons and their full detail to every WorldDetail
    for key, world_detail in result.items():
        desig, slot_str = key.rsplit("-", 1)
        slot_idx = int(slot_str)
        matching = [o for o in orbits.orbits
                    if o.star_designation == desig and o.slot_index == slot_idx]
        if not matching:
            continue
        parent_orbit = matching[0]
        on        = parent_orbit.orbit_number
        hzco_here = orbits.star_hzco.get(desig, 1.0)
        hz_dev    = parent_orbit.hz_deviation

        host_for_moon = next(
            (s for s in system.stellar_system.stars if s.designation == desig),
            system.stellar_system.primary,
        )
        world_detail.moons = _moons_for(
            world_detail, on,
            orbit_au=parent_orbit.orbit_au,
            planet_ecc=parent_orbit.eccentricity,
            star_mass_solar=host_for_moon.mass,
            adjacency_ctx=_moon_adjacency_context(
                on, desig, orbits, system.stellar_system),
        )

        # Generate full SAH + social detail for every significant moon
        for moon in world_detail.moons:
            if not moon.is_ring:
                moon.detail = _moon_detail(
                    moon=moon,
                    hz_deviation=hz_dev,
                    hzco=hzco_here,
                    orbit_number=on,
                    mw_pop=mw_pop,
                    mw_gov=mw_gov,
                    mw_law=mw_law,
                    mw_tl=mw_tl,
                    max_secondary_pop=max_secondary_pop,
                    nhz_atmospheres=nhz_atmospheres,
                )

    return result


def attach_detail(system: TravellerSystem) -> None:  # pylint: disable=too-many-locals,too-many-branches
    """
    Compute WorldDetail for all orbits and attach as `orbit.detail`
    on each OrbitSlot. Also attaches detail for the mainworld orbit
    (extracting values from the mainworld World object).
    """
    nhz = system.nhz_atmospheres
    detail_map = generate_system_detail(system, nhz_atmospheres=nhz)
    mainworld  = system.mainworld

    for orbit in system.system_orbits.orbits:
        key = f"{orbit.star_designation}-{orbit.slot_index}"

        if orbit.is_mainworld_candidate and mainworld:
            uwp = mainworld.uwp()
            sah = uwp[1:4]   # strip starport prefix: "C473574-8" → "473"
            # If the mainworld orbit is a belt, size is effectively 0 regardless
            # of what the World object says — the CRB world generation doesn't
            # know its host orbit type. Belts cannot have significant moons.
            if orbit.world_type == "belt":
                mw_size = 0
            else:
                mw_size = int(mainworld.uwp()[1], 16) if mainworld.uwp()[1] not in ('S',) else 1
            phys    = mainworld.size_detail if mainworld else None
            mw_diam = phys.diameter_km if phys and not isinstance(phys, BeltPhysical) else 0.0
            mw_mass = phys.mass        if phys and not isinstance(phys, BeltPhysical) else 0.0
            mw_ctx = _moon_adjacency_context(
                orbit.orbit_number, orbit.star_designation,
                system.system_orbits, system.stellar_system,
            )
            mw_moons = generate_moons(
                mw_size, orbit.orbit_number,
                orbit_au=orbit.orbit_au,
                planet_ecc=orbit.eccentricity,
                star_mass_solar=system.stellar_system.primary.mass,
                planet_diameter_km=mw_diam,
                planet_mass_earth=mw_mass,
                **mw_ctx,
            )
            mw_hzco   = system.system_orbits.star_hzco.get(orbit.star_designation, 1.0)
            mw_hz_dev = orbit.hz_deviation
            for moon in mw_moons:
                if not moon.is_ring:
                    moon.detail = _moon_detail(
                        moon=moon,
                        hz_deviation=mw_hz_dev,
                        hzco=mw_hzco,
                        orbit_number=orbit.orbit_number,
                        mw_pop=mainworld.population,
                        mw_gov=mainworld.government,
                        mw_law=mainworld.law_level,
                        mw_tl=mainworld.tech_level,
                        max_secondary_pop=max(0, mainworld.population - random.randint(1,6)),
                        nhz_atmospheres=nhz,
                    )
            # WorldDetail for the satellite body itself (with its own moons).
            satellite_detail = WorldDetail(
                sah=sah,
                population=mainworld.population,
                government=mainworld.government,
                law_level=mainworld.law_level,
                tech_level=mainworld.tech_level,
                spaceport=mainworld.starport,
                moons=mw_moons,
            )
            if orbit.world_type == "gas_giant":
                # The orbit slot holds the gas giant; the mainworld is its
                # satellite.  Represent the satellite as the first moon sub-row
                # so the orbit table shows its UWP beneath the gas giant profile.
                satellite_moon = Moon(size_code=mw_size)
                satellite_moon.detail = satellite_detail
                orbit.detail = WorldDetail(
                    sah=orbit.gg_sah,
                    population=0,
                    government=0,
                    law_level=0,
                    tech_level=0,
                    spaceport="-",
                    moons=[satellite_moon],
                )
            else:
                orbit.detail = satellite_detail
        elif orbit.world_type == "empty":
            orbit.detail = None
        else:
            orbit.detail = detail_map.get(key)

    # Belt physical for belt mainworld — mirrors secondary belt logic in
    # generate_system_detail(), placed here to avoid seed disruption for
    # secondary belts that are processed earlier in that function.
    if (mainworld is not None and mainworld.size == 0
            and system.mainworld_orbit is not None):
        mw_orbit = system.mainworld_orbit
        orbits_obj = system.system_orbits
        non_empty = [o for o in orbits_obj.orbits if o.world_type != "empty"]
        outermost_au = max((o.orbit_au for o in non_empty), default=0.0)
        mw_desig = mw_orbit.star_designation
        mw_star_ne = [o for o in non_empty if o.star_designation == mw_desig]
        mw_mao = orbits_obj.star_mao.get(mw_desig, 0.0)
        mw_max_orb = max(
            (o.orbit_number for o in mw_star_ne), default=mw_mao
        )
        orbit_spread = (
            (mw_max_orb - mw_mao) / len(mw_star_ne) if mw_star_ne else 0.0
        )
        same_star_outward = sorted(
            [o for o in orbits_obj.orbits
             if o.star_designation == mw_orbit.star_designation
             and o.orbit_au > mw_orbit.orbit_au
             and o.world_type != "empty"],
            key=lambda o: o.orbit_au,
        )
        next_is_gg = bool(same_star_outward
                          and same_star_outward[0].world_type == "gas_giant")
        is_exploited = "In" in mainworld.trade_codes and mainworld.tech_level >= 8
        bp = generate_belt_physical(
            orbit_au=mw_orbit.orbit_au,
            hz_deviation=mw_orbit.hz_deviation,
            age_gyr=system.stellar_system.primary.age_gyr or 0.0,
            orbit_spread=orbit_spread,
            next_is_gas_giant=next_is_gg,
            is_outermost=mw_orbit.orbit_au >= outermost_au,
            is_exploited=is_exploited,
        )
        if mw_orbit.detail is not None:
            mw_orbit.detail.physical = bp
        mainworld.size_detail = bp


def system_body_table(system: TravellerSystem) -> str:  # pylint: disable=too-many-locals
    """
    Formatted table of all orbits with their physical and social profiles.
    Mainworld shows full UWP; inhabited secondaries show spaceport+SAH+PGL+TL;
    uninhabited worlds show SAH only.
    """
    attach_detail(system)
    orbits = system.system_orbits

    lines = [
        "=" * 100,
        f"  {'Star':<5} {'#':<4} {'Orbit#':<8} {'AU':<9} "
        f"{'Type':<14} {'Profile':<22} {'Codes':<18} {'Moons':<20} {'Zone'}",
        "  " + "-" * 96,
    ]

    for o in orbits.orbits:
        detail = o.detail
        mw_mark = " ← mainworld" if o.is_mainworld_candidate else ""
        if o.is_mainworld_candidate and system.mainworld:
            profile = system.mainworld.uwp()
            codes_str = " ".join(system.mainworld.trade_codes)
        elif detail is None:
            profile = "---"
            codes_str = ""
        else:
            profile = detail.profile
            codes_str = " ".join(detail.trade_codes)

        moon_list = (getattr(detail, "moons", None) or []) if detail else []
        moons_display = moons_str(moon_list)
        lines.append(
            f"  {o.star_designation:<5} {o.slot_index:<4} "
            f"{o.orbit_number:<8.2f} {o.orbit_au:<9.3f} "
            f"{o.world_type:<14} {profile:<22} "
            f"{codes_str:<18} "
            f"{moons_display:<20} "
            f"{o.temperature_zone}{mw_mark}"
        )
        # Moon sub-rows: indented, showing SAH+social profile and trade codes
        for mi, moon in enumerate(moon_list, 1):
            if moon.is_ring:
                ring_count = moon.ring_count
                moon_profile = f"R{ring_count:02d}"
                moon_codes_str = ""
                moon_sah_str = "ring system"
            elif moon.detail is not None:
                d = moon.detail
                moon_profile = d.profile
                moon_codes_str = " ".join(d.trade_codes)
                moon_sah_str = f"size {moon.size_str}"
            else:
                moon_profile = f"size {moon.size_str}"
                moon_codes_str = ""
                moon_sah_str = ""
            lines.append(
                f"     {'':5} {'':4} {'':8} {'':9} "
                f"  {'moon '+str(mi):<12} {moon_profile:<22} "
                f"{moon_codes_str:<18} "
                f"{'':20} {moon_sah_str}"
            )

    lines.append("=" * 100)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    from traveller_system_gen import generate_full_system  # pylint: disable=import-outside-toplevel,ungrouped-imports

    parser = argparse.ArgumentParser(
        description="Generate a complete system with SAH/UWP for all worlds."
    )
    parser.add_argument("--name", default="Unknown")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    sys = generate_full_system(name=args.name, seed=args.seed)
    print(sys.stellar_system.summary())
    print()
    print(system_body_table(sys))
