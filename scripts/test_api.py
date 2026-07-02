#!/usr/bin/env python3
"""
test_api.py — Live-server integration tests for the Traveller World Generator API.

Requires a running FastAPI server (local uvicorn or Azure Functions).
Uses pytest + requests — unlike tests/test_fastapi_app.py which uses TestClient
in-process, these tests hit a real HTTP listener and verify deployment health,
actual HTTP headers, and end-to-end behaviour.

Usage:
    # Local server (default http://localhost:8000):
    .venv/bin/pytest scripts/test_api.py -v

    # Azure Functions:
    BASE_URL=https://traveller-world-gen.azurewebsites.net \\
    FUNC_KEY=<key> \\
    .venv/bin/pytest scripts/test_api.py -v

    # Quick smoke-only run:
    .venv/bin/pytest scripts/test_api.py -v -m smoke

Test organisation
-----------------
  TestVersion               - /api/version shape
  TestSecurityHeaders       - HTTP security headers on every response
  TestWorldGeneration       - GET/POST /api/world — params, content, errors
  TestWorldDeterminism      - same seed → same world across calls
  TestWorldBatch            - POST /api/worlds — count, limits, content
  TestWorldCard             - GET /api/world/{name}/card — HTML output
  TestSystemGeneration      - GET/POST /api/system — flags, structure
  TestSystemDeterminism     - same seed → same system across calls
  TestSystemFlagInteraction - detail / nhz / ecc / incl flags change output
  TestSystemFull            - GET /api/system/full — json/text/html formats
  TestSystemCard            - GET /api/system/{name}/card — HTML output
  TestSystemFromWorld       - POST /api/system/from-world — UWP seeding
  TestSystemSvg             - GET /api/system/svg — SVG content
  TestErrorHandling         - 400/422/404 shapes and codes
  TestRateLimit             - 429 handler shape (requires SlowAPI active)
"""

import os
import sys

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration — read from env or use defaults
# ---------------------------------------------------------------------------

_BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
_FUNC_KEY = os.environ.get("FUNC_KEY", "")   # Azure Function key (?code=…)

SEED_A = 42
SEED_B = 99
NAME = "Cogri"
SAMPLE_UWP = "B667954-B"

# Top-level keys every world JSON response must contain.
WORLD_KEYS = {
    "name", "uwp", "starport", "size", "atmosphere", "temperature",
    "hydrographics", "population", "government", "law_level", "tech_level",
    "has_gas_giant", "gas_giant_count", "belt_count", "population_multiplier",
    "pbg", "bases", "trade_codes", "travel_zone", "notes", "seed",
}

# Top-level keys every system JSON response must contain.
SYSTEM_KEYS = {
    "star_count", "age_gyr", "stars", "orbits", "mainworld",
    "nhz_atmospheres", "orbital_eccentricity", "orbital_inclination",
    "seed", "_app_version",
}

# Keys inside the orbits dict (body["orbits"] is a dict, not a list).
ORBITS_DICT_KEYS = {
    "gas_giant_count", "belt_count", "terrestrial_count",
    "total_worlds", "empty_orbits", "star_zones", "orbits", "mainworld_orbit",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(path: str, params: dict | None = None) -> requests.Response:
    p = dict(params or {})
    if _FUNC_KEY:
        p["code"] = _FUNC_KEY
    return requests.get(f"{_BASE_URL}{path}", params=p, timeout=30)


def _post(path: str, body: dict, params: dict | None = None) -> requests.Response:
    p = dict(params or {})
    if _FUNC_KEY:
        p["code"] = _FUNC_KEY
    return requests.post(f"{_BASE_URL}{path}", json=body, params=p, timeout=30)


def _world(seed: int = SEED_A, name: str = NAME, **kw) -> requests.Response:
    return _get("/api/world", {"seed": seed, "name": name, **kw})


def _system(seed: int = SEED_A, name: str = NAME, **kw) -> requests.Response:
    return _get("/api/system", {"seed": seed, "name": name, **kw})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def world_a() -> dict:
    """Cached world JSON for seed SEED_A."""
    r = _world(SEED_A)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="session")
