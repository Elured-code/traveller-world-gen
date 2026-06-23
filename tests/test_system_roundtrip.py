"""
tests/test_system_roundtrip.py
==============================
Roundtrip tests for the from_dict() classmethods added to Star, StarSystem,
OrbitSlot, SystemOrbits, and TravellerSystem.
"""

import pytest

from traveller_gen.traveller_stellar_gen import Star, StarSystem
from traveller_gen.traveller_orbit_gen import OrbitSlot, SystemOrbits
from traveller_gen.traveller_system_gen import TravellerSystem, generate_full_system


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_star_dict(**overrides) -> dict:
    d = {
        "designation": "Aa",
        "role": "primary",
        "spectral_type": "G",
        "subtype": 2,
        "luminosity_class": "V",
        "mass_solar": 1.05,
        "temperature_k": 5800,
        "diameter_solar": 1.0,
        "luminosity_solar": 1.1,
        "orbit_number": None,
        "orbit_au": None,
        "age_gyr": 4.5,
        "ms_lifespan_gyr": 10.2,
        "orbit_period_yr": None,
        "special_notes": "",
    }
    d.update(overrides)
    return d


def _make_orbit_dict(**overrides) -> dict:
    d = {
        "star": "Aa",
        "orbit_number": 3.0,
        "orbit_au": 0.5,
        "slot_index": 2,
        "world_type": "terrestrial",
        "is_habitable_zone": True,
        "hz_deviation": 0.0,
        "temperature_zone": "temperate",
        "is_mainworld_candidate": True,
        "notes": "",
    }
    d.update(overrides)
    return d


# ---------------------------------------------------------------------------
# TestStarRoundtrip
# ---------------------------------------------------------------------------

class TestStarRoundtrip:
    def test_star_from_dict_basic(self):
        d = _make_star_dict()
        star = Star.from_dict(d)
        assert star.designation == "Aa"
        assert star.spectral_type == "G"
        assert star.subtype == 2
        assert star.lum_class == "V"
        assert star.mass == pytest.approx(1.05)
        assert star.temperature == 5800
        assert star.age_gyr == pytest.approx(4.5)
        assert star.orbit_number is None
        assert star.orbit_au is None

    def test_star_from_dict_eccentricity_inclination(self):
        d = _make_star_dict(
            designation="B",
            role="near",
            orbit_number=5.0,
            orbit_au=12.3,
            orbit_period_yr=30.5,
            orbit_eccentricity=0.15,
            orbit_inclination=12.5,
        )
        star = Star.from_dict(d)
        assert star.orbit_eccentricity == pytest.approx(0.15)
        assert star.orbit_inclination == pytest.approx(12.5)
        assert star.orbit_period_yr == pytest.approx(30.5)

    def test_star_from_dict_white_dwarf(self):
        d = _make_star_dict(
            spectral_type="D",
            subtype=None,
            luminosity_class="D",
        )
        star = Star.from_dict(d)
        assert star.spectral_type == "D"
        assert star.subtype is None

    def test_star_system_from_dict(self):
        system_dict = {
            "star_count": 2,
            "age_gyr": 4.5,
            "stars": [
                _make_star_dict(designation="Aa", role="primary"),
                _make_star_dict(designation="B", role="near",
                                orbit_number=5.0, orbit_au=12.0),
            ],
        }
        ss = StarSystem.from_dict(system_dict)
        assert len(ss.stars) == 2
        assert ss.stars[0].designation == "Aa"
        assert ss.stars[1].designation == "B"
        assert ss.age_gyr == pytest.approx(4.5)


# ---------------------------------------------------------------------------
# TestOrbitRoundtrip
# ---------------------------------------------------------------------------

