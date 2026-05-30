"""
function_app.py
===============
Traveller World & System Generator — Azure Functions HTTP API
=============================================================

Exposes HTTP endpoints using the Azure Functions Python v2
programming model (decorator-based, single-file registration).

Mainworld endpoints  (CRB generation only — fast)
-----------------
GET  /api/world
POST /api/world
    Generate one mainworld.  Parameters: name, seed.

GET  /api/world/{name}
    Generate one mainworld from a URL path name.  Parameter: seed.

POST /api/worlds
    Batch generation.  Parameters: count, prefix, seed.

GET  /api/world/{name}/card
    Mainworld-only HTML display card.  Parameter: seed.

System endpoints  (WBH stellar + orbit + mainworld generation)
----------------
GET  /api/system
POST /api/system
    Generate a full star system.  Parameters: name, seed, detail.

GET  /api/system/{name}
    Generate a full star system from a URL path name.
    Parameters: seed, detail.

GET  /api/system/{name}/card
    Full system HTML card.  Parameters: seed, detail.

GET/POST /api/system/full
    Complete system generation with ALL secondary world and moon profiles
    always attached.  Parameters: name, seed, format.
    format=json (default) | html | text

GET/POST /api/map/system
    Fetch canonical UWP + stellar data from TravellerMap, then generate a
    full system with procedural orbital structure.
    Parameters: name OR (sector + hex), seed, detail, format.

GET  /api/map/system/{name}
    Same as above; world name from URL path.

POST /api/system/from-world
    Generate a full star system around an existing mainworld JSON object.
    The world's UWP and PBG are preserved; stellar data and orbital structure
    are generated procedurally. Temperature is recalculated from orbital position.
    Body: mainworld JSON (from any world or system endpoint).
    Parameters: seed, detail, format.

The 'detail' parameter
----------------------
All system endpoints accept an optional boolean 'detail' parameter
(?detail=true or {"detail": true} in the request body).  When true,
attach_detail() is called after generation, populating secondary world
SAH/social profiles and satellite data for every orbit slot and moon.
Omitting 'detail' (or setting it to false) returns a faster response
with orbital structure and the mainworld only.

Response formats
----------------
Single world (mainworld endpoints):
    HTTP 200  { <world object> }

Single system (system endpoints, JSON):
    HTTP 200  { <TravellerSystem object including orbits with detail> }

Batch:
    HTTP 200  { "count": N, "worlds": [ <world>, ... ] }

HTML card:
    HTTP 200  text/html; charset=utf-8

Error:
    HTTP 4xx/500  { "error": { "code": "...", "message": "..." } }

Local development
-----------------
    func start

    # Mainworld
    curl "http://localhost:7071/api/world?name=Cogri&seed=42"
    curl "http://localhost:7071/api/world/Mora?seed=7"
    curl "http://localhost:7071/api/world/Regina/card" -o regina.html
    curl -X POST "http://localhost:7071/api/worlds" \\
         -H "Content-Type: application/json" \\
         -d '{"count": 3, "prefix": "Spinward-", "seed": 1}'

    # Full system
    curl "http://localhost:7071/api/system?name=Varanthos&seed=6056"
    curl "http://localhost:7071/api/system/Mora?seed=7&detail=true"
    curl "http://localhost:7071/api/system/Ardenne/card?seed=1000&detail=true" \\
         -o ardenne.html
    curl -X POST "http://localhost:7071/api/system" \\
         -H "Content-Type: application/json" \\
         -d '{"name": "Dulinor", "seed": 999, "detail": true}'

    # Complete system (all worlds + moons, selectable format)
    curl "http://localhost:7071/api/system/full?name=Zhodane&seed=42"
    ...
    # TravellerMap — canonical UWP + procedural orbital structure (sector always required)
    curl "http://localhost:7071/api/map/system?name=Regina&sector=Spinward+Marches&seed=42"
    curl "http://localhost:7071/api/map/system/Regina?sector=Spinward+Marches&seed=42&detail=true"
    curl "http://localhost:7071/api/map/system?sector=Spinward+Marches&hex=1910&format=html"
    curl "http://localhost:7071/api/system/full?name=Zhodane&seed=42&format=text"
    curl "http://localhost:7071/api/system/full?name=Zhodane&seed=42&format=html" -o zhodane.html
    curl -X POST "http://localhost:7071/api/system/full" \\
         -H "Content-Type: application/json" \\
         -d '{"name": "Zhodane", "seed": 42, "format": "json"}'

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

import logging
import urllib.error
from typing import Optional

# All endpoint handlers deliberately catch Exception broadly so that any
# unexpected generation error returns a structured 500 rather than crashing.
# pylint: disable=broad-exception-caught

import azure.functions as func

from traveller_world_gen import (
    World, generate_world, generate_atmosphere_detail, generate_gas_mix,
    generate_unusual_subtype,
)
from traveller_world_physical import generate_world_physical, apply_moon_tidal_effects
from traveller_hydro_detail import generate_hydrographic_detail
from traveller_system_gen import generate_full_system, generate_system_from_world
from traveller_world_detail import attach_detail, gg_diameter_from_sah
from traveller_map_fetch import generate_system_from_map

from shared.helpers import (
    ok, error,
    ERR_INVALID_BODY, ERR_INTERNAL, ERR_MISSING_PARAM, ERR_NOT_FOUND, ERR_UPSTREAM,
    apply_seed, parse_count, parse_detail, parse_format, parse_hex_pos, parse_name,
    parse_nhz_atmospheres, parse_orbital_eccentricity, parse_orbital_inclination,
    parse_seed, parse_sector, parse_world_json,
)

logger = logging.getLogger(__name__)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def _attach_mainworld_physical(system) -> None:
    """Populate size_detail on the system mainworld using full orbital parameters."""
    mw = system.mainworld
    if mw is None:
        return
    mw_orbit = system.mainworld_orbit
    orbit_ecc = mw_orbit.eccentricity if mw_orbit is not None else 0.0
    mw.size_detail = generate_world_physical(
        mw,
        age_gyr=system.stellar_system.primary.age_gyr,
        orbit_number=mw_orbit.orbit_number if mw_orbit is not None else None,
        orbit_au=mw_orbit.orbit_au if mw_orbit is not None else None,
        star_mass=system.stellar_system.primary.mass,
        orbit_eccentricity=orbit_ecc,
        hz_deviation=mw_orbit.hz_deviation if mw_orbit is not None else None,
    )
    if mw_orbit is not None and mw.size_detail is not None:
        adj = mw.size_detail.eccentricity_adjusted
        if adj is not None:
            mw_orbit.eccentricity = adj


def _get_mainworld_moons(system) -> list:
    """Return the generated Moon objects for the mainworld (after attach_detail)."""
    mw_orbit = system.mainworld_orbit
    if mw_orbit is None or mw_orbit.detail is None:
        return []
    if mw_orbit.world_type == "gas_giant":
        # Mainworld is a gas giant satellite; its moons are on the satellite WorldDetail
        if mw_orbit.detail.moons:
            sat = mw_orbit.detail.moons[0]
            if sat.detail:
                return sat.detail.moons or []
        return []
    return mw_orbit.detail.moons or []


def _apply_mainworld_moon_tidal(system) -> None:
    """Apply moon tidal DMs and compute seismic stress for mainworld.

    Must be called after both attach_detail() and _attach_mainworld_physical().
    No-op when the mainworld has no physical detail or orbit.
    """
    mw = system.mainworld
    mw_orbit = system.mainworld_orbit
    if mw is None or mw.size_detail is None or mw_orbit is None:
        return
    moons = _get_mainworld_moons(system)
    is_moon = mw_orbit.world_type == "gas_giant"
    gg_mass_earth = 0.0
    gg_sat_moon = None
    if is_moon and getattr(mw_orbit, "gg_sah", ""):
        gg_mass_earth = (
            mw_orbit.gg_mass_earth
            if mw_orbit.gg_mass_earth is not None
            else float(gg_diameter_from_sah(mw_orbit.gg_sah) ** 2)
        )
        if mw_orbit.detail and mw_orbit.detail.moons:
            gg_sat_moon = mw_orbit.detail.moons[0]
    apply_moon_tidal_effects(
        mw.size_detail,
        moons=moons,
        world_size=mw.size,
        world_atmosphere=mw.atmosphere,
        age_gyr=system.stellar_system.primary.age_gyr,
        orbit_number=mw_orbit.orbit_number,
        orbit_au=mw_orbit.orbit_au,
        star_mass=system.stellar_system.primary.mass,
        orbit_eccentricity=mw_orbit.eccentricity,
        is_moon=is_moon,
        gg_mass_earth=gg_mass_earth,
        gg_satellite_moon=gg_sat_moon,
    )
    if mw.size_detail.eccentricity_adjusted is not None:
        mw_orbit.eccentricity = mw.size_detail.eccentricity_adjusted


# ===========================================================================
# Endpoint 1 & 2:  GET /api/world   and   POST /api/world
# ===========================================================================

@app.route(route="world", methods=["GET", "POST"])
def generate_single_world(req: func.HttpRequest) -> func.HttpResponse:
    """Generate a single Traveller mainworld (CRB procedure).

    Parameters: name (str, opt), seed (int, opt).
    Returns: 200 World JSON | 400 INVALID_SEED/NAME_TOO_LONG | 500 INTERNAL_ERROR
    """
    logger.info("generate_single_world [method=%s]", req.method)
    name, err = parse_name(req)
    if err:
        return err
    seed, err = parse_seed(req)
    if err:
        return err
    try:
        seed, rng = apply_seed(seed)
        world = generate_world(name=name or "World-1", seed=seed, rng=rng)
        world.atmosphere_detail = generate_atmosphere_detail(
            world.atmosphere, world.size, temperature=world.temperature
        )
        generate_gas_mix(
            world.atmosphere_detail, world.atmosphere, world.size,
            world.temperature, None, world.hydrographics,
        )
        generate_unusual_subtype(
            world.atmosphere_detail, world.atmosphere,
            world.size, world.hydrographics,
        )
        world.hydrographic_detail = generate_hydrographic_detail(
            world.hydrographics, world.size,
            atmosphere=world.atmosphere,
            temperature=world.temperature,
        rng=rng,
        )
        world.size_detail = generate_world_physical(world, rng=rng)
    except Exception as exc:
        logger.exception("Error generating world: %s", exc)
        return error("An unexpected error occurred while generating the world.",
                     ERR_INTERNAL, status_code=500)
    logger.info("Generated world UWP=%s name=%s", world.uwp(), world.name)
    d = world.to_dict()
    return ok(d)


# ===========================================================================
# Endpoint 3:  GET /api/world/{name}
# ===========================================================================

@app.route(route="world/{name}", methods=["GET"])
def generate_named_world(req: func.HttpRequest) -> func.HttpResponse:
    """Generate a mainworld; name from URL path.

    Parameters: seed (int, opt).
    Returns: 200 World JSON | 400 NAME_TOO_LONG/INVALID_SEED | 500 INTERNAL_ERROR
    """
    route_name = req.route_params.get("name", "").strip() or None
    logger.info("generate_named_world [name=%s]", route_name)
    name, err = parse_name(req, route_name=route_name)
    if err:
        return err
    seed, err = parse_seed(req)
    if err:
        return err
    try:
        seed, rng = apply_seed(seed)
        world = generate_world(name=name or "World-1", seed=seed, rng=rng)
        world.atmosphere_detail = generate_atmosphere_detail(
            world.atmosphere, world.size, temperature=world.temperature
        )
        generate_gas_mix(
            world.atmosphere_detail, world.atmosphere, world.size,
            world.temperature, None, world.hydrographics,
        )
        generate_unusual_subtype(
            world.atmosphere_detail, world.atmosphere,
            world.size, world.hydrographics,
        )
        world.hydrographic_detail = generate_hydrographic_detail(
            world.hydrographics, world.size,
            atmosphere=world.atmosphere,
            temperature=world.temperature,
        rng=rng,
        )
        world.size_detail = generate_world_physical(world, rng=rng)
    except Exception as exc:
        logger.exception("Error generating world: %s", exc)
        return error("An unexpected error occurred while generating the world.",
                     ERR_INTERNAL, status_code=500)
    logger.info("Generated world UWP=%s name=%s", world.uwp(), world.name)
    d = world.to_dict()
    return ok(d)


# ===========================================================================
# Endpoint 4:  POST /api/worlds  (batch)
# ===========================================================================

@app.route(route="worlds", methods=["POST"])
def generate_world_batch(req: func.HttpRequest) -> func.HttpResponse:
    """Batch-generate Traveller mainworlds.

    Parameters: count (int, opt, default 1), prefix (str, opt, default "World-"),
                seed (int, opt).
    Returns: 200 {"count": N, "worlds": [...]} | 400/422 | 500
    """  # pylint: disable=too-many-return-statements
    logger.info("generate_world_batch called")
    body: dict = {}
    if req.get_body():
        try:
            body = req.get_json()
            if not isinstance(body, dict):
                return error("Request body must be a JSON object.", ERR_INVALID_BODY)
        except ValueError:
            return error("Request body is not valid JSON.", ERR_INVALID_BODY)

    count, err = parse_count(req)
    if err:
        return err
    count = count or 1

    max_prefix = 32
    prefix = (str(body.get("prefix","")).strip()
              or req.params.get("prefix","").strip()
              or "World-")
    if len(prefix) > max_prefix:
        return error(f"'prefix' must be {max_prefix} characters or fewer.",
                     ERR_INVALID_BODY)

    seed, err = parse_seed(req)
    if err:
        return err

    try:
        seed, rng = apply_seed(seed)
        worlds = []
        for i in range(count):
            world = generate_world(name=f"{prefix}{i+1}", seed=seed, rng=rng)
            world.atmosphere_detail = generate_atmosphere_detail(
                world.atmosphere, world.size, temperature=world.temperature
            )
            generate_gas_mix(
                world.atmosphere_detail, world.atmosphere, world.size,
                world.temperature, None, world.hydrographics,
            )
            generate_unusual_subtype(
                world.atmosphere_detail, world.atmosphere,
                world.size, world.hydrographics,
            )
            world.hydrographic_detail = generate_hydrographic_detail(
                world.hydrographics, world.size, rng=rng,
            )
            world.size_detail = generate_world_physical(world, rng=rng)
            d = world.to_dict()
            worlds.append(d)
    except Exception as exc:
        logger.exception("Error generating batch: %s", exc)
        return error("An unexpected error occurred while generating the world batch.",
                     ERR_INTERNAL, status_code=500)

    logger.info("Generated batch count=%d prefix=%s", count, prefix)
    return ok({"count": count, "seed": seed, "worlds": worlds})


# ===========================================================================
# Endpoint 5:  GET /api/world/{name}/card  (HTML mainworld card)
# ===========================================================================

@app.route(route="world/{name}/card", methods=["GET"])
def generate_world_card(req: func.HttpRequest) -> func.HttpResponse:
    """Return a standalone HTML mainworld display card.

    Parameters: seed (int, opt).
    Returns: 200 text/html | 400 | 500
    """
    route_name = req.route_params.get("name", "").strip() or None
    logger.info("generate_world_card [name=%s]", route_name)
    name, err = parse_name(req, route_name=route_name)
    if err:
        return err
    seed, err = parse_seed(req)
    if err:
        return err
    try:
        seed, rng = apply_seed(seed)
        world = generate_world(name=name or "World-1", seed=seed, rng=rng)
        world.atmosphere_detail = generate_atmosphere_detail(
            world.atmosphere, world.size, temperature=world.temperature
        )
        generate_gas_mix(
            world.atmosphere_detail, world.atmosphere, world.size,
            world.temperature, None, world.hydrographics,
        )
        generate_unusual_subtype(
            world.atmosphere_detail, world.atmosphere,
            world.size, world.hydrographics,
        )
        world.hydrographic_detail = generate_hydrographic_detail(
            world.hydrographics, world.size,
            atmosphere=world.atmosphere,
            temperature=world.temperature,
        rng=rng,
        )
        world.size_detail = generate_world_physical(world, rng=rng)
        html = world.to_html()
    except Exception as exc:
        logger.exception("Error generating world card: %s", exc)
        return error("An unexpected error occurred while generating the world card.",
                     ERR_INTERNAL, status_code=500)
    logger.info("Generated world card UWP=%s name=%s", world.uwp(), world.name)
    return func.HttpResponse(body=html, status_code=200,
                             mimetype="text/html", charset="utf-8")


# ===========================================================================
# Endpoint 6 & 7:  GET /api/system   and   POST /api/system
# ===========================================================================

@app.route(route="system", methods=["GET", "POST"])
def generate_single_system(req: func.HttpRequest) -> func.HttpResponse:
    """Generate a full Traveller star system (WBH stellar + orbit + CRB mainworld).

    Parameters
    ----------
    name    str, optional   Mainworld name.  Default "World-1".
    seed    int, optional   RNG seed.
    detail  bool, optional  When true, generate secondary world SAH/social
                            codes and satellite profiles (attach_detail).
                            Default false.

    Returns
    -------
    200  TravellerSystem JSON.  Orbit entries include a 'detail' key when
         detail=true; each moon entry includes nested 'detail' when available.
    400  INVALID_SEED / NAME_TOO_LONG
    500  INTERNAL_ERROR
    """
    logger.info("generate_single_system [method=%s]", req.method)
    name, err = parse_name(req)
    if err:
        return err
    seed, err = parse_seed(req)
    if err:
        return err
    want_detail = parse_detail(req)
    want_nhz = parse_nhz_atmospheres(req)
    want_ecc = parse_orbital_eccentricity(req)
    want_incl = parse_orbital_inclination(req)
    try:
        seed, rng = apply_seed(seed)
        system = generate_full_system(name=name or "World-1",
                                      seed=seed, rng=rng,
                                      nhz_atmospheres=want_nhz,
                                      orbital_eccentricity=want_ecc,
                                      orbital_inclination=want_incl)
        if want_detail:
            attach_detail(system, rng=rng)
        _attach_mainworld_physical(system)
        if want_detail:
            _apply_mainworld_moon_tidal(system)
    except Exception as exc:
        logger.exception("Error generating system: %s", exc)
        return error("An unexpected error occurred while generating the system.",
                     ERR_INTERNAL, status_code=500)
    mw = system.mainworld
    logger.info("Generated system name=%s stars=%d worlds=%d detail=%s uwp=%s",
                name, len(system.stellar_system.stars),
                system.system_orbits.total_worlds, want_detail,
                mw.uwp() if mw else "—")
    d = system.to_dict()
    return ok(d)


# ===========================================================================
# Endpoint 8:  GET /api/system/{name}
# ===========================================================================

@app.route(route="system/{name}", methods=["GET"])
def generate_named_system(req: func.HttpRequest) -> func.HttpResponse:
    """Generate a full star system; mainworld name from URL path.

    Parameters: seed (int, opt), detail (bool, opt).
    Returns: 200 TravellerSystem JSON | 400 | 500
    """
    route_name = req.route_params.get("name", "").strip() or None
    logger.info("generate_named_system [name=%s]", route_name)
    name, err = parse_name(req, route_name=route_name)
    if err:
        return err
    seed, err = parse_seed(req)
    if err:
        return err
    want_detail = parse_detail(req)
    want_nhz = parse_nhz_atmospheres(req)
    want_ecc = parse_orbital_eccentricity(req)
    want_incl = parse_orbital_inclination(req)
    try:
        seed, rng = apply_seed(seed)
        system = generate_full_system(name=name or "World-1",
                                      seed=seed, rng=rng,
                                      nhz_atmospheres=want_nhz,
                                      orbital_eccentricity=want_ecc,
                                      orbital_inclination=want_incl)
        if want_detail:
            attach_detail(system, rng=rng)
        _attach_mainworld_physical(system)
        if want_detail:
            _apply_mainworld_moon_tidal(system)
    except Exception as exc:
        logger.exception("Error generating system: %s", exc)
        return error("An unexpected error occurred while generating the system.",
                     ERR_INTERNAL, status_code=500)
    mw = system.mainworld
    logger.info("Generated system name=%s stars=%d worlds=%d detail=%s uwp=%s",
                name, len(system.stellar_system.stars),
                system.system_orbits.total_worlds, want_detail,
                mw.uwp() if mw else "—")
    d = system.to_dict()
    return ok(d)


# ===========================================================================
# Endpoint 9:  GET /api/system/{name}/card  (HTML system card)
# ===========================================================================

# ===========================================================================
# Endpoint 10 & 11:  GET /api/system/full   and   POST /api/system/full
# ===========================================================================

@app.route(route="system/full", methods=["GET", "POST"])
def generate_full_system_complete(req: func.HttpRequest) -> func.HttpResponse:
    """Generate a complete star system with all secondary world and moon profiles.

    Always runs attach_detail() — every orbit slot and moon receives its full
    SAH/social profile.  Use the 'format' parameter to select output type.

    Parameters
    ----------
    name    str, optional   Mainworld name.  Default "World-1".
    seed    int, optional   RNG seed for reproducible results.
    format  str, optional   Output format: 'json' (default), 'html', 'text'.

    Returns
    -------
    200  application/json   Full TravellerSystem JSON with all detail.
    200  text/html          Self-contained HTML system card with all detail.
    200  text/plain         Human-readable text summary with all detail.
    400  INVALID_SEED / NAME_TOO_LONG
    500  INTERNAL_ERROR
    """
    logger.info("generate_full_system_complete [method=%s]", req.method)
    name, err = parse_name(req)
    if err:
        return err
    seed, err = parse_seed(req)
    if err:
        return err
    fmt = parse_format(req)
    want_nhz = parse_nhz_atmospheres(req)
    want_ecc = parse_orbital_eccentricity(req)
    want_incl = parse_orbital_inclination(req)
    try:
        seed, rng = apply_seed(seed)
        system = generate_full_system(name=name or "World-1",
                                      seed=seed, rng=rng,
                                      nhz_atmospheres=want_nhz,
                                      orbital_eccentricity=want_ecc,
                                      orbital_inclination=want_incl)
        attach_detail(system, rng=rng)
        _attach_mainworld_physical(system)
        _apply_mainworld_moon_tidal(system)
    except Exception as exc:
        logger.exception("Error generating full system: %s", exc)
        return error("An unexpected error occurred while generating the system.",
                     ERR_INTERNAL, status_code=500)
    mw = system.mainworld
    logger.info(
        "Generated full system name=%s stars=%d worlds=%d format=%s uwp=%s",
        name, len(system.stellar_system.stars),
        system.system_orbits.total_worlds, fmt,
        mw.uwp() if mw else "—",
    )
    if fmt == "html":
        return func.HttpResponse(
            body=system.to_html(detail_attached=True),
            status_code=200,
            mimetype="text/html",
            charset="utf-8",
        )
    if fmt == "text":
        return func.HttpResponse(
            body=system.summary(),
            status_code=200,
            mimetype="text/plain",
            charset="utf-8",
        )
    d = system.to_dict()
    return ok(d)


@app.route(route="system/{name}/card", methods=["GET"])
def generate_system_card(req: func.HttpRequest) -> func.HttpResponse:
    """Return a standalone HTML system display card.

    Shows stellar summary, full orbital table (with secondary profiles and
    moon sub-rows when detail=true), and a mainworld panel.

    Parameters: seed (int, opt), detail (bool, opt).
    Returns: 200 text/html | 400 | 500
    """
    route_name = req.route_params.get("name", "").strip() or None
    logger.info("generate_system_card [name=%s]", route_name)
    name, err = parse_name(req, route_name=route_name)
    if err:
        return err
    seed, err = parse_seed(req)
    if err:
        return err
    want_detail = parse_detail(req)
    want_nhz = parse_nhz_atmospheres(req)
    want_ecc = parse_orbital_eccentricity(req)
    want_incl = parse_orbital_inclination(req)
    try:
        seed, rng = apply_seed(seed)
        system = generate_full_system(name=name or "World-1",
                                      seed=seed, rng=rng,
                                      nhz_atmospheres=want_nhz,
                                      orbital_eccentricity=want_ecc,
                                      orbital_inclination=want_incl)
        if want_detail:
            attach_detail(system, rng=rng)
        _attach_mainworld_physical(system)
        if want_detail:
            _apply_mainworld_moon_tidal(system)
        html = system.to_html(detail_attached=want_detail)
    except Exception as exc:
        logger.exception("Error generating system card: %s", exc)
        return error("An unexpected error occurred while generating the system card.",
                     ERR_INTERNAL, status_code=500)
    mw = system.mainworld
    logger.info("Generated system card name=%s detail=%s uwp=%s",
                name, want_detail, mw.uwp() if mw else "—")
    return func.HttpResponse(body=html, status_code=200,
                             mimetype="text/html", charset="utf-8")


# ===========================================================================
# Endpoints 12 & 13:  GET/POST /api/map/system   and   GET /api/map/system/{name}
# ===========================================================================

def _map_system_response(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    name: Optional[str],
    sector: Optional[str],
    hex_pos: Optional[str],
    seed: Optional[int],
    want_detail: bool,
    fmt: str,
    want_nhz: bool = False,
    want_ecc: bool = False,
    want_incl: bool = False,
) -> func.HttpResponse:
    """Shared implementation for both map/system endpoint variants."""
    seed, _ = apply_seed(seed)
    try:
        system = generate_system_from_map(
            name=name, sector=sector, hex_pos=hex_pos,
            seed=seed, attach=want_detail,
            nhz_atmospheres=want_nhz,
            orbital_eccentricity=want_ecc,
            orbital_inclination=want_incl,
        )
    except LookupError as exc:
        logger.warning("TravellerMap lookup failed: %s", exc)
        return error(str(exc), ERR_NOT_FOUND, status_code=404)
    except urllib.error.URLError as exc:
        logger.error("TravellerMap upstream error: %s", exc)
        return error(
            "Could not reach the upstream data source. Please try again later.",
            ERR_UPSTREAM, status_code=502,
        )
    except Exception as exc:
        logger.exception("Error generating map system: %s", exc)
        return error(
            "An unexpected error occurred while generating the map system.",
            ERR_INTERNAL, status_code=500,
        )
    _attach_mainworld_physical(system)
    if want_detail:
        _apply_mainworld_moon_tidal(system)
    mw = system.mainworld
    logger.info(
        "Generated map system name=%s stars=%d worlds=%d detail=%s format=%s uwp=%s",
        name or hex_pos,
        len(system.stellar_system.stars),
        system.system_orbits.total_worlds,
        want_detail, fmt,
        mw.uwp() if mw else "—",
    )
    if fmt == "html":
        return func.HttpResponse(
            body=system.to_html(detail_attached=want_detail),
            status_code=200,
            mimetype="text/html",
            charset="utf-8",
        )
    if fmt == "text":
        return func.HttpResponse(
            body=system.summary(),
            status_code=200,
            mimetype="text/plain",
            charset="utf-8",
        )
    d = system.to_dict()
    return ok(d)


# ===========================================================================
# Endpoint 14:  POST /api/system/from-world
# ===========================================================================

@app.route(route="system/from-world", methods=["POST"])
def generate_system_from_existing_world(req: func.HttpRequest) -> func.HttpResponse:
    """Generate a full star system around an existing mainworld.

    The request body must be a mainworld JSON object (as returned by any
    world or system endpoint). The world's UWP, bases, trade codes, and PBG
    values are preserved. New stellar data and orbital structure are generated
    procedurally. Temperature is recalculated from the assigned orbital
    position to remain consistent with the host star's habitable zone.

    Parameters (body + query string)
    ---------------------------------
    <world JSON>   required   Mainworld object from a previous generation call.
    seed           int, opt   RNG seed for stellar/orbital generation.
    detail         bool, opt  Attach secondary world profiles (attach_detail).
    format         str, opt   'json' (default) | 'html' | 'text'.

    Returns
    -------
    200  TravellerSystem JSON/HTML/text with the supplied world as mainworld.
    400  INVALID_BODY / INVALID_SEED
    500  INTERNAL_ERROR
    """
    logger.info("generate_system_from_existing_world called")
    world_dict, err = parse_world_json(req)
    if err or world_dict is None:
        return err or error("Missing world data.", ERR_INVALID_BODY)
    seed, err = parse_seed(req)
    if err:
        return err
    want_detail = parse_detail(req)
    fmt = parse_format(req)
    want_nhz = parse_nhz_atmospheres(req)
    want_ecc = parse_orbital_eccentricity(req)
    want_incl = parse_orbital_inclination(req)
    try:
        seed, rng = apply_seed(seed)
        world = World.from_dict(world_dict)
        system = generate_system_from_world(world, seed=seed, rng=rng,
                                            nhz_atmospheres=want_nhz,
                                            orbital_eccentricity=want_ecc,
                                            orbital_inclination=want_incl)
        if want_detail:
            attach_detail(system, rng=rng)
        _attach_mainworld_physical(system)
        if want_detail:
            _apply_mainworld_moon_tidal(system)
    except Exception as exc:
        logger.exception("Error generating system from world: %s", exc)
        return error(
            "An unexpected error occurred while generating the system.",
            ERR_INTERNAL, status_code=500,
        )
    mw = system.mainworld
    logger.info(
        "Generated system from world name=%s stars=%d worlds=%d detail=%s uwp=%s",
        mw.name if mw else "?",
        len(system.stellar_system.stars),
        system.system_orbits.total_worlds,
        want_detail,
        mw.uwp() if mw else "—",
    )
    if fmt == "html":
        return func.HttpResponse(
            body=system.to_html(detail_attached=want_detail),
            status_code=200, mimetype="text/html", charset="utf-8",
        )
    if fmt == "text":
        return func.HttpResponse(
            body=system.summary(),
            status_code=200, mimetype="text/plain", charset="utf-8",
        )
    d = system.to_dict()
    return ok(d)


@app.route(route="map/system", methods=["GET", "POST"])
def generate_map_system(  # pylint: disable=too-many-return-statements
        req: func.HttpRequest) -> func.HttpResponse:
    """Fetch canonical data from TravellerMap, then generate a full system.

    Sector is always required.  Identify the world by name (within that
    sector) or by hex position.

    Parameters
    ----------
    sector  str, required   Sector name, e.g. "Spinward Marches".
    name    str, optional*  World name within the sector.  * One of name or
    hex     str, optional*  4-digit hex, e.g. "1910".          hex required.
    seed    int, optional   RNG seed for procedural elements.
    detail  bool, optional  Attach secondary world and satellite profiles.
    format  str, optional   'json' (default) | 'html' | 'text'.

    Returns
    -------
    200  Full TravellerSystem JSON/HTML/text with canonical UWP.
    404  NOT_FOUND — world not found on TravellerMap.
    502  UPSTREAM_ERROR — TravellerMap unreachable.
    400  INVALID_SEED / NAME_TOO_LONG / MISSING_PARAM
    500  INTERNAL_ERROR
    """
    logger.info("generate_map_system [method=%s]", req.method)
    name, err = parse_name(req)
    if err:
        return err
    seed, err = parse_seed(req)
    if err:
        return err
    sector, err = parse_sector(req)
    if err:
        return err
    try:
        body = req.get_json()
        body = body if isinstance(body, dict) else None
    except (ValueError, TypeError):
        body = None
    hex_pos, err = parse_hex_pos(req, body)
    if err:
        return err
    if not sector:
        return error(
            "The 'sector' parameter is required to avoid same-name ambiguity.",
            ERR_MISSING_PARAM,
        )
    if not name and not hex_pos:
        return error(
            "Supply 'name' or 'hex' to identify the world within the sector.",
            ERR_MISSING_PARAM,
        )
    want_detail = parse_detail(req)
    fmt = parse_format(req)
    want_nhz = parse_nhz_atmospheres(req)
    want_ecc = parse_orbital_eccentricity(req)
    want_incl = parse_orbital_inclination(req)
    return _map_system_response(name, sector, hex_pos, seed, want_detail, fmt,
                                want_nhz, want_ecc, want_incl)


@app.route(route="map/system/{name}", methods=["GET"])
def generate_named_map_system(req: func.HttpRequest) -> func.HttpResponse:
    """Fetch canonical data from TravellerMap; world name from URL path.

    Sector is always required as a query-string parameter.

    Parameters
    ----------
    sector  str, required   Sector name (query string).
    seed    int, optional   RNG seed.
    detail  bool, optional  Attach secondary world profiles.
    format  str, optional   'json' (default) | 'html' | 'text'.

    Returns
    -------
    200  Full TravellerSystem JSON/HTML/text.
    404  NOT_FOUND
    502  UPSTREAM_ERROR
    400  INVALID_SEED / NAME_TOO_LONG / MISSING_PARAM
    500  INTERNAL_ERROR
    """
    route_name = req.route_params.get("name", "").strip() or None
    logger.info("generate_named_map_system [name=%s]", route_name)
    name, err = parse_name(req, route_name=route_name)
    if err:
        return err
    seed, err = parse_seed(req)
    if err:
        return err
    sector, err = parse_sector(req)
    if err:
        return err
    if not sector:
        return error(
            "The 'sector' query parameter is required to avoid same-name ambiguity.",
            ERR_MISSING_PARAM,
        )
    hex_pos, err = parse_hex_pos(req)
    if err:
        return err
    want_detail = parse_detail(req)
    fmt = parse_format(req)
    want_nhz = parse_nhz_atmospheres(req)
    want_ecc = parse_orbital_eccentricity(req)
    want_incl = parse_orbital_inclination(req)
    return _map_system_response(name, sector, hex_pos, seed, want_detail, fmt,
                                want_nhz, want_ecc, want_incl)
