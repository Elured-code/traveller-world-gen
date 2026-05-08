"""
test_belt_physical.py
=====================
pytest unit tests for traveller_belt_physical.py.

Test strategy
-------------
Deterministic DM / table logic is tested directly. Dice-dependent outcomes are
tested by patching random.randint to a fixed value, so the downstream logic
can be verified without probabilistic flakiness.
"""

import math
from unittest.mock import patch

import pytest

from traveller_belt_physical import (
    BeltPhysical,
    _roll_belt_span,
    _roll_bulk,
    _roll_composition,
    _roll_resource_rating,
    _roll_size_1_bodies,
    _roll_size_s_bodies,
    generate_belt_physical,
)
from traveller_system_gen import generate_full_system
from traveller_world_detail import attach_detail


# ---------------------------------------------------------------------------
# _roll_composition
# ---------------------------------------------------------------------------

class TestRollComposition:
    def test_inner_hz_dm_minus4(self):
        """hz_deviation < 0 → DM-4; force 2D=2 → raw=-2 → clamped row 0 (heavy metallic)."""
        # Row 0: m=60+d6×5, s=0+d6×5, c=0 (mult=0)
        # With randint always 1: m=65, s=5, c=0, total=70, other=30
        with patch("traveller_belt_physical.random.randint", return_value=1):
            m, s, c, other = _roll_composition(hz_deviation=-1.0)
        assert m == 65
        assert s == 5
        assert c == 0
        assert other == 30

    def test_outer_hz_dm_plus4(self):
        """hz_deviation > 2 → DM+4; randint=1 → 2D=2, raw=6 → row 6 (mixed)."""
        # Row 6: m=(0,5,False)=5, s=(40,5,False)=45, c=(0,5,False)=5 → other=45
        with patch("traveller_belt_physical.random.randint", return_value=1):
            m, s, c, other = _roll_composition(hz_deviation=3.0)
        assert m == 5
        assert s == 45
        assert c == 5
        assert other == 45

    def test_hz_zone_no_dm(self):
        """0 <= hz_deviation <= 2 → no DM; randint=1 → 2D=2 → row 2."""
        # Row 2: m=(40,5,False)=45, s=(15,5,False)=20, c=(0,1,False)=1 → other=34
        with patch("traveller_belt_physical.random.randint", return_value=1):
            m, s, c, other = _roll_composition(hz_deviation=1.0)
        assert m == 45
        assert s == 20
        assert c == 1
        assert other == 34

    def test_normalisation_trims_m_first(self):
        """If m+s+c > 100, trim m first then s; other becomes 0."""
        # Row 0 with randint=6: m=60+30=90, s=0+30=30, c=0 → total=120
        # excess=20; m_cut=min(90,20)=20 → m=70, s=30, other=0
        with patch("traveller_belt_physical.random.randint", return_value=6):
            m, s, c, other = _roll_composition(hz_deviation=-1.0)
        assert m + s + c <= 100
        assert other == 0

    def test_normalisation_trims_s_after_m_exhausted(self):
        """Excess beyond what m can absorb is trimmed from s."""
        # Row 0 with randint=6: m=90, s=30, c=0 → total=120
        # excess=20, m absorbs all 20 → m=70, s=30, c=0, other=0
        with patch("traveller_belt_physical.random.randint", return_value=6):
            m, s, c, other = _roll_composition(hz_deviation=-1.0)
        total = m + s + c + other
        assert total == 100

    def test_row_11_m_uses_d3(self):
        """Row 11: m uses D3; DM+4 with 2D=7 → raw=11 → row 11."""
        # Dice sequence: [4,3] → 2D=7+4=11 → row 11
        # Row 11: m=(0,1,True) → D3 die=6 → (6+1)//2=3 → m=3
        #         s=(5,2,False) → d6=1 → s=7
        #         c=(60,5,False) → d6=1 → c=65  total=75, other=25
        dice = iter([4, 3, 6, 1, 1])
        with patch("traveller_belt_physical.random.randint", side_effect=dice):
            m, s, c, other = _roll_composition(hz_deviation=3.0)
        assert c == 65
        assert m + s + c + other == 100

    def test_percentages_sum_to_100(self):
        """Composition always sums to exactly 100."""
        import random as rng
        rng.seed(42)
        for hz_dev in (-2.0, 0.0, 1.5, 3.5):
            m, s, c, other = _roll_composition(hz_dev)
            assert m + s + c + other == 100, f"hz_dev={hz_dev}: {m}+{s}+{c}+{other}≠100"


# ---------------------------------------------------------------------------
# _roll_belt_span
# ---------------------------------------------------------------------------

