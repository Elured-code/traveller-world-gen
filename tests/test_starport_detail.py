"""Tests for traveller_world_starport_detail.py (Issue #101).

Covers: traffic importance, expected weekly lookup, highport/downport
capacities, shipyard (class A/B/C floors and None), annual output, starport
profile format, WTN A+ boost, and attach_starport_detail no-op guards.
"""
import random
import unittest

from traveller_gen.traveller_world_starport_detail import (
    StarportDetail,
    _expected_weekly,
    generate_starport_detail,
    attach_starport_detail,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detail(
    starport="A",
    has_highport=True,
    importance=3,
    wtn=5,
    ef=0,
    inf_f=3,
    population=7,
    tech_level=12,
    trade_codes=None,
    total_population=50_000_000,
    seed=42,
) -> StarportDetail:
    rng = random.Random(seed)
    return generate_starport_detail(
        starport=starport,
        has_highport=has_highport,
        importance=importance,
        wtn=wtn,
        efficiency_factor=ef,
        infrastructure_factor=inf_f,
        population=population,
        tech_level=tech_level,
        trade_codes=trade_codes or [],
        total_population=total_population,
        rng=rng,
    )


class TestExpectedWeekly(unittest.TestCase):

    def test_importance_6_plus(self):
        self.assertEqual(_expected_weekly(6), 2000)
        self.assertEqual(_expected_weekly(10), 2000)

    def test_importance_5(self):
        self.assertEqual(_expected_weekly(5), 1000)

    def test_importance_4(self):
        self.assertEqual(_expected_weekly(4), 150)

    def test_importance_3(self):
        self.assertEqual(_expected_weekly(3), 30)

    def test_importance_0(self):
        self.assertEqual(_expected_weekly(0), 5)

    def test_importance_negative_1(self):
        self.assertEqual(_expected_weekly(-1), 3)

    def test_importance_negative_3(self):
        self.assertEqual(_expected_weekly(-3), 1)

    def test_importance_negative_4_uncharted(self):
        self.assertEqual(_expected_weekly(-4), 0)
        self.assertEqual(_expected_weekly(-10), 0)


class TestTrafficImportance(unittest.TestCase):

    def test_no_wtn_boost(self):
        det = _make_detail(importance=3, wtn=5)
        self.assertEqual(det.traffic_importance, 3)

    def test_wtn_a_plus_boost(self):
        # WTN ≥ 10 (eHex A) adds +1 to traffic importance
        det = _make_detail(importance=3, wtn=10)
        self.assertEqual(det.traffic_importance, 4)

    def test_wtn_9_no_boost(self):
        det = _make_detail(importance=3, wtn=9)
        self.assertEqual(det.traffic_importance, 3)


class TestHighportCapacity(unittest.TestCase):

    def test_class_a_highport_present(self):
        det = _make_detail(starport="A", has_highport=True)
        self.assertIsNotNone(det.highport_capacity)
        # Must be at least the Class A base of 100,000 tonnes
        self.assertGreaterEqual(det.highport_capacity, 100_000)

    def test_class_b_highport_present(self):
        det = _make_detail(starport="B", has_highport=True)
        self.assertIsNotNone(det.highport_capacity)
        self.assertGreaterEqual(det.highport_capacity, 50_000)

    def test_class_c_no_highport(self):
        det = _make_detail(starport="C", has_highport=False)
        self.assertIsNone(det.highport_capacity)

    def test_class_d_highport_present(self):
        det = _make_detail(starport="D", has_highport=True, importance=1,
                           population=5, wtn=3)
        self.assertIsNotNone(det.highport_capacity)
        self.assertGreaterEqual(det.highport_capacity, 500)

    def test_class_e_no_highport(self):
        det = _make_detail(starport="E", has_highport=False, importance=0,
                           population=3, wtn=0, tech_level=5)
        self.assertIsNone(det.highport_capacity)

    def test_class_x_no_highport(self):
        det = _make_detail(starport="X", has_highport=False, importance=-1,
                           population=2, wtn=0, tech_level=3)
        self.assertIsNone(det.highport_capacity)


class TestDownportCapacity(unittest.TestCase):

    def test_class_a_with_highport_smaller_than_highport(self):
        det = _make_detail(starport="A", has_highport=True)
        # Downport is 1D × 10% of highport → always ≤ 60% of highport
        self.assertLessEqual(det.downport_capacity, det.highport_capacity)

    def test_class_a_without_highport_uses_formula(self):
        det = _make_detail(starport="A", has_highport=False)
        self.assertIsNone(det.highport_capacity)
        # Without highport the downport uses the full A formula (base 100,000)
        self.assertGreaterEqual(det.downport_capacity, 100_000)

    def test_class_e_downport_positive(self):
        det = _make_detail(starport="E", has_highport=False, importance=0,
                           population=3, wtn=0, tech_level=5)
        self.assertGreater(det.downport_capacity, 0)

    def test_class_x_downport_zero(self):
        det = _make_detail(starport="X", has_highport=False, importance=-1,
                           population=2, wtn=0, tech_level=3)
        self.assertEqual(det.downport_capacity, 0)

    def test_rounded_to_100(self):
        det = _make_detail(starport="B", has_highport=False)
        self.assertEqual(det.downport_capacity % 100, 0)


class TestDownportLargestPad(unittest.TestCase):

    def test_class_a(self):
        self.assertEqual(_make_detail(starport="A").downport_largest_pad, 2000)

    def test_class_b(self):
        self.assertEqual(_make_detail(starport="B").downport_largest_pad, 2000)

    def test_class_c(self):
        self.assertEqual(_make_detail(starport="C", has_highport=False).downport_largest_pad, 1000)

    def test_class_d(self):
        self.assertEqual(_make_detail(starport="D", has_highport=False,
                                      importance=0, population=4, wtn=2,
                                      tech_level=7).downport_largest_pad, 400)

    def test_class_e(self):
        self.assertEqual(_make_detail(starport="E", has_highport=False,
                                      importance=0, population=3, wtn=0,
                                      tech_level=5).downport_largest_pad, 400)

    def test_class_x(self):
        self.assertEqual(_make_detail(starport="X", has_highport=False,
                                      importance=-1, population=2, wtn=0,
                                      tech_level=3).downport_largest_pad, 0)


class TestShipyardCapacity(unittest.TestCase):

    def test_class_a_has_shipyard(self):
        det = _make_detail(starport="A", tech_level=12,
                           total_population=50_000_000)
        # TL 12 → DM+2, no trade DM; should produce a viable yard
        self.assertIsNotNone(det.shipyard_capacity)

    def test_class_b_has_shipyard(self):
        det = _make_detail(starport="B", tech_level=10,
                           total_population=50_000_000)
        self.assertIsNotNone(det.shipyard_capacity)

    def test_class_c_may_have_shipyard(self):
        # High-pop industrial world: should have a yard
        det = _make_detail(starport="C", tech_level=12,
                           trade_codes=["In"], total_population=500_000_000,
                           importance=3, seed=1)
        # Result depends on rolls; just verify it's either None or a positive int
        self.assertTrue(det.shipyard_capacity is None or det.shipyard_capacity > 0)

    def test_class_d_no_shipyard(self):
        det = _make_detail(starport="D", has_highport=False, importance=1,
                           population=5, wtn=3, tech_level=8)
        self.assertIsNone(det.shipyard_capacity)

    def test_class_e_no_shipyard(self):
        det = _make_detail(starport="E", has_highport=False, importance=0,
                           population=3, wtn=0, tech_level=5)
        self.assertIsNone(det.shipyard_capacity)

    def test_class_x_no_shipyard(self):
        det = _make_detail(starport="X", has_highport=False, importance=-1,
                           population=2, wtn=0, tech_level=3)
        self.assertIsNone(det.shipyard_capacity)

    def test_class_a_floor_minimum(self):
        # Force a low result by using very low pop and negative DMs
        det = _make_detail(starport="A", ef=-5, inf_f=0, tech_level=5,
                           trade_codes=["Ni"], total_population=10,
                           importance=1, population=1, seed=99)
        # Floor kicks in: minimum is 9,000 + 1D×500 = at least 9,500
        if det.shipyard_capacity is not None:
            self.assertGreaterEqual(det.shipyard_capacity, 9_500)

    def test_class_b_floor_minimum(self):
        det = _make_detail(starport="B", ef=-5, inf_f=0, tech_level=5,
                           trade_codes=["Ni"], total_population=10,
                           importance=1, population=1, seed=99)
        if det.shipyard_capacity is not None:
            self.assertGreaterEqual(det.shipyard_capacity, 4_200)

    def test_largest_bay_is_10_percent(self):
        det = _make_detail(starport="A")
        if det.shipyard_capacity is not None:
            self.assertEqual(det.shipyard_largest_bay,
                             max(100, (det.shipyard_capacity // 10 + 99) // 100 * 100))

    def test_no_shipyard_no_bay_no_output(self):
        det = _make_detail(starport="D", has_highport=False, importance=0,
                           population=4, wtn=2, tech_level=7)
        self.assertIsNone(det.shipyard_capacity)
        self.assertIsNone(det.shipyard_largest_bay)
        self.assertIsNone(det.shipyard_annual_output)


class TestAnnualOutput(unittest.TestCase):

    def test_importance_positive_divides_capacity(self):
        det = _make_detail(starport="A", importance=3,
                           total_population=50_000_000, seed=5)
        if det.shipyard_capacity is not None:
            # annual = capacity / importance (rounded to 100)
            self.assertGreater(det.shipyard_annual_output, 0)
            self.assertLessEqual(det.shipyard_annual_output, det.shipyard_capacity)

    def test_importance_zero_equals_capacity(self):
        # importance 0: output = capacity × (1 − 0) = capacity
        det = _make_detail(starport="A", importance=0,
                           total_population=50_000_000, seed=6)
        if det.shipyard_capacity is not None:
            self.assertEqual(det.shipyard_annual_output, det.shipyard_capacity)

    def test_importance_negative_exceeds_capacity(self):
        # importance -1: output = capacity × (1 − (−1)) = capacity × 2
        det = _make_detail(starport="A", importance=-1,
                           total_population=50_000_000, seed=7)
        if det.shipyard_capacity is not None:
            self.assertGreater(det.shipyard_annual_output, det.shipyard_capacity)

    def test_class_c_ten_times_capacity(self):
        det = _make_detail(starport="C", importance=1, tech_level=12,
                           trade_codes=["In"], total_population=500_000_000,
                           seed=2)
        if det.shipyard_capacity is not None:
            self.assertEqual(det.shipyard_annual_output,
                             det.shipyard_capacity * 10)


class TestStarportProfile(unittest.TestCase):

    def test_class_a_highport_positive_importance(self):
        det = _make_detail(starport="A", has_highport=True, importance=3)
        self.assertEqual(det.starport_profile, "A-HY:DY:+3")

    def test_class_b_no_highport(self):
        det = _make_detail(starport="B", has_highport=False, importance=2)
        self.assertEqual(det.starport_profile, "B-HN:DY:+2")

    def test_class_x_negative_importance(self):
        det = _make_detail(starport="X", has_highport=False, importance=-2,
                           population=2, wtn=0, tech_level=3)
        self.assertEqual(det.starport_profile, "X-HN:DN:-2")

    def test_importance_zero(self):
        det = _make_detail(starport="C", has_highport=False, importance=0,
                           population=5, wtn=0, tech_level=8)
        self.assertEqual(det.starport_profile, "C-HN:DY:0")


class TestRoundtripSerialization(unittest.TestCase):

    def test_to_dict_from_dict_roundtrip(self):
        original = _make_detail(starport="A", has_highport=True, seed=77)
        restored = StarportDetail.from_dict(original.to_dict())
        self.assertEqual(original.traffic_importance, restored.traffic_importance)
        self.assertEqual(original.expected_weekly, restored.expected_weekly)
        self.assertEqual(original.highport_capacity, restored.highport_capacity)
        self.assertEqual(original.downport_capacity, restored.downport_capacity)
        self.assertEqual(original.shipyard_capacity, restored.shipyard_capacity)
        self.assertEqual(original.starport_profile, restored.starport_profile)

    def test_no_shipyard_roundtrip(self):
        original = _make_detail(starport="D", has_highport=False, importance=1,
                                population=5, wtn=3, tech_level=8)
        restored = StarportDetail.from_dict(original.to_dict())
        self.assertIsNone(restored.shipyard_capacity)
        self.assertIsNone(restored.shipyard_largest_bay)
        self.assertIsNone(restored.shipyard_annual_output)


class TestSeedDeterminism(unittest.TestCase):

    def test_same_seed_same_result(self):
        d1 = _make_detail(seed=12345)
        d2 = _make_detail(seed=12345)
        self.assertEqual(d1.highport_capacity, d2.highport_capacity)
        self.assertEqual(d1.downport_capacity, d2.downport_capacity)
        self.assertEqual(d1.shipyard_capacity, d2.shipyard_capacity)

    def test_different_seed_may_differ(self):
        d1 = _make_detail(seed=1)
        d2 = _make_detail(seed=2)
        # Very unlikely all three would be identical
        all_same = (d1.highport_capacity == d2.highport_capacity
                    and d1.downport_capacity == d2.downport_capacity
                    and d1.shipyard_capacity == d2.shipyard_capacity)
        self.assertFalse(all_same)


class TestAttachNoOp(unittest.TestCase):

    def test_no_op_when_mainworld_is_none(self):
        class FakeSystem:
            mainworld = None
        attach_starport_detail(FakeSystem())  # must not raise

    def test_no_op_when_importance_detail_is_none(self):
        class FakeWorld:
            importance_detail = None
        class FakeSystem:
            mainworld = FakeWorld()
        attach_starport_detail(FakeSystem())  # must not raise


if __name__ == "__main__":
    unittest.main()
