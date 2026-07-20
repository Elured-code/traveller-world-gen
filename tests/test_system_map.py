"""
test_system_map.py
===================
pytest unit tests for system_map.py.

Test strategy
-------------
build_svg() returns a single self-contained SVG string with no exported
geometry helpers, so — following the precedent set by the poster-html tests
in test_traveller_world_gen.py (TestFullSystemCard) — these tests generate a
real system for a fixed seed and assert on the returned SVG string via regex,
rather than mocking internals.

Test organisation
------------------
  TestCompanionStarPlacement - issue #171 regression: a companion of a
                                secondary star must be drawn in its actual
                                parent's arc zone / table column, not the
                                primary's. Also covers the follow-up feature:
                                that companion is *additionally* nested next
                                to its parent's own context marker wherever
                                the parent itself is shown as dashed context
                                (e.g. inside the primary's zone).
"""

import re

from traveller_gen.system_map import build_svg
from traveller_gen.traveller_system_gen import generate_full_system


class TestCompanionStarPlacement:
    """Regression tests for issue #171."""

    def test_companion_of_secondary_drawn_in_parent_zone_not_primary(self):
        # Seed from the bug report: A (primary), B (near secondary, has its
        # own orbit slots), Ba (companion of B, not of A).
        system = generate_full_system(seed=1076570818)
        stars = system.stellar_system.stars
        desigs = [s.designation for s in stars]
        assert desigs == ["A", "B", "Ba"]
        assert stars[2].role == "companion"

        canvas_w = 1600
        svg, _ = build_svg(system, canvas_w=canvas_w)
        arc_zone_h = canvas_w * 2 // 3

        # Both A and B have their own orbit slots in this seed, so both get
        # an arc zone, in stellar_system order: zi=0 for A, zi=1 for B.
        b_zi = desigs.index("B")

        # Ba is now drawn twice by design: once (this test) in B's own zone
        # as its proper context marker, and once (see the nested-placement
        # test below) nested next to B's own marker inside the primary's
        # zone. So assert *at least one* Ba marker falls in B's zone, rather
        # than assuming a single match.
        ba_ys = [float(m.group(1)) for m in
                 re.finditer(r'<text x="[\d.]+" y="([\d.]+)"[^>]*>Ba</text>', svg)]
        assert ba_ys, "no Ba marker label found in SVG"
        assert any(b_zi * arc_zone_h <= y < (b_zi + 1) * arc_zone_h for y in ba_ys), (
            "Ba should have a marker drawn in B's own arc zone"
        )

        # Table zone: "Star Ba" row must be in B's column, not A's.
        col_w = canvas_w // len(desigs)
        a_ci = desigs.index("A")
        b_ci = desigs.index("B")
        tm = re.search(r'<text x="([\d.]+)" y="[\d.]+"[^>]*>Star Ba</text>', svg)
        assert tm is not None, "'Star Ba' table row not found in SVG"
        ba_x = float(tm.group(1))
        assert b_ci * col_w <= ba_x < (b_ci + 1) * col_w, (
            "Star Ba's table row should be in B's column"
        )
        assert not (a_ci * col_w <= ba_x < (a_ci + 1) * col_w), (
            "Star Ba's table row must not be in the primary's (A's) column"
        )

    def test_companion_of_secondary_also_nested_in_primary_zone_near_parent(self):
        # Same seed as above. B is drawn as a dashed context marker inside
        # the primary's (zone 0) arc zone; Ba (B's own companion) should
        # *additionally* be drawn there too, as a small satellite orbit
        # nested next to B's own marker — not instead of, in addition to,
        # its proper placement in B's own zone (covered by the test above).
        system = generate_full_system(seed=1076570818)
        canvas_w = 1600
        svg, _ = build_svg(system, canvas_w=canvas_w)
        arc_zone_h = canvas_w * 2 // 3

        b_match = re.search(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>B</text>', svg)
        assert b_match is not None, "B's context-arc marker label not found in SVG"
        b_x, b_y = float(b_match.group(1)), float(b_match.group(2))
        assert 0 <= b_y < arc_zone_h, "B's own context marker should be in zone 0"

        ba_matches = [
            (float(m.group(1)), float(m.group(2)))
            for m in re.finditer(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>Ba</text>', svg)
        ]
        assert len(ba_matches) == 2, (
            f"expected exactly 2 Ba markers (own zone + nested in primary "
            f"zone), found {len(ba_matches)}"
        )

        zone0_ba = [(x, y) for x, y in ba_matches if 0 <= y < arc_zone_h]
        assert len(zone0_ba) == 1, "expected exactly one Ba marker nested in zone 0"
        ba_x, ba_y = zone0_ba[0]

        dist = ((ba_x - b_x) ** 2 + (ba_y - b_y) ** 2) ** 0.5
        assert dist < 150, (
            f"nested Ba marker ({ba_x:.1f},{ba_y:.1f}) should be close to its "
            f"parent B's marker ({b_x:.1f},{b_y:.1f}), got distance {dist:.1f}px"
        )

    def test_companion_of_primary_still_drawn_in_primary_zone(self):
        # Seed 3: A (primary), B (close secondary), Aa (companion of the
        # primary itself) — Aa orbiting A directly must still show up in A's
        # own zone, unaffected by the issue #171 fix.
        system = generate_full_system(seed=3)
        stars = system.stellar_system.stars
        desigs = [s.designation for s in stars]
        assert desigs == ["A", "B", "Aa"]
        assert stars[2].role == "companion"

        canvas_w = 1600
        svg, _ = build_svg(system, canvas_w=canvas_w)
        arc_zone_h = canvas_w * 2 // 3

        m = re.search(r'<text x="[\d.]+" y="([\d.]+)"[^>]*>Aa</text>', svg)
        assert m is not None, "Aa's context-arc marker label not found in SVG"
        aa_y = float(m.group(1))
        assert 0 <= aa_y < arc_zone_h, (
            "Aa's marker should stay in the primary's (A's) arc zone"
        )