class TestRollBeltSpan:
    def test_no_dms(self):
        """Base case: no DMs; 2D rolls → span = orbit_spread × roll / 10."""
        # Force both dice to 3 → roll=6, span=10.0×6/10=6.0
        with patch("traveller_belt_physical.random.randint", return_value=3):
            span = _roll_belt_span(orbit_spread=10.0, next_is_gas_giant=False, is_outermost=False)
        assert span == pytest.approx(6.0)

    def test_next_is_gas_giant_dm_plus1(self):
        """next_is_gas_giant → DM+1; dice=3,3 → roll=7, span=10×7/10=7.0."""
        with patch("traveller_belt_physical.random.randint", return_value=3):
            span = _roll_belt_span(orbit_spread=10.0, next_is_gas_giant=True, is_outermost=False)
        assert span == pytest.approx(7.0)

    def test_is_outermost_dm_plus2(self):
        """is_outermost → DM+2; dice=3,3 → roll=8, span=10×8/10=8.0."""
        with patch("traveller_belt_physical.random.randint", return_value=3):
            span = _roll_belt_span(orbit_spread=10.0, next_is_gas_giant=False, is_outermost=True)
        assert span == pytest.approx(8.0)

    def test_both_dms(self):
        """Both DMs: DM+3; dice=3,3 → roll=9, span=10×9/10=9.0."""
        with patch("traveller_belt_physical.random.randint", return_value=3):
            span = _roll_belt_span(orbit_spread=10.0, next_is_gas_giant=True, is_outermost=True)
        assert span == pytest.approx(9.0)

    def test_span_rounded_to_3dp(self):
        """Span is rounded to 3 decimal places."""
        with patch("traveller_belt_physical.random.randint", return_value=3):
            span = _roll_belt_span(orbit_spread=3.3, next_is_gas_giant=False, is_outermost=False)
        assert span == round(3.3 * 6 / 10, 3)


# ---------------------------------------------------------------------------
# _roll_bulk
# ---------------------------------------------------------------------------

class TestRollBulk:
    def test_minimum_is_1(self):
        """Result is always at least 1 even with harsh negative DMs."""
        # age=20 gyr → DM-10; c_pct=0 → DM+0; D2=1+1=2 → 2-10=-8 → max(1,-8)=1
        with patch("traveller_belt_physical.random.randint", return_value=1):
            bulk = _roll_bulk(age_gyr=20.0, c_pct=0)
        assert bulk == 1

    def test_age_dm_rounds_down(self):
        """DM for age = -int(age/2); age=3 → -1."""
        # age=3 → dm_age=-1; c_pct=0 → dm_c=0; D2=2+2=4 → 4-1=3
        with patch("traveller_belt_physical.random.randint", return_value=2):
            bulk = _roll_bulk(age_gyr=3.0, c_pct=0)
        assert bulk == 3

    def test_c_pct_dm(self):
        """DM for c_pct = int(c_pct/10); c_pct=30 → +3."""
        # age=0 → dm_age=0; c_pct=30 → dm_c=3; D2=1+1=2 → 2+3=5
        with patch("traveller_belt_physical.random.randint", return_value=1):
            bulk = _roll_bulk(age_gyr=0.0, c_pct=30)
        assert bulk == 5

    def test_combined_dms(self):
        """age=4 → DM-2, c_pct=20 → DM+2 → net DM=0; D2=1+1=2."""
        with patch("traveller_belt_physical.random.randint", return_value=1):
            bulk = _roll_bulk(age_gyr=4.0, c_pct=20)
        assert bulk == 2


# ---------------------------------------------------------------------------
# _roll_resource_rating
# ---------------------------------------------------------------------------

