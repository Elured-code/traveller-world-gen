"""Tests for Novelty TL nearby-worlds computation (issue #137, TravellerMap worlds).

Covers the pure jumpworlds-response filter (_novelty_tl_floor_from_jumpworlds),
the compute_novelty_tl wiring in generate_system_from_map(), and the resulting
tl_novelty value once attach_tech_detail() runs.
"""
import random
import unittest
import unittest.mock as mock

from traveller_gen.traveller_map_fetch import (
    MapWorldData,
    _novelty_tl_floor_from_jumpworlds,
    generate_system_from_map,
)


def _world(uwp: str, remarks: str = "") -> dict:
    """Build a jumpworlds-shaped world record dict (TravellerMap API shape)."""
    return {"UWP": uwp, "Remarks": remarks}


# ---------------------------------------------------------------------------
# Pure filter: _novelty_tl_floor_from_jumpworlds()
# ---------------------------------------------------------------------------

class TestNoveltyTLFloorFromJumpworlds(unittest.TestCase):
    """No network involved — feeds canned jumpworlds-shaped dicts."""

    def test_empty_list_returns_zero(self):
        assert _novelty_tl_floor_from_jumpworlds([]) == 0

    def test_plain_world_does_not_qualify(self):
        worlds = [_world("C776977-7", "Ni Va")]
        assert _novelty_tl_floor_from_jumpworlds(worlds) == 0

    def test_rich_world_qualifies(self):
        worlds = [_world("B584879-B", "Ri Pa Ph")]
        assert _novelty_tl_floor_from_jumpworlds(worlds) == 11  # 'B' eHex = 11

    def test_industrial_world_qualifies(self):
        worlds = [_world("A646930-D", "Hi In An Ht")]
        assert _novelty_tl_floor_from_jumpworlds(worlds) == 13  # 'D' eHex = 13

    def test_class_a_starport_qualifies_without_trade_codes(self):
        worlds = [_world("A200423-9", "Ni Va")]
        assert _novelty_tl_floor_from_jumpworlds(worlds) == 9

    def test_class_b_starport_without_rich_or_industrial_does_not_qualify(self):
        worlds = [_world("B200423-9", "Ni Va")]
        assert _novelty_tl_floor_from_jumpworlds(worlds) == 0

    def test_highest_among_multiple_qualifying_worlds_wins(self):
        worlds = [
            _world("A646930-9", "Hi In"),   # In, TL 9
            _world("B584879-D", "Ri Pa"),   # Ri, TL 13
            _world("C776977-7", "Ni Va"),   # doesn't qualify
        ]
        assert _novelty_tl_floor_from_jumpworlds(worlds) == 13

    def test_malformed_uwp_is_skipped(self):
        worlds = [{"UWP": "not-a-uwp", "Remarks": "Ri"}, _world("A788899-C", "Ri")]
        assert _novelty_tl_floor_from_jumpworlds(worlds) == 12  # 'C' eHex = 12

    def test_missing_uwp_key_is_skipped(self):
        worlds = [{"Remarks": "Ri In"}]
        assert _novelty_tl_floor_from_jumpworlds(worlds) == 0

    def test_case_insensitive_field_names(self):
        worlds = [{"Uwp": "A646930-9", "Remark": "In"}]
        assert _novelty_tl_floor_from_jumpworlds(worlds) == 9


# ---------------------------------------------------------------------------
# generate_system_from_map() wiring
# ---------------------------------------------------------------------------

def _make_regina() -> MapWorldData:
    return MapWorldData(
        name="Regina", sector="Spinward Marches", hex_pos="1910",
        uwp="A788899-C", bases="NS", remarks="", zone="", pbg="703",
        stars_str="F7 V", worlds=8,
    )


