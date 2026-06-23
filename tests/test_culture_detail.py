"""
pytest unit tests for traveller_world_culture_detail.py (issue #99, Sessions 129–130).

Covers:
  - None guard for uninhabited worlds
  - Diversity minimum value (>=1 for inhabited worlds)
  - Diversity DMs: government 7, government 13-15, PCR bands
  - Diversity label assignment
  - Xenophilia minimum value (>=1 for inhabited worlds)
  - Xenophilia DMs: starport codes, diversity feedback, population, gov/law
  - Xenophilia label assignment (Xenophobic / Moderate / Welcoming)
  - Uniqueness minimum value (>=1 for inhabited worlds)
  - Uniqueness DMs: starport codes (inverted from xenophilia), diversity, xenophilia
  - Uniqueness label assignment (Indistinct / Typical / Distinct / Exotic)
  - Symbology minimum value (>=1 for inhabited worlds)
  - Symbology DMs: government D/E, tech level bands, uniqueness feedback
  - Symbology label assignment (Mundane / Moderate / Prominent / Pervasive)
  - Cohesion minimum value (>=1 for inhabited worlds)
  - Cohesion DMs: government codes, law level bands, PCR bands, diversity feedback
  - Cohesion label assignment (Individualistic / Moderate / Communal / Collectivist)
  - Progressiveness minimum value (>=1 for inhabited worlds)
  - Progressiveness DMs: population, government, law, diversity, xenophilia, cohesion
  - Progressiveness label assignment (Moribund / Conservative / Moderate / Progressive / Innovative)
  - Expansionism minimum value (>=1 for inhabited worlds)
  - Expansionism DMs: government A/C+, diversity, xenophilia
  - Expansionism label assignment (Insular / Moderate / Expansive / Imperialist)
  - Militancy minimum value (>=1 for inhabited worlds)
  - Militancy DMs: government A+, law level bands, xenophilia, expansionism feedback
  - Militancy label assignment (Peaceful / Moderate / Aggressive / Militaristic)
  - Cultural profile is DXUS-CPEM format (9 chars: 8 eHex + 1 hyphen separator)
  - to_dict() / from_dict() round-trip (all fields)
  - attach_culture_detail() mainworld and secondary world wiring
  - Hypothesis property-based bounds invariants
  - _parse_cx_string(): parenthesised/bare, upper/lower eHex, short strings
  - generate_culture_detail_from_cx(): None guard, Diversity/Xenophilia/Symbology
    clamping, Strangeness→Uniqueness scaling, rolled-trait minimums, profile format
  - attach_culture_detail() Cx routing: cx present → from_cx path;
    cx absent → standard generate_culture_detail path
"""

# pylint: disable=import-error
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from traveller_gen.traveller_system_gen import generate_full_system
from traveller_gen.traveller_world_detail import attach_detail
from traveller_gen.traveller_world_culture_detail import (
    CultureDetail,
    _diversity_label,
    _xenophilia_label,
    _uniqueness_label,
    _symbology_label,
    _cohesion_label,
    _progressiveness_label,
    _expansionism_label,
    _militancy_label,
    _parse_cx_string,
    _compute_cx,
    generate_culture_detail,
    generate_culture_detail_from_cx,
    attach_culture_detail,
)

_EHEX = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gen(
        population=7, government=6, law_level=5, pcr=4,
        starport="C", tech_level=8, rng=None,
) -> CultureDetail:
    """Convenience wrapper with sensible defaults."""
    result = generate_culture_detail(
        population=population, government=government,
        law_level=law_level, pcr=pcr, starport=starport,
        tech_level=tech_level, rng=rng,
    )
    assert result is not None
    return result


# ---------------------------------------------------------------------------
# None guard
# ---------------------------------------------------------------------------

class TestNoneGuard:
    def test_uninhabited_returns_none(self):
        assert generate_culture_detail(population=0, government=6, law_level=5) is None

    def test_inhabited_returns_culture_detail(self):
        assert _gen() is not None


# ---------------------------------------------------------------------------
# Diversity bounds
# ---------------------------------------------------------------------------

class TestDiversityBounds:
    def test_diversity_minimum_one(self):
        """Even extreme negative DMs cannot produce diversity < 1."""
        # Pop 1-5 (-2), gov 13 (-4), law 10+ (-1), pcr 7-9 (-2) → DM -9
        cd = _gen(population=3, government=13, law_level=11, pcr=8)
        assert cd.diversity >= 1

    def test_diversity_positive(self):
        cd = _gen()
        assert cd.diversity > 0

    def test_balkanised_government_increases_diversity(self):
        """Gov 7 (balkanised) applies DM+4 — diversity should tend high."""
        rng = random.Random(42)
        results = [
            generate_culture_detail(population=7, government=7, law_level=5,
                                    pcr=4, rng=rng).diversity
            for _ in range(30)
        ]
        assert sum(results) / len(results) > 8.0

    def test_totalitarian_government_decreases_diversity(self):
        """Gov 13-15 applies DM-4 — diversity should tend low."""
        rng = random.Random(42)
        results = [
            generate_culture_detail(population=7, government=14, law_level=5,
                                    pcr=4, rng=rng).diversity
            for _ in range(30)
        ]
        assert sum(results) / len(results) < 8.0


# ---------------------------------------------------------------------------
# Diversity DM effects
# ---------------------------------------------------------------------------

class TestDMEffects:
    def test_small_pop_dm_minus_two(self):
        """Population 1-5 applies DM-2 relative to population 6-8."""
        rng_low  = random.Random(0)
        rng_high = random.Random(0)
        low_vals  = [_gen(population=3, rng=rng_low).diversity  for _ in range(50)]
        high_vals = [_gen(population=7, rng=rng_high).diversity for _ in range(50)]
        assert sum(low_vals) < sum(high_vals)

    def test_large_pop_dm_plus_two(self):
        """Population 9+ applies DM+2 relative to population 6-8."""
        rng_high = random.Random(0)
        rng_base = random.Random(0)
        high_vals = [_gen(population=9, rng=rng_high).diversity for _ in range(50)]
        base_vals = [_gen(population=7, rng=rng_base).diversity for _ in range(50)]
        assert sum(high_vals) > sum(base_vals)

    def test_pcr_low_dm_plus_one(self):
        """PCR 0-3 applies DM+1."""
        rng_low  = random.Random(0)
        rng_mid  = random.Random(0)
        low_vals = [_gen(pcr=2, rng=rng_low).diversity for _ in range(50)]
        mid_vals = [_gen(pcr=5, rng=rng_mid).diversity for _ in range(50)]
        assert sum(low_vals) > sum(mid_vals)

    def test_pcr_high_dm_minus_two(self):
        """PCR 7-9 applies DM-2."""
        rng_high = random.Random(0)
        rng_mid  = random.Random(0)
        high_vals = [_gen(pcr=8, rng=rng_high).diversity for _ in range(50)]
        mid_vals  = [_gen(pcr=5, rng=rng_mid).diversity  for _ in range(50)]
        assert sum(high_vals) < sum(mid_vals)


# ---------------------------------------------------------------------------
# Diversity labels
# ---------------------------------------------------------------------------

class TestLabels:
    @pytest.mark.parametrize("value,expected", [
        (1,  "Monolithic"),
        (2,  "Monolithic"),
        (3,  "Monolithic"),
        (4,  "Homogeneous"),
        (5,  "Homogeneous"),
        (6,  "Diverse"),
        (7,  "Diverse"),
        (8,  "Diverse"),
        (9,  "Multicultural"),
        (10, "Multicultural"),
        (11, "Multicultural"),
        (12, "Balkanised"),
        (20, "Balkanised"),
    ])
    def test_diversity_label_for_value(self, value, expected):
        assert _diversity_label(value) == expected


# ---------------------------------------------------------------------------
# Xenophilia bounds
# ---------------------------------------------------------------------------