def system_a() -> dict:
    """Cached system JSON for seed SEED_A."""
    r = _system(SEED_A)
    assert r.status_code == 200
    return r.json()


# ===========================================================================
# TestVersion
# ===========================================================================

@pytest.mark.smoke
class TestVersion:
    def test_returns_200(self):
        assert _get("/api/version").status_code == 200

    def test_has_version_key(self):
        assert "version" in _get("/api/version").json()

    def test_version_is_string(self):
        v = _get("/api/version").json()["version"]
        assert isinstance(v, str) and len(v) > 0

    def test_content_type_json(self):
        assert "application/json" in _get("/api/version").headers["content-type"]


# ===========================================================================
# TestSecurityHeaders
# ===========================================================================

@pytest.mark.smoke
class TestSecurityHeaders:
    @pytest.fixture(autouse=True)
    def _response(self):
        self.r = _get("/api/version")

    def test_x_content_type_options(self):
        assert self.r.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self):
        assert self.r.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_content_security_policy_present(self):
        assert "Content-Security-Policy" in self.r.headers

    def test_csp_allows_jsdelivr(self):
        csp = self.r.headers["Content-Security-Policy"]
        csp_tokens = csp.replace(";", " ").split()
        assert "https://cdn.jsdelivr.net" in csp_tokens

    def test_csp_blocks_frame_ancestors(self):
        csp = self.r.headers["Content-Security-Policy"]
        assert "frame-ancestors 'self'" in csp


# ===========================================================================
# TestWorldGeneration
# ===========================================================================

class TestWorldGeneration:
    def test_get_returns_200(self):
        assert _world().status_code == 200

    def test_post_returns_200(self):
        r = _post("/api/world", {"seed": SEED_A, "name": NAME})
        assert r.status_code == 200

    def test_get_and_post_same_seed_same_world(self):
        get_uwp = _world().json()["uwp"]
        post_uwp = _post("/api/world", {"seed": SEED_A, "name": NAME}).json()["uwp"]
        assert get_uwp == post_uwp

    def test_response_has_all_required_keys(self, world_a):
        assert WORLD_KEYS <= world_a.keys()

    def test_seed_echoed_in_response(self, world_a):
        assert world_a["seed"] == SEED_A

    def test_name_set_in_response(self, world_a):
        assert world_a["name"] == NAME

    def test_uwp_format(self, world_a):
        uwp = world_a["uwp"]
        assert len(uwp) == 9 and uwp[7] == "-"

    def test_no_seed_auto_generates(self):
        r = _get("/api/world")
        assert r.status_code == 200
        body = r.json()
        assert "uwp" in body
        assert isinstance(body["seed"], int)

    def test_named_world_route(self):
        r = _get(f"/api/world/{NAME}", {"seed": SEED_A})
        assert r.status_code == 200
        assert r.json()["name"] == NAME

    def test_name_too_long_returns_error(self):
        r = _get("/api/world", {"seed": SEED_A, "name": "X" * 200})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "NAME_TOO_LONG"

    def test_invalid_seed_returns_error(self):
        r = _get("/api/world", {"seed": "notanumber"})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "INVALID_SEED"

    def test_trade_codes_is_list(self, world_a):
        assert isinstance(world_a["trade_codes"], list)

    def test_starport_has_code_and_description(self, world_a):
        sp = world_a["starport"]
        assert "code" in sp and "description" in sp

    def test_size_has_code_and_diameter(self, world_a):
        sz = world_a["size"]
        assert "code" in sz and "diameter_km" in sz

    def test_atmosphere_has_code_and_name(self, world_a):
        atm = world_a["atmosphere"]
        assert "code" in atm and "name" in atm


# ===========================================================================
# TestWorldDeterminism
# ===========================================================================

