"""system_pipeline.py — shared post-generate_full_system orchestration.

All three entry points (CLI traveller_system_gen.py, gen-ui app.py, and
fastapi/app.py) call run_detail_pipeline() after generate_full_system() to
attach physical detail, secondary world profiles, mainworld selection, and
social generation from a single shared implementation.

Public API
----------
PipelineOptions   dataclass of generation flags
run_detail_pipeline(system, rng, options)  mutates system in place
"""
import random
from dataclasses import dataclass
from typing import Optional

from traveller_world_gen import generate_hydrographics, apply_mainworld_social
from traveller_world_physical import generate_world_physical, apply_moon_tidal_effects
from traveller_world_atmosphere_detail import (
    generate_advanced_mean_temperature, check_runaway_greenhouse,
)
from traveller_hydro_detail import generate_hydrographic_detail
from traveller_world_detail import (
    attach_detail, apply_secondary_social, reattach_mainworld_orbit,
    gg_diameter_from_sah,
)
from traveller_world_population_detail import attach_population_detail
from traveller_world_government_detail import attach_government_detail
from traveller_world_law_detail import attach_law_detail
from traveller_world_tech_detail import attach_tech_detail
from traveller_system_gen import select_mainworld, attach_body_names


@dataclass
class PipelineOptions:  # pylint: disable=too-many-instance-attributes
    """All flags that control the post-generate_full_system detail pipeline."""
    want_detail:            bool = True
    want_select_mw:         bool = False
    runaway_greenhouse:     bool = False
    independent_government: bool = False
    optional_biomass:       bool = False
    optional_inhospitable:  bool = False
    settlement_type:        str  = "standard"
    want_social_detail:     bool = False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _compute_interior_luminosity(system, mw_au: float) -> float:
    """Sum luminosity of all stars at or interior to the mainworld orbit."""
    stars = system.stellar_system.stars
    return sum(s.luminosity for s in stars if s.orbit_au <= 0.0 or s.orbit_au < mw_au)


def _sync_orbit_sah(mw, mw_orbit) -> None:
    """Sync orbit-slot WorldDetail SAH after any atmosphere/hydro mutation.

    No-op when attach_detail() has not yet run (mw_orbit.detail is None).
    """
    if mw_orbit.world_type == "gas_giant":
        if mw_orbit.detail and mw_orbit.detail.moons:
            sat_det = mw_orbit.detail.moons[0].detail
            if sat_det is not None:
                sat_det.sah = mw.uwp()[1:4]
    elif mw_orbit.detail is not None:
        mw_orbit.detail.sah = mw.uwp()[1:4]


def _attach_physical(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        system,
        rng: Optional[random.Random],
        runaway_greenhouse: bool,
) -> None:
    """Run generate_world_physical + advanced mean temperature + optional RG.

    Mirrors FastAPI's _attach_mainworld_physical().  Always runs advanced
    mean temperature (WBH pp.47-50); runaway greenhouse is flag-controlled.
    """
    mw = system.mainworld
    if mw is None:
        return
    mw_orbit = system.mainworld_orbit
    stars = system.stellar_system.stars
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
            orbit_ecc = adj

    if mw_orbit is None or mw.size_detail is None:
        return

    mw_au = mw_orbit.orbit_au
    interior_lum = _compute_interior_luminosity(system, mw_au)
    pressure_bar = (
        mw.atmosphere_detail.pressure_bar if mw.atmosphere_detail is not None else None
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

    if not runaway_greenhouse or mw.size_detail.advanced_mean_temperature_k is None:
        _sync_orbit_sah(mw, mw_orbit)
        return

    rg = check_runaway_greenhouse(
        atmosphere=mw.atmosphere,
        temp_k=mw.size_detail.advanced_mean_temperature_k,
        age_gyr=system.stellar_system.primary.age_gyr,
        size=mw.size,
    )
    if rg is None:
        _sync_orbit_sah(mw, mw_orbit)
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
        mw.atmosphere_detail.pressure_bar if mw.atmosphere_detail is not None else None
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
    _sync_orbit_sah(mw, mw_orbit)


def _get_mainworld_moons(system) -> list:
    """Return Moon objects for the mainworld (requires attach_detail to have run)."""
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


def _apply_moon_tidal(system) -> None:
    """Apply moon tidal DMs and compute seismic stress for the mainworld.

    Requires both attach_detail() and _attach_physical() to have already run.
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_detail_pipeline(  # pylint: disable=too-many-branches
        system,
        rng: random.Random,
        options: Optional[PipelineOptions] = None,
) -> None:
    """Run all post-generate_full_system orchestration steps.

    Mutates system in place.  Call after generate_full_system() (or any
    generate_system_from_*() variant that returns a physical-only mainworld).

    When want_detail=False only apply_mainworld_social() runs.

    Pipeline order (when want_detail=True):
        _attach_physical → attach_detail → attach_body_names → _apply_moon_tidal
        → [select_mainworld → if swapped: re-physical]
        → apply_mainworld_social
        → [if swapped: reattach_mainworld_orbit + _apply_moon_tidal]
        → apply_secondary_social
        → [social detail: pop / gov / law / TL]
    """
    if options is None:
        options = PipelineOptions()

    swapped = False

    if options.want_detail and system.mainworld is not None:
        _attach_physical(system, rng, options.runaway_greenhouse)
        attach_detail(
            system, rng=rng,
            independent_government=options.independent_government,
            optional_biomass_rule=options.optional_biomass,
            optional_inhospitable_rule=options.optional_inhospitable,
        )
        attach_body_names(system)
        _apply_moon_tidal(system)

    if options.want_select_mw and options.want_detail:
        swapped = select_mainworld(system, rng=rng)
        if swapped:
            _attach_physical(system, rng, options.runaway_greenhouse)

    if system.mainworld is not None:
        apply_mainworld_social(
            system.mainworld, rng=rng, settlement_type=options.settlement_type,
        )

    if swapped and options.want_detail:
        reattach_mainworld_orbit(system, rng=rng)
        _apply_moon_tidal(system)

    if options.want_detail:
        apply_secondary_social(
            system,
            independent_government=options.independent_government,
            rng=rng,
        )

    if options.want_social_detail and options.want_detail:
        attach_population_detail(system, rng=rng)
        attach_government_detail(system, rng=rng)
        attach_law_detail(system, rng=rng)
        attach_tech_detail(system, rng=rng)
