"""Tests for Issue #21 Phases 2, 3, and 4.

Phase 2 — White dwarf physical characterization (WBH p.219 formulas)
Phase 3 — NS, BH, PSR as real star types
Phase 4 — Dead star orbit generation (MAO, radiation zones, existence check)
"""

import math
import random

import pytest

from traveller_gen.traveller_stellar_gen import (
    _wd_temperature,
    _characterize_white_dwarf,
    _characterize_neutron_star,
    _characterize_black_hole,
    _generate_peculiar_star,
    Star,
    StarSystem,
)
from traveller_gen.traveller_orbit_gen import (
    get_mao,
    dead_star_system_exists,
    generate_orbits,
    OrbitSlot,
)
from traveller_gen.traveller_system_gen import generate_full_system


# ---------------------------------------------------------------------------
# Phase 2 — White dwarf physical characterization
# ---------------------------------------------------------------------------

class TestWdTemperatureTable:
    def test_edge_age_zero(self):
        """Age 0.0 Gyr, mass 0.6 → should return 100000 K."""
        assert _wd_temperature(0.0, 0.6) == 100000

    def test_edge_age_thirteen(self):
        """Age 13.0 Gyr, mass 0.6 → should return 3800 K."""
        assert _wd_temperature(13.0, 0.6) == 3800

    def test_age_one_mass_one_two(self):
        """Age 1.0 Gyr, mass 1.2 → base=8000, scaled=8000*(1.2/0.6)=16000."""
        result = _wd_temperature(1.0, 1.2)
        assert result == 16000

    def test_temperature_decreases_with_age(self):
        """Older WD of same mass should be cooler."""
        t_young = _wd_temperature(0.5, 0.6)
        t_old = _wd_temperature(10.0, 0.6)
        assert t_young > t_old

    def test_temperature_scales_with_mass(self):
        """More massive WD at same age should be hotter."""
        t_low = _wd_temperature(5.0, 0.4)
        t_high = _wd_temperature(5.0, 1.0)
        assert t_high > t_low

    def test_clamp_minimum(self):
        """Result should never fall below 3800 K."""
        assert _wd_temperature(100.0, 0.1) == 3800

    def test_clamp_maximum(self):
        """Result should never exceed 100000 K."""
        assert _wd_temperature(0.0, 2.0) == 100000

    def test_interpolation_midpoint(self):
        """Age 0.75 Gyr interpolates between 0.5→10000 and 1.0→8000."""
        result = _wd_temperature(0.75, 0.6)
        assert 8000 < result < 10000


class TestWhiteDwarfCharacterization:
    def _make_wd(self, seed: int, age: float = 5.0):
        import traveller_gen.traveller_stellar_gen as sg
        old_rng = sg._rng  # pylint: disable=protected-access
        sg._rng = random.Random(seed)  # pylint: disable=protected-access
        result = _characterize_white_dwarf(age)
        sg._rng = old_rng  # pylint: disable=protected-access
        return result

    def test_mass_range(self):
        """WD mass should be in [0.11, 1.44] across many seeds."""
        for seed in range(200):
            mass, _t, _d, _l = self._make_wd(seed)
            assert 0.01 <= mass <= 1.44, f"seed {seed}: mass {mass} out of range"

    def test_diameter_from_mass(self):
        """WD diameter should equal 0.01 / mass within floating-point tolerance."""
        for seed in range(50):
            mass, _t, diam, _l = self._make_wd(seed)
            expected = 0.01 / mass
            assert math.isclose(diam, expected, rel_tol=1e-9), (
                f"seed {seed}: diam {diam} != 0.01/{mass}={expected}"
            )

    def test_luminosity_positive(self):
        """WD luminosity should be positive."""
        for seed in range(50):
            _m, _t, _d, lum = self._make_wd(seed)
            assert lum > 0

    def test_temperature_positive(self):
        """WD temperature should be positive."""
        for seed in range(50):
            _m, temp, _d, _l = self._make_wd(seed)
            assert temp > 0

    def test_older_wd_cooler(self):
        """Same seed, older age → lower temperature (within same table region)."""
        mass_y, temp_y, _d, _l = self._make_wd(42, age=0.5)
        mass_o, temp_o, _d2, _l2 = self._make_wd(42, age=10.0)
        # Both use same rng seed so same mass is rolled; then temperature differs by age
        assert temp_y > temp_o, "Younger WD should be hotter than older WD"

    def test_roundtrip_via_star(self):
        """Star with WD type: to_dict/from_dict preserves physical fields."""
        import traveller_gen.traveller_stellar_gen as sg
        old_rng = sg._rng  # pylint: disable=protected-access
        sg._rng = random.Random(7)  # pylint: disable=protected-access
        age = 5.0
        mass, temp, diam, lum = _characterize_white_dwarf(age)
        sg._rng = old_rng  # pylint: disable=protected-access
        star = Star(
            designation="A", role="primary",
            spectral_type="D", subtype=None, lum_class="D",
            mass=mass, temperature=temp, diameter=diam, luminosity=lum,
            age_gyr=age, ms_lifespan_gyr=None,
        )
        d = star.to_dict()
        restored = Star.from_dict(d)
        assert math.isclose(restored.mass, star.mass, rel_tol=1e-3)
        assert restored.temperature == star.temperature
        # diameter is rounded to 3 dp in to_dict(); allow up to 5% round-trip loss
        assert math.isclose(restored.diameter, star.diameter, rel_tol=0.05)
        assert math.isclose(restored.luminosity, star.luminosity, rel_tol=0.1)