class TestWorldDeterminism:
    def test_same_seed_same_uwp(self):
        uwp1 = _world(SEED_A).json()["uwp"]
        uwp2 = _world(SEED_A).json()["uwp"]
        assert uwp1 == uwp2

    def test_same_seed_same_trade_codes(self):
        tc1 = _world(SEED_A).json()["trade_codes"]
        tc2 = _world(SEED_A).json()["trade_codes"]
        assert tc1 == tc2

    def test_different_seeds_usually_differ(self):
        uwp_a = _world(SEED_A).json()["uwp"]
        uwp_b = _world(SEED_B).json()["uwp"]
        # Different seeds almost always produce different worlds
        assert uwp_a != uwp_b

    def test_get_and_post_deterministic(self):
        get_body = _world(SEED_A).json()
        post_body = _post("/api/world", {"seed": SEED_A, "name": NAME}).json()
        assert get_body["uwp"] == post_body["uwp"]
        assert get_body["trade_codes"] == post_body["trade_codes"]


# ===========================================================================
# TestWorldBatch
# ===========================================================================

class TestWorldBatch:
    def test_returns_200(self):
        r = _post("/api/worlds", {"count": 3, "seed": SEED_A})
        assert r.status_code == 200

    def test_response_has_worlds_key(self):
        r = _post("/api/worlds", {"count": 3, "seed": SEED_A})
        assert "worlds" in r.json()

    def test_correct_count_returned(self):
        r = _post("/api/worlds", {"count": 5, "seed": SEED_A})
        assert len(r.json()["worlds"]) == 5

    def test_count_one_returns_one_world(self):
        r = _post("/api/worlds", {"count": 1, "seed": SEED_A})
        assert len(r.json()["worlds"]) == 1

    def test_worlds_have_uwp(self):
        worlds = _post("/api/worlds", {"count": 3, "seed": SEED_A}).json()["worlds"]
        for w in worlds:
            assert "uwp" in w

    def test_batch_is_deterministic(self):
        batch1 = _post("/api/worlds", {"count": 3, "seed": SEED_A}).json()["worlds"]
        batch2 = _post("/api/worlds", {"count": 3, "seed": SEED_A}).json()["worlds"]
        assert [w["uwp"] for w in batch1] == [w["uwp"] for w in batch2]

    def test_prefix_applied_to_names(self):
        worlds = _post("/api/worlds", {
            "count": 3, "seed": SEED_A, "prefix": "Test-"
        }).json()["worlds"]
        assert all(w["name"].startswith("Test-") for w in worlds)

    def test_count_too_large_returns_422(self):
        r = _post("/api/worlds", {"count": 9999, "seed": SEED_A})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "COUNT_TOO_LARGE"

    def test_count_zero_returns_error(self):
        r = _post("/api/worlds", {"count": 0, "seed": SEED_A})
        assert r.status_code in (400, 422)

    def test_missing_count_defaults_to_one(self):
        # count is optional; defaults to 1 when absent.
        r = _post("/api/worlds", {"seed": SEED_A})
        assert r.status_code == 200
        assert len(r.json()["worlds"]) == 1

    def test_response_seed_echoed(self):
        r = _post("/api/worlds", {"count": 2, "seed": SEED_A})
        assert r.json()["seed"] == SEED_A


# ===========================================================================
# TestWorldCard
# ===========================================================================

class TestWorldCard:
    def test_returns_html(self):
        r = _get(f"/api/world/{NAME}/card", {"seed": SEED_A})
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_contains_world_name(self):
        r = _get(f"/api/world/{NAME}/card", {"seed": SEED_A})
        assert NAME in r.text

    def test_minimal_card_no_world_body_section(self):
        r = _get(f"/api/world/{NAME}/card", {"seed": SEED_A})
        assert r.status_code == 200

    def test_detail_true_returns_html(self):
        r = _get(f"/api/world/{NAME}/card", {"seed": SEED_A, "detail": "true"})
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_detail_card_contains_name(self):
        r = _get(f"/api/world/{NAME}/card", {"seed": SEED_A, "detail": "true"})
        assert NAME in r.text


