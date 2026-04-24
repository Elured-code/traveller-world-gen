"""
test_function_app.py
====================
Unit tests for the Traveller World Generator Azure Functions app.

Strategy
--------
Azure Functions are tested without a live Azure runtime by using the
azure-functions SDK's own test helpers.  HttpRequest objects are built
with func.HttpRequest(...) and the function handler is called directly,
returning a real func.HttpResponse.

We never start a network listener; there is no func.start() here.
This approach is fast, hermetic, and produces proper coverage of every
branch in function_app.py and shared/helpers.py.

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
"""

import json
import os
import sys
import random
from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Project root — one level up from the tests/ directory.
# sys.path is already configured by conftest.py when running via pytest.
# PROJECT_ROOT is kept here for locating the schema file.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Stub out the azure.functions package if it is not installed.
# This lets the test suite run in any Python environment.
# ---------------------------------------------------------------------------
try:
    import azure.functions as func
    _AZURE_AVAILABLE = True
except ImportError:
    # Build a minimal stub so tests can still import and run.
    import types

    _af = types.ModuleType("azure.functions")
    _azure = types.ModuleType("azure")
    _azure.functions = _af

    class _AuthLevel:
        FUNCTION  = "function"
        ANONYMOUS = "anonymous"
        ADMIN     = "admin"

    class _HttpRequest:
        def __init__(self, method, url, headers=None, params=None,
                     route_params=None, body=b""):
            self.method       = method.upper()
            self.url          = url
            self.headers      = headers or {}
            self.params       = params or {}
            self.route_params = route_params or {}
            self._body        = body if isinstance(body, bytes) else body.encode()

        def get_body(self) -> bytes:
            return self._body

        def get_json(self):
            if not self._body:
                raise ValueError("No body")
            return json.loads(self._body)

    class _HttpResponse:
        def __init__(self, body="", status_code=200, mimetype="application/json",
                     charset="utf-8"):
            self.status_code = status_code
            self.mimetype    = mimetype
            self._body       = body.encode(charset) if isinstance(body, str) else body

        def get_body(self) -> bytes:
            return self._body

    class _FunctionApp:
        def __init__(self, http_auth_level=None):
            self._auth_level = http_auth_level

        def route(self, route, methods=None):
            def decorator(fn):
                return fn
            return decorator

    _af.AuthLevel    = _AuthLevel
    _af.HttpRequest  = _HttpRequest
    _af.HttpResponse = _HttpResponse
    _af.FunctionApp  = _FunctionApp

    sys.modules["azure"]           = _azure
    sys.modules["azure.functions"] = _af
    import azure.functions as func  # noqa: F811 — now the stub
    _AZURE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Now import the app under test.
# ---------------------------------------------------------------------------
from shared.helpers import (  # noqa: E402
    ok,
    error,
    parse_name,
    parse_seed,
    parse_count,
    max_batch_size,
    ERR_INVALID_SEED,
    ERR_INVALID_COUNT,
    ERR_COUNT_TOO_LARGE,
    ERR_INVALID_BODY,
    ERR_NAME_TOO_LONG,
    ERR_INTERNAL,
)
from function_app import (  # noqa: E402
    generate_single_world,
    generate_named_world,
    generate_world_batch,
)


# ===========================================================================
# Helpers
# ===========================================================================

def make_request(
    method: str = "GET",
    url: str = "http://localhost/api/world",
    params: Optional[Dict[str, str]] = None,
    body: Any = None,
    route_params: Optional[Dict[str, str]] = None,
) -> func.HttpRequest:
    """Build a func.HttpRequest for testing."""
    if body is None:
        raw_body = b""
    elif isinstance(body, (dict, list)):
        raw_body = json.dumps(body).encode()
    elif isinstance(body, str):
        raw_body = body.encode()
    else:
        raw_body = body

    return func.HttpRequest(
        method=method,
        url=url,
        headers={"Content-Type": "application/json"} if raw_body else {},
        params=params or {},
        route_params=route_params or {},
        body=raw_body,
    )