class TestXenophiliaBounds:
    def test_xenophilia_minimum_one(self):
        """Even extreme negative DMs cannot produce xenophilia < 1."""
        # Starport X (-4), monolithic diversity (-2), pop 1-5 (-1),
        # gov D/E (-2), law 10+ (-2) → worst-case DM around -11
        rng = random.Random(1)
        for _ in range(50):
            cd = generate_culture_detail(
                population=2, government=13, law_level=11,
                starport="X", rng=rng,
            )
            assert cd is not None
            assert cd.xenophilia >= 1

    def test_xenophilia_positive(self):
        cd = _gen()
        assert cd.xenophilia > 0


# ---------------------------------------------------------------------------
# Xenophilia DM effects
# ---------------------------------------------------------------------------

class TestXenophiliaDMEffects:
    def test_starport_a_increases_xenophilia(self):
        """Starport A applies DM+2 vs starport C."""
        rng_a = random.Random(0)
        rng_c = random.Random(0)
        a_vals = [_gen(starport="A", rng=rng_a).xenophilia for _ in range(50)]
        c_vals = [_gen(starport="C", rng=rng_c).xenophilia for _ in range(50)]
        assert sum(a_vals) > sum(c_vals)

    def test_starport_x_decreases_xenophilia(self):
        """Starport X applies DM-4 vs starport C."""
        rng_x = random.Random(0)
        rng_c = random.Random(0)
        x_vals = [_gen(starport="X", rng=rng_x).xenophilia for _ in range(50)]
        c_vals = [_gen(starport="C", rng=rng_c).xenophilia for _ in range(50)]
        assert sum(x_vals) < sum(c_vals)

    def test_starport_b_increases_xenophilia(self):
        """Starport B applies DM+1 vs starport C."""
        rng_b = random.Random(0)
        rng_c = random.Random(0)
        b_vals = [_gen(starport="B", rng=rng_b).xenophilia for _ in range(50)]
        c_vals = [_gen(starport="C", rng=rng_c).xenophilia for _ in range(50)]
        assert sum(b_vals) > sum(c_vals)

    def test_empty_starport_no_dm(self):
        """Empty starport string (secondary worlds) applies no DM."""
        rng_e  = random.Random(0)
        rng_c  = random.Random(0)
        e_vals = [_gen(starport="",  rng=rng_e).xenophilia for _ in range(50)]
        c_vals = [_gen(starport="C", rng=rng_c).xenophilia for _ in range(50)]
        # C gives no DM either — sums should be statistically indistinguishable
        assert abs(sum(e_vals) - sum(c_vals)) < 30

    def test_high_law_decreases_xenophilia(self):
        """Law Level A+ applies DM-2."""
        rng_hi  = random.Random(0)
        rng_lo  = random.Random(0)
        hi_vals = [_gen(law_level=11, rng=rng_hi).xenophilia for _ in range(50)]
        lo_vals = [_gen(law_level=3,  rng=rng_lo).xenophilia for _ in range(50)]
        assert sum(hi_vals) < sum(lo_vals)

    def test_gov_d_or_e_decreases_xenophilia(self):
        """Government D (13) or E (14) applies DM-2."""
        rng_hi  = random.Random(0)
        rng_lo  = random.Random(0)
        hi_vals = [_gen(government=13, rng=rng_hi).xenophilia for _ in range(50)]
        lo_vals = [_gen(government=6,  rng=rng_lo).xenophilia for _ in range(50)]
        assert sum(hi_vals) < sum(lo_vals)


# ---------------------------------------------------------------------------
# Xenophilia labels
# ---------------------------------------------------------------------------

class TestXenophiliaLabels:
    @pytest.mark.parametrize("value,expected", [
        (1, "Xenophobic"),
        (2, "Xenophobic"),
        (3, "Xenophobic"),
        (4, "Moderate"),
        (5, "Moderate"),
        (8, "Moderate"),
        (9, "Welcoming"),
        (10, "Welcoming"),
        (20, "Welcoming"),
    ])
    def test_xenophilia_label_for_value(self, value, expected):
        assert _xenophilia_label(value) == expected

    def test_xenophilia_label_on_generated(self):
        """Label on CultureDetail matches the raw value."""
        cd = _gen()
        assert cd.xenophilia_label == _xenophilia_label(cd.xenophilia)


# ---------------------------------------------------------------------------
# Uniqueness bounds
# ---------------------------------------------------------------------------

class TestUniquenessBounds:
    def test_uniqueness_minimum_one(self):
        """Even extreme negative DMs cannot produce uniqueness < 1."""
        # Starport A (-2), xenophilia C+ (-2), welcoming+diverse world
        rng = random.Random(1)
        for _ in range(50):
            cd = generate_culture_detail(
                population=7, government=0, law_level=0,
                starport="A", rng=rng,
            )
            assert cd is not None
            assert cd.uniqueness >= 1

    def test_uniqueness_positive(self):
        cd = _gen()
        assert cd.uniqueness > 0


# ---------------------------------------------------------------------------
# Uniqueness DM effects
# ---------------------------------------------------------------------------

class TestUniquenessDMEffects:
    def test_starport_x_increases_uniqueness(self):
        """Starport X applies DM+4 vs starport C — isolated = more unique."""
        rng_x = random.Random(0)
        rng_c = random.Random(0)
        x_vals = [_gen(starport="X", rng=rng_x).uniqueness for _ in range(50)]
        c_vals = [_gen(starport="C", rng=rng_c).uniqueness for _ in range(50)]
        assert sum(x_vals) > sum(c_vals)

    def test_starport_a_decreases_uniqueness(self):
        """Starport A applies DM-2 vs starport C — cosmopolitan = less unique."""
        rng_a = random.Random(0)
        rng_c = random.Random(0)
        a_vals = [_gen(starport="A", rng=rng_a).uniqueness for _ in range(50)]
        c_vals = [_gen(starport="C", rng=rng_c).uniqueness for _ in range(50)]
        assert sum(a_vals) < sum(c_vals)

    def test_starport_e_increases_uniqueness(self):
        """Starport E applies DM+2 vs starport C."""
        rng_e = random.Random(0)
        rng_c = random.Random(0)
        e_vals = [_gen(starport="E", rng=rng_e).uniqueness for _ in range(50)]
        c_vals = [_gen(starport="C", rng=rng_c).uniqueness for _ in range(50)]
        assert sum(e_vals) > sum(c_vals)

    def test_empty_starport_no_dm(self):
        """Empty starport string applies no uniqueness DM."""
        rng_e = random.Random(0)
        rng_c = random.Random(0)
        e_vals = [_gen(starport="",  rng=rng_e).uniqueness for _ in range(50)]
        c_vals = [_gen(starport="C", rng=rng_c).uniqueness for _ in range(50)]
        assert abs(sum(e_vals) - sum(c_vals)) < 30


# ---------------------------------------------------------------------------
# Uniqueness labels
# ---------------------------------------------------------------------------

class TestUniquenessLabels:
    @pytest.mark.parametrize("value,expected", [
        (1,  "Indistinct"),
        (2,  "Indistinct"),
        (3,  "Indistinct"),
        (4,  "Typical"),
        (5,  "Typical"),
        (8,  "Typical"),
        (9,  "Distinct"),
        (10, "Distinct"),
        (11, "Distinct"),
        (12, "Exotic"),
        (20, "Exotic"),
    ])
    def test_uniqueness_label_for_value(self, value, expected):
        assert _uniqueness_label(value) == expected

    def test_uniqueness_label_on_generated(self):
        """Label on CultureDetail matches the raw value."""
        cd = _gen()
        assert cd.uniqueness_label == _uniqueness_label(cd.uniqueness)


# ---------------------------------------------------------------------------
# Symbology bounds
# ---------------------------------------------------------------------------

class TestSymbologyBounds:
    def test_symbology_minimum_one(self):
        """Even extreme negative DMs cannot produce symbology < 1."""
        # TL 0-1 (-3) is the worst-case — should still be >= 1
        rng = random.Random(1)
        for _ in range(50):
            cd = generate_culture_detail(
                population=7, government=6, law_level=5,
                tech_level=0, rng=rng,
            )
            assert cd is not None
            assert cd.symbology >= 1

    def test_symbology_positive(self):
        cd = _gen()
        assert cd.symbology > 0