# ===========================================================================
# TestSystemGeneration
# ===========================================================================

class TestSystemGeneration:
    def test_get_returns_200(self):
        assert _system().status_code == 200

    def test_post_returns_200(self):
        r = _post("/api/system", {"seed": SEED_A, "name": NAME})
        assert r.status_code == 200

    def test_response_has_required_keys(self, system_a):
        assert SYSTEM_KEYS <= system_a.keys()

    def test_stars_is_non_empty_list(self, system_a):
        assert isinstance(system_a["stars"], list)
        assert len(system_a["stars"]) >= 1

    def test_orbits_is_dict_with_orbit_list(self, system_a):
        # body["orbits"] is a summary dict; body["orbits"]["orbits"] is the slot list.
        assert isinstance(system_a["orbits"], dict)
        assert isinstance(system_a["orbits"]["orbits"], list)

    def test_orbits_dict_has_expected_keys(self, system_a):
        assert ORBITS_DICT_KEYS <= system_a["orbits"].keys()

    def test_mainworld_is_dict(self, system_a):
        assert isinstance(system_a["mainworld"], dict)

    def test_mainworld_has_uwp(self, system_a):
        assert "uwp" in system_a["mainworld"]

    def test_seed_echoed(self, system_a):
        assert system_a["seed"] == SEED_A

    def test_age_gyr_is_positive(self, system_a):
        assert system_a["age_gyr"] > 0

    def test_star_has_classification(self, system_a):
        star = system_a["stars"][0]
        assert "classification" in star

    def test_named_route(self):
        r = _get(f"/api/system/{NAME}", {"seed": SEED_A})
        assert r.status_code == 200
        assert "mainworld" in r.json()

    def test_get_post_same_seed_same_mainworld(self):
        get_uwp = _system().json()["mainworld"]["uwp"]
        post_uwp = _post("/api/system", {"seed": SEED_A, "name": NAME}).json()["mainworld"]["uwp"]
        assert get_uwp == post_uwp


# ===========================================================================
# TestSystemDeterminism
# ===========================================================================

class TestSystemDeterminism:
    def test_same_seed_same_mainworld_uwp(self):
        uwp1 = _system(SEED_A).json()["mainworld"]["uwp"]
        uwp2 = _system(SEED_A).json()["mainworld"]["uwp"]
        assert uwp1 == uwp2

    def test_same_seed_same_star_count(self):
        sc1 = _system(SEED_A).json()["star_count"]
        sc2 = _system(SEED_A).json()["star_count"]
        assert sc1 == sc2

    def test_same_seed_same_orbit_count(self):
        oc1 = len(_system(SEED_A).json()["orbits"])
        oc2 = len(_system(SEED_A).json()["orbits"])
        assert oc1 == oc2

    def test_different_seeds_usually_differ(self):
        uwp_a = _system(SEED_A).json()["mainworld"]["uwp"]
        uwp_b = _system(SEED_B).json()["mainworld"]["uwp"]
        assert uwp_a != uwp_b


# ===========================================================================
# TestSystemFlagInteraction
# ===========================================================================

class TestSystemFlagInteraction:
    def test_detail_true_adds_orbit_detail(self):
        r = _get("/api/system", {"seed": SEED_A, "detail": "true"})
        assert r.status_code == 200
        slots = r.json()["orbits"]["orbits"]
        assert any(o.get("detail") is not None for o in slots)

    def test_detail_false_orbits_have_no_detail(self):
        r = _get("/api/system", {"seed": SEED_A, "detail": "false"})
        slots = r.json()["orbits"]["orbits"]
        assert all(o.get("detail") is None for o in slots)

    def test_orbital_eccentricity_flag(self):
        r = _get("/api/system", {"seed": SEED_A, "orbital_eccentricity": "true"})
        assert r.status_code == 200
        body = r.json()
        assert body["orbital_eccentricity"] is True

    def test_orbital_inclination_flag(self):
        r = _get("/api/system", {"seed": SEED_A, "orbital_inclination": "true"})
        assert r.status_code == 200
        body = r.json()
        assert body["orbital_inclination"] is True

    def test_nhz_atmospheres_flag_accepted(self):
        r = _get("/api/system", {"seed": SEED_A, "nhz_atmospheres": "true"})
        assert r.status_code == 200

    def test_ecc_flag_true_echoed_in_response(self):
        body = _get("/api/system", {"seed": SEED_A, "orbital_eccentricity": "true"}).json()
        assert body["orbital_eccentricity"] is True

    def test_ecc_flag_false_echoed_in_response(self):
        body = _get("/api/system", {"seed": SEED_A, "orbital_eccentricity": "false"}).json()
        assert body["orbital_eccentricity"] is False


