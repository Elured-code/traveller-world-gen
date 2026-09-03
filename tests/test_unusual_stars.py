"""Tests for the Unusual Stars column (Issue #21 Phase 1).

Verifies:
- UNUSUAL_COLUMN and PECULIAR_COLUMN table coverage
- _generate_primary_star_type routing when unusual_stars=True
- generate_primary_star / generate_stellar_data flag threading
- Peculiar environment notes stored in Star.special_notes
- unusual_stars flag threading through generate_full_system and TravellerSystem
- to_dict / from_dict round-trip for the unusual_stars field
- Default (unusual_stars=False) produces identical results to the old code path
"""

import random
import pytest

from traveller_gen.traveller_stellar_gen import (
    UNUSUAL_COLUMN,
    PECULIAR_COLUMN,
    SPECIAL_COLUMN,
    _generate_primary_star_type,
    generate_primary_star,
    generate_stellar_data,
)
from traveller_gen.traveller_system_gen import (
    TravellerSystem,
    generate_full_system,
)


# ---------------------------------------------------------------------------
# Table coverage
# ---------------------------------------------------------------------------

class TestUnusualColumnTable:
    def test_all_2d_results_covered(self):
        for r in range(2, 13):
            result = UNUSUAL_COLUMN.get(r, "Giants" if r >= 12 else None)
            assert result is not None, f"UNUSUAL_COLUMN missing key {r}"

    def test_known_values(self):
        assert UNUSUAL_COLUMN[2] == "Peculiar"
        assert UNUSUAL_COLUMN[3] == "Class VI"
        assert UNUSUAL_COLUMN[4] == "Class IV"
        assert UNUSUAL_COLUMN[5] == "BD"
        assert UNUSUAL_COLUMN[6] == "BD"
        assert UNUSUAL_COLUMN[7] == "BD"
        assert UNUSUAL_COLUMN[8] == "D"
        assert UNUSUAL_COLUMN[9] == "D"
        assert UNUSUAL_COLUMN[10] == "D"
        assert UNUSUAL_COLUMN[11] == "Class III"
        # 12+ → Giants (not in dict, handled by get default)
        assert 12 not in UNUSUAL_COLUMN

    def test_high_roll_defaults_to_giants(self):
        assert UNUSUAL_COLUMN.get(12, "Giants") == "Giants"
        assert UNUSUAL_COLUMN.get(99, "Giants") == "Giants"


class TestPeculiarColumnTable:
    def test_all_2d_results_covered(self):
        for r in range(2, 13):
            result = PECULIAR_COLUMN.get(r, "Anomaly" if r >= 11 else None)
            assert result is not None, f"PECULIAR_COLUMN missing key {r}"

    def test_known_values(self):
        assert PECULIAR_COLUMN[2] == "Black Hole"
        assert PECULIAR_COLUMN[3] == "Pulsar"
        assert PECULIAR_COLUMN[4] == "Neutron Star"
        assert PECULIAR_COLUMN[5] == "Nebula"
        assert PECULIAR_COLUMN[6] == "Nebula"
        assert PECULIAR_COLUMN[7] == "Protostar"
        assert PECULIAR_COLUMN[8] == "Protostar"
        assert PECULIAR_COLUMN[9] == "Star Cluster"
        assert PECULIAR_COLUMN[10] == "Star Cluster"
        assert PECULIAR_COLUMN[11] == "Anomaly"

    def test_high_roll_defaults_to_anomaly(self):
        assert PECULIAR_COLUMN.get(12, "Anomaly") == "Anomaly"


# ---------------------------------------------------------------------------
# Column routing
# ---------------------------------------------------------------------------

class TestUnusualColumnRouting:
    """Verify UNUSUAL_COLUMN is consulted vs SPECIAL_COLUMN based on the flag."""

    def test_flag_false_never_returns_bd_from_special(self):
        """With unusual_stars=False, SPECIAL_COLUMN has no BD result."""
        assert "BD" not in SPECIAL_COLUMN.values()

    def test_flag_true_can_produce_bd(self):
        """With unusual_stars=True, many seeds produce a BD primary eventually."""
        import traveller_gen.traveller_stellar_gen as sg
        found_bd = False
        for seed in range(10000):
            old = sg._rng  # pylint: disable=protected-access
            sg._rng = random.Random(seed)  # pylint: disable=protected-access
            star = generate_primary_star("A", unusual_stars=True)
            sg._rng = old  # pylint: disable=protected-access
            if star.spectral_type == "BD":
                found_bd = True
                break
        assert found_bd, "Expected at least one BD primary across 10000 seeds"

    def test_flag_false_unusual_column_not_used(self):
        """UNUSUAL_COLUMN has BD and D results not in SPECIAL_COLUMN."""
        for key in ("BD", "D", "Peculiar"):
            assert key not in SPECIAL_COLUMN.values(), (
                f"'{key}' unexpectedly found in SPECIAL_COLUMN"
            )


# ---------------------------------------------------------------------------
# Peculiar environment notes
# ---------------------------------------------------------------------------