class TestRollResourceRating:
    def test_base_case_unclamped(self):
        """2D-7+DMs, no exploitation; bulk=5, m_pct=30, c_pct=10."""
        # dm = 5 + int(30/10) + floor(-10/10) = 5+3-1=7
        # 2D(dice=3)-7+7=6 → 6, not clamped
        with patch("traveller_belt_physical.random.randint", return_value=3):
            rating = _roll_resource_rating(bulk=5, m_pct=30, c_pct=10, is_exploited=False)
        assert rating == 6

    def test_clamped_minimum_2(self):
        """Rating < 2 → clamped to 2."""
        # dm=0; 2D(dice=1)-7=-5 → max(2,-5)=2
        with patch("traveller_belt_physical.random.randint", return_value=1):
            rating = _roll_resource_rating(bulk=0, m_pct=0, c_pct=0, is_exploited=False)
        assert rating == 2

    def test_clamped_maximum_12(self):
        """Rating > 12 → clamped to 12."""
        # dm=12+6=18; 2D(dice=6)-7+18=23 → min(12,23)=12
        with patch("traveller_belt_physical.random.randint", return_value=6):
            rating = _roll_resource_rating(bulk=12, m_pct=60, c_pct=0, is_exploited=False)
        assert rating == 12

    def test_c_pct_dm_negative_rounding(self):
        """c_pct DM uses math.floor(-c/10); c_pct=18 → floor(-1.8)=-2."""
        # dm = bulk(0) + m(0) + floor(-18/10) = -2
        # 2D(dice=4)-7-2=-5 → max(2,-5)=2
        with patch("traveller_belt_physical.random.randint", return_value=4):
            rating = _roll_resource_rating(bulk=0, m_pct=0, c_pct=18, is_exploited=False)
        assert rating == 2

    def test_exploitation_reduces_rating(self):
        """Exploitation subtracts 1D from the result before clamping."""
        # Pre-exploitation: 2D(dice=6)-7+12=17 → clamped 12
        # Then subtract 1D(dice=6)=6 → 12-6=6
        with patch("traveller_belt_physical.random.randint", return_value=6):
            rating = _roll_resource_rating(bulk=12, m_pct=0, c_pct=0, is_exploited=True)
        # pre-clamp result=17, then -6 → 11; clamped [2,12] → 11
        assert rating == 11

    def test_exploitation_clamps_to_2(self):
        """Exploitation can push result below 2, which is clamped to 2."""
        # Pre-exploitation: 2D(dice=1)-7=-5 → unclamped -5
        # Then -1D(dice=6)=-11 → max(2,-11)=2
        with patch("traveller_belt_physical.random.randint", return_value=1):
            rating = _roll_resource_rating(bulk=0, m_pct=0, c_pct=0, is_exploited=True)
        assert rating == 2


# ---------------------------------------------------------------------------
# _roll_size_1_bodies
# ---------------------------------------------------------------------------

class TestRollSize1Bodies:
    def test_base_case_low_roll(self):
        """2D-12+bulk+DMs; dice=3,3=6, bulk=3, no DMs → 6-12+3=-3 → max(0,-3)=0."""
        with patch("traveller_belt_physical.random.randint", return_value=3):
            count = _roll_size_1_bodies(bulk=3, hz_deviation=0.0, span_au=0.5)
        assert count == 0

    def test_high_bulk_and_roll(self):
        """dice=6,6=12, bulk=5 → 12-12+5=5."""
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_1_bodies(bulk=5, hz_deviation=0.0, span_au=0.5)
        assert count == 5

    def test_beyond_hzco_plus3_dm(self):
        """hz_deviation > 3 → DM+2; dice=3,3=6, bulk=3 → 6-12+3+2=-1 → 0."""
        with patch("traveller_belt_physical.random.randint", return_value=3):
            count = _roll_size_1_bodies(bulk=3, hz_deviation=3.5, span_au=0.5)
        assert count == 0

    def test_beyond_hzco_plus3_dm_high_roll(self):
        """hz_deviation > 3 → DM+2; dice=6,6=12, bulk=5 → 12-12+5+2=7."""
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_1_bodies(bulk=5, hz_deviation=3.5, span_au=0.5)
        assert count == 7

    def test_narrow_span_dm_minus4(self):
        """span_au < 0.1 → DM-4; dice=6,6=12, bulk=8 → 12-12+8-4=4."""
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_1_bodies(bulk=8, hz_deviation=0.0, span_au=0.05)
        assert count == 4


# ---------------------------------------------------------------------------
# _roll_size_s_bodies
# ---------------------------------------------------------------------------

