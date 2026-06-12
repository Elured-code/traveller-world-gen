"""
app.py
======
Traveller World & System Generator — FastAPI HTTP server
=========================================================

Mirrors azure-api/function_app.py endpoint-for-endpoint using FastAPI +
uvicorn instead of Azure Functions.  Auth level: none (intended to sit behind
a gateway).  Per-IP rate limiting via SlowAPI.

Mainworld endpoints  (CRB generation only — fast)
--------------------------------------------------
GET/POST  /api/world
GET       /api/world/{name}
POST      /api/worlds          (batch)
GET       /api/world/{name}/card

System endpoints  (WBH stellar + orbit + mainworld generation)
--------------------------------------------------------------
GET/POST  /api/system
GET       /api/system/{name}
GET       /api/system/{name}/card
GET/POST  /api/system/full     (always attach_detail; selectable format)
POST      /api/system/from-world

TravellerMap endpoints  (canonical UWP + procedural orbits)
-----------------------------------------------------------
GET/POST  /api/map/system
GET/POST  /api/map/system/full
GET       /api/map/system/svg
GET       /api/map/world/card
GET       /api/map/system/{name}

Optional system parameters
--------------------------
All system endpoints accept boolean flags via query string or JSON body.
Accepted values: true / 1 / yes (case-insensitive) or JSON boolean true.

detail                     — attach secondary world SAH/social profiles and
                             satellite data for every orbit slot and moon.
nhz_atmospheres            — use WBH Non-Habitable Zone atmosphere tables.
orbital_eccentricity       — roll orbital eccentricities (WBH p.27).
orbital_inclination        — roll orbital inclinations (WBH p.28).
runaway_greenhouse         — optional runaway greenhouse check (WBH p.79).
independent_government     — Case 2 secondary government (WBH p.162).
optional_biomass_rule      — raise oxygenated-atmosphere biomass 0→1 (WBH p.131).
optional_inhospitable_rule — single 2D for all non-HZ secondaries (WBH p.130).

Local development
-----------------
    cd fastapi && uvicorn app:app --reload

    # Mainworld
    curl "http://localhost:8000/api/world?name=Cogri&seed=42"
    curl "http://localhost:8000/api/world/Mora?seed=7"
    curl "http://localhost:8000/api/world/Regina/card" -o regina.html
    curl -X POST "http://localhost:8000/api/worlds" \\
         -H "Content-Type: application/json" \\
         -d '{"count": 3, "prefix": "Spinward-", "seed": 1}'

    # Full system
    curl "http://localhost:8000/api/system?name=Varanthos&seed=6056"
    curl "http://localhost:8000/api/system/Mora?seed=7&detail=true"
    curl "http://localhost:8000/api/system/full?name=Zhodane&seed=42"
    curl "http://localhost:8000/api/system/full?name=Zhodane&seed=42&format=text"

    # TravellerMap (sector always required)
    curl "http://localhost:8000/api/map/system?name=Regina&sector=Spinward+Marches&seed=42"
    curl "http://localhost:8000/api/map/system?sector=Spinward+Marches&hex=1910"

    # Optional WBH rules
    curl "http://localhost:8000/api/system/full?seed=42&runaway_greenhouse=true"
    curl "http://localhost:8000/api/system?seed=1&detail=true&independent_government=true"

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

import dataclasses
import logging
import logging.config
import os
import random
import sys
import urllib.error
from typing import Optional

# Make project-root generation modules importable when this file is loaded
# from within the fastapi/ subdirectory.
_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
sys.path.insert(0, _root)   # traveller_* generation modules
sys.path.insert(0, _here)   # helpers.py (this file's own directory)

# All endpoint handlers deliberately catch Exception broadly so that any
# unexpected generation error returns a structured 500 rather than crashing.
# The sys.path.insert above must precede the generation-module imports.
# Pylint cannot resolve imports from within fastapi/ without the sys.path fix,
# and classifies slowapi/helpers differently than fastapi on some configurations.
# pylint: disable=wrong-import-position,import-error,too-many-lines
# pylint: disable=locally-disabled,suppressed-message
# pylint: disable=broad-exception-caught,wrong-import-order

from fastapi import FastAPI, Request
from fastapi.responses import (
    HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
)
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded  # registered as exception handler key
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from helpers import (
    ERR_INTERNAL, ERR_INVALID_BODY, ERR_MISSING_PARAM, ERR_NOT_FOUND, ERR_UPSTREAM,
    apply_seed, error, ok,
    parse_count, parse_detail, parse_format, parse_hex_pos, parse_name,
    parse_nhz_atmospheres, parse_orbital_eccentricity, parse_orbital_inclination,
    parse_runaway_greenhouse, parse_independent_government,
    parse_optional_biomass, parse_optional_inhospitable,
    parse_social_detail, parse_settlement_type, parse_include_mw_card,
    parse_seed, parse_sector, parse_world_json,
)

from system_map import build_svg, PALETTE_DARK, PALETTE_LIGHT

# FastAPI light-mode background matches the page (#f4f0e4), not pure white.
_PALETTE_LIGHT = dataclasses.replace(PALETTE_LIGHT, bg="#f4f0e4")

from traveller_world_gen import (
    World, generate_world, generate_atmosphere_detail, generate_gas_mix,
    generate_unusual_subtype, generate_hydrographics, apply_mainworld_social,
)
from traveller_belt_physical import BeltPhysical
from traveller_world_physical import (
    generate_world_physical, apply_moon_tidal_effects,
)
from traveller_world_atmosphere_detail import (
    generate_advanced_mean_temperature, check_runaway_greenhouse,
)
from traveller_hydro_detail import generate_hydrographic_detail
from traveller_system_gen import (
    generate_full_system, generate_system_from_world, attach_body_names,
)
from traveller_world_detail import (
    attach_detail, gg_diameter_from_sah, apply_secondary_social,
)
from traveller_world_population_detail import attach_population_detail
from traveller_world_government_detail import attach_government_detail
from traveller_world_law_detail import attach_law_detail
from traveller_world_tech_detail import attach_tech_detail
from traveller_map_fetch import generate_system_from_map
from system_pipeline import PipelineOptions, run_detail_pipeline

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging — apply timestamps to all console output.
# This runs when the module is imported (after uvicorn has already configured
# its own loggers), so it overrides the formatters on uvicorn's handlers too.
# ---------------------------------------------------------------------------

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "timestamped": {
            "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "timestamped",
            "stream": "ext://sys.stderr",
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "uvicorn":        {"handlers": ["console"], "level": "INFO",    "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO",    "propagate": False},
        "uvicorn.error":  {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
})

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_RATE_LIMIT = os.environ.get("RATE_LIMIT_PER_MINUTE", "100/minute")

limiter = Limiter(key_func=get_remote_address)


async def _rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:  # pylint: disable=unused-argument
    """Return a project-standard error shape for 429 rate-limit responses."""
    return JSONResponse(
        content={"error": {"code": "RATE_LIMIT_EXCEEDED",
                           "message": "Too many requests. Please slow down."}},
        status_code=429,
    )


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' blob:; "
    "connect-src 'self'; "
    "frame-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):  # pylint: disable=too-few-public-methods
    """Attach security headers to every response."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]         = "DENY"
        response.headers["Content-Security-Policy"] = _CSP
        return response


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Traveller World & System Generator",
    description="Procedural star system generator for the Traveller RPG.",
    version="1.5.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(_SecurityHeadersMiddleware)