class TestPeculiarNotes:
    """When Unusual column → Peculiar, star gets a descriptive special_notes."""

    _ENV_TYPES = ("Nebula", "Protostar", "Star Cluster", "Anomaly")
    _REMNANT_TYPES = ("Black Hole", "Pulsar", "Neutron Star")

    @pytest.mark.parametrize("env", _ENV_TYPES)
    def test_env_type_notes(self, env):
        """Peculiar environment results carry 'Peculiar environment: <type>'."""
        from traveller_gen.traveller_stellar_gen import _generate_peculiar_star
        env_key = f"_PECULIAR_{env.replace(' ', '_')}"
        star = _generate_peculiar_star("A", env_key, "Giants_env")
        assert f"Peculiar environment: {env}" in star.special_notes

    @pytest.mark.parametrize("rem,expected_type", [
        ("Black Hole", "BH"),
        ("Pulsar", "PSR"),
        ("Neutron Star", "NS"),
    ])
    def test_remnant_produces_real_type(self, rem, expected_type):
        """Post-stellar remnants now produce real typed stars (Phase 3)."""
        from traveller_gen.traveller_stellar_gen import _generate_peculiar_star
        rem_key = f"_PECULIAR_{rem.replace(' ', '_')}"
        star = _generate_peculiar_star("A", rem_key, "Giants_placeholder")
        assert star.spectral_type == expected_type
        assert star.lum_class == expected_type
        assert star.subtype is None

    def test_anomaly_produces_valid_giants_star(self):
        """Anomaly falls back to a Giants star (Ia/Ib/II/III) per WBH p.219."""
        from traveller_gen.traveller_stellar_gen import _generate_peculiar_star
        star = _generate_peculiar_star("A", "_PECULIAR_Anomaly", "Giants_env")
        assert star.lum_class in ("Ia", "Ib", "II", "III")
        assert star.mass is not None and star.mass > 0
        assert star.temperature is not None and star.temperature > 0

    @pytest.mark.parametrize("env", ("Nebula", "Star Cluster"))
    def test_young_env_produces_class_v_star(self, env):
        """Nebula/Star Cluster produce a young Class V star (Issue #184)."""
        from traveller_gen.traveller_stellar_gen import _generate_peculiar_star
        env_key = f"_PECULIAR_{env.replace(' ', '_')}"
        star = _generate_peculiar_star("A", env_key, "Giants_env")
        assert star.lum_class == "V"
        assert star.spectral_type in ("O", "B", "A", "F", "G", "K", "M")
        assert star.mass is not None and star.mass > 0
        assert star.temperature is not None and star.temperature > 0

    def test_protostar_env_produces_class_v(self):
        """Protostar uses WBH p.219 rules: Class V star with modified diameter."""
        from traveller_gen.traveller_stellar_gen import _generate_peculiar_star
        star = _generate_peculiar_star("A", "_PECULIAR_Protostar", "Giants_env")
        assert star.lum_class == "V"
        assert star.spectral_type in ("O", "B", "A", "F", "G", "K", "M")
        assert "Peculiar environment: Protostar" in star.special_notes
        assert star.mass > 0
        assert star.temperature > 0


# ---------------------------------------------------------------------------
# Flag threading
# ---------------------------------------------------------------------------

class TestFlagThreading:
    def test_generate_stellar_data_accepts_flag(self):
        rng = random.Random(999)
        system = generate_stellar_data(rng=rng, unusual_stars=False)
        assert system is not None

    def test_generate_full_system_stores_flag(self):
        system = generate_full_system(seed=42, unusual_stars=True)
        assert isinstance(system, TravellerSystem)
        assert system.unusual_stars is True

    def test_generate_full_system_default_false(self):
        system = generate_full_system(seed=42)
        assert system.unusual_stars is False

    def test_to_dict_includes_flag(self):
        system = generate_full_system(seed=42, unusual_stars=True)
        d = system.to_dict()
        assert d["unusual_stars"] is True

    def test_from_dict_restores_flag(self):
        system = generate_full_system(seed=42, unusual_stars=True)
        d = system.to_dict()
        restored = TravellerSystem.from_dict(d)
        assert restored.unusual_stars is True

    def test_from_dict_default_false(self):
        system = generate_full_system(seed=42)
        d = system.to_dict()
        d.pop("unusual_stars", None)
        restored = TravellerSystem.from_dict(d)
        assert restored.unusual_stars is False

    def test_flag_false_no_seed_disruption(self):
        """unusual_stars=False must not change any dice rolls vs not passing it."""
        rng1 = random.Random(12345)
        rng2 = random.Random(12345)
        sys1 = generate_full_system(rng=rng1)
        sys2 = generate_full_system(rng=rng2, unusual_stars=False)
        if sys1.mainworld and sys2.mainworld:
            assert sys1.mainworld.uwp() == sys2.mainworld.uwp()
        assert sys1.stellar_system.primary.spectral_type == \
               sys2.stellar_system.primary.spectral_type


# ---------------------------------------------------------------------------
# Unusual column produces valid stars (fuzz)
# ---------------------------------------------------------------------------

class TestUnusualStarsGenerationFuzz:
    """Run many seeds with unusual_stars=True; each must produce a valid system."""

    @pytest.mark.parametrize("seed", range(100, 130))
    def test_generates_valid_system(self, seed):
        system = generate_full_system(seed=seed, unusual_stars=True)
        assert system is not None
        assert system.stellar_system is not None
        primary = system.stellar_system.primary
        assert primary is not None
        assert primary.spectral_type is not None
        assert not primary.spectral_type.startswith("_PECULIAR_"), (
            f"Seed {seed}: sentinel type leaked into Star.spectral_type"
        )
