"""
tests/test_star_cluster.py
==========================
Tests for Star Cluster generation metadata (issue #182, WBH p.219).

Covers:
  - StarCluster dataclass fields and ranges
  - StarSystem.star_cluster populated for Star Cluster primaries
  - StarSystem.star_cluster absent for non-cluster primaries
  - to_dict() / from_dict() round-trip
  - generate_orbits() merged-star DMs
  - generate_full_system() wiring
  - Schema validation (via traveller_system_schema.json)
"""
import random
import pytest

from traveller_gen.traveller_stellar_gen import (
    StarCluster,
    StarSystem,
    generate_stellar_data,
    _roll_star_cluster_meta,
    _generate_cluster_age,
)
from traveller_gen.traveller_orbit_gen import generate_orbits
from traveller_gen.traveller_system_gen import generate_full_system

# Seed that produces a Star Cluster primary (confirmed in development)
_CLUSTER_SEED = 5936
# Seed that produces a Nebula primary (confirmed in development)
_NEBULA_SEED = 2689
# A plain normal-star seed
_NORMAL_SEED = 42


def _make_cluster_stellar(seed: int = _CLUSTER_SEED) -> StarSystem:
    """Generate stellar data with unusual_stars=True using the given seed."""
    rng = random.Random(seed)
    return generate_stellar_data(rng=rng, unusual_stars=True)


# ---------------------------------------------------------------------------
# StarCluster dataclass
# ---------------------------------------------------------------------------

class TestStarClusterDataclass:
    """StarCluster fields and constraints."""

    def test_fields_present(self):
        system = _make_cluster_stellar()
        sc = system.star_cluster
        assert sc is not None
        assert hasattr(sc, "age_gyr")
        assert hasattr(sc, "single_hex")
        assert hasattr(sc, "hex_diameter")
        assert hasattr(sc, "system_count")
        assert hasattr(sc, "merged_star")
        assert hasattr(sc, "jump_restriction")

    def test_age_positive(self):
        system = _make_cluster_stellar()
        sc = system.star_cluster
        assert sc.age_gyr > 0.0

    def test_age_maximum(self):
        """Cluster age formula caps naturally at 1D×1D×50Myr; with 1D max=6: 1.80 Gyr."""
        for seed in range(100):
            rng = random.Random(seed)
            age = _generate_cluster_age()
            assert age <= 1.80, f"seed {seed}: age {age} exceeds max 1.80 Gyr"

    def test_system_count_range(self):
        """system_count = 2D+5: range 7–17."""
        system = _make_cluster_stellar()
        sc = system.star_cluster
        assert 7 <= sc.system_count <= 17

    def test_single_hex_diameter_is_one(self):
        """When single_hex=True, hex_diameter must be 1."""
        sc = _make_cluster_stellar().star_cluster
        if sc.single_hex:
            assert sc.hex_diameter == 1

    def _make_primary_stub(self, ms_lifespan_gyr: float = 15.0):
        """Create a minimal Star stub for _roll_star_cluster_meta tests."""
        from traveller_gen.traveller_stellar_gen import Star
        return Star(
            designation="A", role="primary",
            spectral_type="G", subtype=5, lum_class="V",
            mass=0.9, temperature=5600, diameter=0.9, luminosity=0.8,
            age_gyr=0.5, ms_lifespan_gyr=ms_lifespan_gyr,
        )

    def test_multi_hex_diameter_valid_range(self):
        """hex_diameter is 1 for single-hex and 2–7 for multi-hex clusters."""
        import traveller_gen.traveller_stellar_gen as sg
        primary = self._make_primary_stub()
        for seed in range(200):
            old_rng = sg._rng
            sg._rng = random.Random(seed)
            sc = _roll_star_cluster_meta(0.5, primary)
            sg._rng = old_rng
            if sc.single_hex:
                assert sc.hex_diameter == 1
            else:
                assert 2 <= sc.hex_diameter <= 7

    def test_jump_restriction_multi_hex(self):
        """Multi-hex clusters have jump_restriction='Jump-2 minimum'."""
        import traveller_gen.traveller_stellar_gen as sg
        primary = self._make_primary_stub()
        for seed in range(200):
            old_rng = sg._rng
            sg._rng = random.Random(seed)
            sc = _roll_star_cluster_meta(0.5, primary)
            sg._rng = old_rng
            if not sc.single_hex:
                assert sc.jump_restriction == "Jump-2 minimum"
                return
        pytest.skip("No multi-hex result in 200 seeds")

    def test_jump_restriction_single_hex(self):
        """Single-hex clusters have no jump restriction."""
        sc = _make_cluster_stellar().star_cluster
        if sc.single_hex:
            assert sc.jump_restriction == ""


