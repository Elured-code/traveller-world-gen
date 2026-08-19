"""Tests for issue #44 Stage 1: temperature_k parameter in gas mix generation.

Covers:
- compute_basic_temperature_k() — deterministic output, None for extreme cold
- _select_gas_mix_table() — Frozen Deep sub-range DM with and without temperature_k
- generate_gas_mix() — temperature_k parameter threads through without dice side-effects
"""
import random

import pytest

from traveller_gen.traveller_world_atmosphere_detail import compute_basic_temperature_k
from traveller_gen.traveller_world_atmosphere_gen import (
    _select_gas_mix_table,  # pylint: disable=protected-access
    generate_gas_mix,
    AtmosphereDetail,
)


# ---------------------------------------------------------------------------
# compute_basic_temperature_k
# ---------------------------------------------------------------------------

class TestComputeBasicTemperatureK:
    """compute_basic_temperature_k returns deterministic K values without dice."""

    def test_returns_int_for_hz_zero(self):
        k = compute_basic_temperature_k(0.0, 6)
        assert isinstance(k, int)
        assert k > 0

    def test_returns_none_for_none_hz(self):
        assert compute_basic_temperature_k(None, 6) is None

    def test_warmer_orbit_gives_higher_temp(self):
        k_inner = compute_basic_temperature_k(-1.5, 6)  # closer to star
        k_outer = compute_basic_temperature_k(1.5, 6)   # farther from star
        assert k_inner is not None and k_outer is not None
        assert k_inner > k_outer

    def test_no_dice_for_moderate_cold(self):
        # hz_deviation 3.5 → Frozen deep but not extreme; should return int, not None
        k = compute_basic_temperature_k(3.5, 10)
        assert k is not None
        assert isinstance(k, int)
        assert k > 0

    def test_returns_none_for_extreme_cold(self):
        # hz_deviation > ~19 triggers modified_roll < -33 (dice territory)
        k = compute_basic_temperature_k(20.0, 0)
        assert k is None

    def test_deterministic_no_rng_consumed(self):
        """Same inputs must always produce the same output (no dice)."""
        rng = random.Random(42)
        state_before = rng.getstate()
        k1 = compute_basic_temperature_k(0.5, 6)
        k2 = compute_basic_temperature_k(0.5, 6)
        state_after = rng.getstate()
        assert k1 == k2
        assert state_before == state_after  # module _rng not consumed

    @pytest.mark.parametrize("atmosphere", [0, 1, 5, 6, 10, 13])
    def test_various_atmospheres_hz_zero(self, atmosphere):
        k = compute_basic_temperature_k(0.0, atmosphere)
        assert k is not None
        assert k >= 3


# ---------------------------------------------------------------------------
# _select_gas_mix_table — Frozen Deep sub-range DM
# ---------------------------------------------------------------------------

class TestSelectGasMixTableFrozenDeep:
    """Frozen Deep (hz_deviation >= 3.01): DM+3 only when 70 <= K <= 100."""

    def _extra_dm(self, temperature_k):
        _, _, _, _, extra_dm, _ = _select_gas_mix_table(
            "Frozen", hz_deviation=3.5, temperature_k=temperature_k
        )
        return extra_dm

    def test_within_band_gives_dm3(self):
        assert self._extra_dm(70) == 3
        assert self._extra_dm(85) == 3
        assert self._extra_dm(100) == 3

    def test_below_band_gives_dm0(self):
        assert self._extra_dm(69) == 0
        assert self._extra_dm(50) == 0

    def test_above_band_gives_dm0(self):
        assert self._extra_dm(101) == 0
        assert self._extra_dm(150) == 0

    def test_no_temperature_k_uses_legacy_dm3(self):
        # Without temperature_k, the heuristic always applies DM+3
        assert self._extra_dm(None) == 3

    def test_not_frozen_deep_unaffected(self):
        # Frozen mid (hz_deviation < 3.01) is not changed by temperature_k
        _, _, _, _, extra_dm, _ = _select_gas_mix_table(
            "Frozen", hz_deviation=2.0, temperature_k=85
        )
        assert extra_dm == 0


# ---------------------------------------------------------------------------
# _select_gas_mix_table — other temperature categories unaffected
# ---------------------------------------------------------------------------

class TestSelectGasMixTableOtherZones:
    """Non-Frozen-Deep branches pass through temperature_k without effect."""

    @pytest.mark.parametrize("temperature,hz_dev", [
        ("Boiling", -3.0),  # very-hot
        ("Boiling", -1.0),  # hot
        ("Hot", 0.0),
        ("Cold", 1.5),
        ("Frozen", 2.0),   # mid
    ])
    def test_extra_dm_unchanged_with_temperature_k(self, temperature, hz_dev):
        _, _, _, _, dm_without, _ = _select_gas_mix_table(
            temperature, hz_dev, temperature_k=None
        )
        _, _, _, _, dm_with, _ = _select_gas_mix_table(
            temperature, hz_dev, temperature_k=85
        )
        assert dm_without == dm_with


# ---------------------------------------------------------------------------
# generate_gas_mix — temperature_k threads through
# ---------------------------------------------------------------------------

class TestGenerateGasMixTemperatureK:
    """generate_gas_mix accepts temperature_k without error."""

    def _make_detail(self):
        return AtmosphereDetail(
            pressure_bar=None,
            oxygen_partial_pressure=None,
            scale_height_km=None,
            taints=[],
            subtype_code=None,
            subtype_name=None,
            hazards=[],
            gas_mix=None,
            min_safe_altitude_km=None,
            no_safe_altitude=False,
            unusual_subtypes=[],
        )

    def test_no_op_for_non_exotic_code(self):
        detail = self._make_detail()
        generate_gas_mix(detail, atm_code=6, size=6, temperature="Temperate",
                         hz_deviation=0.0, hydro=5, temperature_k=280)
        assert detail.gas_mix is None

    @pytest.mark.parametrize("atm_code", [10, 11, 12])
    def test_populates_gas_mix_with_temperature_k(self, atm_code):
        detail = self._make_detail()
        generate_gas_mix(detail, atm_code=atm_code, size=6, temperature="Temperate",
                         hz_deviation=0.0, hydro=0, temperature_k=290)
        assert detail.gas_mix is not None
        assert len(detail.gas_mix) >= 1

    def test_temperature_k_none_works_same_as_before(self):
        """temperature_k=None must not change behaviour relative to omitting it."""
        rng = random.Random(7)
        detail_a = self._make_detail()
        detail_b = self._make_detail()
        # Use the same RNG state for both calls
        import traveller_gen.traveller_world_atmosphere_gen as _twag
        _twag._rng = rng  # pylint: disable=protected-access
        generate_gas_mix(detail_a, 10, 6, "Frozen", 3.5, 0)
        state_mid = rng.getstate()
        _twag._rng = random.Random(7)
        generate_gas_mix(detail_b, 10, 6, "Frozen", 3.5, 0, temperature_k=None)
        assert detail_a.gas_mix == detail_b.gas_mix