# ---------------------------------------------------------------------------
# Symbology DM effects
# ---------------------------------------------------------------------------

class TestSymbologyDMEffects:
    def test_high_tl_increases_symbology(self):
        """TL 12+ applies DM+4 vs TL 8 (no DM)."""
        rng_hi = random.Random(0)
        rng_lo = random.Random(0)
        hi_vals = [_gen(tech_level=12, rng=rng_hi).symbology for _ in range(50)]
        lo_vals = [_gen(tech_level=8,  rng=rng_lo).symbology for _ in range(50)]
        assert sum(hi_vals) > sum(lo_vals)

    def test_low_tl_decreases_symbology(self):
        """TL 0-1 applies DM-3 vs TL 8 (no DM)."""
        rng_lo = random.Random(0)
        rng_hi = random.Random(0)
        lo_vals = [_gen(tech_level=0, rng=rng_lo).symbology for _ in range(50)]
        hi_vals = [_gen(tech_level=8, rng=rng_hi).symbology for _ in range(50)]
        assert sum(lo_vals) < sum(hi_vals)

    def test_mid_tl_no_dm(self):
        """TL 4-8 applies no DM — sums statistically similar."""
        rng_4 = random.Random(0)
        rng_8 = random.Random(0)
        vals_4 = [_gen(tech_level=4, rng=rng_4).symbology for _ in range(50)]
        vals_8 = [_gen(tech_level=8, rng=rng_8).symbology for _ in range(50)]
        assert abs(sum(vals_4) - sum(vals_8)) < 30

    def test_gov_d_increases_symbology(self):
        """Government D (13) applies DM+2."""
        rng_d = random.Random(0)
        rng_n = random.Random(0)
        d_vals = [_gen(government=13, rng=rng_d).symbology for _ in range(50)]
        n_vals = [_gen(government=6,  rng=rng_n).symbology for _ in range(50)]
        assert sum(d_vals) > sum(n_vals)


# ---------------------------------------------------------------------------
# Symbology labels
# ---------------------------------------------------------------------------

class TestSymbologyLabels:
    @pytest.mark.parametrize("value,expected", [
        (1,  "Mundane"),
        (2,  "Mundane"),
        (3,  "Mundane"),
        (4,  "Moderate"),
        (5,  "Moderate"),
        (8,  "Moderate"),
        (9,  "Prominent"),
        (10, "Prominent"),
        (11, "Prominent"),
        (12, "Pervasive"),
        (20, "Pervasive"),
    ])
    def test_symbology_label_for_value(self, value, expected):
        assert _symbology_label(value) == expected

    def test_symbology_label_on_generated(self):
        """Label on CultureDetail matches the raw value."""
        cd = _gen()
        assert cd.symbology_label == _symbology_label(cd.symbology)


# ---------------------------------------------------------------------------
# Cohesion bounds
# ---------------------------------------------------------------------------

class TestCohesionBounds:
    def test_cohesion_minimum_one(self):
        """Even extreme negative DMs cannot produce cohesion < 1."""
        # Law Level 0-2 (-2), PCR 0-3 (-2), Diversity C+ (-4) → DM -8
        rng = random.Random(1)
        for _ in range(50):
            cd = generate_culture_detail(
                population=9, government=0, law_level=0,
                pcr=0, rng=rng,
            )
            assert cd is not None
            assert cd.cohesion >= 1

    def test_cohesion_positive(self):
        cd = _gen()
        assert cd.cohesion > 0


# ---------------------------------------------------------------------------
# Cohesion DM effects
# ---------------------------------------------------------------------------

class TestCohesionDMEffects:
    def test_gov_3_increases_cohesion(self):
        """Government 3 applies DM+2."""
        rng_3 = random.Random(0)
        rng_n = random.Random(0)
        g3_vals = [_gen(government=3,  rng=rng_3).cohesion for _ in range(50)]
        gn_vals = [_gen(government=10, rng=rng_n).cohesion for _ in range(50)]
        assert sum(g3_vals) > sum(gn_vals)

    def test_gov_c_increases_cohesion(self):
        """Government C (12) applies DM+2."""
        rng_c = random.Random(0)
        rng_n = random.Random(0)
        gc_vals = [_gen(government=12, rng=rng_c).cohesion for _ in range(50)]
        gn_vals = [_gen(government=10, rng=rng_n).cohesion for _ in range(50)]
        assert sum(gc_vals) > sum(gn_vals)

    def test_low_law_decreases_cohesion(self):
        """Law Level 0-2 applies DM-2."""
        rng_lo = random.Random(0)
        rng_hi = random.Random(0)
        lo_vals = [_gen(law_level=1, rng=rng_lo).cohesion for _ in range(50)]
        hi_vals = [_gen(law_level=5, rng=rng_hi).cohesion for _ in range(50)]
        assert sum(lo_vals) < sum(hi_vals)

    def test_high_law_increases_cohesion(self):
        """Law Level A+ (10+) applies DM+2."""
        rng_hi = random.Random(0)
        rng_lo = random.Random(0)
        hi_vals = [_gen(law_level=11, rng=rng_hi).cohesion for _ in range(50)]
        lo_vals = [_gen(law_level=5,  rng=rng_lo).cohesion for _ in range(50)]
        assert sum(hi_vals) > sum(lo_vals)

    def test_monolithic_diversity_increases_cohesion(self):
        """Diversity 1-2 applies DM+4 vs diversity 6-8 (no DM)."""
        rng_lo = random.Random(999)
        rng_hi = random.Random(999)
        # Force diversity to 1 by using RNG that produces very low results
        # Instead, test DM directly via generate with fixed RNG — use
        # population/government/law combinations that drive diversity low vs high.
        # Gov 14 + law 11 + pop 3 → diversity DM = -4-1-2 = -7 → diversity tends ~1-2
        lo_div = [
            _gen(population=3, government=14, law_level=11, pcr=8, rng=rng_lo).cohesion
            for _ in range(50)
        ]
        # Gov 7 + pop 9 → diversity DM = +4+2 = +6 → diversity tends ~13-14
        hi_div = [
            _gen(population=9, government=7, law_level=5, pcr=4, rng=rng_hi).cohesion
            for _ in range(50)
        ]
        # Low-diversity worlds (monolithic) should have higher cohesion
        assert sum(lo_div) > sum(hi_div)

    def test_high_pcr_increases_cohesion(self):
        """PCR 7+ applies DM+2 vs PCR 4-6 (no DM)."""
        rng_hi = random.Random(0)
        rng_lo = random.Random(0)
        hi_vals = [_gen(pcr=8, rng=rng_hi).cohesion for _ in range(50)]
        lo_vals = [_gen(pcr=5, rng=rng_lo).cohesion for _ in range(50)]
        assert sum(hi_vals) > sum(lo_vals)


# ---------------------------------------------------------------------------
# Cohesion labels
# ---------------------------------------------------------------------------

class TestCohesionLabels:
    @pytest.mark.parametrize("value,expected", [
        (1,  "Individualistic"),
        (2,  "Individualistic"),
        (3,  "Individualistic"),
        (4,  "Moderate"),
        (5,  "Moderate"),
        (8,  "Moderate"),
        (9,  "Communal"),
        (10, "Communal"),
        (11, "Communal"),
        (12, "Collectivist"),
        (20, "Collectivist"),
    ])
    def test_cohesion_label_for_value(self, value, expected):
        assert _cohesion_label(value) == expected

    def test_cohesion_label_on_generated(self):
        """Label on CultureDetail matches the raw value."""
        cd = _gen()
        assert cd.cohesion_label == _cohesion_label(cd.cohesion)


# ---------------------------------------------------------------------------
# Progressiveness bounds
# ---------------------------------------------------------------------------

class TestProgressivenessBounds:
    def test_progressiveness_minimum_one(self):
        """Even extreme negative DMs cannot produce progressiveness < 1."""
        # Gov D (-6), Law C+ (-4), pop 9+ (-2) → DM -12
        rng = random.Random(1)
        for _ in range(50):
            cd = generate_culture_detail(
                population=10, government=13, law_level=12,
                pcr=4, rng=rng,
            )
            assert cd is not None
            assert cd.progressiveness >= 1

    def test_progressiveness_positive(self):
        cd = _gen()
        assert cd.progressiveness > 0


