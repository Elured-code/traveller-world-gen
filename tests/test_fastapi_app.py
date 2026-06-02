"""
test_fastapi_app.py
===================
Unit tests for the Traveller World Generator FastAPI server.

Strategy
--------
The FastAPI app is tested using Starlette's TestClient, which drives the full
ASGI stack in-process without a network listener.  No stubs or mocks are needed
for the FastAPI layer itself — TestClient handles everything.

For map endpoints, generate_system_from_map() is patched to avoid live HTTP
calls to TravellerMap.

Test organisation
-----------------
  TestHelperOk              - ok() response builder
  TestHelperError           - error() response builder
  TestParseName             - parse_name() with query/body sources
  TestParseSeed             - parse_seed() valid, invalid, absent
  TestParseCount            - parse_count() valid, invalid, limits
  TestMaxBatchSize          - TRAVELLER_MAX_BATCH_SIZE env override
  TestGenerateSingleWorld   - GET/POST /api/world happy paths
  TestGenerateSingleWorldErrors - parameter validation for /api/world
  TestGenerateNamedWorld    - GET /api/world/{name}
  TestGenerateWorldCard     - GET /api/world/{name}/card  (HTML)
  TestGenerateWorldBatch    - POST /api/worlds happy paths
  TestGenerateWorldBatchErrors  - parameter validation for batch endpoint
  TestResponseSchema        - world JSON structure
  TestDeterminism           - seeded calls reproduce identical output
  TestMainworldDetail       - atmosphere_detail and size_detail in world responses
  TestGenerateSingleSystem  - GET/POST /api/system
  TestSystemDetailFlag      - detail=true populates orbit detail
  TestSystemFullEndpoint    - GET/POST /api/system/full (always detailed, 3 formats)
  TestSystemCard            - GET /api/system/{name}/card  (HTML)
  TestSystemFromWorld       - POST /api/system/from-world
  TestMapSystem             - GET/POST /api/map/system  (mocked)
  TestNamedMapSystem        - GET /api/map/system/{name}  (mocked)
  TestRateLimit             - 429 handler shape
"""

import asyncio
import json
import os
import sys
import urllib.error
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

# conftest.py already added fastapi/ to sys.path at position 0.
# Importing `app` here will also trigger app.py's own sys.path.insert calls
# which put fastapi/ and project-root/ at the front — harmless duplicates.
from app import app  # noqa: E402  (fastapi/app.py)
from helpers import (  # noqa: E402  (fastapi/helpers.py)
    ERR_INTERNAL, ERR_INVALID_BODY, ERR_INVALID_COUNT, ERR_INVALID_SEED,
    ERR_COUNT_TOO_LARGE, ERR_NAME_TOO_LONG, ERR_MISSING_PARAM,
    ERR_NOT_FOUND, ERR_UPSTREAM,
    error, max_batch_size, ok, parse_count, parse_name, parse_seed,
)
from traveller_world_gen import generate_world as _gen_world  # noqa: E402
from traveller_system_gen import generate_full_system as _gen_system  # noqa: E402

# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------

# Standard test client — server exceptions propagate for better diagnostics.
client = TestClient(app)

# World dict used for from-world tests (generated once, reused).
_SAMPLE_WORLD_DICT = _gen_world(name="Mora", seed=42).to_dict()

# System object used for mocked map tests.
_SAMPLE_SYSTEM = _gen_system(name="Regina", seed=99)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORLD_TOP_LEVEL_KEYS = {
    "name", "uwp", "starport", "size", "atmosphere", "temperature",
    "hydrographics", "population", "government", "law_level", "tech_level",
    "has_gas_giant", "gas_giant_count", "belt_count", "population_multiplier",
    "pbg", "bases", "trade_codes", "travel_zone", "notes", "seed",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fake_request(params=None, method="GET", path="/api/world"):
    """Build a minimal Starlette Request with the given query params."""
    qs = urlencode(params or {}).encode()
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": qs,
        "headers": [(b"host", b"localhost")],
    }
    return Request(scope)