app.mount("/static", StaticFiles(directory=os.path.join(_here, "static")), name="static")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Redirect the browser root to the web UI."""
    return RedirectResponse(url="/static/index.html")


# ---------------------------------------------------------------------------
# Body parsing helper
# ---------------------------------------------------------------------------

async def _get_body(request: Request) -> dict:
    """Parse the JSON body and return a dict.  Returns {} on failure or absent body."""
    try:
        body_bytes = await request.body()
        if body_bytes:
            data = await request.json()
            if isinstance(data, dict):
                return data
    except (ValueError, TypeError):
        pass
    return {}


# ---------------------------------------------------------------------------
# World generation helper (shared sequence across world endpoints)
# ---------------------------------------------------------------------------

def _build_world(name: str, seed: int, rng) -> World:
    """Run the full mainworld generation pipeline and return a World object."""
    world = generate_world(name=name, seed=seed, rng=rng)
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
    return world


# ---------------------------------------------------------------------------
# System helpers (copied from azure-api/function_app.py; domain-objects only)
# ---------------------------------------------------------------------------

def _attach_mainworld_physical(  # pylint: disable=too-many-branches
        system, runaway_greenhouse: bool = False,
        rng: Optional[random.Random] = None) -> None:
    """Populate size_detail on the system mainworld using full orbital parameters.

    Also computes advanced mean temperature (WBH pp.47-50) and optionally
    applies the runaway greenhouse check (WBH p.79).
    Pass rng to keep physical-detail dice rolls on the same RNG sequence as
    the rest of system generation (required for seed reproducibility).
    """
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
        rng=rng,
    )
    if mw_orbit is not None and mw.size_detail is not None:
        adj = mw.size_detail.eccentricity_adjusted
        if adj is not None:
            mw_orbit.eccentricity = adj

    if mw_orbit is None or mw.size_detail is None:
        return

    # Advanced mean temperature (WBH pp.47-50)
    mw_au = mw_orbit.orbit_au
    stars = system.stellar_system.stars
    interior_lum = sum(
        s.luminosity for s in stars
        if s.orbit_au <= 0.0 or s.orbit_au < mw_au
    )
    pressure_bar = (
        mw.atmosphere_detail.pressure_bar
        if mw.atmosphere_detail is not None else None
    )
    generate_advanced_mean_temperature(
        mw.size_detail,
        atmosphere=mw.atmosphere,
        hydrographics=mw.hydrographics,
        pressure_bar=pressure_bar,
        luminosity=interior_lum,
        orbit_au=mw_au,
        hz_deviation=mw_orbit.hz_deviation,
        orbit_eccentricity=orbit_ecc,
        star_mass=stars[0].mass if stars else 1.0,
    )

    if not runaway_greenhouse:
        return
    if mw.size_detail.advanced_mean_temperature_k is None:
        return

    # Optional runaway greenhouse check (WBH p.79)
    rg = check_runaway_greenhouse(
        atmosphere=mw.atmosphere,
        temp_k=mw.size_detail.advanced_mean_temperature_k,
        age_gyr=system.stellar_system.primary.age_gyr,
        size=mw.size,
    )
    if rg is None:
        return
    mw.size_detail.runaway_greenhouse = True
    if rg.new_atmosphere is not None:
        mw.atmosphere = rg.new_atmosphere
    mw.temperature = "Boiling"
    mw.hydrographics = generate_hydrographics(mw.size, mw.atmosphere, "Boiling")
    mw.hydrographic_detail = generate_hydrographic_detail(
        mw.hydrographics, mw.size,
        atmosphere=mw.atmosphere,
        temperature="Boiling",
    )
    pressure_bar = (
        mw.atmosphere_detail.pressure_bar
        if mw.atmosphere_detail is not None else None
    )
    generate_advanced_mean_temperature(
        mw.size_detail,
        atmosphere=mw.atmosphere,
        hydrographics=mw.hydrographics,
        pressure_bar=pressure_bar,
        luminosity=interior_lum,
        orbit_au=mw_au,
        hz_deviation=mw_orbit.hz_deviation,
        orbit_eccentricity=orbit_ecc,
        star_mass=stars[0].mass if stars else 1.0,
    )
    # Sync the orbit slot WorldDetail SAH with any atmosphere/hydro mutations
    # (e.g. runaway greenhouse).  No-op when attach_detail() hasn't run yet.
    if mw_orbit.world_type == "gas_giant":
        if mw_orbit.detail and mw_orbit.detail.moons:
            sat_det = mw_orbit.detail.moons[0].detail
            if sat_det is not None:
                sat_det.sah = mw.uwp()[1:4]
    elif mw_orbit.detail is not None:
        mw_orbit.detail.sah = mw.uwp()[1:4]


def _get_mainworld_moons(system) -> list:
    """Return the generated Moon objects for the mainworld (after attach_detail)."""
    mw_orbit = system.mainworld_orbit
    if mw_orbit is None or mw_orbit.detail is None:
        return []
    if mw_orbit.world_type == "gas_giant":
        if mw_orbit.detail.moons:
            sat = mw_orbit.detail.moons[0]
            if sat.detail:
                return sat.detail.moons or []
        return []
    return mw_orbit.detail.moons or []


def _apply_mainworld_moon_tidal(system) -> None:
    """Apply moon tidal DMs and compute seismic stress for mainworld.

    Must be called after both attach_detail() and _attach_mainworld_physical().
    """
    mw = system.mainworld
    mw_orbit = system.mainworld_orbit
    if mw is None or mw.size_detail is None or isinstance(mw.size_detail, BeltPhysical) or mw_orbit is None:
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
# Endpoint 1:  GET/POST /api/world
# ===========================================================================

@app.api_route("/api/world", methods=["GET", "POST"])
@limiter.limit(_RATE_LIMIT)
async def generate_single_world(request: Request) -> Response:
    """Generate a single Traveller mainworld (CRB procedure).

    Parameters: name (str, opt), seed (int, opt).
    """
    logger.info("generate_single_world [method=%s]", request.method)
    body = await _get_body(request)
    name, err = parse_name(request, body)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    try:
        seed, rng = apply_seed(seed_val)
        world = _build_world(name or "World-1", seed, rng)
    except Exception as exc:
        logger.exception("Error generating world: %s", exc)
        return error("An unexpected error occurred while generating the world.",
                     ERR_INTERNAL, status_code=500)
    logger.info("Generated world UWP=%s name=%s", world.uwp(), world.name)
    return ok(world.to_dict())


# ===========================================================================
# Endpoint 2:  POST /api/worlds  (batch)
# ===========================================================================

@app.post("/api/worlds")
@limiter.limit(_RATE_LIMIT)
async def generate_world_batch(request: Request) -> Response:  # pylint: disable=too-many-return-statements,too-many-locals
    """Batch-generate Traveller mainworlds.

    Parameters: count (int, opt, default 1), prefix (str, opt, default "World-"),
                seed (int, opt).
    """
    logger.info("generate_world_batch called")
    body: dict = {}
    body_raw = await request.body()
    if body_raw:
        try:
            parsed = await request.json()
            if not isinstance(parsed, dict):
                return error("Request body must be a JSON object.", ERR_INVALID_BODY)
            body = parsed
        except (ValueError, TypeError):
            return error("Request body is not valid JSON.", ERR_INVALID_BODY)

    count, err = parse_count(request, body)
    if err:
        return err
    count = count or 1

    max_prefix = 32
    prefix = (str(body.get("prefix", "")).strip()
               or request.query_params.get("prefix", "").strip()
               or "World-")
    if len(prefix) > max_prefix:
        return error(f"'prefix' must be {max_prefix} characters or fewer.",
                     ERR_INVALID_BODY)

    seed_val, err = parse_seed(request, body)
    if err:
        return err

    try:
        seed, rng = apply_seed(seed_val)
        worlds = []
        for i in range(count):
            world = _build_world(f"{prefix}{i+1}", seed, rng)
            worlds.append(world.to_dict())
    except Exception as exc:
        logger.exception("Error generating batch: %s", exc)
        return error("An unexpected error occurred while generating the world batch.",
                     ERR_INTERNAL, status_code=500)

    logger.info("Generated batch count=%d prefix=%s", count, prefix)
    return ok({"count": count, "seed": seed, "worlds": worlds})


# ===========================================================================
# Endpoint 3:  GET /api/world/{name}/card  (HTML mainworld card)
# (registered before /api/world/{name} to avoid shadowing)
# ===========================================================================

@app.get("/api/world/{name}/card")
@limiter.limit(_RATE_LIMIT)
async def generate_world_card(request: Request) -> Response:  # pylint: disable=too-many-locals
    """Return a standalone HTML mainworld display card.

    Parameters: seed (int, opt), detail (bool, opt).
    When detail=true, generates a full system and returns the mainworld card
    with all detail cards (physical, atmosphere, biological, habitability).
    """
    route_name = request.path_params.get("name", "").strip() or None
    logger.info("generate_world_card [name=%s]", route_name)
    body = await _get_body(request)
    name, err = parse_name(request, body, route_name=route_name)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    want_detail = parse_detail(request, body)
    want_settlement = parse_settlement_type(request, body)
    want_social_detail = parse_social_detail(request, body)
    try:
        seed, rng = apply_seed(seed_val)
        if want_detail:
            system = generate_full_system(name=name or "World-1", seed=seed, rng=rng)
            if system.mainworld is None:
                return error("No mainworld in generated system.",
                             ERR_INTERNAL, status_code=500)
            apply_mainworld_social(system.mainworld, rng=rng, settlement_type=want_settlement)
            _attach_mainworld_physical(system, rng=rng)
            _apply_mainworld_moon_tidal(system)
            attach_detail(system, rng=rng)
            attach_body_names(system)
            if want_social_detail:
                attach_population_detail(system, rng=rng)
                attach_government_detail(system, rng=rng)
                attach_law_detail(system, rng=rng)
                attach_tech_detail(system, rng=rng)
            world = system.mainworld
        else:
            # Minimal path: matches gen-ui with system detail and population detail off.
            # Atmosphere and hydrographic detail are always generated; physical is not.
            world = generate_world(name=name or "World-1", seed=seed, rng=rng)
            world.atmosphere_detail = generate_atmosphere_detail(
                world.atmosphere, world.size, temperature=world.temperature,
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
        html = world.to_html()
    except Exception as exc:
        logger.exception("Error generating world card: %s", exc)
        return error("An unexpected error occurred while generating the world card.",
                     ERR_INTERNAL, status_code=500)
    logger.info("Generated world card UWP=%s name=%s", world.uwp(), world.name)
    return HTMLResponse(content=html, status_code=200)


# ===========================================================================
# Endpoint 4:  GET /api/world/{name}
# ===========================================================================

@app.get("/api/world/{name}")
@limiter.limit(_RATE_LIMIT)
async def generate_named_world(request: Request) -> Response:
    """Generate a mainworld; name from URL path.

    Parameters: seed (int, opt).
    """
    route_name = request.path_params.get("name", "").strip() or None
    logger.info("generate_named_world [name=%s]", route_name)
    body = await _get_body(request)
    name, err = parse_name(request, body, route_name=route_name)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    try:
        seed, rng = apply_seed(seed_val)
        world = _build_world(name or "World-1", seed, rng)
    except Exception as exc:
        logger.exception("Error generating world: %s", exc)
        return error("An unexpected error occurred while generating the world.",
                     ERR_INTERNAL, status_code=500)
    logger.info("Generated world UWP=%s name=%s", world.uwp(), world.name)
    return ok(world.to_dict())


# ===========================================================================
# Endpoint 5:  GET/POST /api/system/full
# (registered before /api/system/{name} to avoid shadowing)
# ===========================================================================

@app.api_route("/api/system/full", methods=["GET", "POST"])
@limiter.limit(_RATE_LIMIT)
async def generate_full_system_complete(request: Request) -> Response:  # pylint: disable=too-many-locals,too-many-return-statements
    """Generate a complete star system with all secondary world and moon profiles.

    Always runs attach_detail() — every orbit slot and moon receives its full
    SAH/social profile.

    Parameters: name, seed, format, nhz_atmospheres, orbital_eccentricity,
                orbital_inclination, runaway_greenhouse, independent_government,
                optional_biomass_rule, optional_inhospitable_rule.
    """
    logger.info("generate_full_system_complete [method=%s]", request.method)
    body = await _get_body(request)
    name, err = parse_name(request, body)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    fmt = parse_format(request, body)
    want_nhz = parse_nhz_atmospheres(request, body)
    want_ecc = parse_orbital_eccentricity(request, body)
    want_incl = parse_orbital_inclination(request, body)
    want_rg = parse_runaway_greenhouse(request, body)
    want_indep = parse_independent_government(request, body)
    want_bio = parse_optional_biomass(request, body)
    want_inhospitable = parse_optional_inhospitable(request, body)
    want_settlement = parse_settlement_type(request, body)
    want_social_detail = parse_social_detail(request, body)
    want_mw_card = parse_include_mw_card(request, body)
    try:
        seed, rng = apply_seed(seed_val)
        system = generate_full_system(name=name or "World-1",
                                      seed=seed, rng=rng,
                                      nhz_atmospheres=want_nhz,
                                      orbital_eccentricity=want_ecc,
                                      orbital_inclination=want_incl)
        run_detail_pipeline(system, rng, PipelineOptions(
            want_detail=True,
            want_select_mw=True,
            runaway_greenhouse=want_rg,
            independent_government=want_indep,
            optional_biomass=want_bio,
            optional_inhospitable=want_inhospitable,
            settlement_type=want_settlement,
            want_social_detail=want_social_detail,
        ))
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
        sys_html = system.to_html(detail_attached=True)
        if want_mw_card and mw is not None:
            return JSONResponse({"sys_html": sys_html, "mw_html": mw.to_html()})
        return HTMLResponse(content=sys_html, status_code=200)
    if fmt == "text":
        return PlainTextResponse(content=system.summary(), status_code=200)
    return ok(system.to_dict())


# ===========================================================================
# Endpoint 6:  POST /api/system/from-world
# (registered before /api/system/{name} to avoid shadowing)
# ===========================================================================

@app.post("/api/system/from-world")
@limiter.limit(_RATE_LIMIT)
async def generate_system_from_existing_world(request: Request) -> Response:  # pylint: disable=too-many-locals,too-many-return-statements
    """Generate a full star system around an existing mainworld.

    The request body must be a mainworld JSON object (as returned by any
    world or system endpoint).  UWP and PBG are preserved.  Temperature is
    recalculated from orbital position.

    Parameters (body + query string): <world JSON> required, seed, detail,
    format, runaway_greenhouse, independent_government, optional_biomass_rule,
    optional_inhospitable_rule.
    """
    logger.info("generate_system_from_existing_world called")
    body_raw = await request.body()
    body: dict = {}
    if body_raw:
        try:
            parsed = await request.json()
            if not isinstance(parsed, dict):
                return error("Request body must be a JSON object.", ERR_INVALID_BODY)
            body = parsed
        except (ValueError, TypeError):
            return error("Request body is not valid JSON.", ERR_INVALID_BODY)

    world_dict, err = parse_world_json(body_raw, body)
    if err or world_dict is None:
        return err or error("Missing world data.", ERR_INVALID_BODY)
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    want_detail = parse_detail(request, body)
    fmt = parse_format(request, body)
    want_nhz = parse_nhz_atmospheres(request, body)
    want_ecc = parse_orbital_eccentricity(request, body)
    want_incl = parse_orbital_inclination(request, body)
    want_rg = parse_runaway_greenhouse(request, body)
    want_indep = parse_independent_government(request, body)
    want_bio = parse_optional_biomass(request, body)
    want_inhospitable = parse_optional_inhospitable(request, body)
    try:
        seed, rng = apply_seed(seed_val)
        world = World.from_dict(world_dict)
        system = generate_system_from_world(world, seed=seed, rng=rng,
                                            nhz_atmospheres=want_nhz,
                                            orbital_eccentricity=want_ecc,
                                            orbital_inclination=want_incl)
        _attach_mainworld_physical(system, runaway_greenhouse=want_rg, rng=rng)
        if want_detail:
            attach_detail(system, rng=rng,
                          independent_government=want_indep,
                          optional_biomass_rule=want_bio,
                          optional_inhospitable_rule=want_inhospitable)
            attach_body_names(system)
            _apply_mainworld_moon_tidal(system)
    except Exception as exc:
        logger.exception("Error generating system from world: %s", exc)
        return error("An unexpected error occurred while generating the system.",
                     ERR_INTERNAL, status_code=500)
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
        return HTMLResponse(
            content=system.to_html(detail_attached=want_detail), status_code=200
        )
    if fmt == "text":
        return PlainTextResponse(content=system.summary(), status_code=200)
    return ok(system.to_dict())


# ===========================================================================
# Endpoint 7:  GET/POST /api/system
# ===========================================================================

@app.api_route("/api/system", methods=["GET", "POST"])
@limiter.limit(_RATE_LIMIT)
async def generate_single_system(request: Request) -> Response:  # pylint: disable=too-many-locals
    """Generate a full Traveller star system (WBH stellar + orbit + CRB mainworld).

    Parameters: name, seed, detail, nhz_atmospheres, orbital_eccentricity,
                orbital_inclination, runaway_greenhouse, independent_government,
                optional_biomass_rule, optional_inhospitable_rule.
    """
    logger.info("generate_single_system [method=%s]", request.method)
    body = await _get_body(request)
    name, err = parse_name(request, body)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    want_detail = parse_detail(request, body)
    want_nhz = parse_nhz_atmospheres(request, body)
    want_ecc = parse_orbital_eccentricity(request, body)
    want_incl = parse_orbital_inclination(request, body)
    want_rg = parse_runaway_greenhouse(request, body)
    want_indep = parse_independent_government(request, body)
    want_bio = parse_optional_biomass(request, body)
    want_inhospitable = parse_optional_inhospitable(request, body)
    want_settlement = parse_settlement_type(request, body)
    want_social_detail = parse_social_detail(request, body)
    try:
        seed, rng = apply_seed(seed_val)
        system = generate_full_system(name=name or "World-1",
                                      seed=seed, rng=rng,
                                      nhz_atmospheres=want_nhz,
                                      orbital_eccentricity=want_ecc,
                                      orbital_inclination=want_incl)
        run_detail_pipeline(system, rng, PipelineOptions(
            want_detail=want_detail,
            want_select_mw=True,
            runaway_greenhouse=want_rg,
            independent_government=want_indep,
            optional_biomass=want_bio,
            optional_inhospitable=want_inhospitable,
            settlement_type=want_settlement,
            want_social_detail=want_social_detail,
        ))
    except Exception as exc:
        logger.exception("Error generating system: %s", exc)
        return error("An unexpected error occurred while generating the system.",
                     ERR_INTERNAL, status_code=500)
    mw = system.mainworld
    logger.info("Generated system name=%s stars=%d worlds=%d detail=%s uwp=%s",
                name, len(system.stellar_system.stars),
                system.system_orbits.total_worlds, want_detail,
                mw.uwp() if mw else "—")
    return ok(system.to_dict())


# ===========================================================================
# Endpoint 8:  GET /api/system/svg  (SVG system map)
# (registered before /api/system/{name} to avoid shadowing)
# ===========================================================================

def _parse_bool_flag(val: object) -> bool:
    """Return True for '1', 'true', 'yes' (case-insensitive) or bool True."""
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes")


@app.get("/api/system/svg")
@limiter.limit(_RATE_LIMIT)
async def generate_system_svg(request: Request) -> Response:  # pylint: disable=too-many-locals
    """Generate a full star system and return it as an SVG map image.

    Query parameters
    ----------------
    name        : str   — world/system name (required)
    seed        : int   — RNG seed (random if absent)
    detail      : bool  — attach secondary world detail (default false)
    perspective : bool  — 60° perspective projection instead of top-down (default false)
    white_bg    : bool  — light background instead of dark (default false)
    """
    params = request.query_params

    name = str(params.get("name", "")).strip()
    if not name:
        return error("name is required", ERR_MISSING_PARAM, 400)

    seed_raw      = params.get("seed")
    seed_val, rng = apply_seed(int(seed_raw) if seed_raw is not None else None)
    want_detail   = _parse_bool_flag(params.get("detail", False))
    persp         = _parse_bool_flag(params.get("perspective", False))
    white_bg      = _parse_bool_flag(params.get("white_bg", False))
    want_ecc      = _parse_bool_flag(params.get("orbital_eccentricity", False))
    want_incl     = _parse_bool_flag(params.get("orbital_inclination",  False))

    try:
        system = generate_full_system(name, seed=seed_val, rng=rng,
                                      orbital_eccentricity=want_ecc,
                                      orbital_inclination=want_incl)
        if system.mainworld is None:
            return error("No mainworld in generated system.", ERR_INTERNAL, 500)
        apply_mainworld_social(system.mainworld, rng=rng)
        if want_detail:
            attach_detail(system, rng=rng)
            attach_body_names(system)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Error generating system SVG: %s", exc)
        return error("An unexpected error occurred while generating the system.", ERR_INTERNAL, 500)

    palette   = _PALETTE_LIGHT if white_bg else PALETTE_DARK
    svg_str, _h = build_svg(system, canvas_w=1600, palette=palette, perspective=persp)

    return Response(content=svg_str, media_type="image/svg+xml")


# ===========================================================================
# Endpoint 9:  GET /api/system/{name}/card  (HTML system card)
# (registered before /api/system/{name} to avoid shadowing)
# ===========================================================================

@app.get("/api/system/{name}/card")
@limiter.limit(_RATE_LIMIT)
async def generate_system_card(request: Request) -> Response:  # pylint: disable=too-many-locals
    """Return a standalone HTML system display card.

    Parameters: seed, detail, nhz_atmospheres, orbital_eccentricity,
                orbital_inclination, runaway_greenhouse, independent_government,
                optional_biomass_rule, optional_inhospitable_rule.
    """
    route_name = request.path_params.get("name", "").strip() or None
    logger.info("generate_system_card [name=%s]", route_name)
    body = await _get_body(request)
    name, err = parse_name(request, body, route_name=route_name)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    want_detail = parse_detail(request, body)
    want_nhz = parse_nhz_atmospheres(request, body)
    want_ecc = parse_orbital_eccentricity(request, body)
    want_incl = parse_orbital_inclination(request, body)
    want_rg = parse_runaway_greenhouse(request, body)
    want_indep = parse_independent_government(request, body)
    want_bio = parse_optional_biomass(request, body)
    want_inhospitable = parse_optional_inhospitable(request, body)
    want_settlement = parse_settlement_type(request, body)
    want_social_detail = parse_social_detail(request, body)
    try:
        seed, rng = apply_seed(seed_val)
        system = generate_full_system(name=name or "World-1",
                                      seed=seed, rng=rng,
                                      nhz_atmospheres=want_nhz,
                                      orbital_eccentricity=want_ecc,
                                      orbital_inclination=want_incl)
        run_detail_pipeline(system, rng, PipelineOptions(
            want_detail=want_detail,
            want_select_mw=True,
            runaway_greenhouse=want_rg,
            independent_government=want_indep,
            optional_biomass=want_bio,
            optional_inhospitable=want_inhospitable,
            settlement_type=want_settlement,
            want_social_detail=want_social_detail,
        ))
        html = system.to_html(detail_attached=want_detail)
    except Exception as exc:
        logger.exception("Error generating system card: %s", exc)
        return error("An unexpected error occurred while generating the system card.",
                     ERR_INTERNAL, status_code=500)
    mw = system.mainworld
    logger.info("Generated system card name=%s detail=%s uwp=%s",
                name, want_detail, mw.uwp() if mw else "—")
    return HTMLResponse(content=html, status_code=200)


# ===========================================================================
# Endpoint 9:  GET /api/system/{name}
# ===========================================================================

@app.get("/api/system/{name}")
@limiter.limit(_RATE_LIMIT)
async def generate_named_system(request: Request) -> Response:  # pylint: disable=too-many-locals
    """Generate a full star system; mainworld name from URL path.

    Parameters: seed, detail, nhz_atmospheres, orbital_eccentricity,
                orbital_inclination, runaway_greenhouse, independent_government,
                optional_biomass_rule, optional_inhospitable_rule.
    """
    route_name = request.path_params.get("name", "").strip() or None
    logger.info("generate_named_system [name=%s]", route_name)
    body = await _get_body(request)
    name, err = parse_name(request, body, route_name=route_name)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    want_detail = parse_detail(request, body)
    want_nhz = parse_nhz_atmospheres(request, body)
    want_ecc = parse_orbital_eccentricity(request, body)
    want_incl = parse_orbital_inclination(request, body)
    want_rg = parse_runaway_greenhouse(request, body)
    want_indep = parse_independent_government(request, body)
    want_bio = parse_optional_biomass(request, body)
    want_inhospitable = parse_optional_inhospitable(request, body)
    try:
        seed, rng = apply_seed(seed_val)
        system = generate_full_system(name=name or "World-1",
                                      seed=seed, rng=rng,
                                      nhz_atmospheres=want_nhz,
                                      orbital_eccentricity=want_ecc,
                                      orbital_inclination=want_incl)
        run_detail_pipeline(system, rng, PipelineOptions(
            want_detail=want_detail,
            want_select_mw=False,
            runaway_greenhouse=want_rg,
            independent_government=want_indep,
            optional_biomass=want_bio,
            optional_inhospitable=want_inhospitable,
        ))
    except Exception as exc:
        logger.exception("Error generating system: %s", exc)
        return error("An unexpected error occurred while generating the system.",
                     ERR_INTERNAL, status_code=500)
    mw = system.mainworld
    logger.info("Generated system name=%s stars=%d worlds=%d detail=%s uwp=%s",
                name, len(system.stellar_system.stars),
                system.system_orbits.total_worlds, want_detail,
                mw.uwp() if mw else "—")
    return ok(system.to_dict())


# ===========================================================================
# Map system shared implementation
# ===========================================================================

def _map_system_response(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    name: Optional[str],
    sector: Optional[str],
    hex_pos: Optional[str],
    seed: Optional[int],
    want_detail: bool,
    fmt: str,
    want_nhz: bool = False,
    want_ecc: bool = False,
    want_incl: bool = False,
    want_rg: bool = False,
    want_indep: bool = False,
    want_bio: bool = False,
    want_inhospitable: bool = False,
) -> Response:
    """Shared implementation for both map/system endpoint variants."""
    seed, rng = apply_seed(seed)
    try:
        system = generate_system_from_map(
            name=name, sector=sector, hex_pos=hex_pos,
            seed=seed, attach=False,
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
    _attach_mainworld_physical(system, runaway_greenhouse=want_rg, rng=rng)
    if want_detail:
        attach_detail(system,
                      independent_government=want_indep,
                      optional_biomass_rule=want_bio,
                      optional_inhospitable_rule=want_inhospitable)
        attach_body_names(system)
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
        return HTMLResponse(
            content=system.to_html(detail_attached=want_detail), status_code=200
        )
    if fmt == "text":
        return PlainTextResponse(content=system.summary(), status_code=200)
    return ok(system.to_dict())


# ===========================================================================
# Endpoint 11:  GET/POST /api/map/system
# ===========================================================================

@app.api_route("/api/map/system", methods=["GET", "POST"])
@limiter.limit(_RATE_LIMIT)
async def generate_map_system(request: Request) -> Response:  # pylint: disable=too-many-return-statements,too-many-locals
    """Fetch canonical data from TravellerMap, then generate a full system.

    Sector is always required.  Identify the world by name or hex position.

    Parameters: sector (required), name or hex, seed, detail, format,
                nhz_atmospheres, orbital_eccentricity, orbital_inclination,
                runaway_greenhouse, independent_government, optional_biomass_rule,
                optional_inhospitable_rule.
    """
    logger.info("generate_map_system [method=%s]", request.method)
    body = await _get_body(request)
    name, err = parse_name(request, body)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    sector, err = parse_sector(request, body)
    if err:
        return err
    hex_pos, err = parse_hex_pos(request, body)
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
    want_detail = parse_detail(request, body)
    fmt = parse_format(request, body)
    want_nhz = parse_nhz_atmospheres(request, body)
    want_ecc = parse_orbital_eccentricity(request, body)
    want_incl = parse_orbital_inclination(request, body)
    want_rg = parse_runaway_greenhouse(request, body)
    want_indep = parse_independent_government(request, body)
    want_bio = parse_optional_biomass(request, body)
    want_inhospitable = parse_optional_inhospitable(request, body)
    return _map_system_response(name, sector, hex_pos, seed_val, want_detail, fmt,
                                want_nhz, want_ecc, want_incl,
                                want_rg, want_indep, want_bio, want_inhospitable)


# ===========================================================================
# Endpoint 12:  GET/POST /api/map/system/full
# (registered before /api/map/system/{name} to avoid shadowing)
# ===========================================================================

@app.api_route("/api/map/system/full", methods=["GET", "POST"])
@limiter.limit(_RATE_LIMIT)
async def generate_map_system_full(request: Request) -> Response:  # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches,too-many-statements
    """Fetch canonical data from TravellerMap and generate a fully detailed system.

    Like /api/map/system but always runs attach_detail(), apply_secondary_social(),
    and accepts the full suite of detail flags and format selection.  The
    canonical UWP and stellar classification from TravellerMap are preserved.

    Sector is always required.  Identify the world by name or hex position.

    Parameters: sector (required), name or hex, seed, format,
                nhz_atmospheres, orbital_eccentricity, orbital_inclination,
                runaway_greenhouse, independent_government, optional_biomass_rule,
                optional_inhospitable_rule, social_detail.
    """
    logger.info("generate_map_system_full [method=%s]", request.method)
    body = await _get_body(request)
    name, err = parse_name(request, body)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    sector, err = parse_sector(request, body)
    if err:
        return err
    hex_pos, err = parse_hex_pos(request, body)
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
    fmt = parse_format(request, body)
    want_nhz = parse_nhz_atmospheres(request, body)
    want_ecc = parse_orbital_eccentricity(request, body)
    want_incl = parse_orbital_inclination(request, body)
    want_rg = parse_runaway_greenhouse(request, body)
    want_indep = parse_independent_government(request, body)
    want_bio = parse_optional_biomass(request, body)
    want_inhospitable = parse_optional_inhospitable(request, body)
    want_social_detail = parse_social_detail(request, body)
    want_mw_card = parse_include_mw_card(request, body)
    seed, rng = apply_seed(seed_val)
    try:
        system = generate_system_from_map(
            name=name, sector=sector, hex_pos=hex_pos,
            seed=seed, attach=False,
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
        logger.exception("Error generating map system full: %s", exc)
        return error(
            "An unexpected error occurred while generating the map system.",
            ERR_INTERNAL, status_code=500,
        )
    try:
        _attach_mainworld_physical(system, runaway_greenhouse=want_rg, rng=rng)
        attach_detail(system, rng=rng,
                      independent_government=want_indep,
                      optional_biomass_rule=want_bio,
                      optional_inhospitable_rule=want_inhospitable)
        attach_body_names(system)
        _apply_mainworld_moon_tidal(system)
        apply_secondary_social(system, independent_government=want_indep, rng=rng)
        if want_social_detail:
            attach_population_detail(system, rng=rng)
            attach_government_detail(system, rng=rng)
            attach_law_detail(system, rng=rng)
            attach_tech_detail(system, rng=rng)
    except Exception as exc:
        logger.exception("Error in map system full detail generation: %s", exc)
        return error(
            "An unexpected error occurred while generating the map system.",
            ERR_INTERNAL, status_code=500,
        )
    mw = system.mainworld
    logger.info(
        "Generated map system full name=%s stars=%d worlds=%d format=%s uwp=%s",
        name or hex_pos,
        len(system.stellar_system.stars),
        system.system_orbits.total_worlds,
        fmt,
        mw.uwp() if mw else "—",
    )
    if fmt == "html":
        sys_html = system.to_html(detail_attached=True)
        if want_mw_card and mw is not None:
            return JSONResponse({"sys_html": sys_html, "mw_html": mw.to_html()})
        return HTMLResponse(content=sys_html, status_code=200)
    if fmt == "text":
        return PlainTextResponse(content=system.summary(), status_code=200)
    return ok(system.to_dict())


# ===========================================================================
# Endpoint 13:  GET /api/map/system/svg  (TravellerMap SVG system map)
# (registered before /api/map/system/{name} to avoid shadowing)
# ===========================================================================

@app.get("/api/map/system/svg")
@limiter.limit(_RATE_LIMIT)
async def generate_map_system_svg(request: Request) -> Response:  # pylint: disable=too-many-return-statements,too-many-locals
    """Fetch canonical data from TravellerMap and return it as an SVG map image.

    Uses the canonical PBG world/belt/gas-giant counts so the map matches
    the system detail card.  Sector is always required.

    Query parameters
    ----------------
    sector      : str  — sector name (required)
    name        : str  — world name within the sector
    hex         : str  — 4-digit hex position (alternative to name)
    seed        : int  — RNG seed (random if absent)
    detail      : bool — attach secondary world detail (default false)
    perspective : bool — 60° perspective projection (default false)
    white_bg    : bool — light background (default false)
    """
    logger.info("generate_map_system_svg called")
    body = await _get_body(request)
    name, err = parse_name(request, body)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    sector, err = parse_sector(request, body)
    if err:
        return err
    hex_pos, err = parse_hex_pos(request, body)
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
    want_detail = parse_detail(request, body)
    persp     = _parse_bool_flag(request.query_params.get("perspective",           False))
    white_bg  = _parse_bool_flag(request.query_params.get("white_bg",             False))
    want_ecc  = _parse_bool_flag(request.query_params.get("orbital_eccentricity", False))
    want_incl = _parse_bool_flag(request.query_params.get("orbital_inclination",  False))
    seed, rng = apply_seed(seed_val)
    try:
        system = generate_system_from_map(
            name=name, sector=sector, hex_pos=hex_pos,
            seed=seed, attach=False,
            orbital_eccentricity=want_ecc,
            orbital_inclination=want_incl,
        )
    except LookupError as exc:
        logger.warning("TravellerMap lookup failed for SVG: %s", exc)
        return error(str(exc), ERR_NOT_FOUND, status_code=404)
    except urllib.error.URLError as exc:
        logger.error("TravellerMap upstream error for SVG: %s", exc)
        return error(
            "Could not reach the upstream data source. Please try again later.",
            ERR_UPSTREAM, status_code=502,
        )
    except Exception as exc:
        logger.exception("Error fetching map system for SVG: %s", exc)
        return error(
            "An unexpected error occurred while generating the map SVG.",
            ERR_INTERNAL, status_code=500,
        )
    if want_detail:
        try:
            attach_detail(system, rng=rng)
            attach_body_names(system)
        except Exception as exc:
            logger.exception("Error attaching detail for map SVG: %s", exc)
            return error(
                "An unexpected error occurred while generating the map SVG.",
                ERR_INTERNAL, status_code=500,
            )
    palette = _PALETTE_LIGHT if white_bg else PALETTE_DARK
    svg_str, _ = build_svg(system, canvas_w=1600, palette=palette, perspective=persp)
    logger.info("Generated map system SVG name=%s sector=%s", name or hex_pos, sector)
    return Response(content=svg_str, media_type="image/svg+xml")


# ===========================================================================
# Endpoint 14:  GET /api/map/world/card  (TravellerMap mainworld card, HTML)
# ===========================================================================

@app.get("/api/map/world/card")
@limiter.limit(_RATE_LIMIT)
async def generate_map_world_card(request: Request) -> Response:  # pylint: disable=too-many-locals,too-many-return-statements
    """Fetch canonical data from TravellerMap and return a detailed mainworld HTML card.

    Runs the same full detail pipeline as /api/map/system/full (attach_detail,
    physical, tidal, secondary social) then returns system.mainworld.to_html().
    Intended for use alongside /api/map/system/full?format=html to populate
    the Mainworld tab in the web UI.

    Parameters: sector (required), name or hex, seed,
                nhz_atmospheres, orbital_eccentricity, orbital_inclination,
                runaway_greenhouse, independent_government, optional_biomass_rule,
                optional_inhospitable_rule, social_detail.
    """
    logger.info("generate_map_world_card called")
    body = await _get_body(request)
    name, err = parse_name(request, body)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    sector, err = parse_sector(request, body)
    if err:
        return err
    hex_pos, err = parse_hex_pos(request, body)
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
    want_nhz = parse_nhz_atmospheres(request, body)
    want_ecc = parse_orbital_eccentricity(request, body)
    want_incl = parse_orbital_inclination(request, body)
    want_rg = parse_runaway_greenhouse(request, body)
    want_indep = parse_independent_government(request, body)
    want_bio = parse_optional_biomass(request, body)
    want_inhospitable = parse_optional_inhospitable(request, body)
    want_social_detail = parse_social_detail(request, body)
    seed, rng = apply_seed(seed_val)
    try:
        system = generate_system_from_map(
            name=name, sector=sector, hex_pos=hex_pos,
            seed=seed, attach=False,
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
        logger.exception("Error generating map world card: %s", exc)
        return error(
            "An unexpected error occurred while generating the map world card.",
            ERR_INTERNAL, status_code=500,
        )
    try:
        _attach_mainworld_physical(system, runaway_greenhouse=want_rg, rng=rng)
        attach_detail(system, rng=rng,
                      independent_government=want_indep,
                      optional_biomass_rule=want_bio,
                      optional_inhospitable_rule=want_inhospitable)
        attach_body_names(system)
        _apply_mainworld_moon_tidal(system)
        apply_secondary_social(system, independent_government=want_indep, rng=rng)
        if want_social_detail:
            attach_population_detail(system, rng=rng)
            attach_government_detail(system, rng=rng)
            attach_law_detail(system, rng=rng)
            attach_tech_detail(system, rng=rng)
    except Exception as exc:
        logger.exception("Error in map world card detail generation: %s", exc)
        return error(
            "An unexpected error occurred while generating the map world card.",
            ERR_INTERNAL, status_code=500,
        )
    mw = system.mainworld
    if mw is None:
        return error("No mainworld in generated system.", ERR_INTERNAL, 500)
    logger.info("Generated map world card name=%s sector=%s uwp=%s",
                name or hex_pos, sector, mw.uwp())
    return HTMLResponse(content=mw.to_html(), status_code=200)


# ===========================================================================
# Endpoint 15:  GET /api/map/system/{name}
# ===========================================================================

@app.get("/api/map/system/{name}")
@limiter.limit(_RATE_LIMIT)
async def generate_named_map_system(request: Request) -> Response:  # pylint: disable=too-many-locals
    """Fetch canonical data from TravellerMap; world name from URL path.

    Sector is always required as a query-string parameter.

    Parameters: sector (required), seed, detail, format, nhz_atmospheres,
                orbital_eccentricity, orbital_inclination, runaway_greenhouse,
                independent_government, optional_biomass_rule,
                optional_inhospitable_rule.
    """
    route_name = request.path_params.get("name", "").strip() or None
    logger.info("generate_named_map_system [name=%s]", route_name)
    body = await _get_body(request)
    name, err = parse_name(request, body, route_name=route_name)
    if err:
        return err
    seed_val, err = parse_seed(request, body)
    if err:
        return err
    sector, err = parse_sector(request, body)
    if err:
        return err
    if not sector:
        return error(
            "The 'sector' query parameter is required to avoid same-name ambiguity.",
            ERR_MISSING_PARAM,
        )
    hex_pos, err = parse_hex_pos(request, body)
    if err:
        return err
    want_detail = parse_detail(request, body)
    fmt = parse_format(request, body)
    want_nhz = parse_nhz_atmospheres(request, body)
    want_ecc = parse_orbital_eccentricity(request, body)
    want_incl = parse_orbital_inclination(request, body)
    want_rg = parse_runaway_greenhouse(request, body)
    want_indep = parse_independent_government(request, body)
    want_bio = parse_optional_biomass(request, body)
    want_inhospitable = parse_optional_inhospitable(request, body)
    return _map_system_response(name, sector, hex_pos, seed_val, want_detail, fmt,
                                want_nhz, want_ecc, want_incl,
                                want_rg, want_indep, want_bio, want_inhospitable)