class TestRollSizeSBodies:
    def test_low_roll_gives_zero(self):
        """2D-9+DM × (bulk+1); dice=3,3=6, dm=0, bulk=3 → (6-9)×4=-12 → max(0,-12)=0."""
        with patch("traveller_belt_physical.random.randint", return_value=3):
            count = _roll_size_s_bodies(bulk=3, hz_deviation=0.0, span_au=0.5, is_outermost=False)
        assert count == 0

    def test_base_case(self):
        """dice=6,6=12, dm=0, bulk=2 → (12-9)×3=9."""
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_s_bodies(bulk=2, hz_deviation=0.0, span_au=0.5, is_outermost=False)
        assert count == 9

    def test_hzco_plus2_to_plus3_dm_plus1(self):
        """hz_deviation in (2,3] → DM+1; dice=6,6=12, bulk=2 → (12-9+1)×3=12."""
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_s_bodies(bulk=2, hz_deviation=2.5, span_au=0.5, is_outermost=False)
        assert count == 12

    def test_hzco_beyond_plus3_dm_plus3(self):
        """hz_deviation > 3 → DM+3; dice=6,6=12, bulk=2 → (12-9+3)×3=18."""
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_s_bodies(bulk=2, hz_deviation=3.5, span_au=0.5, is_outermost=False)
        assert count == 18

    def test_wide_span_dm_plus1(self):
        """span_au > 1.0 → DM+1; dice=6,6=12, bulk=2 → (12-9+1)×3=12."""
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_s_bodies(bulk=2, hz_deviation=0.0, span_au=1.5, is_outermost=False)
        assert count == 12

    def test_narrow_span_halves_count_odd(self):
        """span_au < 0.1 → halve count (round up); 5 → ceil(5/2)=3."""
        # dice=6,6=12, dm=0, bulk=1 → (12-9)×2=6; halved → 3
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_s_bodies(bulk=1, hz_deviation=0.0, span_au=0.05, is_outermost=False)
        assert count == 3

    def test_narrow_span_halves_count_even(self):
        """span_au < 0.1 → halve count (round up); 6 → ceil(6/2)=3."""
        # dice=6,6=12, dm=0, bulk=2 → (12-9)×3=9; halved → ceil(9/2)=5
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_s_bodies(bulk=2, hz_deviation=0.0, span_au=0.05, is_outermost=False)
        assert count == 5

    def test_optional_variance_not_outermost(self):
        """count > 50 but not outermost → no variance applied."""
        # dice=6,6=12, dm=3, bulk=5 → (12-9+3)×6=36; dm=+wide span+1 too:
        # dice=6, bulk=10 → (12-9+3)×11=66; not outermost → count=66 unchanged
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_s_bodies(bulk=10, hz_deviation=3.5, span_au=1.5, is_outermost=False)
        # (12-9+3+1)×11 = 7×11=77 > 50 but not outermost
        assert count == 77

    def test_optional_variance_outermost(self):
        """count > 50 and outermost → variance applied (just verify result is non-negative)."""
        with patch("traveller_belt_physical.random.randint", return_value=6):
            count = _roll_size_s_bodies(bulk=10, hz_deviation=3.5, span_au=1.5, is_outermost=True)
        assert count >= 0


# ---------------------------------------------------------------------------
# generate_belt_physical — integration
# ---------------------------------------------------------------------------