class TestOrbitRoundtrip:
    def test_orbit_slot_from_dict_basic(self):
        d = _make_orbit_dict()
        slot = OrbitSlot.from_dict(d)
        assert slot.star_designation == "Aa"
        assert slot.orbit_number == pytest.approx(3.0)
        assert slot.orbit_au == pytest.approx(0.5)
        assert slot.slot_index == 2
        assert slot.world_type == "terrestrial"
        assert slot.is_habitable_zone is True
        assert slot.is_mainworld_candidate is True
        assert slot.detail is None

    def test_orbit_slot_post_init_fields(self):
        d = _make_orbit_dict(
            eccentricity=0.08,
            inclination=5.5,
            orbit_period_yr=1.23,
        )
        slot = OrbitSlot.from_dict(d)
        assert slot.eccentricity == pytest.approx(0.08)
        assert slot.inclination == pytest.approx(5.5)
        assert slot.orbit_period_yr == pytest.approx(1.23)

    def test_orbit_slot_optional_fields_default(self):
        d = _make_orbit_dict()
        slot = OrbitSlot.from_dict(d)
        assert slot.eccentricity == 0.0
        assert slot.inclination == 0.0
        assert slot.orbit_period_yr is None
        assert slot.canonical_profile == ""
        assert slot.gg_sah == ""
        assert slot.anomaly_type == ""

    def test_system_orbits_from_dict(self):
        star_system = StarSystem.from_dict({
            "stars": [_make_star_dict()],
        })
        orbits_dict = {
            "gas_giant_count": 2,
            "belt_count": 1,
            "terrestrial_count": 3,
            "total_worlds": 6,
            "empty_orbits": 1,
            "star_zones": {
                "Aa": {"mao": 0.10, "hzco": 0.70, "hz_inner": 0.50, "hz_outer": 1.20},
            },
            "orbits": [_make_orbit_dict()],
            "mainworld_orbit": _make_orbit_dict(),
        }
        so = SystemOrbits.from_dict(orbits_dict, star_system)
        assert so.gas_giant_count == 2
        assert so.belt_count == 1
        assert so.total_worlds == 6
        assert len(so.orbits) == 1
        assert so.mainworld_orbit is not None
        assert so.star_mao["Aa"] == pytest.approx(0.10)
        assert so.star_hzco["Aa"] == pytest.approx(0.70)


# ---------------------------------------------------------------------------
# TestSystemRoundtrip
# ---------------------------------------------------------------------------

class TestSystemRoundtrip:
    _WORLD_CORE_KEYS = (
        "name", "starport", "size", "temperature", "population",
        "government", "law_level", "tech_level", "bases", "trade_codes",
        "travel_zone", "notes", "gas_giant_count", "belt_count",
        "population_multiplier",
    )

    def _world_core(self, d: dict) -> dict:
        """Return only the scalar core fields that World.from_dict() restores.

        Atmosphere code, hydrographics code, and the detail sub-objects are
        excluded because World.from_dict() omits the detail branches (they are
        regenerated by _finish_generation() in the UI).
        """
        result = {k: d[k] for k in self._WORLD_CORE_KEYS if k in d}
        if "atmosphere" in d and isinstance(d["atmosphere"], dict):
            result["atmosphere_code"] = d["atmosphere"].get("code")
        if "hydrographics" in d and isinstance(d["hydrographics"], dict):
            result["hydrographics_code"] = d["hydrographics"].get("code")
        return result

    def test_full_system_dict_roundtrip(self):
        # Stellar and orbital structure round-trips exactly.
        # World.from_dict() omits detail sub-objects (regenerated by the UI);
        # compare only the core world fields.
        system = generate_full_system(seed=42)
        d1 = system.to_dict()
        system2 = TravellerSystem.from_dict(d1)
        d2 = system2.to_dict()
        # Stars and orbits must be identical
        assert d1["stars"] == d2["stars"]
        assert d1["orbits"] == d2["orbits"]
        # Generation flags must survive
        assert d1["nhz_atmospheres"] == d2["nhz_atmospheres"]
        assert d1["orbital_eccentricity"] == d2["orbital_eccentricity"]
        assert d1["orbital_inclination"] == d2["orbital_inclination"]
        # Mainworld core fields must survive
        if d1.get("mainworld"):
            assert self._world_core(d1["mainworld"]) == self._world_core(d2["mainworld"])

    def test_system_with_eccentricity_roundtrip(self):
        system = generate_full_system(
            seed=7, orbital_eccentricity=True, orbital_inclination=True
        )
        d1 = system.to_dict()
        system2 = TravellerSystem.from_dict(d1)
        d2 = system2.to_dict()
        assert d1["stars"] == d2["stars"]
        assert d1["orbits"] == d2["orbits"]
        assert system2.orbital_eccentricity is True
        assert system2.orbital_inclination is True
        assert system2.nhz_atmospheres is False
        if d1.get("mainworld"):
            assert self._world_core(d1["mainworld"]) == self._world_core(d2["mainworld"])

    def test_generation_flags_roundtrip(self):
        system = generate_full_system(seed=42, nhz_atmospheres=True)
        d = system.to_dict()
        assert d["nhz_atmospheres"] is True
        assert d["orbital_eccentricity"] is False
        assert d["orbital_inclination"] is False
        system2 = TravellerSystem.from_dict(d)
        assert system2.nhz_atmospheres is True
        assert system2.orbital_eccentricity is False
        assert system2.orbital_inclination is False

    def test_system_no_mainworld(self):
        system = generate_full_system(seed=42)
        d = system.to_dict()
        d["mainworld"] = None
        system2 = TravellerSystem.from_dict(d)
        assert system2.mainworld is None
        assert system2.mainworld_orbit is system2.system_orbits.mainworld_orbit

    def test_from_dict_ignores_app_version_key(self):
        system = generate_full_system(seed=42)
        d = system.to_dict()
        d["_app_version"] = "1.4.0"
        system2 = TravellerSystem.from_dict(d)
        assert system2.stellar_system is not None

    def test_star_fields_preserved(self):
        system = generate_full_system(seed=42)
        d = system.to_dict()
        system2 = TravellerSystem.from_dict(d)
        orig_stars = system.stellar_system.stars
        new_stars = system2.stellar_system.stars
        assert len(new_stars) == len(orig_stars)
        for orig, new in zip(orig_stars, new_stars):
            assert orig.designation == new.designation
            assert orig.spectral_type == new.spectral_type
            assert orig.mass == pytest.approx(new.mass, rel=1e-3)
            assert orig.age_gyr == pytest.approx(new.age_gyr or 0, rel=1e-3)

    def test_orbit_count_preserved(self):
        system = generate_full_system(seed=42)
        d = system.to_dict()
        system2 = TravellerSystem.from_dict(d)
        assert (len(system2.system_orbits.orbits)
                == len(system.system_orbits.orbits))
        assert system2.system_orbits.gas_giant_count == system.system_orbits.gas_giant_count
        assert system2.system_orbits.belt_count == system.system_orbits.belt_count

    def test_mainworld_fields_preserved(self):
        system = generate_full_system(seed=42)
        d = system.to_dict()
        system2 = TravellerSystem.from_dict(d)
        if system.mainworld is not None:
            assert system2.mainworld is not None
            assert system2.mainworld.name == system.mainworld.name
            assert system2.mainworld.starport == system.mainworld.starport
            assert system2.mainworld.tech_level == system.mainworld.tech_level

    def test_invalid_system_raises(self):
        with pytest.raises((ValueError, KeyError)):
            OrbitSlot.from_dict({"star": "Aa"})  # missing required fields