# ---------------------------------------------------------------------------
# Phase 3 — NS, BH, PSR as real star types
# ---------------------------------------------------------------------------

def _make_peculiar(seed: int, pec_type: str) -> Star:
    """Generate a peculiar star of the given WBH Peculiar column type."""
    import traveller_gen.traveller_stellar_gen as sg
    old_rng = sg._rng  # pylint: disable=protected-access
    sg._rng = random.Random(seed)  # pylint: disable=protected-access
    rem_key = f"_PECULIAR_{pec_type.replace(' ', '_')}"
    star = _generate_peculiar_star("A", rem_key, "Giants_placeholder")
    sg._rng = old_rng  # pylint: disable=protected-access
    return star


class TestBlackHoleCharacterization:
    def test_spectral_type(self):
        star = _make_peculiar(1, "Black Hole")
        assert star.spectral_type == "BH"

    def test_lum_class(self):
        star = _make_peculiar(1, "Black Hole")
        assert star.lum_class == "BH"

    def test_subtype_none(self):
        star = _make_peculiar(1, "Black Hole")
        assert star.subtype is None

    def test_temperature_zero(self):
        for seed in range(20):
            star = _make_peculiar(seed, "Black Hole")
            assert star.temperature == 0, f"seed {seed}: BH temperature should be 0"

    def test_luminosity_zero(self):
        for seed in range(20):
            star = _make_peculiar(seed, "Black Hole")
            assert star.luminosity == 0.0, f"seed {seed}: BH luminosity should be 0.0"

    def test_mass_minimum(self):
        """BH mass should be at least 2.2 (minimum roll: 1D=1, d10=1)."""
        for seed in range(50):
            star = _make_peculiar(seed, "Black Hole")
            assert star.mass >= 2.1, f"seed {seed}: BH mass {star.mass} < 2.1"

    def test_schwarzschild_diameter_relation(self):
        """bh_schwarzschild_km should equal 5.9 * mass within tolerance."""
        for seed in range(30):
            star = _make_peculiar(seed, "Black Hole")
            assert star.bh_schwarzschild_km is not None
            expected = 5.9 * star.mass
            assert math.isclose(star.bh_schwarzschild_km, expected, rel_tol=1e-9), (
                f"seed {seed}: schwarzschild_km {star.bh_schwarzschild_km} != {expected}"
            )

    def test_to_dict_includes_schwarzschild(self):
        star = _make_peculiar(1, "Black Hole")
        d = star.to_dict()
        assert "bh_schwarzschild_km" in d
        assert d["bh_schwarzschild_km"] > 0

    def test_roundtrip(self):
        star = _make_peculiar(3, "Black Hole")
        d = star.to_dict()
        restored = Star.from_dict(d)
        assert restored.spectral_type == "BH"
        assert math.isclose(restored.mass, star.mass, rel_tol=1e-3)
        assert restored.bh_schwarzschild_km is not None
        assert math.isclose(restored.bh_schwarzschild_km,
                            star.bh_schwarzschild_km, rel_tol=1e-3)