class TestGenerateBeltPhysical:
    def test_returns_belt_physical_instance(self):
        """generate_belt_physical returns a BeltPhysical instance."""
        with patch("traveller_belt_physical.random.randint", return_value=3):
            result = generate_belt_physical(
                orbit_au=2.8,
                hz_deviation=0.0,
                age_gyr=3.0,
                orbit_spread=20.0,
                next_is_gas_giant=False,
                is_outermost=False,
                is_exploited=False,
            )
        assert isinstance(result, BeltPhysical)

    def test_inner_au_less_than_outer_au(self):
        """inner_au < outer_au (span > 0 is guaranteed when orbit_spread > 0)."""
        with patch("traveller_belt_physical.random.randint", return_value=3):
            result = generate_belt_physical(
                orbit_au=5.2,
                hz_deviation=1.0,
                age_gyr=2.0,
                orbit_spread=15.0,
                next_is_gas_giant=True,
                is_outermost=False,
                is_exploited=False,
            )
        assert result.inner_au < result.outer_au

    def test_inner_au_minimum_zero(self):
        """inner_au cannot be negative even when orbit_au < half span."""
        with patch("traveller_belt_physical.random.randint", return_value=6):
            result = generate_belt_physical(
                orbit_au=0.2,
                hz_deviation=-2.0,
                age_gyr=1.0,
                orbit_spread=50.0,
                next_is_gas_giant=True,
                is_outermost=True,
                is_exploited=False,
            )
        assert result.inner_au >= 0.0

    def test_composition_sums_to_100(self):
        """Composition percentages always sum to 100."""
        import random as rng
        rng.seed(7)
        result = generate_belt_physical(
            orbit_au=2.8,
            hz_deviation=0.5,
            age_gyr=4.0,
            orbit_spread=10.0,
            next_is_gas_giant=False,
            is_outermost=False,
            is_exploited=False,
        )
        total = result.m_type_pct + result.s_type_pct + result.c_type_pct + result.other_pct
        assert total == 100

    def test_bulk_minimum_1(self):
        """Belt bulk is always at least 1."""
        with patch("traveller_belt_physical.random.randint", return_value=1):
            result = generate_belt_physical(
                orbit_au=40.0,
                hz_deviation=5.0,
                age_gyr=12.0,
                orbit_spread=40.0,
                next_is_gas_giant=False,
                is_outermost=True,
                is_exploited=False,
            )
        assert result.bulk >= 1

    def test_resource_rating_clamped(self):
        """Resource rating is always in [2, 12]."""
        import random as rng
        rng.seed(99)
        for _ in range(20):
            result = generate_belt_physical(
                orbit_au=5.2,
                hz_deviation=0.0,
                age_gyr=3.0,
                orbit_spread=20.0,
                next_is_gas_giant=False,
                is_outermost=False,
                is_exploited=True,
            )
            assert 2 <= result.resource_rating <= 12

    def test_to_dict_keys(self):
        """to_dict() returns all expected keys."""
        with patch("traveller_belt_physical.random.randint", return_value=3):
            result = generate_belt_physical(
                orbit_au=2.8,
                hz_deviation=0.0,
                age_gyr=3.0,
                orbit_spread=10.0,
                next_is_gas_giant=False,
                is_outermost=False,
                is_exploited=False,
            )
        d = result.to_dict()
        expected = {
            "inner_au", "outer_au",
            "m_type_pct", "s_type_pct", "c_type_pct", "other_pct",
            "bulk", "resource_rating",
            "size_1_bodies", "size_s_bodies",
        }
        assert set(d.keys()) == expected

    def test_size_1_bodies_non_negative(self):
        """Size 1 body count is always >= 0."""
        import random as rng
        rng.seed(13)
        for _ in range(20):
            result = generate_belt_physical(
                orbit_au=5.2,
                hz_deviation=0.0,
                age_gyr=3.0,
                orbit_spread=20.0,
                next_is_gas_giant=False,
                is_outermost=False,
                is_exploited=False,
            )
            assert result.size_1_bodies >= 0

    def test_size_s_bodies_non_negative(self):
        """Size S body count is always >= 0."""
        import random as rng
        rng.seed(17)
        for _ in range(20):
            result = generate_belt_physical(
                orbit_au=5.2,
                hz_deviation=0.0,
                age_gyr=3.0,
                orbit_spread=20.0,
                next_is_gas_giant=False,
                is_outermost=False,
                is_exploited=False,
            )
            assert result.size_s_bodies >= 0


# ---------------------------------------------------------------------------
# TestAttachDetailBeltMainworld
# ---------------------------------------------------------------------------

class TestAttachDetailBeltMainworld:
    """attach_detail() generates BeltPhysical for belt mainworlds."""

    def test_belt_mainworld_physical_set(self):
        """attach_detail() sets mainworld.physical to BeltPhysical for size-0 mainworld."""
        system = generate_full_system(seed=735659901)
        assert system.mainworld is not None
        assert system.mainworld.size == 0
        attach_detail(system)
        assert isinstance(system.mainworld.physical, BeltPhysical)

    def test_orbit_detail_physical_matches_mainworld_physical(self):
        """mainworld_orbit.detail.physical is the same object as mainworld.physical."""
        system = generate_full_system(seed=735659901)
        attach_detail(system)
        assert system.mainworld_orbit is not None
        assert system.mainworld_orbit.detail is not None
        assert system.mainworld_orbit.detail.physical is system.mainworld.physical

    def test_belt_physical_fields_valid(self):
        """BeltPhysical values are within expected ranges after attach_detail()."""
        system = generate_full_system(seed=735659901)
        attach_detail(system)
        bp = system.mainworld.physical
        assert isinstance(bp, BeltPhysical)
        assert bp.inner_au >= 0.0
        assert bp.outer_au >= bp.inner_au
        assert bp.m_type_pct + bp.s_type_pct + bp.c_type_pct + bp.other_pct == 100
        assert 1 <= bp.bulk
        assert 2 <= bp.resource_rating <= 12
        assert bp.size_1_bodies >= 0
        assert bp.size_s_bodies >= 0

    def test_non_belt_mainworld_physical_unchanged(self):
        """attach_detail() does not set mainworld.physical for non-belt mainworlds."""
        # Seed 42 generates a terrestrial mainworld (size > 0).
        import random
        for seed in range(100):
            system = generate_full_system(seed=seed)
            if system.mainworld and system.mainworld.size > 0:
                attach_detail(system)
                assert system.mainworld.physical is None, (
                    f"seed {seed}: expected None, got {system.mainworld.physical}"
                )
                return
        pytest.skip("No terrestrial mainworld found in seeds 0-99")