# ---------------------------------------------------------------------------
# TestMoonFromDict
# ---------------------------------------------------------------------------

class TestMoonFromDict:
    """Tests for Moon.from_dict()."""

    from traveller_gen.traveller_moon_gen import Moon

    def test_ring_moon_basic(self):
        from traveller_gen.traveller_moon_gen import Moon
        moon = Moon(size_code=0, is_ring=True)
        moon.ring_count = 3
        d = moon.to_dict()
        restored = Moon.from_dict(d)
        assert restored.is_ring is True
        assert restored.size_code == 0
        assert restored.ring_count == 3

    def test_ring_moon_with_centre_span(self):
        from traveller_gen.traveller_moon_gen import Moon
        moon = Moon(size_code=0, is_ring=True)
        moon.ring_centre_pd = 1.75
        moon.ring_span_pd   = 0.12
        d = moon.to_dict()
        restored = Moon.from_dict(d)
        assert restored.is_ring is True
        assert restored.ring_centre_pd == pytest.approx(1.75)
        assert restored.ring_span_pd   == pytest.approx(0.12)

    def test_size_s_moon(self):
        from traveller_gen.traveller_moon_gen import Moon
        moon = Moon(size_code="S")
        d = moon.to_dict()
        restored = Moon.from_dict(d)
        assert restored.size_code == "S"
        assert restored.is_ring is False

    def test_numeric_size_moon_with_orbit_data(self):
        from traveller_gen.traveller_moon_gen import Moon
        moon = Moon(size_code=4)
        moon.orbit_pd           = 12.5
        moon.orbit_km           = 75000.0
        moon.orbit_range        = "middle"
        moon.orbit_period_hours = 420.3
        d = moon.to_dict()
        restored = Moon.from_dict(d)
        assert restored.size_code == 4
        assert restored.orbit_pd == pytest.approx(12.5)
        assert restored.orbit_km == pytest.approx(75000.0)
        assert restored.orbit_range == "middle"
        assert restored.orbit_period_hours == pytest.approx(420.3)
        assert restored.orbit_eccentricity == 0.0
        assert restored.orbit_inclination  == 0.0

    def test_moon_eccentricity_inclination(self):
        from traveller_gen.traveller_moon_gen import Moon
        moon = Moon(size_code=3)
        moon.orbit_pd           = 5.0
        moon.orbit_km           = 20000.0
        moon.orbit_range        = "inner"
        moon.orbit_period_hours = 60.0
        moon.orbit_eccentricity = 0.0312
        moon.orbit_inclination  = 145.5
        d = moon.to_dict()
        restored = Moon.from_dict(d)
        assert restored.orbit_eccentricity == pytest.approx(0.0312)
        assert restored.orbit_inclination  == pytest.approx(145.5)

    def test_gas_giant_moon_flag(self):
        from traveller_gen.traveller_moon_gen import Moon
        moon = Moon(size_code=8, is_gas_giant_moon=True)
        d = moon.to_dict()
        restored = Moon.from_dict(d)
        assert restored.is_gas_giant_moon is True
        assert restored.size_code == 8

    def test_moon_with_nested_detail(self):
        from traveller_gen.traveller_moon_gen import Moon
        from traveller_gen.traveller_world_detail import WorldDetail
        moon = Moon(size_code=5)
        moon.orbit_pd           = 8.0
        moon.orbit_km           = 30000.0
        moon.orbit_range        = "outer"
        moon.orbit_period_hours = 200.0
        moon.detail = WorldDetail(sah="352", population=2, government=1,
                                  law_level=1, tech_level=6, spaceport="H")
        d = moon.to_dict()
        restored = Moon.from_dict(d)
        assert restored.detail is not None
        assert restored.detail.sah == "352"
        assert restored.detail.population == 2
        assert restored.detail.spaceport == "H"