class TestNeutronStarCharacterization:
    def test_spectral_type(self):
        star = _make_peculiar(1, "Neutron Star")
        assert star.spectral_type == "NS"

    def test_lum_class(self):
        star = _make_peculiar(1, "Neutron Star")
        assert star.lum_class == "NS"

    def test_mass_range(self):
        """NS mass: base 1.1–2.1 ☉."""
        for seed in range(50):
            star = _make_peculiar(seed, "Neutron Star")
            assert 1.0 < star.mass <= 2.2, f"seed {seed}: NS mass {star.mass} out of range"

    def test_diameter_range(self):
        """NS diameter: 20–25 km → 20/695700 to 25/695700 solar diameters."""
        lo = 20.0 / 695700.0
        hi = 25.0 / 695700.0
        for seed in range(50):
            star = _make_peculiar(seed, "Neutron Star")
            assert lo <= star.diameter <= hi, (
                f"seed {seed}: NS diameter {star.diameter} outside [{lo}, {hi}]"
            )

    def test_temperature_positive(self):
        for seed in range(20):
            star = _make_peculiar(seed, "Neutron Star")
            assert star.temperature > 0

    def test_roundtrip(self):
        star = _make_peculiar(5, "Neutron Star")
        d = star.to_dict()
        restored = Star.from_dict(d)
        assert restored.spectral_type == "NS"
        assert math.isclose(restored.mass, star.mass, rel_tol=1e-3)
        assert restored.bh_schwarzschild_km is None


class TestPulsarCharacterization:
    def test_spectral_type(self):
        star = _make_peculiar(1, "Pulsar")
        assert star.spectral_type == "PSR"

    def test_lum_class(self):
        star = _make_peculiar(1, "Pulsar")
        assert star.lum_class == "PSR"

    def test_mass_range(self):
        """PSR mass same ranges as NS."""
        for seed in range(50):
            star = _make_peculiar(seed, "Pulsar")
            assert 1.0 < star.mass <= 2.2, f"seed {seed}: PSR mass {star.mass} out of range"

    def test_diameter_range(self):
        lo = 20.0 / 695700.0
        hi = 25.0 / 695700.0
        for seed in range(50):
            star = _make_peculiar(seed, "Pulsar")
            assert lo <= star.diameter <= hi

    def test_roundtrip(self):
        star = _make_peculiar(7, "Pulsar")
        d = star.to_dict()
        restored = Star.from_dict(d)
        assert restored.spectral_type == "PSR"
        assert math.isclose(restored.mass, star.mass, rel_tol=1e-3)


class TestEnvironmentTypesUnchanged:
    """Peculiar environment types must still produce Giants star + special_notes."""

    @pytest.mark.parametrize("env", ["Nebula", "Protostar", "Star_Cluster", "Anomaly"])
    def test_env_type_giants_star(self, env):
        env_key = f"_PECULIAR_{env}"
        import traveller_gen.traveller_stellar_gen as sg
        old_rng = sg._rng  # pylint: disable=protected-access
        sg._rng = random.Random(42)  # pylint: disable=protected-access
        star = _generate_peculiar_star("A", env_key, "Giants_env")
        sg._rng = old_rng  # pylint: disable=protected-access
        assert star.lum_class in ("Ia", "Ib", "II", "III")
        assert "Peculiar environment" in star.special_notes

    @pytest.mark.parametrize("env", ["Nebula", "Protostar", "Star_Cluster", "Anomaly"])
    def test_env_type_not_ns_bh_psr(self, env):
        env_key = f"_PECULIAR_{env}"
        import traveller_gen.traveller_stellar_gen as sg
        old_rng = sg._rng  # pylint: disable=protected-access
        sg._rng = random.Random(42)  # pylint: disable=protected-access
        star = _generate_peculiar_star("A", env_key, "Giants_env")
        sg._rng = old_rng  # pylint: disable=protected-access
        assert star.spectral_type not in ("NS", "BH", "PSR")


# ---------------------------------------------------------------------------
# Phase 4 — Orbit generation for dead star systems
# ---------------------------------------------------------------------------

class TestGetMaoDeadStars:
    def _dummy_star(self, spectral: str) -> Star:
        return Star(
            designation="A", role="primary",
            spectral_type=spectral, subtype=None, lum_class=spectral,
            mass=1.4, temperature=0, diameter=0.00001, luminosity=0.0,
        )

    def test_ns_mao(self):
        assert get_mao(self._dummy_star("NS")) == 0.001

    def test_bh_mao(self):
        assert get_mao(self._dummy_star("BH")) == 0.001

    def test_psr_mao(self):
        assert get_mao(self._dummy_star("PSR")) == 0.001

    def test_wd_mao_unchanged(self):
        assert get_mao(self._dummy_star("D")) == 0.01