# ---------------------------------------------------------------------------
# Progressiveness DM effects
# ---------------------------------------------------------------------------

class TestProgressivenessDMEffects:
    def test_gov_d_strongly_decreases_progressiveness(self):
        """Government D (13) applies DM-6."""
        rng_d = random.Random(0)
        rng_n = random.Random(0)
        d_vals = [_gen(government=13, rng=rng_d).progressiveness for _ in range(50)]
        n_vals = [_gen(government=6,  rng=rng_n).progressiveness for _ in range(50)]
        assert sum(d_vals) < sum(n_vals)

    def test_gov_5_increases_progressiveness(self):
        """Government 5 applies DM+1."""
        rng_5 = random.Random(0)
        rng_n = random.Random(0)
        g5_vals = [_gen(government=5, rng=rng_5).progressiveness for _ in range(50)]
        gn_vals = [_gen(government=6, rng=rng_n).progressiveness for _ in range(50)]
        assert sum(g5_vals) > sum(gn_vals)

    def test_gov_b_decreases_progressiveness(self):
        """Government B (11) applies DM-2."""
        rng_b = random.Random(0)
        rng_n = random.Random(0)
        b_vals = [_gen(government=11, rng=rng_b).progressiveness for _ in range(50)]
        n_vals = [_gen(government=6,  rng=rng_n).progressiveness for _ in range(50)]
        assert sum(b_vals) < sum(n_vals)

    def test_high_xenophilia_increases_progressiveness(self):
        """Xenophilia 9+ applies DM+2."""
        # Force high xenophilia via starport A — compare two runs with same RNG
        rng_a = random.Random(0)
        rng_x = random.Random(0)
        a_vals = [_gen(starport="A", rng=rng_a).progressiveness for _ in range(50)]
        x_vals = [_gen(starport="X", rng=rng_x).progressiveness for _ in range(50)]
        # Starport A raises xenophilia (DM+2 on xen) → tends to raise progressiveness
        assert sum(a_vals) > sum(x_vals)

    def test_low_cohesion_increases_progressiveness(self):
        """Cohesion 1-5 applies DM+2 on progressiveness."""
        # Low PCR → low cohesion DM → cohesion tends low
        rng_lo = random.Random(0)
        rng_hi = random.Random(0)
        lo_vals = [_gen(pcr=0, law_level=1, rng=rng_lo).progressiveness for _ in range(50)]
        hi_vals = [_gen(pcr=8, law_level=9, rng=rng_hi).progressiveness for _ in range(50)]
        # Low PCR + low law → low cohesion → DM+2 on progressiveness
        assert sum(lo_vals) > sum(hi_vals)


# ---------------------------------------------------------------------------
# Progressiveness labels
# ---------------------------------------------------------------------------

class TestProgressivenessLabels:
    @pytest.mark.parametrize("value,expected", [
        (1,  "Moribund"),
        (2,  "Moribund"),
        (3,  "Moribund"),
        (4,  "Conservative"),
        (5,  "Conservative"),
        (6,  "Moderate"),
        (7,  "Moderate"),
        (8,  "Moderate"),
        (9,  "Progressive"),
        (10, "Progressive"),
        (11, "Progressive"),
        (12, "Innovative"),
        (20, "Innovative"),
    ])
    def test_progressiveness_label_for_value(self, value, expected):
        assert _progressiveness_label(value) == expected

    def test_progressiveness_label_on_generated(self):
        """Label on CultureDetail matches the raw value."""
        cd = _gen()
        assert cd.progressiveness_label == _progressiveness_label(cd.progressiveness)


# ---------------------------------------------------------------------------
# Expansionism bounds
# ---------------------------------------------------------------------------

class TestExpansionismBounds:
    def test_expansionism_minimum_one(self):
        """Even extreme negative DMs cannot produce expansionism < 1."""
        # Diversity C+ (-3), xenophilia 9+ (-2) → worst DM ~ -5
        rng = random.Random(1)
        for _ in range(50):
            cd = generate_culture_detail(
                population=9, government=7, law_level=3,
                pcr=4, rng=rng,
            )
            assert cd is not None
            assert cd.expansionism >= 1

    def test_expansionism_positive(self):
        cd = _gen()
        assert cd.expansionism > 0


# ---------------------------------------------------------------------------
# Expansionism DM effects
# ---------------------------------------------------------------------------

class TestExpansionismDMEffects:
    def test_gov_a_increases_expansionism(self):
        """Government A (10) applies DM+2."""
        rng_a = random.Random(0)
        rng_n = random.Random(0)
        a_vals = [_gen(government=10, rng=rng_a).expansionism for _ in range(50)]
        n_vals = [_gen(government=6,  rng=rng_n).expansionism for _ in range(50)]
        assert sum(a_vals) > sum(n_vals)

    def test_gov_c_plus_increases_expansionism(self):
        """Government C+ (12+) applies DM+2."""
        rng_c = random.Random(0)
        rng_n = random.Random(0)
        c_vals = [_gen(government=12, rng=rng_c).expansionism for _ in range(50)]
        n_vals = [_gen(government=6,  rng=rng_n).expansionism for _ in range(50)]
        assert sum(c_vals) > sum(n_vals)

    def test_monolithic_diversity_increases_expansionism(self):
        """Diversity 1-3 applies DM+3."""
        rng_lo = random.Random(0)
        rng_hi = random.Random(0)
        # Low-diversity worlds: small pop, high gov, high law drives diversity down
        lo_vals = [
            _gen(population=3, government=14, law_level=11, pcr=8, rng=rng_lo).expansionism
            for _ in range(50)
        ]
        # High-diversity worlds: gov 7, high pop
        hi_vals = [
            _gen(population=9, government=7, law_level=3, pcr=4, rng=rng_hi).expansionism
            for _ in range(50)
        ]
        assert sum(lo_vals) > sum(hi_vals)

    def test_high_xenophilia_decreases_expansionism(self):
        """Xenophilia 9+ applies DM-2 on expansionism."""
        rng_a = random.Random(0)
        rng_x = random.Random(0)
        # Starport A → high xenophilia → lower expansionism
        a_vals = [_gen(starport="A", rng=rng_a).expansionism for _ in range(50)]
        # Starport X → low xenophilia → higher expansionism
        x_vals = [_gen(starport="X", rng=rng_x).expansionism for _ in range(50)]
        assert sum(a_vals) < sum(x_vals)


# ---------------------------------------------------------------------------
# Expansionism labels
# ---------------------------------------------------------------------------

class TestExpansionismLabels:
    @pytest.mark.parametrize("value,expected", [
        (1,  "Insular"),
        (2,  "Insular"),
        (3,  "Insular"),
        (4,  "Moderate"),
        (5,  "Moderate"),
        (8,  "Moderate"),
        (9,  "Expansive"),
        (10, "Expansive"),
        (11, "Expansive"),
        (12, "Imperialist"),
        (20, "Imperialist"),
    ])
    def test_expansionism_label_for_value(self, value, expected):
        assert _expansionism_label(value) == expected

    def test_expansionism_label_on_generated(self):
        """Label on CultureDetail matches the raw value."""
        cd = _gen()
        assert cd.expansionism_label == _expansionism_label(cd.expansionism)


# ---------------------------------------------------------------------------
# Militancy bounds
# ---------------------------------------------------------------------------

class TestMilitancyBounds:
    def test_militancy_minimum_one(self):
        """Even extreme negative DMs cannot produce militancy < 1."""
        # Expansionism 1-5 (-1), xenophilia 9+ (-2) → worst DM ~ -3
        rng = random.Random(1)
        for _ in range(50):
            cd = generate_culture_detail(
                population=7, government=0, law_level=3,
                starport="A", rng=rng,
            )
            assert cd is not None
            assert cd.militancy >= 1

    def test_militancy_positive(self):
        cd = _gen()
        assert cd.militancy > 0


# ---------------------------------------------------------------------------
# Militancy DM effects
# ---------------------------------------------------------------------------

