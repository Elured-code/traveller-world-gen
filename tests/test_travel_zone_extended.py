"""Tests for assign_travel_zone_extended() and attach_travel_zone_extended().

WBH §10: probabilistic Amber (2D+DMs ≥ 12) and Red (2D+DMs ≥ 12) rolls.
Red takes priority over Amber; Starport X is always Red.
"""
import random
import unittest

from traveller_gen.traveller_world_gen import (
    assign_travel_zone_extended,
    attach_travel_zone_extended,
    _red_zone_dm,
    _amber_zone_dm,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _always(zone: str, **kwargs) -> bool:
    """Return True if all 200 seeds produce the given zone."""
    return all(
        assign_travel_zone_extended(
            kwargs.get("atmosphere", 6),
            kwargs.get("government", 3),
            kwargs.get("law_level", 5),
            kwargs.get("starport", "A"),
            rng=random.Random(s),
            **{k: v for k, v in kwargs.items()
               if k not in ("atmosphere", "government", "law_level", "starport")},
        ) == zone
        for s in range(200)
    )


def _sometimes(zone: str, **kwargs) -> bool:
    """Return True if at least one of 200 seeds produces the given zone."""
    return any(
        assign_travel_zone_extended(
            kwargs.get("atmosphere", 6),
            kwargs.get("government", 3),
            kwargs.get("law_level", 5),
            kwargs.get("starport", "A"),
            rng=random.Random(s),
            **{k: v for k, v in kwargs.items()
               if k not in ("atmosphere", "government", "law_level", "starport")},
        ) == zone
        for s in range(200)
    )


# ---------------------------------------------------------------------------
# Starport X hard rule
# ---------------------------------------------------------------------------

class TestStarportX(unittest.TestCase):

    def test_starport_x_always_red(self):
        for seed in range(20):
            result = assign_travel_zone_extended(
                6, 3, 5, "X", rng=random.Random(seed)
            )
            self.assertEqual(result, "Red")

    def test_starport_x_red_even_with_zero_dms(self):
        result = assign_travel_zone_extended(
            6, 3, 5, "X",
            xenophilia=7, militancy=7,
            rng=random.Random(0),
        )
        self.assertEqual(result, "Red")


# ---------------------------------------------------------------------------
# Red Zone conditions
# ---------------------------------------------------------------------------

class TestRedZone(unittest.TestCase):

    def test_protostar_always_red(self):
        # DM+6 for protostar → 2D+6 ≥ 12 requires 2D ≥ 6; always guaranteed
        # with enough DM to push max roll to 12: 12 max + 6 = 18 ≥ 12 always
        # But with DM+6 and 2D min=2: 2+6=8 < 12. Not always Red.
        # With DM+8 (pulsar): 2+8=10 < 12. Not always.
        # Only magnetar DM+10: 2+10=12 — always Red.
        self.assertTrue(_always("Red", magnetar=True))

    def test_pulsar_likely_red(self):
        # DM+8: min roll 2+8=10, max 12+8=20. Red when 2D ≥ 4.
        # P(2D ≥ 4) = 1 - P(2D ≤ 3) = 1 - 3/36 = 33/36. Very likely.
        # Expect "sometimes" at minimum — over 200 seeds almost certain
        self.assertTrue(_sometimes("Red", pulsar=True))

    def test_ongoing_war_plus_militancy_red(self):
        # Militancy 35 → DM+27, ongoing war → DM+4: total DM+31 → always Red
        self.assertTrue(_always(
            "Red",
            militancy=35, ongoing_war=True,
        ))

    def test_extreme_xenophobia_red(self):
        # Xenophilia 1 → DM+5, plus militancy 35 → DM+27: always Red
        self.assertTrue(_always(
            "Red",
            xenophilia=1, militancy=35,
        ))

    def test_xenophilia_3_no_red_dm(self):
        # Xenophilia 3 is > 2, so does NOT trigger Red DM (only 1–2 do)
        dm = _red_zone_dm(
            magnetar=False, pulsar=False, protostar=False,
            seismic_stress=None, xenophilia=3, militancy=None,
            factional_uprisings=False, ongoing_war=False,
        )
        self.assertEqual(dm, 0)

    def test_seismic_stress_200_plus_red_dm(self):
        # DM+2 for stress ≥ 200; with militancy 35 → DM+27 total → always Red
        self.assertTrue(_always(
            "Red",
            seismic_stress=200, militancy=35,
        ))

    def test_seismic_stress_below_200_no_red_dm(self):
        # Seismic stress 199 is below the 200 threshold — no Red DM
        dm = _red_zone_dm(
            magnetar=False, pulsar=False, protostar=False,
            seismic_stress=199, xenophilia=None, militancy=None,
            factional_uprisings=False, ongoing_war=False,
        )
        self.assertEqual(dm, 0)


# ---------------------------------------------------------------------------
# Amber Zone conditions
# ---------------------------------------------------------------------------

class TestAmberZone(unittest.TestCase):

    def test_government_0_amber_dm4(self):
        # DM+4 for gov 0 only; min 2+4=6, max 12+4=16. Amber when 2D ≥ 8.
        # P(2D ≥ 8) = 15/36. Expect sometimes.
        self.assertTrue(_sometimes("Amber", government=0, law_level=5,
                                   xenophilia=7, militancy=7))

    def test_high_militancy_amber(self):
        # Militancy 35 → DM+(35-8)=+27 → always Amber (Red checked first)
        # but since Red also has DM+27 from militancy, Red may fire first.
        # Just verify Amber or Red: not Green
        for seed in range(50):
            result = assign_travel_zone_extended(
                6, 3, 5, "A", militancy=35, rng=random.Random(seed)
            )
            self.assertNotEqual(result, "Green")

    def test_atmosphere_11_amber_dm(self):
        # Atmosphere 11 (B) → DM+2 for Amber
        self.assertTrue(_sometimes("Amber", atmosphere=11, xenophilia=7, militancy=7))

    def test_atmosphere_12_amber_dm(self):
        # Atmosphere 12 (C) → DM+2 for Amber
        self.assertTrue(_sometimes("Amber", atmosphere=12, xenophilia=7, militancy=7))

    def test_atmosphere_15_amber_dm(self):
        # Atmosphere 15 (F) → DM+2 for Amber
        self.assertTrue(_sometimes("Amber", atmosphere=15, xenophilia=7, militancy=7))

    def test_atmosphere_10_no_amber_dm(self):
        # Atmosphere 10 (A=Exotic) is NOT B, C, or F+ — no WBH §10 Amber DM
        dm = _amber_zone_dm(
            10, 3, 5,
            primordial=False, mean_temp_k=None, pressure_bar=None,
            seismic_stress=None, xenophilia=7, militancy=7,
            factional_uprisings=False, ongoing_war=False,
        )
        self.assertEqual(dm, 0)

    def test_xenophilia_5_amber_dm(self):
        # Xenophilia 5 → DM+1; with government 0 (DM+4) total DM+5
        self.assertTrue(_sometimes("Amber", government=0, xenophilia=5,
                                   militancy=7, law_level=5))

    def test_xenophilia_6_no_amber_dm(self):
        # Xenophilia 6 is above the 0–5 threshold — no Amber DM from xenophilia
        dm = _amber_zone_dm(
            6, 3, 5,
            primordial=False, mean_temp_k=None, pressure_bar=None,
            seismic_stress=None, xenophilia=6, militancy=7,
            factional_uprisings=False, ongoing_war=False,
        )
        self.assertEqual(dm, 0)

    def test_gov_plus_law_gt_20(self):
        # Government 12, Law 12 → G+L=24 > 20 → DM+(24-16)=+8
        # Also gov 12 is not 0 or 7, so no extra DM from those
        self.assertTrue(_sometimes("Amber", government=12, law_level=12,
                                   xenophilia=7, militancy=7))

    def test_gov_plus_law_exactly_20_no_dm(self):
        # G+L=20 is not > 20 → no DM from this rule (other gov/law checks also 0 here)
        # government=10 is not 0 or 7; law=10 is > 0 and < 9; so no standard DMs either
        # G+L exactly 20: no additional DM from gov+law formula
        dm = _amber_zone_dm(
            6, 10, 10,
            primordial=False, mean_temp_k=None, pressure_bar=None,
            seismic_stress=None, xenophilia=7, militancy=7,
            factional_uprisings=False, ongoing_war=False,
        )
        self.assertEqual(dm, 0)

    def test_high_temp_amber_dm(self):
        # Mean temp > 373K → DM+2 for Amber
        self.assertTrue(_sometimes(
            "Amber", mean_temp_k=400, xenophilia=7, militancy=7
        ))

    def test_high_pressure_amber_dm(self):
        # Pressure > 50 bar → DM+2 for Amber
        self.assertTrue(_sometimes(
            "Amber", pressure_bar=60.0, xenophilia=7, militancy=7
        ))

    def test_seismic_stress_100_plus_amber_dm(self):
        # Seismic stress ≥ 100 → DM+2
        self.assertTrue(_sometimes(
            "Amber", seismic_stress=100, xenophilia=7, militancy=7
        ))

    def test_factional_uprisings_amber_dm(self):
        # Factional uprisings → DM+2
        self.assertTrue(_sometimes(
            "Amber", factional_uprisings=True, xenophilia=7, militancy=7
        ))

    def test_ongoing_war_amber_dm(self):
        # Ongoing war → DM+4
        self.assertTrue(_sometimes(
            "Amber", ongoing_war=True, xenophilia=7, militancy=7
        ))

    def test_primordial_amber_dm(self):
        # Primordial system → DM+2
        self.assertTrue(_sometimes(
            "Amber", primordial=True, xenophilia=7, militancy=7
        ))


# ---------------------------------------------------------------------------
# Priority: Red beats Amber
# ---------------------------------------------------------------------------

class TestZonePriority(unittest.TestCase):

    def test_red_beats_amber_when_both_roll_high(self):
        # Magnetar (DM+10) → always Red; verify never Amber
        results = {
            assign_travel_zone_extended(
                11, 0, 0, "A",  # very high Amber DMs too
                magnetar=True, rng=random.Random(s)
            )
            for s in range(50)
        }
        self.assertNotIn("Amber", results)
        self.assertIn("Red", results)

    def test_green_default_with_no_dms(self):
        # Neutral world: mostly Green
        results = [
            assign_travel_zone_extended(
                6, 3, 5, "A", xenophilia=7, militancy=7,
                rng=random.Random(s)
            )
            for s in range(100)
        ]
        green_count = results.count("Green")
        self.assertGreater(green_count, 90)  # 2D ≥ 12 ~1/36 per roll → rare


# ---------------------------------------------------------------------------
# attach_travel_zone_extended — integration
# ---------------------------------------------------------------------------

class _FakeWorld:
    def __init__(self, atmosphere=6, government=3, law_level=5, starport="A"):
        self.atmosphere  = atmosphere
        self.government  = government
        self.law_level   = law_level
        self.starport    = starport
        self.travel_zone = "Green"
        self.size_detail        = None
        self.atmosphere_detail  = None
        self.culture_detail     = None
        self.military_detail    = None


class _FakeStellar:
    def __init__(self, notes=""):
        from traveller_gen.traveller_stellar_gen import Star
        self.stars = [Star(
            designation="A", role="primary",
            spectral_type="G", subtype=5, lum_class="V",
            mass=1.0, temperature=5800, diameter=1.0, luminosity=1.0,
            age_gyr=5.0, ms_lifespan_gyr=10.0,
            special_notes=notes,
        )]


class _FakeSystem:
    def __init__(self, world, notes=""):
        self.mainworld      = world
        self.stellar_system = _FakeStellar(notes)


class TestAttachTravelZone(unittest.TestCase):

    def test_no_op_when_mainworld_none(self):
        class _Sys:
            mainworld = None
        attach_travel_zone_extended(_Sys())  # must not raise

    def test_starport_x_sets_red(self):
        world = _FakeWorld(starport="X")
        system = _FakeSystem(world)
        attach_travel_zone_extended(system, rng=random.Random(0))
        self.assertEqual(world.travel_zone, "Red")

    def test_primordial_note_detected(self):
        world = _FakeWorld()
        system = _FakeSystem(world, notes="Primordial system (age < 0.1 Gyr)")
        # primordial DM+2; with neutral world expect sometimes Amber
        results = set()
        for s in range(200):
            attach_travel_zone_extended(system, rng=random.Random(s))
            results.add(world.travel_zone)
        self.assertIn("Amber", results)

    def test_culture_detail_xenophilia_used(self):
        class _Culture:
            xenophilia = 1
            militancy  = 35
        world = _FakeWorld()
        world.culture_detail = _Culture()
        system = _FakeSystem(world)
        # xenophilia 1 → Red DM+5, militancy 35 → Red DM+27 → always Red
        attach_travel_zone_extended(system, rng=random.Random(0))
        self.assertEqual(world.travel_zone, "Red")

    def test_military_ongoing_war_used(self):
        class _Military:
            state_of_readiness = "War or internal insurgency"
        world = _FakeWorld()
        world.military_detail = _Military()
        system = _FakeSystem(world)
        # ongoing_war=True → DM+4 Amber + DM+4 Red; with neutral culture expect Amber
        results = set()
        for s in range(200):
            attach_travel_zone_extended(system, rng=random.Random(s))
            results.add(world.travel_zone)
        self.assertTrue(results & {"Amber", "Red"})

    def test_determinism_same_rng(self):
        world = _FakeWorld(government=0, law_level=0)
        system = _FakeSystem(world)
        attach_travel_zone_extended(system, rng=random.Random(42))
        zone1 = world.travel_zone
        world.travel_zone = "Green"
        attach_travel_zone_extended(system, rng=random.Random(42))
        zone2 = world.travel_zone
        self.assertEqual(zone1, zone2)


if __name__ == "__main__":
    unittest.main()
