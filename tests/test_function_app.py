"""
test_function_app.py
====================
Unit tests for the Traveller World Generator FastAPI server.

This file was originally written against the Azure Functions architecture
(azure-api/shared/helpers.py + func.HttpRequest).  The project migrated to a
FastAPI ASGI wrapper in commit 68985fe; this file has been updated to use
the FastAPI TestClient pattern that matches test_fastapi_app.py.

Strategy
--------
The FastAPI app is tested using Starlette's TestClient, which drives the full
ASGI stack in-process without a network listener.

Helper-function unit tests (TestHelperOk … TestMaxBatchSize) call helpers
directly with make_fake_request(), which builds a minimal Starlette Request.

Test organisation
-----------------
  TestHelperOk              - ok() response builder
  TestHelperError           - error() response builder
  TestParseNameHelper       - parse_name() with query/body/route sources
  TestParseSeedHelper       - parse_seed() valid, invalid, absent
  TestParseCountHelper      - parse_count() valid, invalid, limits
  TestMaxBatchSize          - TRAVELLER_MAX_BATCH_SIZE env override
  TestGenerateSingleWorld   - GET/POST /api/world happy paths
  TestGenerateSingleWorldErrors - parameter validation for /api/world
  TestGenerateNamedWorld    - GET /api/world/{name} happy paths
  TestGenerateNamedWorldErrors  - parameter validation for named endpoint
  TestGenerateWorldBatch    - POST /api/worlds happy paths
  TestGenerateWorldBatchErrors  - parameter validation for batch endpoint
  TestResponseSchema        - all 200 responses conform to the JSON schema
  TestDeterminism           - seeded calls produce identical results
  TestGenerateWorldCard     - GET /api/world/{name}/card  (HTML)
  TestMainworldDetailInResponse - atmosphere_detail in world responses
  TestMainworldPhysicalInResponse - size_detail in world responses
  TestNhzAtmospheresOption  - parse_nhz_atmospheres() + system endpoint flag
"""

import json
import os
import re
import random
from typing import Any
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import app  # fastapi/app.py (conftest puts fastapi/ first on sys.path)
from helpers import (  # fastapi/helpers.py
    ok,
    error,
    parse_name,
    parse_seed,
    parse_count,
    parse_nhz_atmospheres,
    parse_social_detail,
    max_batch_size,
    ERR_INVALID_SEED,
    ERR_INVALID_COUNT,
    ERR_COUNT_TOO_LARGE,
    ERR_INVALID_BODY,
    ERR_NAME_TOO_LONG,
    ERR_INTERNAL,
)

# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Standard test client — server exceptions propagate for better diagnostics.
client = TestClient(app)


# ===========================================================================
# Helpers
# ===========================================================================

def make_fake_request(params=None, method="GET", path="/api/world"):
    """Build a minimal Starlette Request for direct helper-function tests."""
    qs = urlencode(params or {}).encode()
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": qs,
        "headers": [(b"host", b"localhost")],
    }
    return Request(scope)


def response_json(resp) -> Any:
    """Parse the response body as JSON.

    Accepts both JSONResponse (direct helper call, .body) and
    httpx.Response (TestClient, .json()).
    """
    if hasattr(resp, "json") and callable(resp.json):
        return resp.json()  # httpx.Response from TestClient
    return json.loads(resp.body)  # JSONResponse from direct helper call


WORLD_TOP_LEVEL_KEYS = {
    "name", "uwp", "starport", "size", "atmosphere", "temperature",
    "hydrographics", "population", "government", "law_level", "tech_level",
    "has_gas_giant", "gas_giant_count", "belt_count", "population_multiplier",
    "pbg", "bases", "trade_codes", "travel_zone", "notes", "seed",
}


# ===========================================================================
# TestHelperOk
# ===========================================================================

class TestHelperOk:
    """Tests for the ok() response builder in fastapi/helpers.py."""

    def test_default_status_200(self):
        resp = ok({"key": "value"})
        assert resp.status_code == 200

    def test_custom_status(self):
        resp = ok({"key": "value"}, status_code=201)
        assert resp.status_code == 201

    def test_body_is_json(self):
        payload = {"name": "Mora", "uwp": "A867A69-F"}
        resp = ok(payload)
        assert response_json(resp) == payload

    def test_list_body(self):
        resp = ok([1, 2, 3])
        assert response_json(resp) == [1, 2, 3]

    def test_empty_dict(self):
        resp = ok({})
        assert response_json(resp) == {}


# ===========================================================================
# TestHelperError
# ===========================================================================