class TestMilitancyDMEffects:
    def test_high_gov_increases_militancy(self):
        """Government A+ (10+) applies DM+3."""
        rng_hi = random.Random(0)
        rng_lo = random.Random(0)
        hi_vals = [_gen(government=10, rng=rng_hi).militancy for _ in range(50)]
        lo_vals = [_gen(government=6,  rng=rng_lo).militancy for _ in range(50)]
        assert sum(hi_vals) > sum(lo_vals)

    def test_high_law_increases_militancy(self):
        """Law Level C+ (12+) applies DM+2."""
        rng_hi = random.Random(0)
        rng_lo = random.Random(0)
        hi_vals = [_gen(law_level=12, rng=rng_hi).militancy for _ in range(50)]
        lo_vals = [_gen(law_level=5,  rng=rng_lo).militancy for _ in range(50)]
        assert sum(hi_vals) > sum(lo_vals)

    def test_high_xenophilia_decreases_militancy(self):
        """Xenophilia 9+ applies DM-2 on militancy."""
        rng_a = random.Random(0)
        rng_x = random.Random(0)
        # Starport A → high xenophilia → lower militancy
        a_vals = [_gen(starport="A", rng=rng_a).militancy for _ in range(50)]
        x_vals = [_gen(starport="X", rng=rng_x).militancy for _ in range(50)]
        assert sum(a_vals) < sum(x_vals)


# ---------------------------------------------------------------------------
# Militancy labels
# ---------------------------------------------------------------------------

class TestMilitancyLabels:
    @pytest.mark.parametrize("value,expected", [
        (1,  "Peaceful"),
        (2,  "Peaceful"),
        (3,  "Peaceful"),
        (4,  "Moderate"),
        (5,  "Moderate"),
        (8,  "Moderate"),
        (9,  "Aggressive"),
        (10, "Aggressive"),
        (11, "Aggressive"),
        (12, "Militaristic"),
        (20, "Militaristic"),
    ])
    def test_militancy_label_for_value(self, value, expected):
        assert _militancy_label(value) == expected

    def test_militancy_label_on_generated(self):
        """Label on CultureDetail matches the raw value."""
        cd = _gen()
        assert cd.militancy_label == _militancy_label(cd.militancy)


# ---------------------------------------------------------------------------
# Profile string
# ---------------------------------------------------------------------------

class TestProfileString:
    def test_profile_dxus_cpem_format(self):
        """cultural_profile is 9 chars in DXUS-CPEM format with hyphen at position 4."""
        cd = _gen()
        assert len(cd.cultural_profile) == 9
        assert cd.cultural_profile[4] == "-"
        assert all(c in _EHEX for c in cd.cultural_profile[:4])
        assert all(c in _EHEX for c in cd.cultural_profile[5:])

    def test_profile_d_matches_diversity(self):
        cd = _gen()
        assert cd.cultural_profile[0] == _EHEX[min(cd.diversity, len(_EHEX) - 1)]

    def test_profile_x_matches_xenophilia(self):
        cd = _gen()
        assert cd.cultural_profile[1] == _EHEX[min(cd.xenophilia, len(_EHEX) - 1)]

    def test_profile_u_matches_uniqueness(self):
        cd = _gen()
        assert cd.cultural_profile[2] == _EHEX[min(cd.uniqueness, len(_EHEX) - 1)]

    def test_profile_s_matches_symbology(self):
        cd = _gen()
        assert cd.cultural_profile[3] == _EHEX[min(cd.symbology, len(_EHEX) - 1)]

    def test_profile_c_matches_cohesion(self):
        cd = _gen()
        assert cd.cultural_profile[5] == _EHEX[min(cd.cohesion, len(_EHEX) - 1)]

    def test_profile_p_matches_progressiveness(self):
        cd = _gen()
        assert cd.cultural_profile[6] == _EHEX[min(cd.progressiveness, len(_EHEX) - 1)]

    def test_profile_e_matches_expansionism(self):
        cd = _gen()
        assert cd.cultural_profile[7] == _EHEX[min(cd.expansionism, len(_EHEX) - 1)]

    def test_profile_m_matches_militancy(self):
        cd = _gen()
        assert cd.cultural_profile[8] == _EHEX[min(cd.militancy, len(_EHEX) - 1)]


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_to_dict_from_dict(self):
        cd = _gen()
        restored = CultureDetail.from_dict(cd.to_dict())
        assert restored.diversity        == cd.diversity
        assert restored.diversity_label  == cd.diversity_label
        assert restored.xenophilia       == cd.xenophilia
        assert restored.xenophilia_label == cd.xenophilia_label
        assert restored.uniqueness       == cd.uniqueness
        assert restored.uniqueness_label == cd.uniqueness_label
        assert restored.symbology        == cd.symbology
        assert restored.symbology_label  == cd.symbology_label
        assert restored.cohesion              == cd.cohesion
        assert restored.cohesion_label        == cd.cohesion_label
        assert restored.progressiveness       == cd.progressiveness
        assert restored.progressiveness_label == cd.progressiveness_label
        assert restored.expansionism          == cd.expansionism
        assert restored.expansionism_label    == cd.expansionism_label
        assert restored.militancy             == cd.militancy
        assert restored.militancy_label       == cd.militancy_label
        assert restored.cultural_profile      == cd.cultural_profile

    def test_to_dict_keys(self):
        cd = _gen()
        d = cd.to_dict()
        assert set(d.keys()) == {
            "diversity", "diversity_label",
            "xenophilia", "xenophilia_label",
            "uniqueness", "uniqueness_label",
            "symbology", "symbology_label",
            "cohesion", "cohesion_label",
            "progressiveness", "progressiveness_label",
            "expansionism", "expansionism_label",
            "militancy", "militancy_label",
            "cultural_profile",
            "cultural_extension",
        }

    def test_from_dict_backward_compat_xenophilia(self):
        """Old saved data without xenophilia/uniqueness/symbology/cohesion gets safe defaults."""
        old = {"diversity": 7, "diversity_label": "Diverse",
               "cultural_profile": "7"}
        restored = CultureDetail.from_dict(old)
        assert restored.diversity == 7
        assert restored.xenophilia == 1              # default
        assert restored.xenophilia_label == "Xenophobic"
        assert restored.uniqueness == 1              # default
        assert restored.uniqueness_label == "Indistinct"
        assert restored.symbology == 1               # default
        assert restored.symbology_label == "Mundane"
        assert restored.cohesion == 1                    # default
        assert restored.cohesion_label == "Individualistic"
        assert restored.progressiveness == 1             # default
        assert restored.progressiveness_label == "Moribund"
        assert restored.expansionism == 1                # default
        assert restored.militancy == 1                   # default

    def test_from_dict_backward_compat_uniqueness(self):
        """Data with xenophilia but no uniqueness/symbology/cohesion/progressiveness."""
        old = {"diversity": 7, "diversity_label": "Diverse",
               "xenophilia": 9, "xenophilia_label": "Welcoming",
               "cultural_profile": "79"}
        restored = CultureDetail.from_dict(old)
        assert restored.xenophilia == 9
        assert restored.uniqueness == 1              # default
        assert restored.symbology == 1               # default
        assert restored.cohesion == 1                # default
        assert restored.progressiveness == 1         # default
        assert restored.expansionism == 1            # default
        assert restored.militancy == 1               # default

    def test_from_dict_backward_compat_symbology(self):
        """Data with uniqueness but no symbology onward gets defaults."""
        old = {"diversity": 7, "xenophilia": 9, "uniqueness": 10,
               "cultural_profile": "79A"}
        restored = CultureDetail.from_dict(old)
        assert restored.uniqueness == 10
        assert restored.symbology == 1               # default
        assert restored.cohesion == 1                # default
        assert restored.progressiveness == 1         # default
        assert restored.expansionism == 1            # default
        assert restored.militancy == 1               # default

    def test_from_dict_backward_compat_progressiveness(self):
        """Data with cohesion but no progressiveness onward gets defaults."""
        old = {"diversity": 7, "xenophilia": 9, "uniqueness": 10,
               "symbology": 8, "cohesion": 6, "cultural_profile": "79A86"}
        restored = CultureDetail.from_dict(old)
        assert restored.cohesion == 6
        assert restored.progressiveness == 1         # default
        assert restored.expansionism == 1            # default
        assert restored.militancy == 1               # default

    def test_from_dict_backward_compat_expansionism(self):
        """Data with progressiveness but no expansionism/militancy gets defaults."""
        old = {"diversity": 7, "xenophilia": 9, "uniqueness": 10,
               "symbology": 8, "cohesion": 6, "progressiveness": 5,
               "cultural_profile": "79A865"}
        restored = CultureDetail.from_dict(old)
        assert restored.progressiveness == 5
        assert restored.expansionism == 1            # default
        assert restored.militancy == 1               # default


