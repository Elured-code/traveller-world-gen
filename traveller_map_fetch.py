"""
traveller_map_fetch.py
======================
Fetch canonical world and stellar data from the TravellerMap public API
(https://travellermap.com) and generate a fully detailed Traveller star system.

The canonical UWP and stellar classification string are preserved exactly as
published in the Second Survey data.  Orbital structure, secondary world
profiles, and satellite data are generated procedurally from the canonical
stellar data, so the output differs between runs unless a seed is provided.

Sector is always required to avoid ambiguity — many world names (e.g. "Regina",
"Mora") appear in multiple sectors across the Traveller universe.

Usage — command line
--------------------
    # By world name + sector (sector always required)
    python traveller_map_fetch.py --name Regina --sector "Spinward Marches"
    python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --seed 42 --detail
    python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --format json
    python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --html > regina.html

    # By sector + hex
    python traveller_map_fetch.py --sector "Spinward Marches" --hex 1910
    python traveller_map_fetch.py --sector "Spinward Marches" --hex 1910 --seed 42

Usage — Python API
------------------
    from traveller_map_fetch import generate_system_from_map

    # By name + sector (sector always required with name)
    system = generate_system_from_map(
        name="Regina", sector="Spinward Marches", seed=42, attach=True
    )
    print(system.summary())

    # By location
    system = generate_system_from_map(
        sector="Spinward Marches", hex_pos="1910", seed=42
    )
    print(system.to_json())

Data provenance
---------------
Canonical data (UWP, stellar classification, bases, trade codes, travel zone,
PBG) is sourced from the TravellerMap API and is copyright the respective
publishers.  All procedurally generated content (orbital structure, secondary
worlds, moons) is produced by this project's generation modules.

Requires network access to https://travellermap.com.  No third-party packages
are needed beyond the project's existing requirements.txt — the standard
library urllib is used for HTTP.

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

import json
import random
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Tuple

from traveller_stellar_gen import (
    Star,
    StarSystem,
    _generate_system_age,
    _main_sequence_lifespan,
    _secondary_orbit,
    _star_properties,
)
from traveller_orbit_gen import generate_orbits
from traveller_system_gen import TravellerSystem, generate_temperature_from_orbit
from traveller_world_gen import World
from traveller_world_detail import attach_detail


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRAVELLERMAP_BASE = "https://travellermap.com"
SEARCH_ENDPOINT   = f"{TRAVELLERMAP_BASE}/api/search"
DATA_ENDPOINT     = f"{TRAVELLERMAP_BASE}/data"

_HEX_MAP = {ch: i for i, ch in enumerate("0123456789ABCDEFG")}

_VALID_LUM_CLASSES = {"Ia", "Ib", "II", "III", "IV", "V", "VI"}

_VALID_TRADE_CODES = {
    "Ag", "As", "Ba", "De", "Fl", "Ga", "Hi", "Ht", "Ic", "In",
    "Lo", "Lt", "Na", "Ni", "Po", "Ri", "Va", "Wa",
}

# Secondary star role order for multi-star systems read from TravellerMap.
# TravellerMap gives classification strings only; orbital separation is unknown,
# so we assign close → near → far for the 2nd, 3rd, 4th+ stars.
_SECONDARY_ROLES = ["close", "near", "far"]


# ---------------------------------------------------------------------------
# Raw data container
# ---------------------------------------------------------------------------

@dataclass
class MapWorldData:  # pylint: disable=too-many-instance-attributes
    """World data as returned by TravellerMap before reconstruction."""
    name:      str   # canonical world name
    sector:    str   # sector name
    hex_pos:   str   # 4-digit hex, e.g. "1910"
    uwp:       str   # Universal World Profile, e.g. "A788899-C"
    bases:     str   # base letter string, e.g. "NW"
    remarks:   str   # trade codes + extensions, e.g. "Ri Ph An Cp"
    zone:      str   # "" / " " = Green, "A" = Amber, "R" = Red
    pbg:       str   # Population-Belt-Gas digit string, e.g. "703"
    stars_str: str   # stellar classification, e.g. "G2 V M7 V"


# ---------------------------------------------------------------------------
# TravellerMap API
# ---------------------------------------------------------------------------

def _raw_field(raw: dict, *keys: str, default: str = "") -> str:
    """
    Extract a string field from a TravellerMap API record.

    Tries each key in order, then falls back to a case-insensitive scan of
    the entire record.  TravellerMap has changed field capitalisation across
    API versions (e.g. UWP / Uwp, Stars / Stellar, PBG / Pbg), so checking
    both is necessary for reliable extraction.
    """
    for key in keys:
        val = raw.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    raw_ci = {k.lower(): v for k, v in raw.items()}
    for key in keys:
        val = raw_ci.get(key.lower())
        if val is not None and str(val).strip():
            return str(val).strip()
    return default


def _world_sector_name(world_record: dict) -> str:
    """Extract the sector name from a TravellerMap world record."""
    raw = world_record.get("Sector", "")
    if isinstance(raw, dict):
        return raw.get("Name", "")
    return str(raw)


def _name_to_hex(name: str, sector: str, timeout: int = 10) -> str:
    """
    Search TravellerMap for a world by name within a sector and return its
    4-digit hex position string (e.g. "1910").

    The search endpoint returns limited data (no UWP details), but it does
    provide HexX / HexY coordinates which we use to build the hex string for
    a subsequent full-data lookup.

    Raises
    ------
    LookupError  if the world is not found in the specified sector.
    urllib.error.URLError  on network failure.
    """
    url = f"{SEARCH_ENDPOINT}?{urllib.parse.urlencode({'q': name})}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "traveller-world-gen/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    items  = data.get("Results", {}).get("Items", [])
    worlds = [item["World"] for item in items if "World" in item]

    sector_worlds = [
        w for w in worlds
        if _world_sector_name(w).lower() == sector.lower()
    ]
    if not sector_worlds:
        raise LookupError(
            f"No worlds found in sector '{sector}' matching '{name}'."
        )

    for w in sector_worlds:
        if w.get("Name", "").lower() == name.lower():
            hex_x = int(w.get("HexX", 0))
            hex_y = int(w.get("HexY", 0))
            return f"{hex_x:02d}{hex_y:02d}"

    raise LookupError(
        f"'{name}' not found in sector '{sector}'. "
        f"Found: {', '.join(w.get('Name', '?') for w in sector_worlds[:5])}."
    )


def _fetch_world_json(
    name:    Optional[str] = None,
    sector:  Optional[str] = None,
    hex_pos: Optional[str] = None,
    timeout: int = 10,
) -> dict:
    """
    Fetch one world's full JSON record from the TravellerMap data API.

    Uses the /data/{sector}/{hex} endpoint which returns the complete world
    profile (UWP, PBG, Bases, Remarks, Zone, Stellar).  If only a name is
    supplied, the search API is called first to resolve the hex position.

    Sector is always required.  Supply name or hex_pos to identify the world.

    Raises
    ------
    ValueError     if sector is missing, or neither name nor hex_pos supplied.
    LookupError    if no matching world is found.
    urllib.error.URLError  on network failure or HTTP error.
    """
    if not sector:
        raise ValueError("Sector is required to avoid ambiguity.")
    if not name and not hex_pos:
        raise ValueError("Supply name or hex_pos (both require sector).")

    # Resolve name → hex if needed
    if not hex_pos:
        hex_pos = _name_to_hex(name, sector, timeout=timeout)

    encoded_sector = urllib.parse.quote(sector, safe="")
    url = f"{DATA_ENDPOINT}/{encoded_sector}/{hex_pos}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "traveller-world-gen/1.0",
                      "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    worlds = data.get("Worlds", [])
    if not worlds:
        raise LookupError(
            f"No world at hex {hex_pos} in sector '{sector}'."
        )
    return worlds[0]


def fetch_world_data(
    name:    Optional[str] = None,
    sector:  Optional[str] = None,
    hex_pos: Optional[str] = None,
) -> MapWorldData:
    """
    Fetch a world from TravellerMap and return a MapWorldData.

    Supply name for a name search, or sector + hex_pos for a direct lookup.
    Both may be supplied — the location is then used for disambiguation.
    """
    raw = _fetch_world_json(name=name, sector=sector, hex_pos=hex_pos)

    # /data endpoint returns Sector as a plain string
    sector_name = _world_sector_name(raw) or sector or "Unknown"

    return MapWorldData(
        name      = _raw_field(raw, "Name",                     default=name    or "Unknown"),
        sector    = sector_name,
        hex_pos   = _raw_field(raw, "Hex",                      default=hex_pos or "0000"),
        uwp       = _raw_field(raw, "UWP", "Uwp",               default="X000000-0"),
        bases     = _raw_field(raw, "Bases", "Base",             default=""),
        remarks   = _raw_field(raw, "Remarks", "Remark",         default=""),
        zone      = _raw_field(raw, "Zone", "TravelCode",        default=""),
        pbg       = _raw_field(raw, "PBG", "Pbg",               default="000"),
        stars_str = _raw_field(raw, "Stellar", "Stars", "Star",  default="G2 V"),
    )


# ---------------------------------------------------------------------------
# UWP parsing
# ---------------------------------------------------------------------------

def _from_hex(ch: str) -> int:
    """Convert a single Traveller hex digit to int (0–16)."""
    return _HEX_MAP.get(ch.upper(), 0)


def parse_uwp(uwp_str: str) -> dict:
    """
    Parse a UWP string (e.g. 'A788899-C') into a dict of characteristic
    integer values.

    Returns sensible zero-defaults if the string is malformed.

    Keys: starport (str), size, atmosphere, hydrographics, population,
          government, law_level, tech_level (all int).
    """
    s = uwp_str.strip().replace(" ", "")
    if len(s) < 9 or s[7] != "-":
        return {
            "starport": "X", "size": 0, "atmosphere": 0,
            "hydrographics": 0, "population": 0, "government": 0,
            "law_level": 0, "tech_level": 0,
        }
    return {
        "starport":      s[0].upper(),
        "size":          _from_hex(s[1]),
        "atmosphere":    _from_hex(s[2]),
        "hydrographics": _from_hex(s[3]),
        "population":    _from_hex(s[4]),
        "government":    _from_hex(s[5]),
        "law_level":     _from_hex(s[6]),
        "tech_level":    _from_hex(s[8]),
    }


# ---------------------------------------------------------------------------
# Stellar string parsing and StarSystem reconstruction
# ---------------------------------------------------------------------------

def parse_stellar_string(
    stars_str: str,
) -> List[Tuple[str, Optional[int], str]]:
    """
    Parse a TravellerMap stellar classification string into a list of
    (spectral_type, subtype, lum_class) tuples.

    Handles main-sequence stars ('G2 V'), white dwarfs ('D'), brown dwarfs
    ('BD'), and all luminosity classes (Ia, Ib, II–VI).  Always returns at
    least one entry, defaulting to G2 V on parse failure.

    Examples
    --------
    'G2 V'          → [('G', 2, 'V')]
    'G2 V M7 V'     → [('G', 2, 'V'), ('M', 7, 'V')]
    'K3 IV D'       → [('K', 3, 'IV'), ('D', None, 'D')]
    'BD'            → [('BD', None, 'BD')]
    'M0 V M5 VI D'  → [('M', 0, 'V'), ('M', 5, 'VI'), ('D', None, 'D')]
    """
    tokens  = stars_str.strip().split()
    results: List[Tuple[str, Optional[int], str]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "BD":
            results.append(("BD", None, "BD"))
            i += 1
        elif tok == "D":
            results.append(("D", None, "D"))
            i += 1
        elif (len(tok) >= 2
              and tok[0] in "OBAFGKM"
              and tok[1].isdigit()):
            spectral = tok[0]
            subtype  = int(tok[1])
            if (i + 1 < len(tokens)
                    and tokens[i + 1] in _VALID_LUM_CLASSES):
                lum_class = tokens[i + 1]
                i += 2
            else:
                lum_class = "V"
                i += 1
            results.append((spectral, subtype, lum_class))
        else:
            i += 1

    return results if results else [("G", 2, "V")]


def reconstruct_star_system(stars_str: str) -> StarSystem:  # pylint: disable=too-many-locals
    """
    Build a StarSystem from a TravellerMap stellar classification string.

    Physical properties (mass, luminosity, diameter, temperature) are derived
    from the canonical classification using the same WBH lookup tables as the
    procedural generator.  System age is rolled randomly (seeded if a seed was
    set before calling this function).

    Secondary stars (2nd, 3rd, …) receive designations B, C, … and random
    orbital positions (close → near → far), so their exact Orbit# values
    vary per seed.  The star classifications themselves are fixed by the
    canonical data.
    """
    parsed = parse_stellar_string(stars_str)
    system = StarSystem()

    # Primary star
    sp0, sub0, lum0          = parsed[0]
    mass0, temp0, diam0, lum_val0 = _star_properties(sp0, sub0, lum0)
    ms_life0                 = _main_sequence_lifespan(mass0)
    age                      = _generate_system_age(mass0, ms_life0)

    primary = Star(
        designation   = "A",
        role          = "primary",
        spectral_type = sp0,
        subtype       = sub0,
        lum_class     = lum0,
        mass          = mass0,
        temperature   = temp0,
        diameter      = diam0,
        luminosity    = lum_val0,
        orbit_number  = 0.0,
        orbit_au      = 0.0,
        age_gyr       = age,
        ms_lifespan_gyr = ms_life0,
    )
    system.stars.append(primary)

    # Secondary stars
    desig_ord = ord("B")
    for idx, (sp, sub, lum) in enumerate(parsed[1:]):
        mass_s, temp_s, diam_s, lum_s = _star_properties(sp, sub, lum)
        ms_life_s    = _main_sequence_lifespan(mass_s)
        role         = _SECONDARY_ROLES[min(idx, len(_SECONDARY_ROLES) - 1)]
        orbit_num, orbit_au_val = _secondary_orbit(role)
        desig        = chr(desig_ord)
        desig_ord   += 1

        star = Star(
            designation   = desig,
            role          = role,
            spectral_type = sp,
            subtype       = sub,
            lum_class     = lum,
            mass          = mass_s,
            temperature   = temp_s,
            diameter      = diam_s,
            luminosity    = lum_s,
            orbit_number  = orbit_num,
            orbit_au      = orbit_au_val,
            age_gyr       = age,
            ms_lifespan_gyr = ms_life_s,
        )
        system.stars.append(star)

    return system


# ---------------------------------------------------------------------------
# World reconstruction from canonical UWP
# ---------------------------------------------------------------------------

def reconstruct_world(map_data: MapWorldData) -> World:
    """
    Build a World dataclass from canonical TravellerMap data.

    The UWP digits are parsed exactly; no dice are rolled.  Temperature is
    set to a placeholder string and filled in from the orbital position by
    generate_system_from_map() after orbits are generated.
    """
    uwp = parse_uwp(map_data.uwp)

    # PBG: P = population multiplier, B = belt count, G = gas giant count
    pbg      = map_data.pbg.strip()
    pop_mult = int(pbg[0]) if len(pbg) > 0 and pbg[0].isdigit() else 0
    belt_cnt = int(pbg[1]) if len(pbg) > 1 and pbg[1].isdigit() else 0
    gg_cnt   = int(pbg[2]) if len(pbg) > 2 and pbg[2].isdigit() else 0

    # Base codes — keep only codes understood by the rest of the pipeline
    bases = [b for b in map_data.bases if b in {"N", "S", "W", "D", "M", "H", "C"}]

    # Trade codes — extract only the standard 18 codes from the remarks string
    trade_codes = [
        tok for tok in map_data.remarks.split()
        if tok in _VALID_TRADE_CODES
    ]

    zone_map   = {"A": "Amber", "R": "Red"}
    travel_zone = zone_map.get(map_data.zone.upper(), "Green")

    world = World(name=map_data.name)
    world.starport            = uwp["starport"]
    world.size                = uwp["size"]
    world.atmosphere          = uwp["atmosphere"]
    world.temperature         = "Temperate"   # filled in by generate_system_from_map
    world.hydrographics       = uwp["hydrographics"]
    world.population          = uwp["population"]
    world.government          = uwp["government"]
    world.law_level           = uwp["law_level"]
    world.tech_level          = uwp["tech_level"]
    world.population_multiplier = pop_mult
    world.belt_count          = belt_cnt
    world.gas_giant_count     = gg_cnt
    world.has_gas_giant       = gg_cnt > 0
    world.bases               = bases
    world.trade_codes         = trade_codes
    world.travel_zone         = travel_zone
    world.notes               = [
        f"Canonical UWP from TravellerMap — "
        f"{map_data.sector} {map_data.hex_pos} {map_data.uwp}"
    ]
    return world


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def _reconcile_orbit_types(orbits: "SystemOrbits",
                            canonical_gg: int,
                            canonical_belt: int) -> None:
    """
    Redistribute world types in non-mainworld, non-empty slots to match
    the canonical gas-giant and belt counts from the PBG field.

    Slots are re-typed in-place; excess slots become terrestrial.
    Mainworld and empty slots are left unchanged.
    Call _recount_orbit_metadata() after the mainworld type is resolved.
    """
    slots = [o for o in orbits.orbits
             if o.world_type != "empty" and not o.is_mainworld_candidate]
    n = len(slots)
    pool = ["gas_giant"] * canonical_gg + ["belt"] * canonical_belt
    if len(pool) > n:
        pool = pool[:n]
    else:
        pool += ["terrestrial"] * (n - len(pool))
    random.shuffle(pool)
    for o, wtype in zip(slots, pool):
        o.world_type = wtype


def _recount_orbit_metadata(orbits: "SystemOrbits") -> None:
    """Update SystemOrbits count fields from the actual orbit list."""
    orbits.gas_giant_count   = sum(1 for o in orbits.orbits if o.world_type == "gas_giant")
    orbits.belt_count        = sum(1 for o in orbits.orbits if o.world_type == "belt")
    orbits.terrestrial_count = sum(1 for o in orbits.orbits if o.world_type == "terrestrial")
    orbits.total_worlds      = (orbits.gas_giant_count
                                + orbits.belt_count
                                + orbits.terrestrial_count)


def generate_system_from_map(
    name:    Optional[str] = None,
    sector:  Optional[str] = None,
    hex_pos: Optional[str] = None,
    seed:    Optional[int] = None,
    attach:  bool = False,
) -> TravellerSystem:
    """
    Fetch a world from TravellerMap and generate a complete star system.

    The canonical UWP and stellar classification are preserved exactly.
    Orbital structure, secondary world SAH/social profiles, and satellite
    data are generated procedurally — output varies per run unless seed
    is provided.

    Parameters
    ----------
    name     World name to search on TravellerMap.  Requires sector.
    sector   Sector name — always required to avoid same-name ambiguity.
    hex_pos  4-digit hex position, e.g. '1910'.  Alternative to name.
    seed     RNG seed for reproducible orbital generation.
    attach   If True, generate all secondary world and moon profiles.

    Returns
    -------
    TravellerSystem with canonical stellar data and mainworld UWP.

    Raises
    ------
    ValueError  if sector is missing, or neither name nor hex_pos supplied.
    LookupError if TravellerMap returns no matching world.
    urllib.error.URLError on network failure.
    """
    # Step 1: fetch canonical data — mainworld is taken directly from this
    map_data = fetch_world_data(name=name, sector=sector, hex_pos=hex_pos)

    if seed is not None:
        random.seed(seed)

    # Step 2: canonical stellar system (types fixed, orbit positions random)
    stellar = reconstruct_star_system(map_data.stars_str)

    # Step 3: procedural orbital layout
    orbits  = generate_orbits(stellar)

    # Step 4: canonical mainworld — UWP used verbatim, no dice rolls
    world = reconstruct_world(map_data)

    # Step 5: reconcile orbit slot types with canonical PBG gas-giant and belt
    # counts.  generate_orbits() used random rolls; we reassign world types
    # across non-mainworld, non-empty slots so the placed types match PBG.
    _reconcile_orbit_types(orbits, world.gas_giant_count, world.belt_count)

    # Step 6: resolve mainworld orbit slot; stamp it with the canonical UWP so
    # the orbit table shows the real profile instead of blank/procedural data.
    mw_orbit = orbits.mainworld_orbit
    if mw_orbit is not None:
        mw_orbit.canonical_profile = world.uwp()
        mw_orbit.world_type = "belt" if world.size == 0 else "terrestrial"
    _recount_orbit_metadata(orbits)

    # Step 6b: temperature is not in the UWP — derive from orbital position
    if mw_orbit is not None:
        hzco = orbits.star_hzco.get(mw_orbit.star_designation, 1.0)
        world.temperature = generate_temperature_from_orbit(
            atmosphere   = world.atmosphere,
            hz_deviation = mw_orbit.hz_deviation,
            hzco         = hzco,
            orbit        = mw_orbit.orbit_number,
        )
        world.notes.append(
            f"Temperature derived from orbit: "
            f"Star {mw_orbit.star_designation} "
            f"Orbit# {mw_orbit.orbit_number:.2f} "
            f"({mw_orbit.orbit_au:.3f} AU)  "
            f"HZ dev {mw_orbit.hz_deviation:+.2f}"
        )

    system = TravellerSystem(
        stellar_system  = stellar,
        system_orbits   = orbits,
        mainworld       = world,
        mainworld_orbit = mw_orbit,
    )

    if attach:
        attach_detail(system)

    return system


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:  # pylint: disable=too-many-return-statements,missing-function-docstring
    # pylint: disable=import-outside-toplevel
    import argparse
    import sys as _sys
    # pylint: enable=import-outside-toplevel

    parser = argparse.ArgumentParser(
        description=(
            "Fetch a world from TravellerMap and generate a complete "
            "Traveller star system from the canonical UWP and stellar data. "
            "--sector is always required to avoid same-name ambiguity."
        )
    )
    parser.add_argument("--sector", required=True,
                        help="Sector name, e.g. 'Spinward Marches' (always required)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--name", help="World name within the sector")
    src.add_argument("--hex",  metavar="NNNN",
                     help="4-digit hex position within the sector, e.g. 1910")
    parser.add_argument("--seed",   type=int, default=None,
                        help="RNG seed for reproducible orbital generation")
    parser.add_argument("--detail", action="store_true",
                        help="Attach all secondary world and moon profiles")
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument("--format", choices=["text", "json", "html"], default=None,
                     help="Output format (default: text)")
    fmt.add_argument("--json", action="store_true", help="Output as JSON")
    fmt.add_argument("--html", action="store_true",
                     help="Output as HTML card (implies --detail)")
    args = parser.parse_args()

    if args.html:
        out_format  = "html"
        want_detail = True
    elif args.json:
        out_format  = "json"
        want_detail = args.detail
    elif args.format:
        out_format  = args.format
        want_detail = args.detail or (args.format == "html")
    else:
        out_format  = "text"
        want_detail = args.detail

    try:
        system = generate_system_from_map(
            name    = args.name,
            sector  = args.sector,
            hex_pos = args.hex,
            seed    = args.seed,
            attach  = want_detail,
        )
    except LookupError as exc:
        _sys.exit(f"Not found: {exc}")
    except urllib.error.URLError as exc:
        _sys.exit(f"Network error fetching from TravellerMap: {exc}")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _sys.exit(f"Error: {exc}")

    if out_format == "json":
        print(system.to_json())
    elif out_format == "html":
        print(system.to_html(detail_attached=want_detail))
    else:
        print(system.summary())


if __name__ == "__main__":
    main()
