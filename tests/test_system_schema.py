"""Tests for traveller_system_schema.json.

Validates TravellerSystem.to_dict() output against the JSON Schema 2020-12
schema.  Uses jsonschema + referencing for $ref resolution; skips validator
tests gracefully if the library is absent.
"""

import json
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from traveller_gen.traveller_system_gen import generate_full_system  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "src", "traveller_gen")
SYSTEM_SCHEMA_PATH = os.path.join(_SRC, "traveller_system_schema.json")
WORLD_SCHEMA_PATH  = os.path.join(_SRC, "traveller_world_schema.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_schema(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _try_import_jsonschema():
    try:
        import jsonschema  # noqa: PLC0415
        return jsonschema
    except ImportError:
        return None


def _make_validator(schema: dict):
    """Return a jsonschema Draft202012Validator with the world schema registered."""
    jsonschema = _try_import_jsonschema()
    if jsonschema is None:
        return None
    try:
        from referencing import Registry, Resource  # noqa: PLC0415
        world_schema = _load_schema(WORLD_SCHEMA_PATH)
        world_id = world_schema["$id"]
        registry = Registry().with_resource(world_id, Resource.from_contents(world_schema))
        return jsonschema.Draft202012Validator(schema, registry=registry)
    except Exception:  # pylint: disable=broad-except
        return None


def _generate(seed: int, **kwargs) -> dict:
    rng = random.Random(seed)
    system = generate_full_system("T", seed=seed, rng=rng, **kwargs)
    return system.to_dict()


# ---------------------------------------------------------------------------
# Schema file integrity
# ---------------------------------------------------------------------------

class TestSystemSchemaFile:
    def test_schema_file_exists(self):
        assert os.path.isfile(SYSTEM_SCHEMA_PATH)

    def test_schema_is_valid_json(self):
        schema = _load_schema(SYSTEM_SCHEMA_PATH)
        assert isinstance(schema, dict)

    def test_schema_has_dollar_schema_key(self):
        assert "$schema" in _load_schema(SYSTEM_SCHEMA_PATH)

    def test_schema_declares_object_type(self):
        assert _load_schema(SYSTEM_SCHEMA_PATH)["type"] == "object"

    def test_schema_forbids_additional_properties(self):
        assert _load_schema(SYSTEM_SCHEMA_PATH).get("additionalProperties") is False

    def test_schema_has_required_top_level_fields(self):
        required = set(_load_schema(SYSTEM_SCHEMA_PATH).get("required", []))
        expected = {
            "star_count", "age_gyr", "stars", "orbits", "mainworld",
            "nhz_atmospheres", "orbital_eccentricity", "orbital_inclination",
            "runaway_greenhouse", "independent_government",
            "optional_biomass", "optional_inhospitable", "relic_tech",
            "settlement_type", "select_mainworld", "social_detail",
            "unusual_stars", "_app_version",
        }
        assert expected == required

    def test_star_def_has_required_fields(self):
        star_def = _load_schema(SYSTEM_SCHEMA_PATH)["$defs"]["Star"]
        required = set(star_def.get("required", []))
        assert {"designation", "role", "spectral_type", "mass_solar",
                "temperature_k", "luminosity_solar"}.issubset(required)

    def test_star_role_enum(self):
        star_def = _load_schema(SYSTEM_SCHEMA_PATH)["$defs"]["Star"]
        enum = set(star_def["properties"]["role"]["enum"])
        assert enum == {"primary", "companion", "close", "near", "far"}

    def test_star_spectral_type_enum_includes_dead_types(self):
        star_def = _load_schema(SYSTEM_SCHEMA_PATH)["$defs"]["Star"]
        enum = set(star_def["properties"]["spectral_type"]["enum"])
        assert {"NS", "BH", "PSR", "D", "BD"}.issubset(enum)

    def test_orbit_slot_world_type_enum(self):
        slot_def = _load_schema(SYSTEM_SCHEMA_PATH)["$defs"]["OrbitSlot"]
        enum = set(slot_def["properties"]["world_type"]["enum"])
        assert enum == {"belt", "gas_giant", "terrestrial", "empty", "star"}

    def test_orbit_slot_temperature_zone_enum(self):
        slot_def = _load_schema(SYSTEM_SCHEMA_PATH)["$defs"]["OrbitSlot"]
        enum = set(slot_def["properties"]["temperature_zone"]["enum"])
        assert enum == {"boiling", "hot", "temperate", "cold", "frozen"}

    def test_settlement_type_enum(self):
        props = _load_schema(SYSTEM_SCHEMA_PATH)["properties"]
        enum = set(props["settlement_type"]["enum"])
        assert enum == {"standard", "long_settled", "well_settled", "backwater", "unsettled"}

    def test_mainworld_ref_targets_world_schema(self):
        schema = _load_schema(SYSTEM_SCHEMA_PATH)
        mw_prop = schema["properties"]["mainworld"]
        refs = [opt.get("$ref", "") for opt in mw_prop.get("oneOf", [])]
        world_schema_id = _load_schema(WORLD_SCHEMA_PATH)["$id"]
        assert world_schema_id in refs


# ---------------------------------------------------------------------------
# Structural (no jsonschema library needed)
# ---------------------------------------------------------------------------

class TestSystemStructure:
    def _sys(self, seed: int, **kw) -> dict:
        return _generate(seed, **kw)

    def test_top_level_required_keys_present(self):
        d = self._sys(1)
        for key in ("star_count", "age_gyr", "stars", "orbits", "mainworld",
                    "nhz_atmospheres", "unusual_stars", "_app_version"):
            assert key in d, f"Missing key: {key}"

    def test_star_count_matches_stars_array(self):
        d = self._sys(42)
        assert d["star_count"] == len(d["stars"])

    def test_stars_array_nonempty(self):
        assert len(self._sys(1)["stars"]) >= 1

    def test_primary_star_role(self):
        d = self._sys(1)
        assert d["stars"][0]["role"] == "primary"

    def test_orbits_has_required_keys(self):
        orbits = self._sys(1)["orbits"]
        for key in ("gas_giant_count", "belt_count", "terrestrial_count",
                    "total_worlds", "empty_orbits", "star_zones", "orbits"):
            assert key in orbits

    def test_total_worlds_matches_orbit_count(self):
        d = self._sys(10)
        filled = sum(1 for o in d["orbits"]["orbits"] if o["world_type"] != "empty")
        assert d["orbits"]["total_worlds"] == filled

    def test_seed_round_trips(self):
        d = self._sys(99999, orbital_eccentricity=True)
        assert d.get("seed") == 99999

    def test_unusual_stars_flag_propagates(self):
        d = _generate(21977, unusual_stars=True)
        assert d["unusual_stars"] is True

    def test_bh_system_has_zero_worlds(self):
        d = _generate(21977, unusual_stars=True)
        assert d["orbits"]["total_worlds"] == 0

    def test_bh_star_has_schwarzschild_km(self):
        d = _generate(21977, unusual_stars=True)
        primary = d["stars"][0]
        assert primary["spectral_type"] == "BH"
        assert "bh_schwarzschild_km" in primary
        assert primary["bh_schwarzschild_km"] > 0

    def test_protostar_has_zero_worlds(self):
        d = _generate(13387, unusual_stars=True)
        primary = d["stars"][0]
        assert "Protostar" in primary["special_notes"]
        assert d["orbits"]["total_worlds"] == 0

    def test_protostar_age_under_001_gyr(self):
        d = _generate(13387, unusual_stars=True)
        assert d["age_gyr"] < 0.01

    def test_protostar_primary_is_class_v(self):
        d = _generate(13387, unusual_stars=True)
        primary = d["stars"][0]
        assert primary["luminosity_class"] == "V"
        assert primary["spectral_type"] in ("O", "B", "A", "F", "G", "K", "M")

    def test_protostar_companions_also_protostar(self):
        # Run a few protostar seeds; any companion stars must also be protostars
        for seed in (13387, 16308, 17224, 22684):
            d = _generate(seed, unusual_stars=True)
            primaries_note = d["stars"][0]["special_notes"]
            if "Protostar" not in primaries_note:
                continue
            for star in d["stars"][1:]:
                assert "Protostar" in star["special_notes"], (
                    f"Seed {seed}: companion {star['designation']} is not a protostar"
                )

    def test_radiation_zone_only_present_when_true(self):
        d = _generate(1000, unusual_stars=True, orbital_eccentricity=True)
        for orbit in d["orbits"]["orbits"]:
            if "radiation_zone" in orbit:
                assert orbit["radiation_zone"] is True

    def test_eccentricity_fields_present_when_enabled(self):
        d = _generate(1, orbital_eccentricity=True)
        stars_with_orbit = [s for s in d["stars"] if s["orbit_number"] is not None]
        for star in stars_with_orbit:
            if star.get("orbit_eccentricity", 0) > 0:
                assert "orbit_au_min" in star
                assert "orbit_au_max" in star


# ---------------------------------------------------------------------------
# jsonschema validation
# ---------------------------------------------------------------------------

class TestSystemSchemaValidation:
    """Requires jsonschema and referencing; skips gracefully if absent."""

    @classmethod
    def setup_class(cls):
        schema = _load_schema(SYSTEM_SCHEMA_PATH)
        cls.validator = _make_validator(schema)

    def _validate(self, d: dict) -> None:
        if self.validator is None:
            pytest.skip("jsonschema / referencing not available")
        errors = list(self.validator.iter_errors(d))
        assert not errors, f"Schema violations: {[e.message for e in errors]}"

    def test_normal_system_passes(self):
        self._validate(_generate(1))

    def test_multi_star_system_passes(self):
        self._validate(_generate(100))

    def test_full_detail_system_passes(self):
        self._validate(_generate(42, nhz_atmospheres=True,
                                  orbital_eccentricity=True,
                                  orbital_inclination=True))

    def test_unusual_stars_bh_passes(self):
        self._validate(_generate(21977, unusual_stars=True))

    def test_unusual_stars_protostar_passes(self):
        self._validate(_generate(13387, unusual_stars=True))

    def test_unusual_stars_nebula_passes(self):
        self._validate(_generate(2689, unusual_stars=True))

    def test_unusual_stars_star_cluster_passes(self):
        self._validate(_generate(5936, unusual_stars=True))

    def test_unusual_stars_anomaly_passes(self):
        self._validate(_generate(3587, unusual_stars=True))

    def test_thirty_normal_seeds_all_pass(self):
        for seed in range(1, 31):
            d = _generate(seed)
            self._validate(d)

    def test_ten_unusual_seeds_all_pass(self):
        for seed in [21977, 38329, 52515, 13387, 2689, 5936, 3587, 16308, 17224, 22684]:
            d = _generate(seed, unusual_stars=True)
            self._validate(d)

    def test_missing_star_count_fails(self):
        if self.validator is None:
            pytest.skip("jsonschema / referencing not available")
        d = _generate(1)
        del d["star_count"]
        errors = list(self.validator.iter_errors(d))
        assert errors, "Expected validation error for missing star_count"

    def test_invalid_settlement_type_fails(self):
        if self.validator is None:
            pytest.skip("jsonschema / referencing not available")
        d = _generate(1)
        d["settlement_type"] = "not_a_valid_type"
        errors = list(self.validator.iter_errors(d))
        assert errors, "Expected validation error for invalid settlement_type"

    def test_invalid_world_type_fails(self):
        if self.validator is None:
            pytest.skip("jsonschema / referencing not available")
        d = _generate(42)
        if d["orbits"]["orbits"]:
            d["orbits"]["orbits"][0]["world_type"] = "comet"
            errors = list(self.validator.iter_errors(d))
            assert errors, "Expected validation error for invalid world_type"
