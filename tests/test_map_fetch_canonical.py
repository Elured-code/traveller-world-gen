"""Tests that canonical TravellerMap UWP data is preserved through the full pipeline.

Regression for the bug where run_detail_pipeline() called apply_mainworld_social(),
which rolled dice and overwrote canonical social digits (population, government,
law level, starport, tech level).

Aegir (Solomani Rim 1339) is used as the reference world:
  UWP A76A885-D  Ri Wa Ph Ht
  PBG 502  Stars M2 V  Zone (none)  Cx [6B3B]  Ix +3
"""
import random
import unittest
import unittest.mock as mock


def _make_aegir() -> "MapWorldData":  # type: ignore[name-defined]
    from traveller_gen.traveller_map_fetch import MapWorldData
    return MapWorldData(
        name="Aegir",
        sector="Solomani Rim",
        hex_pos="1339",
        uwp="A76A885-D",
        bases="",
        remarks="Ri Wa Ph Ht",
        zone="",
        pbg="502",
        stars_str="M2 V",
        worlds=5,
        cx="6B3B",
        importance=3,
    )


def _fetch_aegir(seed: int = 42, **kwargs):
    from traveller_gen.traveller_map_fetch import generate_system_from_map
    data = _make_aegir()
    with mock.patch("traveller_gen.traveller_map_fetch.fetch_world_data", return_value=data):
        return generate_system_from_map(
            name="Aegir", sector="Solomani Rim", seed=seed, **kwargs
        )


class TestAegirUWPPreservation(unittest.TestCase):
    """Canonical UWP digits must survive generate_system_from_map()."""

    def _system(self, seed: int = 42):
        return _fetch_aegir(seed=seed)

    def test_full_uwp_string(self):
        mw = self._system().mainworld
        assert mw.uwp() == "A76A885-D", f"Expected A76A885-D, got {mw.uwp()}"

    def test_starport_canonical(self):
        assert self._system().mainworld.starport == "A"

    def test_size_canonical(self):
        assert self._system().mainworld.size == 7

    def test_atmosphere_canonical(self):
        assert self._system().mainworld.atmosphere == 6

    def test_hydrographics_canonical(self):
        assert self._system().mainworld.hydrographics == 10

    def test_population_canonical(self):
        assert self._system().mainworld.population == 8

    def test_government_canonical(self):
        assert self._system().mainworld.government == 8

    def test_law_level_canonical(self):
        assert self._system().mainworld.law_level == 5

    def test_tech_level_canonical(self):
        assert self._system().mainworld.tech_level == 13

    def test_canonical_profile_on_orbit_slot(self):
        sys = self._system()
        mw_orbit = sys.mainworld_orbit
        assert mw_orbit is not None
        assert mw_orbit.canonical_profile == "A76A885-D"

    def test_trade_codes_from_remarks(self):
        mw = self._system().mainworld
        for code in ("Ri", "Wa", "Ht"):
            assert code in mw.trade_codes, f"Expected trade code {code!r} in {mw.trade_codes}"

    def test_travel_zone_green(self):
        assert self._system().mainworld.travel_zone == "Green"

    def test_population_multiplier_from_pbg(self):
        assert self._system().mainworld.population_multiplier == 5

    def test_gas_giant_count_from_pbg(self):
        assert self._system().mainworld.gas_giant_count == 2

    def test_belt_count_zero_from_pbg(self):
        assert self._system().mainworld.belt_count == 0

    def test_uwp_deterministic_across_seeds(self):
        for seed in (1, 99, 12345, 999999):
            mw = _fetch_aegir(seed=seed).mainworld
            assert mw.uwp() == "A76A885-D", (
                f"seed {seed}: expected A76A885-D, got {mw.uwp()}"
            )


class TestAegirThroughPipeline(unittest.TestCase):
    """Canonical UWP must survive run_detail_pipeline() (the gen-ui full-system path).

    This is the primary regression test: previously apply_mainworld_social() was called
    unconditionally and rolled fresh dice over the canonical social digits.
    """

    def _run_pipeline(self, seed: int = 42, **opts):
        from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions
        sys = _fetch_aegir(seed=seed)
        rng = random.Random(seed)
        run_detail_pipeline(sys, rng, PipelineOptions(want_detail=True, **opts))
        return sys

    def test_uwp_after_pipeline(self):
        sys2 = _fetch_aegir(seed=42)
        from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions
        run_detail_pipeline(sys2, random.Random(42), PipelineOptions(want_detail=True))
        assert sys2.mainworld.uwp() == "A76A885-D", (
            f"Pipeline overwrote canonical UWP: expected A76A885-D, got {sys2.mainworld.uwp()}"
        )

    def test_starport_after_pipeline(self):
        assert self._run_pipeline().mainworld.starport == "A"

    def test_population_after_pipeline(self):
        assert self._run_pipeline().mainworld.population == 8

    def test_government_after_pipeline(self):
        assert self._run_pipeline().mainworld.government == 8

    def test_law_level_after_pipeline(self):
        assert self._run_pipeline().mainworld.law_level == 5

    def test_tech_level_after_pipeline(self):
        assert self._run_pipeline().mainworld.tech_level == 13

    def test_uwp_deterministic_through_pipeline(self):
        for seed in (1, 99, 12345, 999999):
            sys = _fetch_aegir(seed=seed)
            from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions
            run_detail_pipeline(sys, random.Random(seed), PipelineOptions(want_detail=True))
            mw = sys.mainworld
            assert mw.uwp() == "A76A885-D", (
                f"seed {seed}: pipeline produced {mw.uwp()} instead of A76A885-D"
            )


class TestAegirWithSocialDetail(unittest.TestCase):
    """Canonical UWP must survive the full social detail pipeline."""

    def _run(self, seed: int = 42):
        from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions
        sys = _fetch_aegir(seed=seed)
        rng = random.Random(seed)
        run_detail_pipeline(sys, rng, PipelineOptions(
            want_detail=True, want_social_detail=True,
        ))
        return sys

    def test_uwp_after_social_detail(self):
        mw = self._run().mainworld
        assert mw.uwp() == "A76A885-D", (
            f"Social pipeline overwrote canonical UWP: got {mw.uwp()}"
        )

    def test_population_detail_attached(self):
        sys = self._run()
        assert sys.mainworld.population_detail is not None

    def test_starport_detail_attached(self):
        sys = self._run()
        assert sys.mainworld.starport_detail is not None

    def test_culture_from_cx(self):
        sys = self._run()
        mw = sys.mainworld
        assert mw.culture_detail is not None, "CultureDetail should be generated from Cx"

    def test_importance_detail_attached(self):
        sys = self._run()
        assert sys.mainworld.importance_detail is not None


if __name__ == "__main__":
    unittest.main()
