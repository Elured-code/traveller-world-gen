"""
test_orbit_gen.py
=================
pytest unit tests for traveller_orbit_gen.py orbital inclination feature.

Licence
-------
MIT Licence — see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.
"""

from unittest.mock import call, patch

from traveller_gen.traveller_orbit_gen import (
    _ANOM_ECC_DM,
    OrbitSlot,
    roll_eccentricity,
    roll_inclination,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_orbit_slot(world_type: str = "terrestrial") -> OrbitSlot:
    """Construct a minimal OrbitSlot for testing."""
    return OrbitSlot(
        star_designation="A",
        orbit_number=3.0,
        orbit_au=1.0,
        slot_index=3,
        world_type=world_type,
        is_habitable_zone=True,
        hz_deviation=0.0,
        temperature_zone="temperate",
    )


# ---------------------------------------------------------------------------
# TestRollInclination
# ---------------------------------------------------------------------------

class TestRollInclination:
    """Tests for roll_inclination() (WBH p.28)."""

    def test_range_0_to_180(self):
        """200 random calls all return values in [0.0, 180.0]."""
        import random  # pylint: disable=import-outside-toplevel
        for seed in range(200):
            random.seed(seed)
            result = roll_inclination()
            assert 0.0 <= result <= 180.0, f"seed={seed} out of range: {result}"

    def test_band_very_low(self):
        """2D ≤ 6 → Very Low: 1D÷2. Mock: first=3 (≤6), inner=6 → 3.0°."""
        with patch("traveller_gen.traveller_orbit_gen.roll", side_effect=[3]) as _mock_roll, \
             patch("traveller_gen.traveller_orbit_gen.random.randint", return_value=6):
            result = roll_inclination()
        assert result == 3.0

    def test_band_low(self):
        """2D = 7 → Low: 1D. Mock: first=7, inner randint=4 → 4.0°."""
        roll_calls = iter([7])
        randint_calls = iter([4])
        with patch("traveller_gen.traveller_orbit_gen.roll", side_effect=roll_calls), \
             patch("traveller_gen.traveller_orbit_gen.random.randint", side_effect=randint_calls):
            result = roll_inclination()
        assert result == 4.0

    def test_band_moderate(self):
        """2D = 8 → Moderate: 2D. Mock: first=8, second roll(2)=5 → 5.0°."""
        with patch("traveller_gen.traveller_orbit_gen.roll", side_effect=[8, 5]):
            result = roll_inclination()
        assert result == 5.0

    def test_band_retrograde(self):
        """2D = 12 → Retrograde: 180 - sub_roll. Sub: 2D=7, randint=3 → 3.0° → 177.0°."""
        roll_calls = iter([12, 7])
        randint_calls = iter([3])
        with patch("traveller_gen.traveller_orbit_gen.roll", side_effect=roll_calls), \
             patch("traveller_gen.traveller_orbit_gen.random.randint", side_effect=randint_calls):
            result = roll_inclination()
        assert result == 177.0


# ---------------------------------------------------------------------------
# TestOrbitSlotInclination
# ---------------------------------------------------------------------------

class TestOrbitSlotInclination:
    """Tests for OrbitSlot.inclination field and to_dict() serialisation."""

    def test_default_zero(self):
        """OrbitSlot.inclination defaults to 0.0 without touching the flag."""
        slot = _make_orbit_slot()
        assert slot.inclination == 0.0

    def test_to_dict_includes_inclination_when_positive(self):
        """to_dict() emits 'inclination' key when inclination > 0."""
        slot = _make_orbit_slot()
        slot.inclination = 25.5
        d = slot.to_dict()
        assert "inclination" in d
        assert d["inclination"] == 25.5

    def test_to_dict_omits_inclination_when_zero(self):
        """to_dict() omits 'inclination' key when inclination == 0.0."""
        slot = _make_orbit_slot()
        assert slot.inclination == 0.0
        d = slot.to_dict()
        assert "inclination" not in d


# ---------------------------------------------------------------------------
# TestAnomalyEccentricityDMs
# ---------------------------------------------------------------------------

class TestAnomalyEccentricityDMs:
    """Regression for issue #64: anomalous orbit eccentricity DMs (WBH pp.49-50).

    Each test patches traveller_orbit_gen.roll and asserts that the first call
    (roll(2, dm)) uses the DM specified by WBH for that anomaly type.
    """

    def _assert_dm(self, anomaly_dm: int, expected_dm: int) -> None:
        """Call roll_eccentricity with anomaly_dm and check the first roll call."""
        with patch("traveller_gen.traveller_orbit_gen.roll",
                   side_effect=[5, 3]) as mock_roll:
            roll_eccentricity(3.0, 5.0, anomaly_dm=anomaly_dm)
        assert mock_roll.call_args_list[0] == call(2, expected_dm)

    def test_random_orbit_dm(self):
        """Random anomalous orbit applies DM+2 (WBH p.49)."""
        self._assert_dm(_ANOM_ECC_DM["random"], 2)

    def test_eccentric_orbit_dm(self):
        """Eccentric anomalous orbit applies DM+5 (WBH p.49)."""
        self._assert_dm(_ANOM_ECC_DM["eccentric"], 5)

    def test_inclined_orbit_dm(self):
        """Inclined anomalous orbit applies DM+2 (WBH p.50)."""
        self._assert_dm(_ANOM_ECC_DM["inclined"], 2)

    def test_retrograde_orbit_dm(self):
        """Retrograde anomalous orbit applies DM+2 (WBH p.50)."""
        self._assert_dm(_ANOM_ECC_DM["retrograde"], 2)

    def test_trojan_orbit_dm_zero(self):
        """Trojan anomalous orbit has no specified DM — defaults to 0."""
        self._assert_dm(_ANOM_ECC_DM.get("trojan_leading", 0), 0)

    def test_normal_orbit_dm_zero(self):
        """Normal (non-anomalous) orbit uses no anomaly DM."""
        self._assert_dm(0, 0)


# ---------------------------------------------------------------------------
# TestSlotIndexContinuity
# ---------------------------------------------------------------------------

class TestSlotIndexContinuity:
    """A star split into an inner + outer placement zone (by a companion's
    exclusion band) must get one continuous slot_index sequence, not a
    reset per zone — a reset previously produced duplicate (star, slot_index)
    keys, which attach_detail() uses to key its WorldDetail results."""

    def test_slot_index_continuous_across_inner_and_outer_zones(self):
        # pylint: disable=import-outside-toplevel
        from traveller_gen.traveller_system_gen import generate_full_system

        system = generate_full_system(seed=1559916071)
        a_slots = [o.slot_index for o in system.system_orbits.orbits
                   if o.star_designation == "A"]
        assert sorted(a_slots) == list(range(1, len(a_slots) + 1))