def response_json(resp: func.HttpResponse) -> Any:
    """Parse the response body as JSON."""
    return json.loads(resp.get_body())


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
    """Tests for the ok() response builder in shared/helpers.py."""

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
    """Tests for the error() response builder in shared/helpers.py."""

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
    """Tests for parse_name() in shared/helpers.py."""

    def test_name_from_query_string(self):
        req = make_request(params={"name": "Cogri"})
        name, err = parse_name(req)
        assert err is None
        assert name == "Cogri"

    def test_name_from_json_body(self):
        req = make_request(method="POST", body={"name": "Mora"})
        name, err = parse_name(req)
        assert err is None
        assert name == "Mora"

    def test_route_param_takes_priority_over_query(self):
        req = make_request(params={"name": "Query"},
                           route_params={"name": "Route"})
        name, err = parse_name(req, route_name="Route")
        assert err is None
        assert name == "Route"

    def test_absent_name_returns_none(self):
        req = make_request()
        name, err = parse_name(req)
        assert err is None
        assert name is None

    def test_name_too_long_returns_error(self):
        long_name = "A" * 65
        req = make_request(params={"name": long_name})
        name, err = parse_name(req)
        assert name is None
        assert err is not None
        assert response_json(err)["error"]["code"] == ERR_NAME_TOO_LONG

    def test_name_exactly_at_limit_is_accepted(self):
        exact = "B" * 64
        req = make_request(params={"name": exact})
        name, err = parse_name(req)
        assert err is None
        assert name == exact

    def test_empty_string_treated_as_absent(self):
        req = make_request(params={"name": "   "})
        name, err = parse_name(req)
        assert err is None
        assert name is None


# ===========================================================================
# TestParseSeedHelper
# ===========================================================================

class TestParseSeedHelper:
    """Tests for parse_seed() in shared/helpers.py."""

    def test_absent_seed_returns_none(self):
        req = make_request()
        seed, err = parse_seed(req)
        assert err is None
        assert seed is None

    def test_valid_integer_seed_from_query(self):
        req = make_request(params={"seed": "42"})
        seed, err = parse_seed(req)
        assert err is None
        assert seed == 42

    def test_valid_negative_seed(self):
        req = make_request(params={"seed": "-7"})
        seed, err = parse_seed(req)
        assert err is None
        assert seed == -7

    def test_zero_seed(self):
        req = make_request(params={"seed": "0"})
        seed, err = parse_seed(req)
        assert err is None
        assert seed == 0

    def test_seed_from_json_body(self):
        req = make_request(method="POST", body={"seed": 99})
        seed, err = parse_seed(req)
        assert err is None
        assert seed == 99

    def test_non_integer_seed_returns_error(self):
        req = make_request(params={"seed": "abc"})
        seed, err = parse_seed(req)
        assert seed is None
        assert err is not None
        assert response_json(err)["error"]["code"] == ERR_INVALID_SEED

    def test_float_seed_returns_error(self):
        req = make_request(params={"seed": "3.14"})
        seed, err = parse_seed(req)
        assert seed is None
        assert err is not None
        assert response_json(err)["error"]["code"] == ERR_INVALID_SEED


# ===========================================================================
# TestParseCountHelper
# ===========================================================================