class TestHelperError:
    """Tests for the error() response builder in fastapi/helpers.py."""

    def test_default_status_400(self):
        resp = error("bad input", "BAD_CODE")
        assert resp.status_code == 400

    def test_custom_status(self):
        resp = error("too large", ERR_COUNT_TOO_LARGE, status_code=422)
        assert resp.status_code == 422

    def test_body_has_error_wrapper(self):
        body = response_json(error("oops", "SOME_CODE"))
        assert "error" in body
        assert body["error"]["code"] == "SOME_CODE"
        assert body["error"]["message"] == "oops"

    def test_500_internal_error(self):
        resp = error("something broke", ERR_INTERNAL, status_code=500)
        assert resp.status_code == 500
        assert response_json(resp)["error"]["code"] == ERR_INTERNAL


# ===========================================================================
# TestParseNameHelper
# ===========================================================================

class TestParseNameHelper:
    """Tests for parse_name() in fastapi/helpers.py."""

    def test_name_from_query_string(self):
        req = make_fake_request(params={"name": "Cogri"})
        name, err = parse_name(req, {})
        assert err is None
        assert name == "Cogri"

    def test_name_from_json_body(self):
        name, err = parse_name(make_fake_request(), {"name": "Mora"})
        assert err is None
        assert name == "Mora"

    def test_route_param_takes_priority_over_query(self):
        req = make_fake_request(params={"name": "Query"})
        name, err = parse_name(req, {}, route_name="Route")
        assert err is None
        assert name == "Route"

    def test_absent_name_returns_none(self):
        name, err = parse_name(make_fake_request(), {})
        assert err is None
        assert name is None

    def test_name_too_long_returns_error(self):
        long_name = "A" * 65
        req = make_fake_request(params={"name": long_name})
        name, err = parse_name(req, {})
        assert name is None
        assert err is not None
        assert response_json(err)["error"]["code"] == ERR_NAME_TOO_LONG

    def test_name_exactly_at_limit_is_accepted(self):
        exact = "B" * 64
        req = make_fake_request(params={"name": exact})
        name, err = parse_name(req, {})
        assert err is None
        assert name == exact

    def test_empty_string_treated_as_absent(self):
        req = make_fake_request(params={"name": "   "})
        name, err = parse_name(req, {})
        assert err is None
        assert name is None


# ===========================================================================
# TestParseSeedHelper
# ===========================================================================

class TestParseSeedHelper:
    """Tests for parse_seed() in fastapi/helpers.py."""

    def test_absent_seed_returns_none(self):
        seed, err = parse_seed(make_fake_request(), {})
        assert err is None
        assert seed is None

    def test_valid_integer_seed_from_query(self):
        req = make_fake_request(params={"seed": "42"})
        seed, err = parse_seed(req, {})
        assert err is None
        assert seed == 42

    def test_valid_negative_seed(self):
        req = make_fake_request(params={"seed": "-7"})
        seed, err = parse_seed(req, {})
        assert err is None
        assert seed == -7

    def test_zero_seed(self):
        req = make_fake_request(params={"seed": "0"})
        seed, err = parse_seed(req, {})
        assert err is None
        assert seed == 0

    def test_seed_from_json_body(self):
        seed, err = parse_seed(make_fake_request(), {"seed": 99})
        assert err is None
        assert seed == 99

    def test_non_integer_seed_returns_error(self):
        req = make_fake_request(params={"seed": "abc"})
        seed, err = parse_seed(req, {})
        assert seed is None
        assert err is not None
        assert response_json(err)["error"]["code"] == ERR_INVALID_SEED

    def test_float_seed_returns_error(self):
        req = make_fake_request(params={"seed": "3.14"})
        seed, err = parse_seed(req, {})
        assert seed is None
        assert err is not None
        assert response_json(err)["error"]["code"] == ERR_INVALID_SEED


# ===========================================================================
# TestParseCountHelper
# ===========================================================================

class TestParseCountHelper:
    """Tests for parse_count() in fastapi/helpers.py."""

    def test_absent_returns_none(self):
        count, err = parse_count(make_fake_request(), {})
        assert err is None
        assert count is None

    def test_valid_count_from_query(self):
        req = make_fake_request(params={"count": "5"})
        count, err = parse_count(req, {})
        assert err is None
        assert count == 5

    def test_valid_count_from_body(self):
        count, err = parse_count(make_fake_request(), {"count": 3})
        assert err is None
        assert count == 3

    def test_count_of_one_is_valid(self):
        req = make_fake_request(params={"count": "1"})
        count, err = parse_count(req, {})
        assert err is None
        assert count == 1

    def test_count_of_zero_returns_error(self):
        req = make_fake_request(params={"count": "0"})
        count, err = parse_count(req, {})
        assert count is None
        assert err is not None
        assert response_json(err)["error"]["code"] == ERR_INVALID_COUNT

    def test_negative_count_returns_error(self):
        req = make_fake_request(params={"count": "-1"})
        count, err = parse_count(req, {})
        assert count is None
        assert err is not None
        assert response_json(err)["error"]["code"] == ERR_INVALID_COUNT

    def test_non_integer_count_returns_error(self):
        req = make_fake_request(params={"count": "lots"})
        count, err = parse_count(req, {})
        assert count is None
        assert err is not None
        assert response_json(err)["error"]["code"] == ERR_INVALID_COUNT

    def test_count_at_max_is_accepted(self):
        limit = max_batch_size()
        req = make_fake_request(params={"count": str(limit)})
        count, err = parse_count(req, {})
        assert err is None
        assert count == limit

    def test_count_over_max_returns_422(self):
        limit = max_batch_size()
        req = make_fake_request(params={"count": str(limit + 1)})
        count, err = parse_count(req, {})
        assert count is None
        assert err is not None
        assert err.status_code == 422
        assert response_json(err)["error"]["code"] == ERR_COUNT_TOO_LARGE