# ---------------------------------------------------------------------------
# attach_culture_detail integration
# ---------------------------------------------------------------------------

class TestAttachCultureDetail:
    def _make_system(self, seed=1):
        rng = random.Random(seed)
        system = generate_full_system(seed=seed, rng=rng)
        attach_detail(system, rng=rng)
        return system, rng

    def test_mainworld_uninhabited_no_culture(self):
        """Uninhabited mainworld → culture_detail stays None."""
        for seed in range(1, 200):
            system, rng = self._make_system(seed)
            mw = system.mainworld
            if mw is not None and mw.population == 0:
                attach_culture_detail(system, rng=rng)
                assert mw.culture_detail is None  # type: ignore[attr-defined]
                return
        pytest.skip("No uninhabited mainworld found in seeds 1-199")

    def test_mainworld_inhabited_has_culture(self):
        """Inhabited mainworld → culture_detail is set with both traits."""
        for seed in range(1, 200):
            system, rng = self._make_system(seed)
            mw = system.mainworld
            if mw is not None and mw.population > 0:
                attach_culture_detail(system, rng=rng)
                cd = mw.culture_detail  # type: ignore[attr-defined]
                assert cd is not None
                assert isinstance(cd, CultureDetail)
                assert cd.diversity >= 1
                assert cd.xenophilia >= 1
                assert cd.uniqueness >= 1
                assert cd.symbology >= 1
                assert cd.cohesion >= 1
                assert cd.progressiveness >= 1
                assert cd.expansionism >= 1
                assert cd.militancy >= 1
                return
        pytest.skip("No inhabited mainworld found in seeds 1-199")

    def test_secondary_inhabited_gets_culture(self):
        """Inhabited secondary world → culture_detail is set."""
        for seed in range(1, 300):
            system, rng = self._make_system(seed)
            attach_culture_detail(system, rng=rng)
            for orbit in system.system_orbits.orbits:
                if orbit.is_mainworld_candidate:
                    continue
                det = orbit.detail
                if det is not None and det.inhabited:
                    assert det.culture_detail is not None
                    return
        pytest.skip("No inhabited secondary found in seeds 1-299")

    def test_secondary_uninhabited_no_culture(self):
        """Uninhabited secondary world → culture_detail stays None."""
        for seed in range(1, 100):
            system, rng = self._make_system(seed)
            attach_culture_detail(system, rng=rng)
            for orbit in system.system_orbits.orbits:
                if orbit.is_mainworld_candidate:
                    continue
                det = orbit.detail
                if det is not None and not det.inhabited:
                    assert det.culture_detail is None
                    return
        pytest.skip("No uninhabited secondary found in seeds 1-99")


# ---------------------------------------------------------------------------
# Hypothesis property-based tests
# ---------------------------------------------------------------------------

@given(
    population=st.integers(min_value=1, max_value=15),
    government=st.integers(min_value=0, max_value=15),
    law_level=st.integers(min_value=0, max_value=18),
    pcr=st.integers(min_value=0, max_value=9),
    starport=st.sampled_from(["A", "B", "C", "D", "E", "X", ""]),
    tech_level=st.integers(min_value=0, max_value=16),
)
@settings(max_examples=300)
def test_hypothesis_diversity_bounds(population, government, law_level, pcr, starport, tech_level):
    """Diversity is always ≥ 1 for inhabited worlds."""
    cd = generate_culture_detail(
        population=population, government=government,
        law_level=law_level, pcr=pcr, starport=starport, tech_level=tech_level,
    )
    assert cd is not None
    assert cd.diversity >= 1


@given(
    population=st.integers(min_value=1, max_value=15),
    government=st.integers(min_value=0, max_value=15),
    law_level=st.integers(min_value=0, max_value=18),
    pcr=st.integers(min_value=0, max_value=9),
    starport=st.sampled_from(["A", "B", "C", "D", "E", "X", ""]),
    tech_level=st.integers(min_value=0, max_value=16),
)
@settings(max_examples=300)
def test_hypothesis_xenophilia_bounds(population, government, law_level, pcr, starport, tech_level):
    """Xenophilia is always ≥ 1 for inhabited worlds."""
    cd = generate_culture_detail(
        population=population, government=government,
        law_level=law_level, pcr=pcr, starport=starport, tech_level=tech_level,
    )
    assert cd is not None
    assert cd.xenophilia >= 1


@given(
    population=st.integers(min_value=1, max_value=15),
    government=st.integers(min_value=0, max_value=15),
    law_level=st.integers(min_value=0, max_value=18),
    pcr=st.integers(min_value=0, max_value=9),
    starport=st.sampled_from(["A", "B", "C", "D", "E", "X", ""]),
    tech_level=st.integers(min_value=0, max_value=16),
)
@settings(max_examples=300)
def test_hypothesis_uniqueness_bounds(population, government, law_level, pcr, starport, tech_level):
    """Uniqueness is always ≥ 1 for inhabited worlds."""
    cd = generate_culture_detail(
        population=population, government=government,
        law_level=law_level, pcr=pcr, starport=starport, tech_level=tech_level,
    )
    assert cd is not None
    assert cd.uniqueness >= 1


@given(
    population=st.integers(min_value=1, max_value=15),
    government=st.integers(min_value=0, max_value=15),
    law_level=st.integers(min_value=0, max_value=18),
    pcr=st.integers(min_value=0, max_value=9),
    starport=st.sampled_from(["A", "B", "C", "D", "E", "X", ""]),
    tech_level=st.integers(min_value=0, max_value=16),
)
@settings(max_examples=300)
def test_hypothesis_symbology_bounds(population, government, law_level, pcr, starport, tech_level):
    """Symbology is always ≥ 1 for inhabited worlds."""
    cd = generate_culture_detail(
        population=population, government=government,
        law_level=law_level, pcr=pcr, starport=starport, tech_level=tech_level,
    )
    assert cd is not None
    assert cd.symbology >= 1


@given(
    population=st.integers(min_value=1, max_value=15),
    government=st.integers(min_value=0, max_value=15),
    law_level=st.integers(min_value=0, max_value=18),
    pcr=st.integers(min_value=0, max_value=9),
    starport=st.sampled_from(["A", "B", "C", "D", "E", "X", ""]),
    tech_level=st.integers(min_value=0, max_value=16),
)
@settings(max_examples=300)
def test_hypothesis_cohesion_bounds(population, government, law_level, pcr, starport, tech_level):
    """Cohesion is always ≥ 1 for inhabited worlds."""
    cd = generate_culture_detail(
        population=population, government=government,
        law_level=law_level, pcr=pcr, starport=starport, tech_level=tech_level,
    )
    assert cd is not None
    assert cd.cohesion >= 1


@given(
    population=st.integers(min_value=1, max_value=15),
    government=st.integers(min_value=0, max_value=15),
    law_level=st.integers(min_value=0, max_value=18),
    pcr=st.integers(min_value=0, max_value=9),
    starport=st.sampled_from(["A", "B", "C", "D", "E", "X", ""]),
    tech_level=st.integers(min_value=0, max_value=16),
)
@settings(max_examples=300)
def test_hypothesis_progressiveness_bounds(population, government, law_level, pcr, starport, tech_level):
    """Progressiveness is always ≥ 1 for inhabited worlds."""
    cd = generate_culture_detail(
        population=population, government=government,
        law_level=law_level, pcr=pcr, starport=starport, tech_level=tech_level,
    )
    assert cd is not None
    assert cd.progressiveness >= 1