# ===========================================================================
# TestSystemFull
# ===========================================================================

class TestSystemFull:
    def test_json_format_returns_200(self):
        r = _get("/api/system/full", {"seed": SEED_A})
        assert r.status_code == 200
        assert "application/json" in r.headers["content-type"]

    def test_json_has_system_keys(self):
        body = _get("/api/system/full", {"seed": SEED_A}).json()
        assert SYSTEM_KEYS <= body.keys()

    def test_text_format_returns_plain_text(self):
        r = _get("/api/system/full", {"seed": SEED_A, "format": "text"})
        assert r.status_code == 200
        assert "text/plain" in r.headers["content-type"]

    def test_text_format_contains_star_header(self):
        r = _get("/api/system/full", {"seed": SEED_A, "format": "text"})
        assert "Star" in r.text or "star" in r.text.lower()

    def test_html_format_returns_html(self):
        r = _get("/api/system/full", {"seed": SEED_A, "format": "html"})
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_html_format_contains_table(self):
        r = _get("/api/system/full", {"seed": SEED_A, "format": "html"})
        assert "<table" in r.text.lower()

    def test_full_always_has_detail(self):
        body = _get("/api/system/full", {"seed": SEED_A}).json()
        slots = body["orbits"]["orbits"]
        # /api/system/full always runs attach_detail
        assert any(o.get("detail") is not None for o in slots)

    def test_post_full_json(self):
        r = _post("/api/system/full", {"seed": SEED_A, "name": NAME})
        assert r.status_code == 200
        assert "mainworld" in r.json()

    def test_full_deterministic(self):
        uwp1 = _get("/api/system/full", {"seed": SEED_A}).json()["mainworld"]["uwp"]
        uwp2 = _get("/api/system/full", {"seed": SEED_A}).json()["mainworld"]["uwp"]
        assert uwp1 == uwp2

    def test_unknown_format_falls_back_to_json(self):
        # Unknown format values are silently treated as json.
        r = _get("/api/system/full", {"seed": SEED_A, "format": "pdf"})
        assert r.status_code == 200
        assert "mainworld" in r.json()


# ===========================================================================
# TestSystemCard
# ===========================================================================

class TestSystemCard:
    def test_returns_html(self):
        r = _get(f"/api/system/{NAME}/card", {"seed": SEED_A})
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_contains_world_name(self):
        r = _get(f"/api/system/{NAME}/card", {"seed": SEED_A})
        assert NAME in r.text

    def test_contains_table_element(self):
        r = _get(f"/api/system/{NAME}/card", {"seed": SEED_A})
        assert "<table" in r.text.lower()


# ===========================================================================
# TestSystemFromWorld
# ===========================================================================