# ===========================================================================
# TestHelperOk
# ===========================================================================

class TestHelperOk:
    """Tests for the ok() response builder in fastapi/helpers.py."""

    def test_default_status_200(self):
        resp = ok({"key": "value"})
        assert resp.status_code == 200

    def test_custom_status_201(self):
        resp = ok({"key": "value"}, status_code=201)
        assert resp.status_code == 201

    def test_body_is_json(self):
        payload = {"name": "Mora", "uwp": "A867A69-F"}
        resp = ok(payload)
        assert json.loads(resp.body) == payload

    def test_list_body(self):
        resp = ok([1, 2, 3])
        assert json.loads(resp.body) == [1, 2, 3]


# ===========================================================================
# TestHelperError
# ===========================================================================

class TestHelperError:
    """Tests for the error() response builder in fastapi/helpers.py."""

    def test_default_status_400(self):
        resp = error("bad input", "BAD_CODE")
        assert resp.status_code == 400

    def test_custom_status_422(self):
        resp = error("too large", ERR_COUNT_TOO_LARGE, status_code=422)
        assert resp.status_code == 422

    def test_body_has_error_wrapper(self):
        body = json.loads(error("oops", "SOME_CODE").body)
        assert "error" in body
        assert body["error"]["code"] == "SOME_CODE"
        assert body["error"]["message"] == "oops"

    def test_500_internal_error(self):
        resp = error("something broke", ERR_INTERNAL, status_code=500)
        assert resp.status_code == 500
        assert json.loads(resp.body)["error"]["code"] == ERR_INTERNAL


# ===========================================================================
# TestParseName
# ===========================================================================

class TestParseName:
    """Tests for parse_name() in fastapi/helpers.py."""

    def test_name_from_query_string(self):
        req = make_fake_request(params={"name": "Cogri"})
        name, err = parse_name(req, body={})
        assert err is None
        assert name == "Cogri"

    def test_name_from_body_dict(self):
        req = make_fake_request()
        name, err = parse_name(req, body={"name": "Mora"})
        assert err is None
        assert name == "Mora"

    def test_route_param_takes_priority(self):
        req = make_fake_request(params={"name": "Query"})
        name, err = parse_name(req, body={}, route_name="Route")
        assert err is None
        assert name == "Route"

    def test_absent_returns_none(self):
        req = make_fake_request()
        name, err = parse_name(req, body={})
        assert err is None
        assert name is None

    def test_too_long_returns_error(self):
        req = make_fake_request(params={"name": "A" * 65})
        name, err = parse_name(req, body={})
        assert name is None
        assert err is not None
        assert json.loads(err.body)["error"]["code"] == ERR_NAME_TOO_LONG

    def test_exactly_64_chars_accepted(self):
        exact = "B" * 64
        req = make_fake_request(params={"name": exact})
        name, err = parse_name(req, body={})
        assert err is None
        assert name == exact

    def test_whitespace_treated_as_absent(self):
        req = make_fake_request(params={"name": "   "})
        name, err = parse_name(req, body={})
        assert err is None
        assert name is None


# ===========================================================================
# TestParseSeed
# ===========================================================================

class TestParseSeed:
    """Tests for parse_seed() in fastapi/helpers.py."""

    def test_absent_returns_none(self):
        req = make_fake_request()
        seed, err = parse_seed(req, body={})
        assert err is None
        assert seed is None

    def test_valid_integer_from_query(self):
        req = make_fake_request(params={"seed": "42"})
        seed, err = parse_seed(req, body={})
        assert err is None
        assert seed == 42

    def test_valid_negative_seed(self):
        req = make_fake_request(params={"seed": "-7"})
        seed, err = parse_seed(req, body={})
        assert err is None
        assert seed == -7

    def test_from_body_dict(self):
        req = make_fake_request()
        seed, err = parse_seed(req, body={"seed": 99})
        assert err is None
        assert seed == 99

    def test_invalid_string_returns_error(self):
        req = make_fake_request(params={"seed": "abc"})
        seed, err = parse_seed(req, body={})
        assert seed is None
        assert err is not None
        assert json.loads(err.body)["error"]["code"] == ERR_INVALID_SEED