class TestParseCountHelper:
    """Tests for parse_count() in shared/helpers.py."""

    def test_absent_returns_none(self):
        req = make_request()
        count, err = parse_count(req)
        assert err is None
        assert count is None

    def test_valid_count_from_query(self):
        req = make_request(params={"count": "5"})
        count, err = parse_count(req)
        assert err is None
        assert count == 5

    def test_valid_count_from_body(self):
        req = make_request(method="POST", body={"count": 3})
        count, err = parse_count(req)
        assert err is None
        assert count == 3

    def test_count_of_one_is_valid(self):
        req = make_request(params={"count": "1"})
        count, err = parse_count(req)
        assert err is None
        assert count == 1

    def test_count_of_zero_returns_error(self):
        req = make_request(params={"count": "0"})
        count, err = parse_count(req)
        assert count is None
        assert response_json(err)["error"]["code"] == ERR_INVALID_COUNT

    def test_negative_count_returns_error(self):
        req = make_request(params={"count": "-1"})
        count, err = parse_count(req)
        assert count is None
        assert response_json(err)["error"]["code"] == ERR_INVALID_COUNT

    def test_non_integer_count_returns_error(self):
        req = make_request(params={"count": "lots"})
        count, err = parse_count(req)
        assert count is None
        assert response_json(err)["error"]["code"] == ERR_INVALID_COUNT

    def test_count_at_max_is_accepted(self):
        limit = max_batch_size()
        req = make_request(params={"count": str(limit)})
        count, err = parse_count(req)
        assert err is None
        assert count == limit

    def test_count_over_max_returns_422(self):
        limit = max_batch_size()
        req = make_request(params={"count": str(limit + 1)})
        count, err = parse_count(req)
        assert count is None
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
        req = make_request(method="GET")
        resp = generate_single_world(req)
        assert resp.status_code == 200

    def test_post_returns_200(self):
        req = make_request(method="POST")
        resp = generate_single_world(req)
        assert resp.status_code == 200

    def test_response_is_valid_json(self):
        req = make_request()
        resp = generate_single_world(req)
        body = response_json(resp)  # raises if invalid
        assert isinstance(body, dict)

    def test_response_has_all_required_keys(self):
        req = make_request()
        body = response_json(generate_single_world(req))
        assert WORLD_TOP_LEVEL_KEYS == set(body.keys())

    def test_name_param_respected(self):
        req = make_request(params={"name": "Mora"})
        body = response_json(generate_single_world(req))
        assert body["name"] == "Mora"

    def test_default_name_used_when_absent(self):
        req = make_request()
        body = response_json(generate_single_world(req))
        assert body["name"] == "World-1"

    def test_seed_produces_deterministic_result(self):
        req1 = make_request(params={"name": "Test", "seed": "42"})
        req2 = make_request(params={"name": "Test", "seed": "42"})
        body1 = response_json(generate_single_world(req1))
        body2 = response_json(generate_single_world(req2))
        assert body1["uwp"] == body2["uwp"]

    def test_uwp_format(self):
        import re
        req = make_request(params={"seed": "1"})
        body = response_json(generate_single_world(req))
        assert re.match(r"^[ABCDEX][0-9A-G]{6}-[0-9A-G]$", body["uwp"])

    def test_temperature_is_valid_enum(self):
        req = make_request(params={"seed": "7"})
        body = response_json(generate_single_world(req))
        assert body["temperature"] in {"Frozen", "Cold", "Temperate", "Hot", "Boiling"}

    def test_travel_zone_is_valid_enum(self):
        req = make_request(params={"seed": "3"})
        body = response_json(generate_single_world(req))
        assert body["travel_zone"] in {"Green", "Amber", "Red"}

    def test_starport_code_is_valid(self):
        req = make_request(params={"seed": "5"})
        body = response_json(generate_single_world(req))
        assert body["starport"]["code"] in {"A", "B", "C", "D", "E", "X"}

    def test_bases_is_list_of_valid_codes(self):
        req = make_request(params={"seed": "9"})
        body = response_json(generate_single_world(req))
        assert isinstance(body["bases"], list)
        for code in body["bases"]:
            assert code in {"C", "H", "M", "N", "S"}

    def test_trade_codes_are_valid(self):
        valid_codes = {
            "Ag", "As", "Ba", "De", "Fl", "Ga", "Hi", "Ht", "Ic", "In",
            "Lo", "Lt", "Na", "Ni", "Po", "Ri", "Va", "Wa",
        }
        req = make_request(params={"seed": "11"})
        body = response_json(generate_single_world(req))
        for code in body["trade_codes"]:
            assert code in valid_codes

    def test_has_gas_giant_is_bool(self):
        req = make_request(params={"seed": "13"})
        body = response_json(generate_single_world(req))
        assert isinstance(body["has_gas_giant"], bool)

    def test_notes_is_list(self):
        req = make_request(params={"seed": "17"})
        body = response_json(generate_single_world(req))
        assert isinstance(body["notes"], list)

    def test_post_with_json_body_name(self):
        req = make_request(method="POST", body={"name": "Regina", "seed": 10})
        body = response_json(generate_single_world(req))
        assert body["name"] == "Regina"


# ===========================================================================
# TestGenerateSingleWorldErrors
# ===========================================================================