# ---------------------------------------------------------------------------
# StarSystem wiring
# ---------------------------------------------------------------------------

class TestStarSystemClusterWiring:
    """star_cluster is set only for Star Cluster primaries."""

    def test_star_cluster_set_for_cluster_primary(self):
        system = _make_cluster_stellar()
        assert system.star_cluster is not None
        assert isinstance(system.star_cluster, StarCluster)

    def test_star_cluster_none_for_nebula_primary(self):
        """Nebula primary does not produce a StarCluster."""
        rng = random.Random(_NEBULA_SEED)
        system = generate_stellar_data(rng=rng, unusual_stars=True)
        assert "Nebula" in system.primary.special_notes
        assert system.star_cluster is None

    def test_star_cluster_none_for_normal_star(self):
        """Normal star primary does not produce a StarCluster."""
        rng = random.Random(_NORMAL_SEED)
        system = generate_stellar_data(rng=rng)
        assert system.star_cluster is None

    def test_primary_notes_say_star_cluster(self):
        """The primary's special_notes confirm the environment."""
        system = _make_cluster_stellar()
        assert "Star Cluster" in system.primary.special_notes

    def test_primary_is_class_v(self):
        """Star Cluster primary is a young Class V star (issue #184 behaviour retained)."""
        system = _make_cluster_stellar()
        assert system.primary.lum_class == "V"


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip
# ---------------------------------------------------------------------------

class TestStarClusterRoundTrip:
    """StarCluster serialisation round-trip."""

    def test_to_dict_contains_star_cluster(self):
        system = _make_cluster_stellar()
        d = system.to_dict()
        assert "star_cluster" in d
        assert isinstance(d["star_cluster"], dict)

    def test_star_cluster_dict_fields(self):
        system = _make_cluster_stellar()
        sc_d = system.to_dict()["star_cluster"]
        assert set(sc_d.keys()) == {
            "age_gyr", "single_hex", "hex_diameter",
            "system_count", "merged_star", "jump_restriction",
            "member_stars",
        }

    def test_from_dict_reconstructs_star_cluster(self):
        system = _make_cluster_stellar()
        d = system.to_dict()
        restored = StarSystem.from_dict(d)
        assert restored.star_cluster is not None
        sc_orig = system.star_cluster
        sc_rest = restored.star_cluster
        assert sc_rest.age_gyr == sc_orig.age_gyr
        assert sc_rest.single_hex == sc_orig.single_hex
        assert sc_rest.hex_diameter == sc_orig.hex_diameter
        assert sc_rest.system_count == sc_orig.system_count
        assert sc_rest.merged_star == sc_orig.merged_star
        assert sc_rest.jump_restriction == sc_orig.jump_restriction
        assert sc_rest.member_stars == sc_orig.member_stars

    def test_no_star_cluster_key_for_normal_star(self):
        """Normal star systems do not emit 'star_cluster' in to_dict()."""
        rng = random.Random(_NORMAL_SEED)
        system = generate_stellar_data(rng=rng)
        d = system.to_dict()
        assert "star_cluster" not in d

    def test_star_cluster_from_dict_none_when_absent(self):
        """from_dict() on a dict without star_cluster sets star_cluster=None."""
        rng = random.Random(_NORMAL_SEED)
        system = generate_stellar_data(rng=rng)
        d = system.to_dict()
        restored = StarSystem.from_dict(d)
        assert restored.star_cluster is None


# ---------------------------------------------------------------------------
# generate_orbits() merged-star DMs
# ---------------------------------------------------------------------------