@given(
    population=st.integers(min_value=1, max_value=15),
    government=st.integers(min_value=0, max_value=15),
    law_level=st.integers(min_value=0, max_value=18),
    pcr=st.integers(min_value=0, max_value=9),
    starport=st.sampled_from(["A", "B", "C", "D", "E", "X", ""]),
    tech_level=st.integers(min_value=0, max_value=16),
)
@settings(max_examples=300)
def test_hypothesis_expansionism_bounds(population, government, law_level, pcr, starport, tech_level):
    """Expansionism is always ≥ 1 for inhabited worlds."""
    cd = generate_culture_detail(
        population=population, government=government,
        law_level=law_level, pcr=pcr, starport=starport, tech_level=tech_level,
    )
    assert cd is not None
    assert cd.expansionism >= 1


@given(
    population=st.integers(min_value=1, max_value=15),
    government=st.integers(min_value=0, max_value=15),
    law_level=st.integers(min_value=0, max_value=18),
    pcr=st.integers(min_value=0, max_value=9),
    starport=st.sampled_from(["A", "B", "C", "D", "E", "X", ""]),
    tech_level=st.integers(min_value=0, max_value=16),
)
@settings(max_examples=300)
def test_hypothesis_militancy_bounds(population, government, law_level, pcr, starport, tech_level):
    """Militancy is always ≥ 1 for inhabited worlds."""
    cd = generate_culture_detail(
        population=population, government=government,
        law_level=law_level, pcr=pcr, starport=starport, tech_level=tech_level,
    )
    assert cd is not None
    assert cd.militancy >= 1


@given(
    population=st.integers(min_value=1, max_value=15),
    government=st.integers(min_value=0, max_value=15),
    law_level=st.integers(min_value=0, max_value=18),
    pcr=st.integers(min_value=0, max_value=9),
    starport=st.sampled_from(["A", "B", "C", "D", "E", "X", ""]),
    tech_level=st.integers(min_value=0, max_value=16),
)
@settings(max_examples=300)
def test_hypothesis_profile_dxus_cpem(population, government, law_level, pcr, starport, tech_level):
    """Cultural profile is always DXUS-CPEM format: 9 chars, hyphen at position 4."""
    cd = generate_culture_detail(
        population=population, government=government,
        law_level=law_level, pcr=pcr, starport=starport, tech_level=tech_level,
    )
    assert cd is not None
    assert len(cd.cultural_profile) == 9
    assert cd.cultural_profile[4] == "-"
    assert all(c in _EHEX for c in cd.cultural_profile[:4])
    assert all(c in _EHEX for c in cd.cultural_profile[5:])


# ---------------------------------------------------------------------------
# _parse_cx_string
# ---------------------------------------------------------------------------

class TestParseCxString:
    def test_bare_four_chars(self):
        assert _parse_cx_string("7567") == (7, 5, 6, 7)

    def test_parenthesised(self):
        assert _parse_cx_string("(7567)") == (7, 5, 6, 7)

    def test_hex_digits_upper(self):
        """A–F map to 10–15."""
        assert _parse_cx_string("ABCD") == (10, 11, 12, 13)

    def test_hex_digits_lower(self):
        """Case insensitive."""
        assert _parse_cx_string("abcd") == (10, 11, 12, 13)

    def test_strangeness_zero(self):
        assert _parse_cx_string("7007") == (7, 0, 0, 7)

    def test_too_short_returns_zeros(self):
        assert _parse_cx_string("") == (0, 0, 0, 0)
        assert _parse_cx_string("75") == (0, 0, 0, 0)

    def test_whitespace_stripped(self):
        assert _parse_cx_string("( 7567 )") == (7, 5, 6, 7)


# ---------------------------------------------------------------------------
# generate_culture_detail_from_cx
# ---------------------------------------------------------------------------

def _gen_cx(
        cx="7567",
        population=7, importance=2, government=6, law_level=5,
        pcr=4, starport="C", tech_level=8, rng=None,
) -> CultureDetail:
    """Convenience wrapper for generate_culture_detail_from_cx."""
    result = generate_culture_detail_from_cx(
        cx=cx, population=population, importance=importance,
        government=government, law_level=law_level, pcr=pcr,
        starport=starport, tech_level=tech_level, rng=rng,
    )
    assert result is not None
    return result


class TestFromCxNoneGuard:
    def test_uninhabited_returns_none(self):
        assert generate_culture_detail_from_cx(
            cx="7567", population=0, importance=2,
            government=6, law_level=5,
        ) is None

    def test_inhabited_returns_culture_detail(self):
        assert _gen_cx() is not None


class TestFromCxDiversityMapping:
    def test_diversity_from_h_within_bounds(self):
        """H=7, Pop=7 → diversity in [2, 12]."""
        cd = _gen_cx(cx="7567", population=7)
        assert 2 <= cd.diversity <= 12

    def test_diversity_clamped_to_lower_bound(self):
        """H=0 → diversity = max(1, Pop-5) not 0."""
        cd = _gen_cx(cx="0567", population=7)
        assert cd.diversity == max(1, 7 - 5)   # == 2

    def test_diversity_clamped_to_upper_bound(self):
        """H=F (15) → diversity = Pop+5."""
        cd = _gen_cx(cx="F567", population=7)
        assert cd.diversity == 7 + 5   # == 12

    def test_diversity_min_one(self):
        """Pop=1, H=0 → diversity = max(1, -4) = 1."""
        cd = _gen_cx(cx="0567", population=1)
        assert cd.diversity == 1


class TestFromCxXenophiliaMapping:
    def test_xenophilia_from_a_within_bounds(self):
        """A=5, Pop=7, Imp=2 → xenophilia in [4, 14]."""
        cd = _gen_cx(cx="7567", population=7, importance=2)
        assert 4 <= cd.xenophilia <= 14

    def test_xenophilia_clamped_to_lower_bound(self):
        """A=0, Pop=7, Imp=2 → xenophilia = max(1, 9-5) = 4."""
        cd = _gen_cx(cx="7067", population=7, importance=2)
        assert cd.xenophilia == 4

    def test_xenophilia_clamped_to_upper_bound(self):
        """A=F (15), Pop=7, Imp=2 → xenophilia = 9+5 = 14."""
        cd = _gen_cx(cx="7F67", population=7, importance=2)
        assert cd.xenophilia == 14

    def test_xenophilia_min_one(self):
        """Pop=1, Imp=0, A=0 → xenophilia ≥ 1."""
        cd = _gen_cx(cx="7067", population=1, importance=0)
        assert cd.xenophilia >= 1


class TestFromCxUniquenessMapping:
    def test_strangeness_zero_gives_uniqueness_one(self):
        """S=0 → max(1, ceil(0×3/2)) = 1."""
        cd = _gen_cx(cx="7507")
        assert cd.uniqueness == 1

    def test_strangeness_two_gives_three(self):
        """S=2 → ceil(2×3/2) = 3."""
        cd = _gen_cx(cx="7527")
        assert cd.uniqueness == 3

    def test_strangeness_five_gives_eight(self):
        """S=5 → ceil(5×3/2) = 8."""
        cd = _gen_cx(cx="7557")
        assert cd.uniqueness == 8

    def test_strangeness_ten_gives_fifteen(self):
        """S=A (10) → ceil(10×3/2) = 15."""
        cd = _gen_cx(cx="75A7")
        assert cd.uniqueness == 15

    def test_uniqueness_min_one(self):
        """S=0 → uniqueness never below 1."""
        cd = _gen_cx(cx="7507")
        assert cd.uniqueness >= 1


class TestFromCxSymbologyMapping:
    def test_symbology_from_s2_within_bounds(self):
        """S2=7, TL=8 → symbology in [3, 13]."""
        cd = _gen_cx(cx="7567", tech_level=8)
        assert 3 <= cd.symbology <= 13

    def test_symbology_clamped_to_lower_bound(self):
        """S2=0, TL=8 → symbology = max(1, TL-5) = 3."""
        cd = _gen_cx(cx="7560", tech_level=8)
        assert cd.symbology == 3

    def test_symbology_clamped_to_upper_bound(self):
        """S2=F (15), TL=8 → symbology = TL+5 = 13."""
        cd = _gen_cx(cx="756F", tech_level=8)
        assert cd.symbology == 13

    def test_symbology_min_one(self):
        """TL=0, S2=0 → symbology = max(1, -5) = 1."""
        cd = _gen_cx(cx="7560", tech_level=0)
        assert cd.symbology == 1