# ===========================================================================
# TestMaxBatchSize
# ===========================================================================

class TestMaxBatchSize:
    """Tests for the TRAVELLER_MAX_BATCH_SIZE environment override."""

    def test_default_is_20(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRAVELLER_MAX_BATCH_SIZE", None)
            assert max_batch_size() == 20

    def test_env_override(self):
        with patch.dict(os.environ, {"TRAVELLER_MAX_BATCH_SIZE": "5"}):
            assert max_batch_size() == 5

    def test_invalid_env_falls_back_to_default(self):
        with patch.dict(os.environ, {"TRAVELLER_MAX_BATCH_SIZE": "notanint"}):
            assert max_batch_size() == 20


# ===========================================================================
# TestGenerateSingleWorld
# ===========================================================================

class TestGenerateSingleWorld:
    """Happy-path tests for GET/POST /api/world."""

    def test_get_returns_200(self):
        resp = client.get("/api/world")
        assert resp.status_code == 200

    def test_post_returns_200(self):
        resp = client.post("/api/world")
        assert resp.status_code == 200

    def test_response_is_valid_json(self):
        resp = client.get("/api/world")
        assert isinstance(resp.json(), dict)

    def test_response_has_all_required_keys(self):
        body = client.get("/api/world").json()
        assert WORLD_TOP_LEVEL_KEYS.issubset(set(body.keys()))
        assert not (set(body.keys()) - WORLD_TOP_LEVEL_KEYS - {"size_detail"})

    def test_name_param_respected(self):
        body = client.get("/api/world?name=Mora").json()
        assert body["name"] == "Mora"

    def test_default_name_used_when_absent(self):
        body = client.get("/api/world").json()
        assert body["name"] == "World-1"

    def test_seed_produces_deterministic_result(self):
        body1 = client.get("/api/world?name=Test&seed=42").json()
        body2 = client.get("/api/world?name=Test&seed=42").json()
        assert body1["uwp"] == body2["uwp"]

    def test_uwp_format(self):
        body = client.get("/api/world?seed=1").json()
        assert re.match(r"^[ABCDEX][0-9A-Z]{6}-[0-9A-Z]$", body["uwp"])

    def test_temperature_is_valid_enum(self):
        body = client.get("/api/world?seed=7").json()
        assert body["temperature"] in {"Frozen", "Cold", "Temperate", "Hot", "Boiling"}

    def test_travel_zone_is_valid_enum(self):
        body = client.get("/api/world?seed=3").json()
        assert body["travel_zone"] in {"Green", "Amber", "Red"}

    def test_starport_code_is_valid(self):
        body = client.get("/api/world?seed=5").json()
        assert body["starport"]["code"] in {"A", "B", "C", "D", "E", "X"}

    def test_bases_is_list_of_valid_codes(self):
        body = client.get("/api/world?seed=9").json()
        assert isinstance(body["bases"], list)
        for code in body["bases"]:
            assert code in {"C", "H", "M", "N", "S"}

    def test_trade_codes_are_valid(self):
        valid_codes = {
            "Ag", "As", "Ba", "De", "Fl", "Ga", "Hi", "Ht", "Ic", "In",
            "Lo", "Lt", "Na", "Ni", "Po", "Ri", "Va", "Wa",
        }
        body = client.get("/api/world?seed=11").json()
        for code in body["trade_codes"]:
            assert code in valid_codes

    def test_has_gas_giant_is_bool(self):
        body = client.get("/api/world?seed=13").json()
        assert isinstance(body["has_gas_giant"], bool)

    def test_notes_is_list(self):
        body = client.get("/api/world?seed=17").json()
        assert isinstance(body["notes"], list)

    def test_post_with_json_body_name(self):
        body = client.post("/api/world", json={"name": "Regina", "seed": 10}).json()
        assert body["name"] == "Regina"


# ===========================================================================
# TestGenerateSingleWorldErrors
# ===========================================================================

class TestGenerateSingleWorldErrors:
    """Error-path tests for /api/world."""

    def test_invalid_seed_returns_400(self):
        resp = client.get("/api/world?seed=not-a-number")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_SEED

    def test_name_too_long_returns_400(self):
        resp = client.get(f"/api/world?name={'X' * 65}")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_NAME_TOO_LONG

    def test_internal_error_returns_500(self):
        with patch("app.generate_world", side_effect=RuntimeError("boom")):
            resp = client.get("/api/world")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == ERR_INTERNAL


# ===========================================================================
# TestGenerateNamedWorld
# ===========================================================================

class TestGenerateNamedWorld:
    """Happy-path tests for GET /api/world/{name}."""

    def test_returns_200(self):
        resp = client.get("/api/world/Mora")
        assert resp.status_code == 200

    def test_name_from_route_param(self):
        body = client.get("/api/world/Efate").json()
        assert body["name"] == "Efate"

    def test_seed_respected(self):
        b1 = client.get("/api/world/Glisten?seed=42").json()
        b2 = client.get("/api/world/Glisten?seed=42").json()
        assert b1["uwp"] == b2["uwp"]

    def test_response_has_all_required_keys(self):
        body = client.get("/api/world/Aramis").json()
        assert WORLD_TOP_LEVEL_KEYS.issubset(set(body.keys()))
        assert not (set(body.keys()) - WORLD_TOP_LEVEL_KEYS - {"size_detail"})

    def test_different_names_produce_correct_name_field(self):
        for world_name in ("Rhylanor", "Jae Tellona", "Porozlo"):
            body = client.get(f"/api/world/{world_name}").json()
            assert body["name"] == world_name


# ===========================================================================
# TestGenerateNamedWorldErrors
# ===========================================================================

class TestGenerateNamedWorldErrors:
    """Error-path tests for /api/world/{name}."""

    def test_name_too_long_returns_400(self):
        resp = client.get(f"/api/world/{'Z' * 65}")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_NAME_TOO_LONG

    def test_invalid_seed_returns_400(self):
        resp = client.get("/api/world/Mora?seed=xyz")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_SEED

    def test_internal_error_returns_500(self):
        with patch("app.generate_world", side_effect=RuntimeError("boom")):
            resp = client.get("/api/world/Mora")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == ERR_INTERNAL


# ===========================================================================
# TestGenerateWorldBatch
# ===========================================================================

class TestGenerateWorldBatch:
    """Happy-path tests for POST /api/worlds."""

    def test_returns_200(self):
        resp = client.post("/api/worlds", json={"count": 1})
        assert resp.status_code == 200

    def test_response_has_count_and_worlds_keys(self):
        body = client.post("/api/worlds", json={"count": 2}).json()
        assert "count" in body
        assert "worlds" in body

    def test_count_field_matches_requested_count(self):
        body = client.post("/api/worlds", json={"count": 3}).json()
        assert body["count"] == 3
        assert len(body["worlds"]) == 3

    def test_default_count_is_one(self):
        body = client.post("/api/worlds", json={}).json()
        assert body["count"] == 1
        assert len(body["worlds"]) == 1

    def test_empty_body_uses_default_count(self):
        body = client.post("/api/worlds").json()
        assert body["count"] == 1

    def test_default_prefix_world_dash(self):
        body = client.post("/api/worlds", json={"count": 2}).json()
        assert body["worlds"][0]["name"] == "World-1"
        assert body["worlds"][1]["name"] == "World-2"

    def test_custom_prefix_applied(self):
        body = client.post("/api/worlds", json={"count": 3, "prefix": "Spinward-"}).json()
        assert body["worlds"][0]["name"] == "Spinward-1"
        assert body["worlds"][2]["name"] == "Spinward-3"

    def test_prefix_from_query_string(self):
        body = client.post("/api/worlds?prefix=Q-&count=2").json()
        assert body["worlds"][0]["name"] == "Q-1"

    def test_seed_produces_deterministic_batch(self):
        b1 = client.post("/api/worlds", json={"count": 3, "seed": 55}).json()
        b2 = client.post("/api/worlds", json={"count": 3, "seed": 55}).json()
        for w1, w2 in zip(b1["worlds"], b2["worlds"]):
            assert w1["uwp"] == w2["uwp"]

    def test_each_world_has_all_required_keys(self):
        body = client.post("/api/worlds", json={"count": 5}).json()
        for world in body["worlds"]:
            assert WORLD_TOP_LEVEL_KEYS.issubset(set(world.keys()))
            assert not (set(world.keys()) - WORLD_TOP_LEVEL_KEYS - {"size_detail"})

    def test_count_from_query_string(self):
        body = client.post("/api/worlds?count=4").json()
        assert body["count"] == 4
        assert len(body["worlds"]) == 4

    def test_max_batch_size_accepted(self):
        limit = max_batch_size()
        resp = client.post("/api/worlds", json={"count": limit})
        assert resp.status_code == 200
        assert resp.json()["count"] == limit


# ===========================================================================
# TestGenerateWorldBatchErrors
# ===========================================================================

class TestGenerateWorldBatchErrors:
    """Error-path tests for POST /api/worlds."""

    def test_invalid_json_body_returns_400(self):
        resp = client.post(
            "/api/worlds",
            content=b"not json at all {{{",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_BODY

    def test_body_not_object_returns_400(self):
        resp = client.post("/api/worlds", json=[1, 2, 3])
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

    def test_invalid_seed_returns_400(self):
        resp = client.post("/api/worlds", json={"count": 2, "seed": "bad"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_SEED

    def test_prefix_too_long_returns_400(self):
        resp = client.post("/api/worlds", json={"count": 1, "prefix": "P" * 33})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_BODY

    def test_internal_error_returns_500(self):
        with patch("app.generate_world", side_effect=RuntimeError("boom")):
            resp = client.post("/api/worlds", json={"count": 1})
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == ERR_INTERNAL


# ===========================================================================
# TestResponseSchema
# ===========================================================================

class TestResponseSchema:
    """Validate all 200 responses against traveller_world_schema.json.

    These tests use jsonschema if installed; they skip gracefully if not.
    """

    SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "traveller_gen", "traveller_world_schema.json")

    @classmethod
    def _schema(cls):
        with open(cls.SCHEMA_PATH, encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def _validator(cls):
        try:
            import jsonschema  # pylint: disable=import-outside-toplevel
            return jsonschema
        except ImportError:
            return None

    def test_single_world_response_validates(self):
        v = self._validator()
        if v is None:
            return
        schema = self._schema()
        body = client.get("/api/world?seed=1").json()
        v.validate(instance=body, schema=schema)

    def test_named_world_response_validates(self):
        v = self._validator()
        if v is None:
            return
        schema = self._schema()
        body = client.get("/api/world/Mora?seed=2").json()
        v.validate(instance=body, schema=schema)

    def test_each_world_in_batch_validates(self):
        v = self._validator()
        if v is None:
            return
        schema = self._schema()
        payload = client.post("/api/worlds", json={"count": 5, "seed": 4}).json()
        for i, world in enumerate(payload["worlds"]):
            try:
                v.validate(instance=world, schema=schema)
            except v.ValidationError as exc:
                raise AssertionError(
                    f"World {i} in batch failed schema validation: {exc.message}"
                ) from exc

    def test_twenty_random_worlds_all_validate(self):
        v = self._validator()
        if v is None:
            return
        schema = self._schema()
        for seed in range(20):
            body = client.get(f"/api/world?seed={seed}").json()
            try:
                v.validate(instance=body, schema=schema)
            except v.ValidationError as exc:
                raise AssertionError(
                    f"World with seed={seed} (UWP={body.get('uwp')}) "
                    f"failed schema validation: {exc.message}"
                ) from exc


# ===========================================================================
# TestDeterminism
# ===========================================================================

class TestDeterminism:
    """Cross-endpoint seed determinism tests."""

    def test_same_seed_same_result_across_calls(self):
        """Calling the same endpoint twice with the same seed must produce
        an identical UWP, regardless of any state left from previous calls."""
        uwps = set()
        for _ in range(3):
            uwps.add(client.get("/api/world?name=Pinpoint&seed=77").json()["uwp"])
        assert len(uwps) == 1, f"Seed 77 produced different UWPs: {uwps}"

    def test_different_seeds_likely_differ(self):
        """Two different seeds should almost certainly produce different
        worlds (not guaranteed, but with a tiny false-failure probability)."""
        uwp_a = client.get("/api/world?seed=100").json()["uwp"]
        uwp_b = client.get("/api/world?seed=200").json()["uwp"]
        assert uwp_a != uwp_b, (
            "Seeds 100 and 200 produced the same UWP — extremely unlikely "
            "unless the seeding logic is broken."
        )

    def test_batch_seed_matches_sequential_singles(self):
        """A seeded batch of N worlds should produce the same sequence as
        N sequential single-world calls with the same starting seed."""
        seed = 42
        count = 4

        batch_uwps = [
            w["uwp"]
            for w in client.post(
                "/api/worlds", json={"count": count, "seed": seed}
            ).json()["worlds"]
        ]

        rng = random.Random(seed)
        from traveller_gen.traveller_world_gen import (  # pylint: disable=import-outside-toplevel
            generate_world as _gen,
            generate_atmosphere_detail as _gen_atm,
            generate_gas_mix as _gen_gas,
            generate_unusual_subtype as _gen_unusual,
        )
        from traveller_gen.traveller_world_physical import (  # pylint: disable=import-outside-toplevel
            generate_world_physical as _gen_phys,
        )
        from traveller_gen.traveller_hydro_detail import (  # pylint: disable=import-outside-toplevel
            generate_hydrographic_detail as _gen_hydro,
        )
        sequential_uwps = []
        for i in range(count):
            world = _gen(name=f"World-{i+1}", seed=seed, rng=rng)
            world.atmosphere_detail = _gen_atm(
                world.atmosphere, world.size, temperature=world.temperature
            )
            _gen_gas(
                world.atmosphere_detail, world.atmosphere, world.size,
                world.temperature, None, world.hydrographics,
            )
            _gen_unusual(
                world.atmosphere_detail, world.atmosphere,
                world.size, world.hydrographics,
            )
            world.hydrographic_detail = _gen_hydro(
                world.hydrographics, world.size, rng=rng
            )
            world.size_detail = _gen_phys(world, rng=rng)
            sequential_uwps.append(world.uwp())

        assert batch_uwps == sequential_uwps


# ===========================================================================
# TestGenerateWorldCard
# ===========================================================================

class TestGenerateWorldCard:
    """Tests for GET /api/world/{name}/card — HTML display card endpoint."""

    def test_returns_200(self):
        resp = client.get("/api/world/Mora/card")
        assert resp.status_code == 200

    def test_content_type_is_html(self):
        resp = client.get("/api/world/Mora/card")
        assert "text/html" in resp.headers["content-type"]

    def test_body_is_valid_html(self):
        body = client.get("/api/world/Cogri/card").text
        assert "<!DOCTYPE html>" in body
        assert "<html" in body
        assert "</html>" in body

    def test_name_appears_in_html(self):
        body = client.get("/api/world/Regina/card").text
        assert "Regina" in body

    def test_uwp_appears_in_html(self):
        body = client.get("/api/world/Glisten/card?seed=42").text
        assert re.search(r"[ABCDEX][0-9A-G]{6}-[0-9A-G]", body)

    def test_seed_produces_deterministic_html(self):
        html1 = client.get("/api/world/T/card?seed=7").text
        html2 = client.get("/api/world/T/card?seed=7").text
        assert html1 == html2

    def test_tl_era_correct_in_html(self):
        """TL era labels in the card must match rulebook definitions."""
        from traveller_gen.traveller_world_gen import World  # pylint: disable=import-outside-toplevel
        w8 = World(name="T", starport="C", size=5, atmosphere=6,
                   temperature="Temperate", hydrographics=5, population=5,
                   government=4, law_level=3, tech_level=8)
        assert "Pre-Stellar" in w8.to_html()
        assert "Early stellar age" not in w8.to_html()

    def test_name_too_long_returns_400(self):
        resp = client.get(f"/api/world/{'Z' * 65}/card")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_NAME_TOO_LONG

    def test_invalid_seed_returns_400(self):
        resp = client.get("/api/world/Mora/card?seed=bad")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == ERR_INVALID_SEED

    def test_internal_error_returns_500(self):
        with patch("app.generate_world", side_effect=RuntimeError("boom")):
            resp = client.get("/api/world/Mora/card")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == ERR_INTERNAL


# ===========================================================================
# TestMainworldDetailInResponse
# ===========================================================================

class TestMainworldDetailInResponse:
    """Verify atmosphere detail is populated in mainworld API responses."""

    def test_single_world_atmosphere_has_profile(self):
        body = client.get("/api/world?seed=1").json()
        assert "profile" in body["atmosphere"]

    def test_single_world_atmosphere_has_detail(self):
        body = client.get("/api/world?seed=1").json()
        assert "detail" in body["atmosphere"]

    def test_named_world_atmosphere_has_profile(self):
        body = client.get("/api/world/Mora?seed=5").json()
        assert "profile" in body["atmosphere"]

    def test_batch_worlds_all_have_atmosphere_profile(self):
        body = client.post("/api/worlds", json={"count": 3, "seed": 7}).json()
        for world in body["worlds"]:
            assert "profile" in world["atmosphere"]

    def test_batch_worlds_all_have_atmosphere_detail(self):
        # seed=1, count=3 confirmed to produce only non-zero atmosphere worlds
        body = client.post("/api/worlds", json={"count": 3, "seed": 1}).json()
        for world in body["worlds"]:
            assert "detail" in world["atmosphere"]

    def test_world_card_html_contains_atmosphere_detail(self):
        body = client.get("/api/world/Aramis/card?seed=3").text
        assert "Atmosphere" in body

    def test_atmosphere_profile_is_string(self):
        body = client.get("/api/world?seed=2").json()
        assert isinstance(body["atmosphere"]["profile"], str)
        assert len(body["atmosphere"]["profile"]) > 0

    def test_atmosphere_detail_is_dict(self):
        # seed=1 produces a non-vacuum atmosphere so detail is present
        body = client.get("/api/world?seed=1").json()
        assert isinstance(body["atmosphere"]["detail"], dict)


# ===========================================================================
# TestMainworldPhysicalInResponse
# ===========================================================================

_WORLD_PHYSICAL_KEYS = {
    "composition", "diameter_km", "density_g_cm3", "mass_earth",
    "gravity_g", "escape_velocity_km_s", "axial_tilt_deg",
    "day_length_hours", "basic_day_length_hours", "tidal_status", "resource_rating",
}
_VALID_COMPOSITIONS = {
    "Heavy Iron Core", "Dense Core", "Standard", "Low Density", "Icy",
}
_VALID_TIDAL_STATUSES = {
    "none", "braking", "prograde", "retrograde", "3:2_lock", "1:1_lock",
}


class TestMainworldPhysicalInResponse:
    """Verify world physical detail is populated in mainworld API responses."""

    def test_single_world_has_size_detail(self):
        # seed=1 produces a non-belt world (size > 0)
        body = client.get("/api/world?seed=1").json()
        assert "size_detail" in body

    def test_belt_world_has_no_size_detail(self):
        # seed=2 produces a size-0 belt mainworld; generate_world_physical returns None
        body = client.get("/api/world?seed=2").json()
        assert body["size"]["code"] == 0
        assert "size_detail" not in body

    def test_size_detail_has_required_keys(self):
        body = client.get("/api/world?seed=1").json()
        assert _WORLD_PHYSICAL_KEYS == set(body["size_detail"].keys())

    def test_size_detail_composition_is_valid_enum(self):
        body = client.get("/api/world?seed=1").json()
        assert body["size_detail"]["composition"] in _VALID_COMPOSITIONS

    def test_size_detail_diameter_km_is_positive(self):
        body = client.get("/api/world?seed=1").json()
        assert body["size_detail"]["diameter_km"] > 0

    def test_size_detail_gravity_g_is_positive(self):
        body = client.get("/api/world?seed=1").json()
        assert body["size_detail"]["gravity_g"] > 0

    def test_size_detail_tidal_status_is_valid(self):
        # No orbital data in standalone call — expect "none"
        body = client.get("/api/world?seed=1").json()
        assert body["size_detail"]["tidal_status"] in _VALID_TIDAL_STATUSES

    def test_named_world_has_size_detail(self):
        body = client.get("/api/world/Mora?seed=1").json()
        if body["size"]["code"] > 0:
            assert "size_detail" in body

    def test_batch_worlds_physical_consistent_with_size(self):
        body = client.post("/api/worlds", json={"count": 5, "seed": 10}).json()
        for world in body["worlds"]:
            if world["size"]["code"] == 0:
                assert "size_detail" not in world
            else:
                assert "size_detail" in world

    def test_system_mainworld_has_size_detail(self):
        # The system endpoint generates physical details for the mainworld;
        # if size_detail is present it must only appear on non-belt worlds.
        body = client.get("/api/system?seed=42").json()
        mw = body["mainworld"]
        if "size_detail" in mw:
            assert mw["size"]["code"] > 0

    def test_system_mainworld_tidal_status_valid(self):
        body = client.get("/api/system?seed=42").json()
        mw = body["mainworld"]
        if "size_detail" in mw:
            assert mw["size_detail"]["tidal_status"] in _VALID_TIDAL_STATUSES


# ===========================================================================
# TestNhzAtmospheresOption
# ===========================================================================

class TestNhzAtmospheresOption:
    """Tests for parse_nhz_atmospheres() and its wiring into system endpoints."""

    def test_absent_nhz_returns_false(self):
        assert parse_nhz_atmospheres(make_fake_request(), {}) is False

    def test_query_string_true(self):
        for val in ("true", "1", "yes"):
            req = make_fake_request(params={"nhz_atmospheres": val})
            assert parse_nhz_atmospheres(req, {}) is True

    def test_query_string_false(self):
        req = make_fake_request(params={"nhz_atmospheres": "false"})
        assert parse_nhz_atmospheres(req, {}) is False

    def test_json_body_bool_true(self):
        assert parse_nhz_atmospheres(make_fake_request(), {"nhz_atmospheres": True}) is True

    def test_json_body_bool_false(self):
        assert parse_nhz_atmospheres(make_fake_request(), {"nhz_atmospheres": False}) is False

    def test_system_response_includes_all_option_flags(self):
        body = client.get("/api/system?seed=7").json()
        assert "nhz_atmospheres" in body
        assert "orbital_eccentricity" in body
        assert "orbital_inclination" in body
        assert "seed" in body

    def test_system_nhz_false_by_default(self):
        body = client.get("/api/system?seed=7").json()
        assert body["nhz_atmospheres"] is False

    def test_system_nhz_true_when_requested(self):
        body = client.get("/api/system?seed=7&nhz_atmospheres=true").json()
        assert body["nhz_atmospheres"] is True

    def test_system_orbital_flags_reflected(self):
        body = client.get(
            "/api/system?seed=7&orbital_eccentricity=true&orbital_inclination=true"
        ).json()
        assert body["orbital_eccentricity"] is True
        assert body["orbital_inclination"] is True


# ===========================================================================
# TestSocialDetailOption
# ===========================================================================

_CULTURE_TRAIT_KEYS = {
    "diversity", "xenophilia", "uniqueness", "symbology",
    "cohesion", "progressiveness", "expansionism", "militancy",
}
_CULTURE_LABEL_KEYS = {k + "_label" for k in _CULTURE_TRAIT_KEYS}
_CULTURE_KEYS = _CULTURE_TRAIT_KEYS | _CULTURE_LABEL_KEYS | {"cultural_profile", "cultural_extension"}


class TestSocialDetailOption:
    """Tests for parse_social_detail() and culture_detail wiring in system endpoints.

    seed=2 with detail=true&social_detail=true produces an inhabited mainworld
    with a full CultureDetail object.
    """

    def test_absent_social_detail_returns_false(self):
        assert parse_social_detail(make_fake_request(), {}) is False

    def test_query_string_true(self):
        for val in ("true", "1", "yes"):
            req = make_fake_request(params={"social_detail": val})
            assert parse_social_detail(req, {}) is True

    def test_query_string_false(self):
        req = make_fake_request(params={"social_detail": "false"})
        assert parse_social_detail(req, {}) is False

    def test_json_body_bool_true(self):
        assert parse_social_detail(make_fake_request(), {"social_detail": True}) is True

    def test_json_body_bool_false(self):
        assert parse_social_detail(make_fake_request(), {"social_detail": False}) is False

    def test_system_mainworld_has_culture_detail(self):
        body = client.get("/api/system?seed=2&detail=true&social_detail=true").json()
        assert "culture_detail" in body["mainworld"]

    def test_culture_detail_has_all_required_keys(self):
        body = client.get("/api/system?seed=2&detail=true&social_detail=true").json()
        cd = body["mainworld"]["culture_detail"]
        assert _CULTURE_KEYS == set(cd.keys())

    def test_cultural_profile_format(self):
        body = client.get("/api/system?seed=2&detail=true&social_detail=true").json()
        profile = body["mainworld"]["culture_detail"]["cultural_profile"]
        assert re.fullmatch(r"[0-9A-Z]{4}-[0-9A-Z]{4}", profile)

    def test_all_trait_values_at_least_one(self):
        body = client.get("/api/system?seed=2&detail=true&social_detail=true").json()
        cd = body["mainworld"]["culture_detail"]
        for key in _CULTURE_TRAIT_KEYS:
            assert cd[key] >= 1, f"{key} = {cd[key]} < 1"

    def test_culture_detail_absent_without_social_detail(self):
        body = client.get("/api/system?seed=2&detail=true").json()
        assert "culture_detail" not in body["mainworld"]

    def test_world_card_html_has_culture_section(self):
        html = client.get(
            "/api/world/Test/card?seed=2&detail=true&social_detail=true"
        ).text
        assert "Culture detail" in html

    def test_world_card_html_no_culture_without_social_detail(self):
        html = client.get("/api/world/Test/card?seed=2&detail=true").text
        assert "Culture detail" not in html

    # -- importance_detail --

    def test_system_mainworld_has_importance_detail(self):
        body = client.get("/api/system?seed=2&detail=true&social_detail=true").json()
        assert "importance_detail" in body["mainworld"]

    def test_importance_detail_has_required_keys(self):
        body = client.get("/api/system?seed=2&detail=true&social_detail=true").json()
        imp = body["mainworld"]["importance_detail"]
        required = {"importance", "starport_dm", "population_dm", "tech_dm",
                    "agricultural_dm", "industrial_dm", "rich_dm",
                    "base_dm", "waystation_dm", "labour_factor"}
        assert required.issubset(set(imp.keys()))

    def test_importance_equals_sum_of_dms(self):
        body = client.get("/api/system?seed=2&detail=true&social_detail=true").json()
        imp = body["mainworld"]["importance_detail"]
        expected = (
            imp["starport_dm"] + imp["population_dm"] + imp["tech_dm"]
            + imp["agricultural_dm"] + imp["industrial_dm"] + imp["rich_dm"]
            + imp["base_dm"] + imp["waystation_dm"]
        )
        assert imp["importance"] == expected

    def test_importance_detail_absent_without_social_detail(self):
        body = client.get("/api/system?seed=2&detail=true").json()
        assert "importance_detail" not in body["mainworld"]

    def test_world_card_html_has_importance_row(self):
        html = client.get(
            "/api/world/Test/card?seed=2&detail=true&social_detail=true"
        ).text
        assert "World importance" in html

    def test_world_card_html_no_importance_without_social_detail(self):
        html = client.get("/api/world/Test/card?seed=2&detail=true").text
        assert "World importance" not in html