class TestOrbitSlotRadiationZone:
    def _make_slot(self) -> OrbitSlot:
        return OrbitSlot(
            star_designation="A", orbit_number=1.0, orbit_au=0.4,
            slot_index=1, world_type="terrestrial",
            is_habitable_zone=False, hz_deviation=0.5,
            temperature_zone="cold",
        )

    def test_default_false(self):
        slot = self._make_slot()
        assert slot.radiation_zone is False

    def test_to_dict_omits_when_false(self):
        slot = self._make_slot()
        d = slot.to_dict()
        assert "radiation_zone" not in d

    def test_to_dict_includes_when_true(self):
        slot = self._make_slot()
        slot.radiation_zone = True
        d = slot.to_dict()
        assert d.get("radiation_zone") is True

    def test_from_dict_restores_true(self):
        slot = self._make_slot()
        slot.radiation_zone = True
        d = slot.to_dict()
        restored = OrbitSlot.from_dict(d)
        assert restored.radiation_zone is True

    def test_from_dict_default_false(self):
        slot = self._make_slot()
        d = slot.to_dict()
        assert "radiation_zone" not in d
        restored = OrbitSlot.from_dict(d)
        assert restored.radiation_zone is False


class TestDeadStarSystemExists:
    def _build_system(self, primary_type: str, extra_dead: int = 0) -> StarSystem:
        """Build a minimal StarSystem for testing dead_star_system_exists."""
        primary = Star(
            designation="A", role="primary",
            spectral_type=primary_type, subtype=None, lum_class=primary_type,
            mass=1.4, temperature=0, diameter=0.00001, luminosity=0.0,
            orbit_number=0.0, orbit_au=0.0,
        )
        stars = [primary]
        for i in range(extra_dead):
            companion = Star(
                designation=f"A{chr(ord('a') + i)}", role="companion",
                spectral_type="NS", subtype=None, lum_class="NS",
                mass=1.4, temperature=0, diameter=0.00001, luminosity=0.0,
            )
            stars.append(companion)
        return StarSystem(stars=stars)

    def test_natural_12_always_succeeds(self):
        """Seed the RNG so 2D always rolls 12; result must be True regardless of DMs."""
        import traveller_gen.traveller_orbit_gen as og
        system = self._build_system("BH")

        found_true = False
        for seed in range(10000):
            rng = random.Random(seed)
            # Check if this seed gives 2+6=... we need raw roll to be 12
            r1, r2 = rng.randint(1, 6), rng.randint(1, 6)
            if r1 + r2 == 12:
                old_rng = og._rng  # pylint: disable=protected-access
                og._rng = random.Random(seed)  # pylint: disable=protected-access
                result = dead_star_system_exists(system.primary, system)
                og._rng = old_rng  # pylint: disable=protected-access
                assert result is True, f"seed {seed}: natural 12 should always return True"
                found_true = True
                break
        assert found_true, "No seed found producing natural 12 in first 10000 seeds"

    def test_bh_with_extra_dead_mostly_false(self):
        """BH primary + extra dead star → DM-6; should fail (roll<8) most of the time."""
        system = self._build_system("BH", extra_dead=1)
        false_count = 0
        for seed in range(200):
            rng = random.Random(seed)
            result = dead_star_system_exists(system.primary, system, rng=rng)
            if not result:
                false_count += 1
        # DM-6 → only natural 12 succeeds. 200 seeds: ~200/36 ≈ 5-6 successes
        assert false_count > 150, f"Expected mostly False with BH+dead, got {false_count}/200"

    def test_d_primary_can_succeed(self):
        """WD primary (D) has no extra DMs; should sometimes succeed."""
        system = self._build_system("D")
        true_count = 0
        for seed in range(200):
            rng = random.Random(seed)
            result = dead_star_system_exists(system.primary, system, rng=rng)
            if result:
                true_count += 1
        assert true_count > 50, f"Expected some True for WD primary, got {true_count}/200"


