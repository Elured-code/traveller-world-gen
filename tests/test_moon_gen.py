"""
tests/test_moon_gen.py
======================
Unit tests for moon orbit placement (WBH pp.74-77).

Tests cover:
  - Hill sphere calculations
  - Moon removal rules
  - Moon Orbit Range (MOR)
  - Orbit PD rolling
  - Period formula
  - Ring placement
  - generate_moons() integration
"""

from unittest.mock import patch
import pytest

from traveller_moon_gen import (  # pylint: disable=import-error
    generate_moons,
    _hill_sphere_au,
    _hill_sphere_pd,
    _hill_moon_limit,
    _moon_orbit_range,
    _roll_moon_pd,
    _moon_period_hours,
    _place_ring,
)


# ---------------------------------------------------------------------------
# TestHillSphere
# ---------------------------------------------------------------------------

class TestHillSphere:
    """Hill sphere radius calculations (WBH p.74)."""

    def test_hill_sphere_au_known_example(self):
        """WBH p.74 example: GG at 1.06 AU, ecc=0.10, mass=1200⊕, star=1.836☉ → ≈0.083 AU."""
        result = _hill_sphere_au(1.06, 0.10, 1200.0, 1.836)
        assert abs(result - 0.083) < 0.002

    def test_hill_sphere_pd_known_example(self):
        """Same GG with diameter 14×12800=179200 km: hill_au ≈ 0.083 → ≈69.3 PD."""
        hill_au = _hill_sphere_au(1.06, 0.10, 1200.0, 1.836)
        result = _hill_sphere_pd(hill_au, 14 * 12800)
        assert abs(result - 69.3) < 1.0

    def test_hill_moon_limit(self):
        """69.37 PD → floor(69.37 / 2) = 34."""
        assert _hill_moon_limit(69.37) == 34

    def test_hill_sphere_zero_ecc_larger_than_nonzero(self):
        """ecc=0 gives a larger Hill sphere radius than ecc=0.1 for the same other params."""
        hs_0  = _hill_sphere_au(1.06, 0.0,  1200.0, 1.836)
        hs_01 = _hill_sphere_au(1.06, 0.10, 1200.0, 1.836)
        assert hs_0 > hs_01


# ---------------------------------------------------------------------------
# TestMoonRemoval
# ---------------------------------------------------------------------------

class TestMoonRemoval:
    """Moon removal when Hill sphere is too small (WBH p.75)."""

    def test_no_moons_or_rings_when_hill_pd_below_0_5(self):
        """hill_pd=0.4 → moon_limit=0 → everything removed."""
        with patch("traveller_moon_gen._moon_quantity", return_value=1), \
             patch("traveller_moon_gen._hill_sphere_pd", return_value=0.4), \
             patch("traveller_moon_gen._hill_sphere_au", return_value=1.0), \
             patch("traveller_moon_gen.random.randint", return_value=3):
            result = generate_moons(
                size_code=5, orbit_number=2.0,
                orbit_au=1.0, star_mass_solar=1.0,
            )
        assert result == []

    def test_moon_becomes_ring_when_hill_moon_limit_is_1(self):
        """hill_pd=2.5 → moon_limit=1; one sig moon is converted to a ring."""
        with patch("traveller_moon_gen._moon_quantity", return_value=1), \
             patch("traveller_moon_gen._hill_sphere_pd", return_value=2.5), \
             patch("traveller_moon_gen._hill_sphere_au", return_value=1.0), \
             patch("traveller_moon_gen.random.randint", return_value=3):
            moons = generate_moons(
                size_code=5, orbit_number=2.0,
                orbit_au=1.0, star_mass_solar=1.0,
            )
        assert len(moons) == 1
        assert moons[0].is_ring

    def test_ring_survives_when_hill_moon_limit_is_1(self):
        """hill_pd=2.5 → moon_limit=1; a pre-existing ring survives."""
        with patch("traveller_moon_gen._moon_quantity", return_value=0), \
             patch("traveller_moon_gen._hill_sphere_pd", return_value=2.5), \
             patch("traveller_moon_gen._hill_sphere_au", return_value=1.0):
            moons = generate_moons(
                size_code=5, orbit_number=2.0,
                orbit_au=1.0, star_mass_solar=1.0,
            )
        assert len(moons) == 1
        assert moons[0].is_ring


# ---------------------------------------------------------------------------
# TestMoonOrbitRange
# ---------------------------------------------------------------------------

class TestMoonOrbitRange:
    """MOR computation (WBH p.75)."""

    def test_mor_basic(self):
        """moon_limit=34, n_moons=5 → MOR = 34 − 2 = 32."""
        assert _moon_orbit_range(34, 5) == 32

    def test_mor_capped_at_200_plus_n(self):
        """moon_limit=210, n_moons=3 → uncapped MOR=208; cap=203 → 203."""
        assert _moon_orbit_range(210, 3) == 203

    def test_mor_zero_when_limit_le_2(self):
        """moon_limit ≤ 2 → MOR = 0 (no room below the Roche limit)."""
        assert _moon_orbit_range(2, 5) == 0
        assert _moon_orbit_range(1, 5) == 0


# ---------------------------------------------------------------------------
# TestOrbitRolling
# ---------------------------------------------------------------------------