class TestFromCxRolledTraits:
    def test_remaining_traits_at_least_one(self):
        """Cohesion, Progressiveness, Expansionism, Militancy are all ≥ 1."""
        rng = random.Random(0)
        for _ in range(50):
            cd = _gen_cx(rng=rng)
            assert cd.cohesion >= 1
            assert cd.progressiveness >= 1
            assert cd.expansionism >= 1
            assert cd.militancy >= 1

    def test_profile_format(self):
        """from_cx produces valid DXUS-CPEM profile."""
        cd = _gen_cx()
        assert len(cd.cultural_profile) == 9
        assert cd.cultural_profile[4] == "-"
        assert all(c in _EHEX for c in cd.cultural_profile[:4])
        assert all(c in _EHEX for c in cd.cultural_profile[5:])

    def test_profile_d_matches_diversity(self):
        cd = _gen_cx()
        assert cd.cultural_profile[0] == _EHEX[min(cd.diversity, len(_EHEX) - 1)]

    def test_profile_u_matches_uniqueness(self):
        cd = _gen_cx()
        assert cd.cultural_profile[2] == _EHEX[min(cd.uniqueness, len(_EHEX) - 1)]


class TestAttachCultureDetailCxPath:
    """attach_culture_detail routes to from_cx when world.cx is present."""

    def _make_system(self, seed=1):
        rng = random.Random(seed)
        system = generate_full_system(seed=seed, rng=rng)
        attach_detail(system, rng=rng)
        return system, rng

    def test_cx_path_used_when_cx_present(self):
        """World with cx attribute produces CultureDetail with clamped diversity."""
        system, rng = self._make_system(seed=10)
        mw = system.mainworld
        if mw is None or mw.population == 0:
            pytest.skip("Mainworld uninhabited in seed 10")
        # Stamp a known Cx: H=pop, A=5, S=5, S2=8
        pop = mw.population
        cx_h = _EHEX[min(pop, len(_EHEX) - 1)]
        mw.cx = f"{cx_h}558"  # type: ignore[attr-defined]
        mw.importance = 2      # type: ignore[attr-defined]
        attach_culture_detail(system, rng=rng)
        cd = mw.culture_detail  # type: ignore[attr-defined]
        assert cd is not None
        # Diversity H==pop → clamped to [max(1,pop-5), pop+5]; value == pop
        assert cd.diversity == pop
        # Uniqueness S=5 → ceil(5×3/2) = 8
        assert cd.uniqueness == 8

    def test_no_cx_uses_normal_path(self):
        """World without cx uses standard generate_culture_detail."""
        system, rng = self._make_system(seed=5)
        mw = system.mainworld
        if mw is None or mw.population == 0:
            pytest.skip("Mainworld uninhabited in seed 5")
        assert not hasattr(mw, "cx")
        attach_culture_detail(system, rng=rng)
        cd = mw.culture_detail  # type: ignore[attr-defined]
        assert cd is not None
        assert isinstance(cd, CultureDetail)


# ---------------------------------------------------------------------------
# _compute_cx and cultural_extension (issue #141)
# ---------------------------------------------------------------------------

class TestComputeCx:
    """Tests for the DXUS → HASS forward conversion (_compute_cx)."""

    def test_uninhabited_returns_0000(self):
        assert _compute_cx(10, 10, 10, 10, 0, 8, 2) == "0000"

    def test_known_good_conversion(self):
        # Pop=6, TL=9, Imp=2; diversity=6, xenophilia=8, uniqueness=9, symbology=10
        # H = clamp(6, max(1,1), 11) = 6
        # A = clamp(8, max(1,3), 13) = 8
        # S = round(9 × 2/3) = round(6.0) = 6
        # S2= clamp(10, max(1,4), 14) = 10 → eHex 'A'
        result = _compute_cx(6, 8, 9, 10, 6, 9, 2)
        assert result == "686A"

    def test_h_clamped_to_upper(self):
        # diversity far above pop+5
        result = _compute_cx(30, 5, 5, 5, 6, 9, 0)
        h = _EHEX.index(result[0])
        assert h == 11  # pop+5 = 11

    def test_h_clamped_to_lower(self):
        # diversity far below pop-5
        result = _compute_cx(1, 5, 5, 5, 10, 9, 0)
        h = _EHEX.index(result[0])
        assert h == max(1, 10 - 5)  # = 5

    def test_a_clamped_to_upper(self):
        # xenophilia far above imp+pop+5
        result = _compute_cx(5, 35, 5, 5, 6, 9, 2)
        a = _EHEX.index(result[1])
        assert a == 13  # imp+pop+5 = 13

    def test_a_minimum_1_for_inhabited(self):
        # imp+pop very low — lower bound still clamped to 1
        result = _compute_cx(5, 1, 5, 5, 1, 9, -5)
        a = _EHEX.index(result[1])
        assert a >= 1

    def test_s_strangeness_rounding(self):
        # uniqueness=10 → round(10 × 2/3) = round(6.666) = 7
        result = _compute_cx(5, 5, 10, 5, 6, 9, 0)
        s = _EHEX.index(result[2])
        assert s == 7

    def test_s_minimum_1(self):
        result = _compute_cx(5, 5, 1, 5, 6, 9, 0)
        s = _EHEX.index(result[2])
        assert s == 1

    def test_s2_clamped_to_tl_bounds(self):
        # symbology far above TL+5
        result = _compute_cx(5, 5, 5, 30, 6, 9, 0)
        s2 = _EHEX.index(result[3])
        assert s2 == 14  # TL+5 = 14

    def test_result_is_4_chars(self):
        result = _compute_cx(8, 8, 8, 8, 6, 9, 2)
        assert len(result) == 4
        assert all(c in _EHEX for c in result)


class TestCulturalExtensionField:
    """cultural_extension stored on CultureDetail and round-trips cleanly."""

    def test_generate_culture_detail_sets_extension(self):
        cd = generate_culture_detail(
            population=6, government=6, law_level=6,
            tech_level=9, importance=2,
        )
        assert cd is not None
        assert len(cd.cultural_extension) == 4
        assert all(c in _EHEX for c in cd.cultural_extension)

    def test_uninhabited_returns_none_not_0000(self):
        cd = generate_culture_detail(population=0, government=0, law_level=0)
        assert cd is None

    def test_from_cx_sets_extension(self):
        cd = generate_culture_detail_from_cx(
            cx="7567", population=7, importance=2,
            government=6, law_level=5, tech_level=10,
        )
        assert cd is not None
        assert len(cd.cultural_extension) == 4

    def test_round_trip_preserves_extension(self):
        cd = generate_culture_detail(
            population=7, government=5, law_level=4,
            tech_level=10, importance=1,
        )
        assert cd is not None
        d = cd.to_dict()
        assert "cultural_extension" in d
        cd2 = CultureDetail.from_dict(d)
        assert cd2.cultural_extension == cd.cultural_extension

    def test_from_dict_missing_extension_defaults_to_empty(self):
        cd = generate_culture_detail(population=6, government=6, law_level=6)
        assert cd is not None
        d = cd.to_dict()
        del d["cultural_extension"]
        cd2 = CultureDetail.from_dict(d)
        assert cd2.cultural_extension == ""

    def test_extension_matches_compute_cx(self):
        """cultural_extension on CultureDetail matches _compute_cx directly."""
        cd = generate_culture_detail(
            population=8, government=6, law_level=5,
            tech_level=12, importance=3,
        )
        assert cd is not None
        expected = _compute_cx(
            cd.diversity, cd.xenophilia, cd.uniqueness, cd.symbology,
            8, 12, 3,
        )
        assert cd.cultural_extension == expected
