"""
Property-based tests using Hypothesis (issue #38, Phase 2).

Strategy: draw an integer seed via st.integers(), pass to generate_world(seed=seed)
which sets the module RNG deterministically.  Each Hypothesis example is therefore
self-contained — no shared-state cross-contamination between examples.

Requires: hypothesis>=6.100 (see requirements-dev.txt)
"""

import re
import sys
import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure the project root is on the path (mirrors conftest.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_UWP_RE = re.compile(r"^[A-EX][0-9A-Z]{6}-[0-9A-Z]$")


# ===========================================================================
# TestGeneratorRangeInvariants
# ===========================================================================

class TestGeneratorRangeInvariants:
    """generate_world(seed=N) must always produce fields within documented ranges."""

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_size_in_range(self, seed):
        from traveller_world_gen import generate_world
        w = generate_world(seed=seed)
        assert 0 <= w.size <= 10, f"size={w.size} out of range for seed={seed}"

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_atmosphere_in_range(self, seed):
        from traveller_world_gen import generate_world
        w = generate_world(seed=seed)
        assert 0 <= w.atmosphere <= 15, f"atmosphere={w.atmosphere} out of range for seed={seed}"

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_hydrographics_in_range(self, seed):
        from traveller_world_gen import generate_world
        w = generate_world(seed=seed)
        assert 0 <= w.hydrographics <= 10, f"hydrographics={w.hydrographics} out of range for seed={seed}"

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_population_in_range(self, seed):
        from traveller_world_gen import generate_world
        w = generate_world(seed=seed)
        assert 0 <= w.population <= 10, f"population={w.population} out of range for seed={seed}"

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_government_in_range(self, seed):
        from traveller_world_gen import generate_world
        w = generate_world(seed=seed)
        assert 0 <= w.government <= 15, f"government={w.government} out of range for seed={seed}"

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_law_level_in_range(self, seed):
        from traveller_world_gen import generate_world
        w = generate_world(seed=seed)
        assert 0 <= w.law_level <= 18, f"law_level={w.law_level} out of range for seed={seed}"

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_starport_is_valid(self, seed):
        from traveller_world_gen import generate_world
        from world_codes import StarportCode
        w = generate_world(seed=seed)
        valid = {e.value for e in StarportCode}
        assert w.starport in valid, f"starport={w.starport!r} not in StarportCode for seed={seed}"

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_temperature_is_valid(self, seed):
        from traveller_world_gen import generate_world
        from world_codes import TemperatureCategory
        w = generate_world(seed=seed)
        valid = {e.value for e in TemperatureCategory}
        assert w.temperature in valid, (
            f"temperature={w.temperature!r} not in TemperatureCategory for seed={seed}"
        )

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_trade_codes_are_valid(self, seed):
        from traveller_world_gen import generate_world
        from world_codes import TradeCode
        w = generate_world(seed=seed)
        valid = {e.value for e in TradeCode}
        for tc in w.trade_codes:
            assert tc in valid, f"trade_code={tc!r} not in TradeCode for seed={seed}"

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_travel_zone_is_valid(self, seed):
        from traveller_world_gen import generate_world
        from world_codes import TravelZone
        w = generate_world(seed=seed)
        valid = {e.value for e in TravelZone}
        assert w.travel_zone in valid, (
            f"travel_zone={w.travel_zone!r} not in TravelZone for seed={seed}"
        )


# ===========================================================================
# TestUWPFormat
# ===========================================================================

class TestUWPFormat:
    """World.uwp() always returns a valid 9-character UWP string."""

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    @settings(max_examples=200)
    def test_uwp_matches_pattern(self, seed):
        from traveller_world_gen import generate_world
        w = generate_world(seed=seed)
        uwp = w.uwp()
        assert _UWP_RE.match(uwp), (
            f"UWP {uwp!r} does not match expected format for seed={seed}"
        )

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_uwp_length_is_nine(self, seed):
        from traveller_world_gen import generate_world
        w = generate_world(seed=seed)
        assert len(w.uwp()) == 9, f"UWP {w.uwp()!r} is not 9 chars for seed={seed}"


# ===========================================================================
# TestWorldRoundTrip
# ===========================================================================

class TestWorldRoundTrip:
    """World.from_dict(world.to_dict()) reconstructs an identical World."""

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    @settings(max_examples=200)
    def test_uwp_preserved(self, seed):
        from traveller_world_gen import generate_world, World
        world = generate_world(seed=seed)
        restored = World.from_dict(world.to_dict())
        assert world.uwp() == restored.uwp(), (
            f"UWP changed after round-trip: {world.uwp()!r} → {restored.uwp()!r} (seed={seed})"
        )

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_trade_codes_preserved(self, seed):
        from traveller_world_gen import generate_world, World
        world = generate_world(seed=seed)
        restored = World.from_dict(world.to_dict())
        assert sorted(world.trade_codes) == sorted(restored.trade_codes), (
            f"trade_codes changed after round-trip (seed={seed})"
        )

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_bases_preserved(self, seed):
        from traveller_world_gen import generate_world, World
        world = generate_world(seed=seed)
        restored = World.from_dict(world.to_dict())
        assert sorted(world.bases) == sorted(restored.bases), (
            f"bases changed after round-trip (seed={seed})"
        )

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_travel_zone_preserved(self, seed):
        from traveller_world_gen import generate_world, World
        world = generate_world(seed=seed)
        restored = World.from_dict(world.to_dict())
        assert world.travel_zone == restored.travel_zone, (
            f"travel_zone changed after round-trip (seed={seed})"
        )

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    def test_temperature_preserved(self, seed):
        from traveller_world_gen import generate_world, World
        world = generate_world(seed=seed)
        restored = World.from_dict(world.to_dict())
        assert world.temperature == restored.temperature, (
            f"temperature changed after round-trip (seed={seed})"
        )


# ===========================================================================
# TestValidationAcceptsGenerated
# ===========================================================================

class TestValidationAcceptsGenerated:
    """
    World._validate_world_codes() must accept every world produce by generate_world().

    This is the key cross-check: if a generator produces an out-of-range value
    the range tests above will catch it, but this test verifies that the Phase 1
    validator and the generators agree on what constitutes a valid world.
    """

    @given(st.integers(min_value=0, max_value=2**31 - 1))
    @settings(max_examples=200)
    def test_generated_world_passes_validation(self, seed):
        from traveller_world_gen import generate_world, World
        world = generate_world(seed=seed)
        # _validate_world_codes raises ValueError on invalid data; must not raise
        World._validate_world_codes(world.to_dict())  # pylint: disable=protected-access