# ---------------------------------------------------------------------------
# TestWorldDetailFromDict
# ---------------------------------------------------------------------------

class TestWorldDetailFromDict:
    """Tests for WorldDetail.from_dict()."""

    def test_basic_uninhabited(self):
        from traveller_gen.traveller_world_detail import WorldDetail
        wd = WorldDetail(sah="473")
        d = wd.to_dict()
        restored = WorldDetail.from_dict(d)
        assert restored.sah == "473"
        assert restored.population == 0
        assert restored.spaceport == "-"
        assert restored.inhabited is False

    def test_inhabited_fields_preserved(self):
        from traveller_gen.traveller_world_detail import WorldDetail
        wd = WorldDetail(sah="566", population=5, government=3,
                         law_level=2, tech_level=8, spaceport="F")
        d = wd.to_dict()
        restored = WorldDetail.from_dict(d)
        assert restored.sah == "566"
        assert restored.population == 5
        assert restored.government == 3
        assert restored.law_level == 2
        assert restored.tech_level == 8
        assert restored.spaceport == "F"
        assert restored.inhabited is True

    def test_trade_codes_preserved(self):
        from traveller_gen.traveller_world_detail import WorldDetail
        wd = WorldDetail(sah="566", population=5, government=3,
                         law_level=2, tech_level=8, spaceport="F")
        d = wd.to_dict()
        restored = WorldDetail.from_dict(d)
        assert restored.trade_codes == wd.trade_codes

    def test_gas_giant_sah(self):
        from traveller_gen.traveller_world_detail import WorldDetail
        wd = WorldDetail(sah="GM9")
        d = wd.to_dict()
        restored = WorldDetail.from_dict(d)
        assert restored.sah == "GM9"
        assert restored.is_gas_giant is True
        assert restored.trade_codes == []

    def test_moons_reconstructed(self):
        from traveller_gen.traveller_moon_gen import Moon
        from traveller_gen.traveller_world_detail import WorldDetail
        m1 = Moon(size_code=3)
        m2 = Moon(size_code=0, is_ring=True)
        wd = WorldDetail(sah="473", moons=[m1, m2])
        d = wd.to_dict()
        restored = WorldDetail.from_dict(d)
        assert len(restored.moons) == 2
        sizes = {m.size_code for m in restored.moons}
        assert 3 in sizes
        assert 0 in sizes

    def test_belt_physical_reconstructed(self):
        from traveller_gen.traveller_belt_physical import BeltPhysical
        from traveller_gen.traveller_world_detail import WorldDetail
        bp = BeltPhysical(
            inner_au=2.1, outer_au=3.4,
            m_type_pct=15, s_type_pct=60, c_type_pct=20, other_pct=5,
            bulk=4, resource_rating=7,
            size_1_bodies=2, size_s_bodies=5,
            mean_temperature_k=180,
        )
        wd = WorldDetail(sah="000")
        wd.physical = bp
        d = wd.to_dict()
        restored = WorldDetail.from_dict(d)
        assert restored.physical is not None
        from traveller_gen.traveller_belt_physical import BeltPhysical as BP
        assert isinstance(restored.physical, BP)
        assert restored.physical.inner_au == pytest.approx(2.1)
        assert restored.physical.resource_rating == 7

    def test_biomass_biocomplexity_preserved(self):
        from traveller_gen.traveller_world_detail import WorldDetail
        wd = WorldDetail(sah="566")
        wd.biomass_rating       = 4
        wd.biocomplexity_rating = 3
        d = wd.to_dict()
        restored = WorldDetail.from_dict(d)
        assert restored.biomass_rating       == 4
        assert restored.biocomplexity_rating == 3

    def test_physical_absent_stays_none(self):
        from traveller_gen.traveller_world_detail import WorldDetail
        wd = WorldDetail(sah="473")
        d = wd.to_dict()
        restored = WorldDetail.from_dict(d)
        assert restored.physical is None