class TestSystemFromWorld:
    def test_returns_200(self):
        r = _post("/api/system/from-world", {"uwp": SAMPLE_UWP, "name": NAME, "seed": SEED_A})
        assert r.status_code == 200

    def test_has_system_keys(self):
        r = _post("/api/system/from-world", {"uwp": SAMPLE_UWP, "name": NAME, "seed": SEED_A})
        assert SYSTEM_KEYS <= r.json().keys()

    def test_mainworld_name_matches_input(self):
        r = _post("/api/system/from-world", {"uwp": SAMPLE_UWP, "name": NAME, "seed": SEED_A})
        # The system is generated around the provided world; the mainworld name is preserved.
        assert r.json()["mainworld"]["name"] == NAME

    def test_missing_uwp_returns_error(self):
        r = _post("/api/system/from-world", {"name": NAME, "seed": SEED_A})
        assert r.status_code in (400, 422)

    def test_deterministic(self):
        body = {"uwp": SAMPLE_UWP, "name": NAME, "seed": SEED_A}
        stars1 = _post("/api/system/from-world", body).json()["star_count"]
        stars2 = _post("/api/system/from-world", body).json()["star_count"]
        assert stars1 == stars2


# ===========================================================================
# TestSystemSvg
# ===========================================================================

class TestSystemSvg:
    def test_returns_svg(self):
        r = _get("/api/system/svg", {"seed": SEED_A, "name": NAME})
        assert r.status_code == 200
        assert "image/svg+xml" in r.headers["content-type"]

    def test_body_is_svg(self):
        r = _get("/api/system/svg", {"seed": SEED_A, "name": NAME})
        assert r.text.strip().startswith("<svg") or "<?xml" in r.text

    def test_perspective_flag_accepted(self):
        r = _get("/api/system/svg", {"seed": SEED_A, "name": NAME, "perspective": "true"})
        assert r.status_code == 200
        assert "image/svg+xml" in r.headers["content-type"]

    def test_missing_name_returns_error(self):
        r = _get("/api/system/svg", {"seed": SEED_A})
        assert r.status_code == 400

    def test_deterministic(self):
        svg1 = _get("/api/system/svg", {"seed": SEED_A, "name": NAME}).text
        svg2 = _get("/api/system/svg", {"seed": SEED_A, "name": NAME}).text
        assert svg1 == svg2


# ===========================================================================
# TestErrorHandling
# ===========================================================================

@pytest.mark.smoke
class TestErrorHandling:
    def test_unknown_route_returns_404(self):
        r = _get("/api/does-not-exist")
        assert r.status_code == 404

    def test_404_is_json(self):
        r = _get("/api/does-not-exist")
        assert "application/json" in r.headers["content-type"]

    def test_invalid_seed_error_code(self):
        r = _get("/api/world", {"seed": "abc"})
        assert r.json()["error"]["code"] == "INVALID_SEED"

    def test_name_too_long_error_code(self):
        r = _get("/api/world", {"seed": SEED_A, "name": "X" * 200})
        assert r.json()["error"]["code"] == "NAME_TOO_LONG"

    def test_batch_count_too_large_error_code(self):
        r = _post("/api/worlds", {"count": 9999, "seed": SEED_A})
        assert r.json()["error"]["code"] == "COUNT_TOO_LARGE"

    def test_error_response_shape(self):
        r = _get("/api/world", {"seed": "bad"})
        body = r.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_system_svg_missing_name_error(self):
        r = _get("/api/system/svg", {"seed": SEED_A})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "MISSING_PARAM"


# ===========================================================================
# TestRateLimit
# ===========================================================================

class TestRateLimit:
    """
    Rate limit tests send many rapid requests to trigger the 429 handler.
    Only meaningful if RATE_LIMIT_PER_MINUTE is set low (e.g. 5/minute).
    Skipped automatically if the server rate limit is the default 100/minute.
    """

    def test_rate_limit_response_shape(self):
        """Send 120 rapid requests; if we hit a 429 verify its shape."""
        for _ in range(120):
            r = _get("/api/version")
            if r.status_code == 429:
                body = r.json()
                assert "error" in body
                assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
                return
        pytest.skip("Rate limit not triggered at default 100/minute threshold")


# ---------------------------------------------------------------------------
# Entry point for direct execution (non-pytest)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import subprocess
    sys.exit(subprocess.call(
        [sys.executable, "-m", "pytest", __file__, "-v"] + sys.argv[1:]
    ))