class TestComputeNoveltyTLWiring(unittest.TestCase):
    """generate_system_from_map(compute_novelty_tl=...) behaviour."""

    def _fetch(self, seed=42, **kwargs):
        data = _make_regina()
        with mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_world_data", return_value=data,
        ):
            return generate_system_from_map(
                name="Regina", sector="Spinward Marches", seed=seed, **kwargs
            )

    def test_default_does_not_call_fetch_jumpworlds(self):
        """compute_novelty_tl defaults to False — no extra API call."""
        with mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_jumpworlds",
        ) as mock_fetch:
            system = self._fetch()
        mock_fetch.assert_not_called()
        assert getattr(system, "novelty_tl_floor", None) is None

    def test_false_does_not_call_fetch_jumpworlds(self):
        with mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_jumpworlds",
        ) as mock_fetch:
            system = self._fetch(compute_novelty_tl=False)
        mock_fetch.assert_not_called()
        assert getattr(system, "novelty_tl_floor", None) is None

    def test_true_calls_fetch_jumpworlds_with_sector_and_hex(self):
        with mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_jumpworlds", return_value=[],
        ) as mock_fetch:
            self._fetch(compute_novelty_tl=True)
        mock_fetch.assert_called_once_with("Spinward Marches", "1910")

    def test_true_stamps_novelty_tl_floor_on_system(self):
        nearby = [_world("B584879-D", "Ri Pa")]  # 'D' eHex = 13
        with mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_jumpworlds", return_value=nearby,
        ):
            system = self._fetch(compute_novelty_tl=True)
        assert system.novelty_tl_floor == 13  # type: ignore[attr-defined]

    def test_no_qualifying_worlds_stamps_zero_not_none(self):
        nearby = [_world("C776977-7", "Ni Va")]
        with mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_jumpworlds", return_value=nearby,
        ):
            system = self._fetch(compute_novelty_tl=True)
        assert system.novelty_tl_floor == 0  # type: ignore[attr-defined]

    def test_jumpworlds_network_failure_degrades_gracefully(self):
        """A jumpworlds fetch failure must not fail the whole system fetch."""
        import urllib.error
        with mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_jumpworlds",
            side_effect=urllib.error.URLError("boom"),
        ):
            system = self._fetch(compute_novelty_tl=True)
        assert system.mainworld is not None
        assert system.mainworld.uwp() == "A788899-C"
        assert getattr(system, "novelty_tl_floor", None) is None


# ---------------------------------------------------------------------------
# End-to-end: attach_tech_detail() picks up the stamped floor
# ---------------------------------------------------------------------------

class TestNoveltyTLEndToEnd(unittest.TestCase):
    """system.novelty_tl_floor flows through to tech_detail.tl_novelty."""

    def test_mainworld_novelty_tl_raised_by_floor(self):
        from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions

        data = _make_regina()  # UWP tech_level 'C' == 12
        nearby = [_world("B584879-F", "Ri Pa")]  # 'F' eHex = 15
        with mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_world_data", return_value=data,
        ), mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_jumpworlds", return_value=nearby,
        ):
            system = generate_system_from_map(
                name="Regina", sector="Spinward Marches", seed=7,
                compute_novelty_tl=True,
            )
        rng = random.Random(7)
        run_detail_pipeline(
            system, rng,
            PipelineOptions(want_detail=True, want_social_detail=True),
        )
        assert system.mainworld.tech_detail is not None
        assert system.mainworld.tech_detail.tl_novelty == 15

    def test_without_compute_flag_novelty_tl_stays_placeholder(self):
        """Regression: not passing compute_novelty_tl leaves the old placeholder behaviour."""
        from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions

        data = _make_regina()
        with mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_world_data", return_value=data,
        ), mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_jumpworlds",
        ) as mock_fetch:
            system = generate_system_from_map(
                name="Regina", sector="Spinward Marches", seed=7,
            )
        rng = random.Random(7)
        run_detail_pipeline(
            system, rng,
            PipelineOptions(want_detail=True, want_social_detail=True),
        )
        mock_fetch.assert_not_called()
        assert system.mainworld.tech_detail.tl_novelty == (
            system.mainworld.tech_detail.tl_high_common
        )


if __name__ == "__main__":
    unittest.main()