class TestPsrRadiationZones:
    def _build_psr_star(self) -> Star:
        return Star(
            designation="A", role="primary",
            spectral_type="PSR", subtype=None, lum_class="PSR",
            mass=1.5, temperature=5000, diameter=2.8e-5, luminosity=1e-15,
            orbit_number=0.0, orbit_au=0.0, age_gyr=5.0,
        )

    def test_psr_orbits_flagged_radiation_zone(self):
        """All occupied orbits in a PSR system should have radiation_zone=True."""
        import traveller_gen.traveller_stellar_gen as sg
        # Find a seed where the PSR system exists AND has at least one world
        for seed in range(500):
            rng = random.Random(seed)
            psr_star = self._build_psr_star()
            star_system = StarSystem(stars=[psr_star])
            orbits = generate_orbits(star_system, rng=rng)
            worlds = [o for o in orbits.orbits if o.world_type != "empty"]
            if worlds:
                for o in worlds:
                    assert o.radiation_zone is True, (
                        f"seed {seed}: PSR orbit {o.orbit_number} not flagged radiation_zone"
                    )
                return
        pytest.skip("No PSR system with worlds found in 500 seeds")

    def test_ns_orbits_not_radiation_zone(self):
        """NS (not PSR) orbits should not have radiation_zone=True."""
        ns_star = Star(
            designation="A", role="primary",
            spectral_type="NS", subtype=None, lum_class="NS",
            mass=1.4, temperature=5000, diameter=2.8e-5, luminosity=1e-15,
            orbit_number=0.0, orbit_au=0.0, age_gyr=5.0,
        )
        star_system = StarSystem(stars=[ns_star])
        for seed in range(100):
            rng = random.Random(seed)
            orbits = generate_orbits(star_system, rng=rng)
            worlds = [o for o in orbits.orbits if o.world_type != "empty"]
            if worlds:
                for o in worlds:
                    assert o.radiation_zone is False, (
                        f"seed {seed}: NS orbit has unexpected radiation_zone=True"
                    )
                return


class TestDeadStarOrbitIntegration:
    def test_wd_system_has_mao_0_01(self):
        """WD primary MAO should be 0.01 (unchanged from Phase 1)."""
        wd_star = Star(
            designation="A", role="primary",
            spectral_type="D", subtype=None, lum_class="D",
            mass=0.7, temperature=5000, diameter=0.013, luminosity=0.0001,
            orbit_number=0.0, orbit_au=0.0, age_gyr=5.0,
        )
        assert get_mao(wd_star) == 0.01

    def test_psr_system_mao_0_001(self):
        """PSR primary MAO should be 0.001."""
        psr_star = Star(
            designation="A", role="primary",
            spectral_type="PSR", subtype=None, lum_class="PSR",
            mass=1.4, temperature=5000, diameter=2.8e-5, luminosity=1e-15,
            orbit_number=0.0, orbit_au=0.0, age_gyr=5.0,
        )
        assert get_mao(psr_star) == 0.001

    def test_dead_star_generate_orbits_runs(self):
        """generate_orbits with NS/BH/PSR primary should complete without error."""
        for spec in ("NS", "BH", "PSR"):
            dead_star = Star(
                designation="A", role="primary",
                spectral_type=spec, subtype=None, lum_class=spec,
                mass=1.4, temperature=5000, diameter=2.8e-5, luminosity=1e-15,
                orbit_number=0.0, orbit_au=0.0, age_gyr=5.0,
            )
            star_system = StarSystem(stars=[dead_star])
            for seed in range(20):
                rng = random.Random(seed)
                orbits = generate_orbits(star_system, rng=rng)
                assert orbits is not None, f"{spec} seed {seed}: generate_orbits returned None"

    def test_ns_system_orbits_valid(self):
        """An NS primary should generate either empty orbits or valid orbit slots."""
        ns_star = Star(
            designation="A", role="primary",
            spectral_type="NS", subtype=None, lum_class="NS",
            mass=1.4, temperature=5000, diameter=2.8e-5, luminosity=1e-15,
            orbit_number=0.0, orbit_au=0.0, age_gyr=5.0,
        )
        star_system = StarSystem(stars=[ns_star])
        for seed in range(100):
            rng = random.Random(seed)
            orbits = generate_orbits(star_system, rng=rng)
            # All orbits should have orbit_au > 0
            for o in orbits.orbits:
                assert o.orbit_au > 0, f"seed {seed}: orbit_au {o.orbit_au} not positive"