class TestGenerateSingleWorldErrors:
    """Error-path tests for /api/world."""

    def test_invalid_seed_returns_400(self):
        req = make_request(params={"seed": "not-a-number"})
        resp = generate_single_world(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_INVALID_SEED

    def test_name_too_long_returns_400(self):
        req = make_request(params={"name": "X" * 65})
        resp = generate_single_world(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_NAME_TOO_LONG

    def test_internal_error_returns_500(self):
        """Simulate an unexpected exception in generate_world()."""
        req = make_request()
        with patch("function_app.generate_world", side_effect=RuntimeError("boom")):
            resp = generate_single_world(req)
        assert resp.status_code == 500
        assert response_json(resp)["error"]["code"] == ERR_INTERNAL


# ===========================================================================
# TestGenerateNamedWorld
# ===========================================================================

class TestGenerateNamedWorld:
    """Happy-path tests for GET /api/world/{name}."""

    def test_returns_200(self):
        req = make_request(route_params={"name": "Mora"})
        resp = generate_named_world(req)
        assert resp.status_code == 200

    def test_name_from_route_param(self):
        req = make_request(route_params={"name": "Efate"})
        body = response_json(generate_named_world(req))
        assert body["name"] == "Efate"

    def test_seed_respected(self):
        req1 = make_request(params={"seed": "42"},
                            route_params={"name": "Glisten"})
        req2 = make_request(params={"seed": "42"},
                            route_params={"name": "Glisten"})
        b1 = response_json(generate_named_world(req1))
        b2 = response_json(generate_named_world(req2))
        assert b1["uwp"] == b2["uwp"]

    def test_response_has_all_required_keys(self):
        req = make_request(route_params={"name": "Aramis"})
        body = response_json(generate_named_world(req))
        assert WORLD_TOP_LEVEL_KEYS == set(body.keys())

    def test_different_names_produce_correct_name_field(self):
        for world_name in ("Rhylanor", "Jae Tellona", "Porozlo"):
            req = make_request(route_params={"name": world_name})
            body = response_json(generate_named_world(req))
            assert body["name"] == world_name


# ===========================================================================
# TestGenerateNamedWorldErrors
# ===========================================================================

class TestGenerateNamedWorldErrors:
    """Error-path tests for /api/world/{name}."""

    def test_name_too_long_returns_400(self):
        long_name = "Z" * 65
        req = make_request(route_params={"name": long_name})
        resp = generate_named_world(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_NAME_TOO_LONG

    def test_invalid_seed_returns_400(self):
        req = make_request(params={"seed": "xyz"},
                           route_params={"name": "Mora"})
        resp = generate_named_world(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_INVALID_SEED

    def test_internal_error_returns_500(self):
        req = make_request(route_params={"name": "Mora"})
        with patch("function_app.generate_world", side_effect=RuntimeError("boom")):
            resp = generate_named_world(req)
        assert resp.status_code == 500
        assert response_json(resp)["error"]["code"] == ERR_INTERNAL


# ===========================================================================
# TestGenerateWorldBatch
# ===========================================================================

class TestGenerateWorldBatch:
    """Happy-path tests for POST /api/worlds."""

    def test_returns_200(self):
        req = make_request(method="POST", body={"count": 1})
        resp = generate_world_batch(req)
        assert resp.status_code == 200

    def test_response_has_count_and_worlds_keys(self):
        req = make_request(method="POST", body={"count": 2})
        body = response_json(generate_world_batch(req))
        assert "count" in body
        assert "worlds" in body

    def test_count_field_matches_requested_count(self):
        req = make_request(method="POST", body={"count": 3})
        body = response_json(generate_world_batch(req))
        assert body["count"] == 3
        assert len(body["worlds"]) == 3

    def test_default_count_is_one(self):
        req = make_request(method="POST", body={})
        body = response_json(generate_world_batch(req))
        assert body["count"] == 1
        assert len(body["worlds"]) == 1

    def test_empty_body_uses_default_count(self):
        req = make_request(method="POST")
        body = response_json(generate_world_batch(req))
        assert body["count"] == 1

    def test_default_prefix_world_dash(self):
        req = make_request(method="POST", body={"count": 2})
        body = response_json(generate_world_batch(req))
        assert body["worlds"][0]["name"] == "World-1"
        assert body["worlds"][1]["name"] == "World-2"

    def test_custom_prefix_applied(self):
        req = make_request(method="POST",
                           body={"count": 3, "prefix": "Spinward-"})
        body = response_json(generate_world_batch(req))
        assert body["worlds"][0]["name"] == "Spinward-1"
        assert body["worlds"][2]["name"] == "Spinward-3"

    def test_prefix_from_query_string(self):
        req = make_request(method="POST",
                           params={"prefix": "Q-", "count": "2"})
        body = response_json(generate_world_batch(req))
        assert body["worlds"][0]["name"] == "Q-1"

    def test_seed_produces_deterministic_batch(self):
        req1 = make_request(method="POST",
                            body={"count": 3, "seed": 55})
        req2 = make_request(method="POST",
                            body={"count": 3, "seed": 55})
        b1 = response_json(generate_world_batch(req1))
        b2 = response_json(generate_world_batch(req2))
        for w1, w2 in zip(b1["worlds"], b2["worlds"]):
            assert w1["uwp"] == w2["uwp"]

    def test_each_world_has_all_required_keys(self):
        req = make_request(method="POST", body={"count": 5})
        body = response_json(generate_world_batch(req))
        for world in body["worlds"]:
            assert WORLD_TOP_LEVEL_KEYS == set(world.keys())

    def test_count_from_query_string(self):
        req = make_request(method="POST", params={"count": "4"})
        body = response_json(generate_world_batch(req))
        assert body["count"] == 4
        assert len(body["worlds"]) == 4

    def test_max_batch_size_accepted(self):
        from shared.helpers import max_batch_size
        limit = max_batch_size()
        req = make_request(method="POST", body={"count": limit})
        resp = generate_world_batch(req)
        assert resp.status_code == 200
        assert response_json(resp)["count"] == limit


# ===========================================================================
# TestGenerateWorldBatchErrors
# ===========================================================================

class TestGenerateWorldBatchErrors:
    """Error-path tests for POST /api/worlds."""

    def test_invalid_json_body_returns_400(self):
        req = make_request(method="POST", body=b"not json at all {{{")
        resp = generate_world_batch(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_INVALID_BODY

    def test_body_not_object_returns_400(self):
        req = make_request(method="POST", body=[1, 2, 3])
        resp = generate_world_batch(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_INVALID_BODY

    def test_count_zero_returns_400(self):
        req = make_request(method="POST", body={"count": 0})
        resp = generate_world_batch(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_INVALID_COUNT

    def test_count_too_large_returns_422(self):
        from shared.helpers import max_batch_size
        limit = max_batch_size()
        req = make_request(method="POST", body={"count": limit + 1})
        resp = generate_world_batch(req)
        assert resp.status_code == 422
        assert response_json(resp)["error"]["code"] == ERR_COUNT_TOO_LARGE

    def test_invalid_seed_returns_400(self):
        req = make_request(method="POST", body={"count": 2, "seed": "bad"})
        resp = generate_world_batch(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_INVALID_SEED

    def test_prefix_too_long_returns_400(self):
        req = make_request(method="POST",
                           body={"count": 1, "prefix": "P" * 33})
        resp = generate_world_batch(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_INVALID_BODY

    def test_internal_error_returns_500(self):
        req = make_request(method="POST", body={"count": 1})
        with patch("function_app.generate_world", side_effect=RuntimeError("boom")):
            resp = generate_world_batch(req)
        assert resp.status_code == 500
        assert response_json(resp)["error"]["code"] == ERR_INTERNAL


# ===========================================================================
# TestResponseSchema
# ===========================================================================

class TestResponseSchema:
    """Validate all 200 responses against traveller_world_schema.json.

    These tests use jsonschema if installed; they skip gracefully if not.
    """

    SCHEMA_PATH = os.path.join(PROJECT_ROOT, "traveller_world_schema.json")

    @classmethod
    def _schema(cls):
        with open(cls.SCHEMA_PATH, encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def _validator(cls):
        try:
            import jsonschema
            return jsonschema
        except ImportError:
            return None

    def test_single_world_response_validates(self):
        v = self._validator()
        if v is None:
            return  # skip if jsonschema not installed
        schema = self._schema()
        req = make_request(params={"seed": "1"})
        body = response_json(generate_single_world(req))
        v.validate(instance=body, schema=schema)

    def test_named_world_response_validates(self):
        v = self._validator()
        if v is None:
            return
        schema = self._schema()
        req = make_request(params={"seed": "2"},
                           route_params={"name": "Mora"})
        body = response_json(generate_named_world(req))
        v.validate(instance=body, schema=schema)

    def test_each_world_in_batch_validates(self):
        v = self._validator()
        if v is None:
            return
        schema = self._schema()
        req = make_request(method="POST", body={"count": 5, "seed": 3})
        payload = response_json(generate_world_batch(req))
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
            req = make_request(params={"seed": str(seed)})
            body = response_json(generate_single_world(req))
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
            req = make_request(params={"name": "Pinpoint", "seed": "77"})
            uwps.add(response_json(generate_single_world(req))["uwp"])
        assert len(uwps) == 1, f"Seed 77 produced different UWPs: {uwps}"

    def test_different_seeds_likely_differ(self):
        """Two different seeds should almost certainly produce different
        worlds (not guaranteed, but with a tiny false-failure probability)."""
        req_a = make_request(params={"seed": "100"})
        req_b = make_request(params={"seed": "200"})
        uwp_a = response_json(generate_single_world(req_a))["uwp"]
        uwp_b = response_json(generate_single_world(req_b))["uwp"]
        # There are 160+ possible UWPs; a collision here would be remarkable.
        assert uwp_a != uwp_b, (
            "Seeds 100 and 200 produced the same UWP — extremely unlikely "
            "unless the seeding logic is broken."
        )

    def test_batch_seed_matches_sequential_singles(self):
        """A seeded batch of N worlds should produce the same sequence as
        N sequential single-world calls with the same starting seed."""
        seed = 42
        count = 4

        # Batch call
        req_batch = make_request(method="POST",
                                 body={"count": count, "seed": seed})
        batch_uwps = [
            w["uwp"] for w in response_json(generate_world_batch(req_batch))["worlds"]
        ]

        # Sequential calls using the same seed progression
        random.seed(seed)
        from traveller_world_gen import generate_world as _gen
        sequential_uwps = [_gen(name=f"World-{i+1}").uwp() for i in range(count)]

        assert batch_uwps == sequential_uwps


# ===========================================================================
# TestGenerateWorldCard
# ===========================================================================

class TestGenerateWorldCard:
    """Tests for GET /api/world/{name}/card — HTML display card endpoint."""

    def test_returns_200(self):
        from function_app import generate_world_card
        req = make_request(route_params={"name": "Mora"})
        resp = generate_world_card(req)
        assert resp.status_code == 200

    def test_content_type_is_html(self):
        from function_app import generate_world_card
        req = make_request(route_params={"name": "Mora"})
        resp = generate_world_card(req)
        assert "text/html" in resp.mimetype

    def test_body_is_valid_html(self):
        from function_app import generate_world_card
        req = make_request(route_params={"name": "Cogri"})
        body = generate_world_card(req).get_body().decode("utf-8")
        assert "<!DOCTYPE html>" in body
        assert "<html" in body
        assert "</html>" in body

    def test_name_appears_in_html(self):
        from function_app import generate_world_card
        req = make_request(route_params={"name": "Regina"})
        body = generate_world_card(req).get_body().decode("utf-8")
        assert "Regina" in body

    def test_uwp_appears_in_html(self):
        from function_app import generate_world_card
        req = make_request(params={"seed": "42"},
                           route_params={"name": "Glisten"})
        body = generate_world_card(req).get_body().decode("utf-8")
        # UWP pattern: one letter followed by 6 hex chars, dash, one hex char
        import re
        assert re.search(r"[ABCDEX][0-9A-G]{6}-[0-9A-G]", body)

    def test_seed_produces_deterministic_html(self):
        from function_app import generate_world_card
        req1 = make_request(params={"seed": "7"}, route_params={"name": "T"})
        req2 = make_request(params={"seed": "7"}, route_params={"name": "T"})
        html1 = generate_world_card(req1).get_body().decode("utf-8")
        html2 = generate_world_card(req2).get_body().decode("utf-8")
        assert html1 == html2

    def test_tl_era_correct_in_html(self):
        """TL era labels in the card must match rulebook definitions.
        This is the regression test for the bug found in the inline widget."""
        from function_app import generate_world_card
        from traveller_world_gen import World
        # Force a known TL by generating and calling to_html() directly
        w8 = World(name="T", starport="C", size=5, atmosphere=6,
                   temperature="Temperate", hydrographics=5, population=5,
                   government=4, law_level=3, tech_level=8)
        assert "Pre-Stellar" in w8.to_html()
        assert "Early stellar age" not in w8.to_html()

    def test_name_too_long_returns_400(self):
        from function_app import generate_world_card
        req = make_request(route_params={"name": "Z" * 65})
        resp = generate_world_card(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_NAME_TOO_LONG

    def test_invalid_seed_returns_400(self):
        from function_app import generate_world_card
        req = make_request(params={"seed": "bad"},
                           route_params={"name": "Mora"})
        resp = generate_world_card(req)
        assert resp.status_code == 400
        assert response_json(resp)["error"]["code"] == ERR_INVALID_SEED

    def test_internal_error_returns_500(self):
        from function_app import generate_world_card
        req = make_request(route_params={"name": "Mora"})
        with patch("function_app.generate_world", side_effect=RuntimeError("boom")):
            resp = generate_world_card(req)
        assert resp.status_code == 500
        assert response_json(resp)["error"]["code"] == ERR_INTERNAL