# ---------------------------------------------------------------------------
# TestOrbitDetailRoundtrip
# ---------------------------------------------------------------------------

class TestOrbitDetailRoundtrip:
    """Integration tests: OrbitSlot.detail survives to_dict() → from_dict()."""

    def test_orbit_detail_restored_after_attach_detail(self):
        from traveller_gen.traveller_world_detail import attach_detail
        system = generate_full_system(seed=42)
        attach_detail(system)
        d = system.to_dict()
        system2 = TravellerSystem.from_dict(d)
        # At least one non-empty orbit must have detail reconstructed
        non_empty = [o for o in system2.system_orbits.orbits
                     if o.world_type != "empty"]
        assert any(o.detail is not None for o in non_empty), (
            "No orbit had detail restored after round-trip"
        )

    def test_orbit_detail_sah_matches(self):
        from traveller_gen.traveller_world_detail import attach_detail
        system = generate_full_system(seed=42)
        attach_detail(system)
        d = system.to_dict()
        system2 = TravellerSystem.from_dict(d)
        orig_slots  = {o.slot_index: o for o in system.system_orbits.orbits
                       if o.detail is not None}
        new_slots   = {o.slot_index: o for o in system2.system_orbits.orbits
                       if o.detail is not None}
        assert set(orig_slots.keys()) == set(new_slots.keys()), (
            "detail present on different slots after round-trip"
        )
        for idx, orig in orig_slots.items():
            assert new_slots[idx].detail.sah == orig.detail.sah
            assert new_slots[idx].detail.profile == orig.detail.profile

    def test_orbit_detail_moons_count_matches(self):
        from traveller_gen.traveller_world_detail import attach_detail
        system = generate_full_system(seed=42)
        attach_detail(system)
        d = system.to_dict()
        system2 = TravellerSystem.from_dict(d)
        for orig, new in zip(system.system_orbits.orbits,
                             system2.system_orbits.orbits):
            if orig.detail is not None:
                assert new.detail is not None
                assert len(new.detail.moons) == len(orig.detail.moons)

    def test_system_to_dict_stable_after_detail_roundtrip(self):
        from traveller_gen.traveller_world_detail import attach_detail
        system = generate_full_system(seed=13)
        attach_detail(system)
        d1 = system.to_dict()
        system2 = TravellerSystem.from_dict(d1)
        d2 = system2.to_dict()
        # Orbit count and star data must be identical
        assert len(d1["orbits"]["orbits"]) == len(d2["orbits"]["orbits"])
        assert d1["stars"] == d2["stars"]
        # Each orbit's detail sah must match
        for o1, o2 in zip(d1["orbits"]["orbits"], d2["orbits"]["orbits"]):
            if o1.get("detail"):
                assert o2.get("detail") is not None
                assert o1["detail"]["sah"] == o2["detail"]["sah"]


# ── Issue #115 — HZCO and HZ limits displayed in Stars table ─────────────────

class TestSystemHTMLStarHZ:
    """to_html() exposes MAO, HZCO, and HZ inner/outer limits in the Stars table."""

    def _html(self, seed=42):
        from traveller_gen.traveller_system_gen import generate_full_system  # pylint: disable=import-outside-toplevel
        return generate_full_system("TestWorld", seed=seed).to_html()

    def test_mao_column_header_present(self):
        assert "MAO" in self._html()

    def test_hz_orbit_column_header_present(self):
        assert "HZ Orbit#" in self._html()

    def test_primary_star_hz_shows_three_values(self):
        import re  # pylint: disable=import-outside-toplevel
        assert re.search(r'\d+\.\d+\s*–\s*\d+\.\d+\s*–\s*\d+\.\d+', self._html())

    def test_mao_value_is_numeric(self):
        import re  # pylint: disable=import-outside-toplevel
        assert re.search(r'<td class="mono">\d+\.\d+</td>', self._html())
