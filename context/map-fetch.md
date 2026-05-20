# map-fetch.md — traveller_map_fetch.py

Read this when working on TravellerMap integration, canonical UWP seeding,
the name-lookup pipeline, or the map-fetch CLI.

See `context/generation-pipeline.md` for the TravellerMap-seeded pipeline
diagram.

---

## traveller_map_fetch.py — TravellerMap integration

Uses only Python stdlib (`urllib.request`) — no extra dependencies.

### Public API

```python
system: TravellerSystem = generate_system_from_map(
    name: Optional[str] = None,
    sector: Optional[str] = None,
    hex_pos: Optional[str] = None,
    seed: Optional[int] = None,
    attach: bool = False,
    orbital_eccentricity: bool = False,
    orbital_inclination: bool = False,
) -> TravellerSystem
# Raises LookupError if world not found.
# Raises AmbiguousWorldError if name matches more than one world in the sector.
# Raises urllib.error.URLError if TravellerMap API is unreachable.
```

### Key exceptions and dataclasses

```python
class AmbiguousWorldError(Exception):
    name: str
    sector: str
    candidates: list    # list of (world_name: str, hex_pos: str) tuples

@dataclass
class MapWorldData:
    name: str; sector: str; hex_pos: str
    uwp: str            # canonical, e.g. "A867A69-F"
    bases: str
    remarks: str
    zone: str
    pbg: str
    stars_str: str      # canonical stellar string, e.g. "G2 V M7 V"
```

### Internal functions

```python
fetch_world_data(name, sector, hex_pos) -> MapWorldData
parse_uwp(uwp_str) -> dict              # maps UWP string to size/atm/hydro/etc. ints
parse_stellar_string(stars_str)         # -> List[Tuple[spectral, subtype, lum_class]]
reconstruct_star_system(stars_str)      # -> StarSystem (canonical types, random orbits)
reconstruct_world(map_data)             # -> World (canonical UWP, placeholder temperature)
```

### TravellerMap API access — two-step fetch

1. If `name` is given: `GET /api/search?q={name}` — returns minimal data including
   `HexX`/`HexY` coordinates. Filtered to the requested sector. Raises
   `LookupError` if not found; raises `AmbiguousWorldError` if more than one
   exact match.
2. `GET /data/{sector}/{hex}` — fetches the full world record (`UWP`, `PBG`,
   `Bases`, `Remarks`, `Zone`, `Stellar`). This is the authoritative source.

If `hex_pos` is provided directly, step 1 is skipped.

### Case-inconsistent TravellerMap field names

`_raw_field()` uses case-insensitive multi-alias lookup:
- `"UWP"` / `"Uwp"`
- `"Stars"` / `"Stellar"` / `"Star"`
- `"PBG"` / `"Pbg"`

When adding new field access, always use `_raw_field()` with all known aliases.

### Sector is always required

Many world names exist in multiple sectors (e.g. "Regina", "Mora"). `sector` is
required by every map endpoint and by the CLI. Returns `400 MISSING_PARAM` if
absent at the API layer.

### Duplicate world names within a sector

The Spinward Marches alone has 7 pairs (e.g. Aramis at 2540 and 3110).
`_name_to_hex()` raises `AmbiguousWorldError` (with `candidates` list) when a
name search returns more than one exact match. The gen-ui shows a modal
disambiguation dialog and re-calls with the selected hex position. Callers that
supply `hex_pos` directly bypass the issue entirely.

### Pipeline inside `generate_system_from_map()`

1. `fetch_world_data()` — two-step HTTP fetch
2. `random.seed(seed)` if provided
3. `reconstruct_star_system(stars_str)` — primary at orbit 0; secondary orbits
   assigned heuristically (close→near→far) with random orbit numbers
4. `generate_orbits(stellar, orbital_eccentricity=..., orbital_inclination=...)` — full WBH procedural orbital layout; eccentricity/inclination flags threaded through
5. `reconstruct_world(map_data)` — canonical UWP digits via eHex decoding;
   no dice rolled; gas/belt counts from PBG override procedural counts
6. Stamp mainworld orbit slot: `mw_orbit.canonical_profile = world.uwp()`;
   correct `mw_orbit.world_type` to `"terrestrial"` or `"belt"` from size digit
7. `generate_temperature_from_orbit()` — temperature from orbital position
   (temperature is not stored in TravellerMap UWP)
8. `generate_atmosphere_detail()` with `hz_deviation` for orbit-position DMs;
   then `generate_gas_mix()` and `generate_unusual_subtype()` (after hydrographics
   is already set in the reconstructed world). Mirrors the pipeline in
   `generate_mainworld_at_orbit()`.
9. Assemble `TravellerSystem`
10. `attach_detail()` if `attach=True`

### Uninhabited mainworlds

Worlds with population = 0 are handled correctly. `reconstruct_world()` sets
`population=0` from the UWP `000` social digits. `canonical_profile` takes
display priority in all output paths.

### Stellar string parsing

Handles `G2 V`, `D`, `BD`, multi-star strings separated by spaces, and all WBH
luminosity classes (`Ia Ib II III IV V VI`). Brown dwarfs (`BD`) and white dwarfs
(`D`) receive `subtype=None`.

---

## CLI

`--sector` is always required.

```bash
# By name + sector
python traveller_map_fetch.py --name Regina --sector "Spinward Marches"

# By hex position (bypasses name search)
python traveller_map_fetch.py --sector "Spinward Marches" --hex 1910

# With seed and secondary world detail
python traveller_map_fetch.py --name Mora --sector "Spinward Marches" --seed 42 --detail

# Output formats
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --html > regina.html
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --format json
python traveller_map_fetch.py --name Regina --sector "Spinward Marches" --format text

# Uninhabited worlds work correctly
python traveller_map_fetch.py --name Tavonni --sector "Spinward Marches" --detail
```