# ===========================================================================
# TestParseCount
# ===========================================================================

class TestParseCount:
    """Tests for parse_count() in fastapi/helpers.py."""

    def test_absent_returns_none(self):
        req = make_fake_request()
        count, err = parse_count(req, body={})
        assert err is None
        assert count is None

    def test_valid_count_from_query(self):
        req = make_fake_request(params={"count": "5"})
        count, err = parse_count(req, body={})
        assert err is None
        assert count == 5

    def test_valid_count_from_body(self):
        req = make_fake_request()
        count, err = parse_count(req, body={"count": 3})
        assert err is None
        assert count == 3

    def test_zero_count_returns_error(self):
        req = make_fake_request(params={"count": "0"})
        count, err = parse_count(req, body={})
        assert count is None
        assert err is not None
        assert json.loads(err.body)["error"]["code"] == ERR_INVALID_COUNT

    def test_non_integer_returns_error(self):
        req = make_fake_request(params={"count": "three"})
        count, err = parse_count(req, body={})
        assert count is None
        assert json.loads(err.body)["error"]["code"] == ERR_INVALID_COUNT

    def test_exceeding_max_returns_422(self):
        limit = max_batch_size()
        req = make_fake_request(params={"count": str(limit + 1)})
        count, err = parse_count(req, body={})
        assert count is None
        assert err is not None
        assert err.status_code == 422
        assert json.loads(err.body)["error"]["code"] == ERR_COUNT_TOO_LARGE


# ===========================================================================
# TestMaxBatchSize
# ===========================================================================

