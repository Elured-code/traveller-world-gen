"""
tests/test_system_roundtrip.py
==============================
Roundtrip tests for the from_dict() classmethods added to Star, StarSystem,
OrbitSlot, SystemOrbits, and TravellerSystem.
"""

import pytest

from traveller_stellar_gen import Star, StarSystem
from traveller_orbit_gen import OrbitSlot, SystemOrbits
from traveller_system_gen import TravellerSystem, generate_full_system


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
        if d1.get("mainworld"):
            assert self._world_core(d1["mainworld"]) == self._world_core(d2["mainworld"])

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
