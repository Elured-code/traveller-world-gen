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


class TestAegirCountsAndBases(unittest.TestCase):
    """Gas-giant count, belt count, world count, and bases must all survive the
    full detail pipeline.

    Regression guard for apply_mainworld_social() overwriting population_multiplier
    and bases, and for any future pipeline step inadvertently resetting PBG-derived
    counts or the TravellerMap world total.

    Aegir (Solomani Rim 1339):
      PBG 502  →  population_multiplier=5, belt_count=0, gas_giant_count=2
      bases=""  →  world.bases==[]
      worlds=5  →  system.system_orbits.total_worlds==5
    """

    def _run(self, seed: int = 42, social: bool = True):
        from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions
        sys = _fetch_aegir(seed=seed)
        rng = random.Random(seed)
        run_detail_pipeline(sys, rng, PipelineOptions(
            want_detail=True, want_social_detail=social,
        ))
        return sys

    # ------------------------------------------------------------------
    # PBG-derived counts
    # ------------------------------------------------------------------

    def test_gas_giant_count_after_pipeline(self):
        assert self._run().mainworld.gas_giant_count == 2, (
            "gas_giant_count (from PBG G=2) was overwritten by the pipeline"
        )

    def test_belt_count_after_pipeline(self):
        assert self._run().mainworld.belt_count == 0, (
            "belt_count (from PBG B=0) was overwritten by the pipeline"
        )

    def test_population_multiplier_after_pipeline(self):
        assert self._run().mainworld.population_multiplier == 5, (
            "population_multiplier (from PBG P=5) was overwritten by apply_mainworld_social()"
        )

    def test_total_worlds_after_pipeline(self):
        sys = self._run()
        assert sys.system_orbits.total_worlds == 5, (
            f"total_worlds (from MapWorldData.worlds=5) changed to "
            f"{sys.system_orbits.total_worlds} during the pipeline"
        )

    # ------------------------------------------------------------------
    # Bases
    # ------------------------------------------------------------------

    def test_bases_empty_after_pipeline(self):
        mw = self._run().mainworld
        assert mw.bases == [], (
            f"bases (canonical empty from TravellerMap) were overwritten "
            f"by apply_mainworld_social(): got {mw.bases!r}"
        )

    def test_bases_empty_with_social_detail(self):
        mw = self._run(social=True).mainworld
        assert mw.bases == [], (
            f"bases were overwritten during social detail pipeline: got {mw.bases!r}"
        )

    def test_bases_preserved_with_actual_bases(self):
        """World with real base codes must have those codes preserved."""
        from traveller_gen.traveller_map_fetch import MapWorldData, generate_system_from_map
        from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions
        data = MapWorldData(
            name="Mora",
            sector="Spinward Marches",
            hex_pos="3124",
            uwp="AA99AC7-F",
            bases="N W",
            remarks="Hi In Ht",
            zone="",
            pbg="612",
            stars_str="F0 V",
            worlds=9,
            cx="[A34C]",
            importance=4,
        )
        with mock.patch(
            "traveller_gen.traveller_map_fetch.fetch_world_data", return_value=data
        ):
            sys = generate_system_from_map("Mora", sector="Spinward Marches", seed=99)
        rng = random.Random(99)
        run_detail_pipeline(sys, rng, PipelineOptions(want_detail=True, want_social_detail=True))
        assert sys.mainworld.bases == ["N", "W"], (
            f"Canonical bases ['N', 'W'] were overwritten: got {sys.mainworld.bases!r}"
        )

    # ------------------------------------------------------------------
    # Determinism: counts must be stable across seeds
    # ------------------------------------------------------------------

    def test_counts_deterministic_across_seeds(self):
        """PBG-derived counts and bases must be identical for every seed."""
        from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions
        for seed in (1, 99, 12345, 999999):
            sys = _fetch_aegir(seed=seed)
            run_detail_pipeline(sys, random.Random(seed), PipelineOptions(want_detail=True))
            mw = sys.mainworld
            assert mw.gas_giant_count == 2, f"seed {seed}: gas_giant_count={mw.gas_giant_count}"
            assert mw.belt_count == 0,      f"seed {seed}: belt_count={mw.belt_count}"
            assert mw.population_multiplier == 5, (
                f"seed {seed}: population_multiplier={mw.population_multiplier}"
            )
            assert mw.bases == [],          f"seed {seed}: bases={mw.bases!r}"

    def test_total_worlds_not_changed_by_pipeline(self):
        """total_worlds must be the same before and after run_detail_pipeline()."""
        from traveller_gen.system_pipeline import run_detail_pipeline, PipelineOptions
        sys = _fetch_aegir(seed=42)
        before = sys.system_orbits.total_worlds
        run_detail_pipeline(sys, random.Random(42), PipelineOptions(want_detail=True))
        assert sys.system_orbits.total_worlds == before, (
            f"total_worlds changed from {before} to {sys.system_orbits.total_worlds} "
            f"during run_detail_pipeline()"
        )


if __name__ == "__main__":
    unittest.main()