class TestMergedStarOrbitDMs:
    """generate_orbits() applies reduced world counts for merged-star clusters."""

    def _make_merged_cluster(self) -> StarCluster:
        """Build a StarCluster with merged_star=True directly."""
        return StarCluster(
            age_gyr=1.5,
            single_hex=True,
            hex_diameter=1,
            system_count=10,
            merged_star=True,
            jump_restriction="",
            member_stars=[],
        )

    def test_merged_star_flag_via_meta(self):
        """merged_star=True when ms_lifespan < age_gyr in _roll_star_cluster_meta."""
        import traveller_gen.traveller_stellar_gen as sg
        from traveller_gen.traveller_stellar_gen import Star
        # Primary with short lifespan (hot, massive star)
        primary = Star(
            designation="A", role="primary",
            spectral_type="B", subtype=5, lum_class="V",
            mass=5.0, temperature=15000, diameter=3.0, luminosity=500.0,
            age_gyr=1.5, ms_lifespan_gyr=0.3,
        )
        old_rng = sg._rng
        sg._rng = random.Random(0)
        sc = _roll_star_cluster_meta(1.5, primary)
        sg._rng = old_rng
        assert sc.merged_star is True
        assert primary.ms_lifespan_gyr < sc.age_gyr

    def test_not_merged_when_lifespan_exceeds_age(self):
        """merged_star=False when primary ms_lifespan > cluster age_gyr."""
        import traveller_gen.traveller_stellar_gen as sg
        from traveller_gen.traveller_stellar_gen import Star
        primary = Star(
            designation="A", role="primary",
            spectral_type="G", subtype=5, lum_class="V",
            mass=0.9, temperature=5600, diameter=0.9, luminosity=0.8,
            age_gyr=0.5, ms_lifespan_gyr=15.0,
        )
        old_rng = sg._rng
        sg._rng = random.Random(0)
        sc = _roll_star_cluster_meta(0.5, primary)
        sg._rng = old_rng
        assert sc.merged_star is False

    def test_merged_star_orbits_succeed(self):
        """generate_orbits() with a merged-star StarCluster returns SystemOrbits."""
        rng = random.Random(_CLUSTER_SEED)
        system = generate_stellar_data(rng=rng, unusual_stars=True)
        merged_sc = self._make_merged_cluster()
        rng2 = random.Random(99)
        orbits = generate_orbits(system, cluster=merged_sc, rng=rng2)
        assert orbits is not None

    def test_non_merged_cluster_orbits_succeed(self):
        """generate_orbits() for non-merged cluster completes without error."""
        rng = random.Random(_CLUSTER_SEED)
        system = generate_stellar_data(rng=rng, unusual_stars=True)
        assert system.star_cluster is not None and not system.star_cluster.merged_star
        rng2 = random.Random(_CLUSTER_SEED)
        _ = generate_stellar_data(rng=rng2, unusual_stars=True)
        orbits = generate_orbits(system, cluster=system.star_cluster, rng=rng2)
        assert orbits is not None


# ---------------------------------------------------------------------------
# generate_full_system() wiring
# ---------------------------------------------------------------------------

class TestGenerateFullSystemWiring:
    """generate_full_system() propagates StarCluster to TravellerSystem."""

    def test_full_system_cluster_seed(self):
        """generate_full_system() with cluster seed populates stellar_system.star_cluster."""
        system = generate_full_system(seed=_CLUSTER_SEED, unusual_stars=True)
        sc = system.stellar_system.star_cluster
        assert sc is not None
        assert isinstance(sc, StarCluster)

    def test_full_system_normal_seed(self):
        """generate_full_system() with normal seed has no star_cluster."""
        system = generate_full_system(seed=_NORMAL_SEED)
        assert system.stellar_system.star_cluster is None

    def test_full_system_to_dict_star_cluster(self):
        """TravellerSystem.to_dict() includes star_cluster for cluster systems."""
        system = generate_full_system(seed=_CLUSTER_SEED, unusual_stars=True)
        d = system.to_dict()
        assert "star_cluster" in d
        sc_d = d["star_cluster"]
        assert sc_d["age_gyr"] > 0.0
        assert isinstance(sc_d["merged_star"], bool)


# ---------------------------------------------------------------------------
# StarCluster member_stars
# ---------------------------------------------------------------------------

class TestMemberStars:
    """member_stars: spectral classes for the other systems in the cluster."""

    def test_member_stars_count(self):
        """member_stars has exactly system_count - 1 entries."""
        sc = _make_cluster_stellar().star_cluster
        assert len(sc.member_stars) == sc.system_count - 1

    def test_member_stars_format(self):
        """Each member star entry is a valid 'X# V' classification string."""
        import re
        sc = _make_cluster_stellar().star_cluster
        pattern = re.compile(r"^[OBAFGKM]\d V$")
        for entry in sc.member_stars:
            assert pattern.match(entry), f"Unexpected member_stars entry: {entry!r}"

    def test_member_stars_in_to_dict(self):
        """StarCluster.to_dict() includes 'member_stars' as a list."""
        sc = _make_cluster_stellar().star_cluster
        d = sc.to_dict()
        assert "member_stars" in d
        assert isinstance(d["member_stars"], list)
        assert len(d["member_stars"]) == sc.system_count - 1

    def test_member_stars_round_trip(self):
        """member_stars survives to_dict() / from_dict() round-trip."""
        import traveller_gen.traveller_stellar_gen as sg
        sc = _make_cluster_stellar().star_cluster
        d = sc.to_dict()
        restored = sg.StarCluster.from_dict(d)
        assert restored.member_stars == sc.member_stars

    def test_member_stars_deterministic(self):
        """Same seed always produces the same member_stars list."""
        sc1 = _make_cluster_stellar(_CLUSTER_SEED).star_cluster
        sc2 = _make_cluster_stellar(_CLUSTER_SEED).star_cluster
        assert sc1.member_stars == sc2.member_stars