class TestOrbitRolling:
    """Orbit PD rolling per the Moon Orbit Location table (WBH pp.75-76)."""

    def test_inner_range_result(self):
        """1D=1 → inner; 2D=12 (r2d=10); formula: 10×60÷60+2 = 12.0 PD."""
        with patch("traveller_moon_gen.random.randint", return_value=1), \
             patch("traveller_moon_gen._roll", return_value=12):
            pd, rng = _roll_moon_pd(60)
        assert rng == "inner"
        assert pd == 12.0

    def test_middle_range_result(self):
        """1D=4 → middle; 2D=12 (r2d=10); MOR=60: 10×2+10+3 = 33.0 PD."""
        with patch("traveller_moon_gen.random.randint", return_value=4), \
             patch("traveller_moon_gen._roll", return_value=12):
            pd, rng = _roll_moon_pd(60)
        assert rng == "middle"
        assert pd == 33.0

    def test_outer_range_result(self):
        """1D=6 → outer; 2D=12 (r2d=10); MOR=60: 10×3+30+4 = 64.0 PD."""
        with patch("traveller_moon_gen.random.randint", return_value=6), \
             patch("traveller_moon_gen._roll", return_value=12):
            pd, rng = _roll_moon_pd(60)
        assert rng == "outer"
        assert pd == 64.0

    def test_dm1_shifts_range_toward_inner_when_mor_lt_60(self):
        """MOR=30 → DM+1; natural roll=3 becomes effective 4 → middle range."""
        with patch("traveller_moon_gen.random.randint", return_value=3), \
             patch("traveller_moon_gen._roll", return_value=6):
            _, rng = _roll_moon_pd(30)
        assert rng == "middle"


# ---------------------------------------------------------------------------
# TestPeriod
# ---------------------------------------------------------------------------

class TestPeriod:
    """Orbital period calculation (WBH p.76)."""

    def test_period_known_example(self):
        """WBH example: orbit_km=22×14×12800, mass=1200⊕ → period ≈ 624.7 hours."""
        orbit_km = 22 * 14 * 12800
        result = _moon_period_hours(orbit_km, 1200.0)
        assert abs(result - 624.7) < 2.0

    def test_period_zero_mass_returns_zero(self):
        """Zero planet mass → period returns 0.0 (guard against division by zero)."""
        assert _moon_period_hours(1_000_000.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# TestRingPlacement
# ---------------------------------------------------------------------------

class TestRingPlacement:
    """Ring centre location and span (WBH p.77)."""

    def test_ring_centre_formula(self):
        """roll(2)=8 → centre=0.4+1.0=1.4; roll(3)=6 → span=0.06+0.07=0.13."""
        with patch("traveller_moon_gen._roll", side_effect=[8, 6]):
            centre, span = _place_ring(12800.0)
        assert centre == pytest.approx(1.4, abs=0.001)
        assert span == pytest.approx(0.13, abs=0.001)

    def test_ring_span_formula(self):
        """roll(2)=10 → centre=0.4+1.25=1.65; roll(3)=10 → span=0.10+0.07=0.17."""
        with patch("traveller_moon_gen._roll", side_effect=[10, 10]):
            centre, span = _place_ring(12800.0)
        assert centre == pytest.approx(1.65, abs=0.001)
        assert span == pytest.approx(0.17, abs=0.001)

    def test_inner_edge_clamp(self):
        """roll(2)=2 (naive centre=0.65), roll(3)=18 (span=0.25): inner edge 0.525 → clamped."""
        with patch("traveller_moon_gen._roll", side_effect=[2, 18]):
            centre, span = _place_ring(12800.0)
        assert centre - span / 2.0 >= 0.549  # innermost edge ≥ 0.55 PD


# ---------------------------------------------------------------------------
# TestGenerateMoonsOrbit
# ---------------------------------------------------------------------------

class TestGenerateMoonsOrbit:
    """Integration: generate_moons() with orbit placement parameters."""

    def test_moons_get_orbit_when_data_provided(self):
        """Size-8 planet at 1.5 AU with star_mass=1.0 → sig moons have orbit_pd set."""
        moons = generate_moons(
            size_code=8, orbit_number=3.0,
            orbit_au=1.5, star_mass_solar=1.0,
        )
        sig = [m for m in moons if not m.is_ring]
        for m in sig:
            assert m.orbit_pd is not None
            assert m.orbit_pd > 0.0
            assert m.orbit_km is not None
            assert m.orbit_range in ("inner", "middle", "outer", "excess")
            assert m.orbit_period_hours is not None

    def test_no_orbit_without_data(self):
        """Default call with no orbit params → orbit_pd remains None on all moons."""
        moons = generate_moons(size_code=8, orbit_number=3.0)
        for m in moons:
            assert m.orbit_pd is None

    def test_moon_orbits_ascending(self):
        """Multiple sig moons always have ascending orbit_pd values after placement."""
        for _ in range(20):
            moons = generate_moons(
                size_code=10, orbit_number=3.0,
                orbit_au=2.0, star_mass_solar=1.0,
            )
            sig = [m for m in moons if not m.is_ring and m.orbit_pd is not None]
            pds = [m.orbit_pd for m in sig]
            assert pds == sorted(pds), f"orbits not ascending: {pds}"
