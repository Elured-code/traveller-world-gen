"""Tests for system_pipeline.run_detail_pipeline()."""
import random

import pytest

from system_pipeline import PipelineOptions, run_detail_pipeline
from traveller_system_gen import generate_full_system


def _system(seed=42, **kwargs):
    rng = random.Random(seed)
    return generate_full_system("TestWorld", seed=seed, rng=rng, **kwargs), rng


class TestPipelineOptionsDefaults:
    def test_defaults(self):
        opts = PipelineOptions()
        assert opts.want_detail is True
        assert opts.want_select_mw is False
        assert opts.runaway_greenhouse is False
        assert opts.independent_government is False
        assert opts.optional_biomass is False
        assert opts.optional_inhospitable is False
        assert opts.settlement_type == "standard"
        assert opts.want_social_detail is False


class TestSocialOnlyPath:
    """want_detail=False: only apply_mainworld_social runs."""

    def test_social_populated(self):
        system, rng = _system(seed=1001)
        run_detail_pipeline(system, rng, PipelineOptions(want_detail=False))
        mw = system.mainworld
        assert mw is not None
        assert mw.starport != "X" or mw.population == 0

    def test_no_physical_detail(self):
        system, rng = _system(seed=1002)
        run_detail_pipeline(system, rng, PipelineOptions(want_detail=False))
        mw = system.mainworld
        assert mw is None or mw.size_detail is None

    def test_no_secondary_detail(self):
        system, rng = _system(seed=1003)
        run_detail_pipeline(system, rng, PipelineOptions(want_detail=False))
        for orbit in system.system_orbits.orbits:
            assert orbit.detail is None


class TestFullDetailPath:
    """want_detail=True: physical + secondary profiles + social."""

    def test_mainworld_has_physical(self):
        system, rng = _system(seed=2001)
        run_detail_pipeline(system, rng, PipelineOptions(want_detail=True))
        mw = system.mainworld
        assert mw is not None
        assert mw.size_detail is not None

    def test_mainworld_has_social(self):
        system, rng = _system(seed=2002)
        run_detail_pipeline(system, rng, PipelineOptions(want_detail=True))
        mw = system.mainworld
        assert mw is not None
        assert mw.population is not None

    def test_secondary_detail_attached(self):
        system, rng = _system(seed=2003)
        run_detail_pipeline(system, rng, PipelineOptions(want_detail=True))
        has_detail = any(
            o.detail is not None for o in system.system_orbits.orbits
        )
        assert has_detail

    def test_body_names_assigned(self):
        system, rng = _system(seed=2004)
        run_detail_pipeline(system, rng, PipelineOptions(want_detail=True))
        named = [
            o for o in system.system_orbits.orbits if o.name
        ]
        assert len(named) > 0

    def test_advanced_temperature_computed(self):
        system, rng = _system(seed=2005)
        run_detail_pipeline(system, rng, PipelineOptions(want_detail=True))
        mw = system.mainworld
        assert mw is not None
        assert mw.size_detail is not None
        assert mw.size_detail.advanced_mean_temperature_k is not None


class TestSelectMainworld:
    """want_select_mw=True: selection runs without error."""

    def test_select_runs(self):
        system, rng = _system(seed=3001)
        run_detail_pipeline(system, rng, PipelineOptions(
            want_detail=True,
            want_select_mw=True,
        ))
        mw = system.mainworld
        assert mw is not None
        assert mw.population is not None

    def test_mainworld_has_physical_after_select(self):
        system, rng = _system(seed=3002)
        run_detail_pipeline(system, rng, PipelineOptions(
            want_detail=True,
            want_select_mw=True,
        ))
        assert system.mainworld is not None
        assert system.mainworld.size_detail is not None


class TestSocialDetail:
    """want_social_detail=True: population/gov/law/TL detail attached."""

    def test_population_detail_attached(self):
        system, rng = _system(seed=4001)
        run_detail_pipeline(system, rng, PipelineOptions(
            want_detail=True,
            want_social_detail=True,
        ))
        mw = system.mainworld
        if mw is None or mw.population == 0:
            pytest.skip("uninhabited mainworld — no social detail expected")
        assert mw.population_detail is not None or mw.tech_detail is not None


class TestRngContinuity:
    """Same seed + same options → same mainworld UWP (regression guard)."""

    def test_deterministic_social(self):
        system_a, rng_a = _system(seed=5001)
        run_detail_pipeline(system_a, rng_a, PipelineOptions(want_detail=False))

        system_b, rng_b = _system(seed=5001)
        run_detail_pipeline(system_b, rng_b, PipelineOptions(want_detail=False))

        assert system_a.mainworld is not None
        assert system_b.mainworld is not None
        assert system_a.mainworld.uwp() == system_b.mainworld.uwp()

    def test_deterministic_full(self):
        system_a, rng_a = _system(seed=5002)
        run_detail_pipeline(system_a, rng_a, PipelineOptions(want_detail=True))

        system_b, rng_b = _system(seed=5002)
        run_detail_pipeline(system_b, rng_b, PipelineOptions(want_detail=True))

        assert system_a.mainworld is not None
        assert system_b.mainworld is not None
        assert system_a.mainworld.uwp() == system_b.mainworld.uwp()

    def test_deterministic_with_select(self):
        system_a, rng_a = _system(seed=5003)
        run_detail_pipeline(system_a, rng_a, PipelineOptions(
            want_detail=True, want_select_mw=True,
        ))

        system_b, rng_b = _system(seed=5003)
        run_detail_pipeline(system_b, rng_b, PipelineOptions(
            want_detail=True, want_select_mw=True,
        ))

        assert system_a.mainworld is not None
        assert system_b.mainworld is not None
        assert system_a.mainworld.uwp() == system_b.mainworld.uwp()


class TestNoneMainworld:
    """Pipeline handles systems where mainworld is None gracefully."""

    def test_no_crash_no_mainworld(self):
        system, rng = _system(seed=6001)
        system.mainworld = None
        run_detail_pipeline(system, rng, PipelineOptions(want_detail=True))