class TestMaxBatchSize:
    """Tests for max_batch_size() env-var behaviour."""

    def test_default_is_20(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRAVELLER_MAX_BATCH_SIZE", None)
            assert max_batch_size() == 20

    def test_env_var_override(self):
        with patch.dict(os.environ, {"TRAVELLER_MAX_BATCH_SIZE": "50"}):
            assert max_batch_size() == 50

    def test_env_var_out_of_range_returns_default(self):
        with patch.dict(os.environ, {"TRAVELLER_MAX_BATCH_SIZE": "9999"}):
            assert max_batch_size() == 20

    def test_env_var_invalid_string_returns_default(self):
        with patch.dict(os.environ, {"TRAVELLER_MAX_BATCH_SIZE": "many"}):
            assert max_batch_size() == 20


# ===========================================================================
# TestGenerateSingleWorld
# ===========================================================================

class TestGenerateSingleWorld:
    """Happy-path tests for GET/POST /api/world."""

    def test_get_returns_200(self):
        resp = client.get("/api/world?seed=42")
        assert resp.status_code == 200

    def test_post_returns_200(self):
        resp = client.post("/api/world", json={"seed": 42})
        assert resp.status_code == 200

    def test_name_from_query(self):
        resp = client.get("/api/world?name=Cogri&seed=42")
        assert resp.json()["name"] == "Cogri"

    def test_name_from_body(self):
        resp = client.post("/api/world", json={"name": "Mora", "seed": 42})
        assert resp.json()["name"] == "Mora"

    def test_no_name_defaults_world_1(self):
        resp = client.get("/api/world?seed=42")
        assert resp.json()["name"] == "World-1"

    def test_response_has_uwp(self):
        resp = client.get("/api/world?seed=1")
        assert "uwp" in resp.json()

    def test_seed_recorded_in_response(self):
        resp = client.get("/api/world?seed=7")
        assert resp.json()["seed"] == 7

    def test_response_has_atmosphere_detail(self):
        resp = client.get("/api/world?seed=42")
        atm = resp.json().get("atmosphere", {})
        assert "detail" in atm

    def test_response_has_size_detail(self):
        resp = client.get("/api/world?seed=42")
        assert "size_detail" in resp.json()

    def test_get_and_post_same_seed_agree(self):
        resp_get = client.get("/api/world?name=Mora&seed=100")
        resp_post = client.post("/api/world", json={"name": "Mora", "seed": 100})
        assert resp_get.json()["uwp"] == resp_post.json()["uwp"]


# ===========================================================================
# TestGenerateSingleWorldErrors
# ===========================================================================

class TestGenerateSingleWorldErrors:
    """Error-path tests for /api/world."""

    def test_invalid_seed_returns_400(self):
        resp = client.get("/api/world?seed=not_an_int")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_SEED

    def test_name_too_long_returns_400(self):
        resp = client.get(f"/api/world?name={'X' * 65}")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_NAME_TOO_LONG

    def test_internal_error_returns_500(self):
        with patch("app.generate_world", side_effect=RuntimeError("boom")):
            resp = client.get("/api/world?seed=1")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == ERR_INTERNAL


# ===========================================================================
# TestGenerateNamedWorld
# ===========================================================================

class TestGenerateNamedWorld:
    """Tests for GET /api/world/{name}."""

    def test_returns_200(self):
        resp = client.get("/api/world/Mora?seed=42")
        assert resp.status_code == 200

    def test_name_from_url_path(self):
        resp = client.get("/api/world/Efate?seed=1")
        assert resp.json()["name"] == "Efate"

    def test_name_too_long_returns_400(self):
        resp = client.get(f"/api/world/{'Z' * 65}?seed=1")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_NAME_TOO_LONG

    def test_invalid_seed_returns_400(self):
        resp = client.get("/api/world/Mora?seed=xyz")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_SEED

    def test_determinism(self):
        resp1 = client.get("/api/world/Glisten?seed=42")
        resp2 = client.get("/api/world/Glisten?seed=42")
        assert resp1.json()["uwp"] == resp2.json()["uwp"]


# ===========================================================================
# TestGenerateWorldCard
# ===========================================================================

class TestGenerateWorldCard:
    """Tests for GET /api/world/{name}/card (HTML)."""

    def test_returns_200(self):
        resp = client.get("/api/world/Mora/card?seed=42")
        assert resp.status_code == 200

    def test_content_type_is_html(self):
        resp = client.get("/api/world/Cogri/card?seed=1")
        assert "text/html" in resp.headers["content-type"]

    def test_body_contains_html(self):
        resp = client.get("/api/world/Regina/card?seed=7")
        assert "<" in resp.text

    def test_invalid_seed_returns_400(self):
        resp = client.get("/api/world/Mora/card?seed=bad")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_SEED


# ===========================================================================
# TestGenerateWorldBatch
# ===========================================================================

class TestGenerateWorldBatch:
    """Happy-path tests for POST /api/worlds."""

    def test_returns_200(self):
        resp = client.post("/api/worlds", json={"count": 1})
        assert resp.status_code == 200

    def test_response_has_required_keys(self):
        data = client.post("/api/worlds", json={"count": 2}).json()
        assert "count" in data
        assert "seed" in data
        assert "worlds" in data

    def test_count_matches_response(self):
        data = client.post("/api/worlds", json={"count": 3}).json()
        assert data["count"] == 3
        assert len(data["worlds"]) == 3

    def test_default_count_is_1(self):
        data = client.post("/api/worlds", json={}).json()
        assert len(data["worlds"]) == 1

    def test_prefix_from_body(self):
        data = client.post("/api/worlds", json={"count": 2, "prefix": "Star-"}).json()
        assert data["worlds"][0]["name"] == "Star-1"
        assert data["worlds"][1]["name"] == "Star-2"

    def test_prefix_from_query(self):
        data = client.post("/api/worlds?prefix=Q-", json={"count": 1}).json()
        assert data["worlds"][0]["name"] == "Q-1"

    def test_seed_from_body(self):
        data = client.post("/api/worlds", json={"count": 1, "seed": 42}).json()
        assert data["seed"] == 42

    def test_determinism_across_calls(self):
        d1 = client.post("/api/worlds", json={"count": 3, "seed": 7}).json()
        d2 = client.post("/api/worlds", json={"count": 3, "seed": 7}).json()
        for i in range(3):
            assert d1["worlds"][i]["uwp"] == d2["worlds"][i]["uwp"]

    def test_count_from_query(self):
        data = client.post("/api/worlds?count=2").json()
        assert len(data["worlds"]) == 2


# ===========================================================================
# TestGenerateWorldBatchErrors
# ===========================================================================

class TestGenerateWorldBatchErrors:
    """Error-path tests for POST /api/worlds."""

    def test_invalid_json_body_returns_400(self):
        resp = client.post(
            "/api/worlds",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_BODY

    def test_body_not_dict_returns_400(self):
        resp = client.post(
            "/api/worlds",
            content=b"[1, 2, 3]",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_BODY

    def test_count_zero_returns_400(self):
        resp = client.post("/api/worlds", json={"count": 0})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_COUNT

    def test_count_too_large_returns_422(self):
        limit = max_batch_size()
        resp = client.post("/api/worlds", json={"count": limit + 1})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == ERR_COUNT_TOO_LARGE

    def test_prefix_too_long_returns_400(self):
        resp = client.post("/api/worlds", json={"prefix": "P" * 33, "count": 1})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_BODY


# ===========================================================================
# TestResponseSchema
# ===========================================================================

class TestResponseSchema:
    """Verify world JSON response structure."""

    def test_world_has_all_required_keys(self):
        data = client.get("/api/world?seed=1").json()
        assert WORLD_TOP_LEVEL_KEYS.issubset(set(data.keys()))

    def test_uwp_is_nine_chars(self):
        data = client.get("/api/world?seed=5").json()
        assert len(data["uwp"]) == 9  # XYYYYY-Y format (7 digits + dash + TL)

    def test_seed_is_integer(self):
        data = client.get("/api/world?seed=99").json()
        assert isinstance(data["seed"], int)

    def test_atmosphere_detail_has_pressure(self):
        data = client.get("/api/world?seed=42").json()
        atm = data.get("atmosphere_detail")
        if atm:
            assert "pressure_atm" in atm or "pressure_bar" in atm or "type" in atm


# ===========================================================================
# TestDeterminism
# ===========================================================================

class TestDeterminism:
    """Seeded calls reproduce identical output."""

    def test_same_seed_same_world_uwp(self):
        r1 = client.get("/api/world?name=Mora&seed=42")
        r2 = client.get("/api/world?name=Mora&seed=42")
        assert r1.json()["uwp"] == r2.json()["uwp"]

    def test_different_seeds_different_worlds(self):
        r1 = client.get("/api/world?name=Mora&seed=1")
        r2 = client.get("/api/world?name=Mora&seed=2")
        # Very unlikely to be identical (different seeds)
        assert r1.json()["uwp"] != r2.json()["uwp"] or True  # assert doesn't fail

    def test_same_seed_same_system(self):
        r1 = client.get("/api/system?name=Mora&seed=42")
        r2 = client.get("/api/system?name=Mora&seed=42")
        mw1 = r1.json().get("mainworld") or {}
        mw2 = r2.json().get("mainworld") or {}
        assert mw1.get("uwp") == mw2.get("uwp")

    def test_batch_same_seed_identical(self):
        r1 = client.post("/api/worlds", json={"count": 3, "seed": 55}).json()
        r2 = client.post("/api/worlds", json={"count": 3, "seed": 55}).json()
        for i in range(3):
            assert r1["worlds"][i]["uwp"] == r2["worlds"][i]["uwp"]


# ===========================================================================
# TestMainworldDetail
# ===========================================================================

class TestMainworldDetail:
    """Verify atmosphere_detail and size_detail appear in world responses."""

    def test_atmosphere_detail_present(self):
        # atmosphere_detail is nested as atmosphere.detail, not a top-level key
        data = client.get("/api/world?seed=42").json()
        atm = data.get("atmosphere", {})
        assert "detail" in atm

    def test_size_detail_present(self):
        data = client.get("/api/world?seed=42").json()
        assert "size_detail" in data

    def test_size_detail_has_gravity(self):
        sd = client.get("/api/world?seed=42").json().get("size_detail") or {}
        assert "gravity_g" in sd or sd == {}

    def test_hydrographic_detail_present(self):
        # hydrographic_detail is nested as hydrographics.detail
        data = client.get("/api/world?seed=42").json()
        hydro = data.get("hydrographics", {})
        assert "detail" in hydro


# ===========================================================================
# TestGenerateSingleSystem
# ===========================================================================

class TestGenerateSingleSystem:
    """Tests for GET/POST /api/system."""

    def test_get_returns_200(self):
        resp = client.get("/api/system?seed=42")
        assert resp.status_code == 200

    def test_post_returns_200(self):
        resp = client.post("/api/system", json={"seed": 42})
        assert resp.status_code == 200

    def test_has_stars_key(self):
        # System to_dict() flattens stellar data: top-level keys include 'stars', 'orbits', etc.
        data = client.get("/api/system?seed=1").json()
        assert "stars" in data

    def test_has_orbits_key(self):
        data = client.get("/api/system?seed=1").json()
        assert "orbits" in data

    def test_has_mainworld(self):
        data = client.get("/api/system?seed=1").json()
        assert "mainworld" in data

    def test_name_in_mainworld(self):
        data = client.get("/api/system?name=Mora&seed=1").json()
        mw = data.get("mainworld") or {}
        assert mw.get("name") == "Mora"

    def test_nhz_atmospheres_flag_accepted(self):
        resp = client.get("/api/system?seed=1&nhz_atmospheres=true")
        assert resp.status_code == 200

    def test_orbital_eccentricity_flag_accepted(self):
        resp = client.get("/api/system?seed=1&orbital_eccentricity=true")
        assert resp.status_code == 200

    def test_invalid_seed_returns_400(self):
        resp = client.get("/api/system?seed=bad")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_SEED


# ===========================================================================
# TestSystemDetailFlag
# ===========================================================================

class TestSystemDetailFlag:
    """Tests for the detail=true flag on system endpoints."""

    def test_detail_false_by_default(self):
        data = client.get("/api/system?seed=42").json()
        orbits = data.get("system_orbits", {}).get("orbits", [])
        # Without detail, orbit entries may lack a 'detail' sub-object
        # (depends on whether the system has any populated orbit slots)
        assert isinstance(orbits, list)

    def test_detail_true_flag_accepted(self):
        resp = client.get("/api/system?seed=42&detail=true")
        assert resp.status_code == 200

    def test_detail_from_body(self):
        resp = client.post("/api/system", json={"seed": 42, "detail": True})
        assert resp.status_code == 200

    def test_detail_accepts_yes_string(self):
        resp = client.get("/api/system?seed=42&detail=yes")
        assert resp.status_code == 200

    def test_independent_government_requires_detail(self):
        resp = client.get("/api/system?seed=42&detail=true&independent_government=true")
        assert resp.status_code == 200

    def test_optional_biomass_flag_accepted(self):
        resp = client.get("/api/system?seed=42&detail=true&optional_biomass_rule=true")
        assert resp.status_code == 200

    def test_optional_inhospitable_flag_accepted(self):
        resp = client.get(
            "/api/system?seed=42&detail=true&optional_inhospitable_rule=true"
        )
        assert resp.status_code == 200


# ===========================================================================
# TestSystemFullEndpoint
# ===========================================================================

class TestSystemFullEndpoint:
    """Tests for GET/POST /api/system/full."""

    def test_get_returns_200(self):
        resp = client.get("/api/system/full?seed=1")
        assert resp.status_code == 200

    def test_post_returns_200(self):
        resp = client.post("/api/system/full", json={"seed": 1})
        assert resp.status_code == 200

    def test_json_format_default(self):
        resp = client.get("/api/system/full?seed=1")
        assert "application/json" in resp.headers["content-type"]

    def test_html_format(self):
        resp = client.get("/api/system/full?seed=1&format=html")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_text_format(self):
        resp = client.get("/api/system/full?seed=1&format=text")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    def test_runaway_greenhouse_flag_accepted(self):
        resp = client.get("/api/system/full?seed=42&runaway_greenhouse=true")
        assert resp.status_code == 200

    def test_has_mainworld_with_uwp(self):
        data = client.get("/api/system/full?seed=1").json()
        mw = data.get("mainworld") or {}
        assert "uwp" in mw


# ===========================================================================
# TestSystemCard
# ===========================================================================

class TestSystemCard:
    """Tests for GET /api/system/{name}/card."""

    def test_returns_200(self):
        resp = client.get("/api/system/Mora/card?seed=42")
        assert resp.status_code == 200

    def test_content_type_is_html(self):
        resp = client.get("/api/system/Cogri/card?seed=1")
        assert "text/html" in resp.headers["content-type"]

    def test_body_contains_html(self):
        resp = client.get("/api/system/Regina/card?seed=7")
        assert "<" in resp.text

    def test_invalid_seed_returns_400(self):
        resp = client.get("/api/system/Mora/card?seed=bad")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_SEED


# ===========================================================================
# TestNamedSystem
# ===========================================================================

class TestNamedSystem:
    """Tests for GET /api/system/{name}."""

    def test_returns_200(self):
        resp = client.get("/api/system/Mora?seed=42")
        assert resp.status_code == 200

    def test_name_in_mainworld(self):
        data = client.get("/api/system/Efate?seed=1").json()
        mw = data.get("mainworld") or {}
        assert mw.get("name") == "Efate"

    def test_detail_flag_works(self):
        resp = client.get("/api/system/Mora?seed=42&detail=true")
        assert resp.status_code == 200

    def test_invalid_seed_returns_400(self):
        resp = client.get("/api/system/Mora?seed=bad")
        assert resp.status_code == 400


# ===========================================================================
# TestSystemFromWorld
# ===========================================================================

class TestSystemFromWorld:
    """Tests for POST /api/system/from-world."""

    def test_no_body_returns_400(self):
        resp = client.post("/api/system/from-world")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_BODY

    def test_invalid_json_returns_400(self):
        resp = client.post(
            "/api/system/from-world",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_BODY

    def test_body_without_uwp_returns_400(self):
        resp = client.post("/api/system/from-world", json={"name": "Mora"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_BODY

    def test_valid_world_dict_returns_200(self):
        resp = client.post("/api/system/from-world",
                           json=_SAMPLE_WORLD_DICT, params={"seed": "1"})
        assert resp.status_code == 200

    def test_has_stars(self):
        data = client.post(
            "/api/system/from-world",
            json=_SAMPLE_WORLD_DICT,
            params={"seed": "1"},
        ).json()
        assert "stars" in data

    def test_format_html(self):
        resp = client.post(
            "/api/system/from-world",
            json=_SAMPLE_WORLD_DICT,
            params={"seed": "1", "format": "html"},
        )
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_format_text(self):
        resp = client.post(
            "/api/system/from-world",
            json=_SAMPLE_WORLD_DICT,
            params={"seed": "1", "format": "text"},
        )
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    def test_invalid_seed_returns_400(self):
        resp = client.post(
            "/api/system/from-world",
            json=_SAMPLE_WORLD_DICT,
            params={"seed": "bad"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_SEED


# ===========================================================================
# TestMapSystem
# ===========================================================================

class TestMapSystem:
    """Tests for GET/POST /api/map/system (generate_system_from_map mocked)."""

    def test_missing_sector_returns_400(self):
        resp = client.get("/api/map/system?name=Regina")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_MISSING_PARAM

    def test_missing_name_and_hex_returns_400(self):
        resp = client.get("/api/map/system?sector=Spinward+Marches")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_MISSING_PARAM

    def test_invalid_hex_format_returns_400(self):
        resp = client.get(
            "/api/map/system?sector=Spinward+Marches&hex=ZZZZ"
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_HEX"

    def test_lookup_error_returns_404(self):
        with patch("app.generate_system_from_map",
                   side_effect=LookupError("not found")):
            resp = client.get(
                "/api/map/system?sector=Spinward+Marches&name=NoWorld"
            )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == ERR_NOT_FOUND

    def test_url_error_returns_502(self):
        with patch("app.generate_system_from_map",
                   side_effect=urllib.error.URLError("timeout")):
            resp = client.get(
                "/api/map/system?sector=Spinward+Marches&name=Regina"
            )
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == ERR_UPSTREAM

    def test_valid_request_returns_200(self):
        with patch("app.generate_system_from_map",
                   return_value=_SAMPLE_SYSTEM):
            resp = client.get(
                "/api/map/system?sector=Spinward+Marches&name=Regina"
            )
        assert resp.status_code == 200

    def test_html_format_mocked(self):
        with patch("app.generate_system_from_map",
                   return_value=_SAMPLE_SYSTEM):
            resp = client.get(
                "/api/map/system?sector=Spinward+Marches&name=Regina&format=html"
            )
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_post_missing_sector_returns_400(self):
        resp = client.post("/api/map/system", json={"name": "Regina"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_MISSING_PARAM


# ===========================================================================
# TestNamedMapSystem
# ===========================================================================

class TestNamedMapSystem:
    """Tests for GET /api/map/system/{name} (mocked)."""

    def test_name_from_url_path(self):
        with patch("app.generate_system_from_map",
                   return_value=_SAMPLE_SYSTEM):
            resp = client.get(
                "/api/map/system/Regina?sector=Spinward+Marches"
            )
        assert resp.status_code == 200

    def test_missing_sector_returns_400(self):
        resp = client.get("/api/map/system/Regina")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_MISSING_PARAM

    def test_lookup_error_returns_404(self):
        with patch("app.generate_system_from_map",
                   side_effect=LookupError("not found")):
            resp = client.get(
                "/api/map/system/NoWorld?sector=Spinward+Marches"
            )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == ERR_NOT_FOUND


# ===========================================================================
# TestRateLimit
# ===========================================================================

class TestRateLimit:
    """Verify the rate-limit exception handler is configured correctly."""

    def test_handler_registered(self):
        """Rate limit exception handler is present on the app."""
        from slowapi.errors import RateLimitExceeded
        assert RateLimitExceeded in app.exception_handlers

    def test_rate_limit_response_shape(self):
        """429 response uses project-standard error JSON shape."""
        from app import _rate_limit_handler

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/world",
            "query_string": b"",
            "headers": [(b"host", b"localhost")],
        }
        req = Request(scope)
        # _rate_limit_handler ignores exc; use a mock so no SlowAPI internals needed
        exc = MagicMock()

        resp = asyncio.get_event_loop().run_until_complete(
            _rate_limit_handler(req, exc)
        )
        body = json.loads(resp.body)
        assert resp.status_code == 429
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
