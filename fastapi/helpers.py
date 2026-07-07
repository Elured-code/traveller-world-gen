"""
helpers.py
==========
Utility functions shared across all FastAPI endpoints.

Mirrors azure-api/shared/helpers.py with FastAPI-native types.  Uses a flat
module (not a shared/ sub-package) to avoid a sys.path naming conflict with
azure-api/shared/ when both directories are on sys.path during tests.

Responsibilities:
  - Parse and validate inbound query-string / JSON-body / path parameters.
  - Build consistent JSON HTTP responses (success and error).
  - Centralise error code strings so endpoints never hard-code them.

Licence
-------
MIT Licence — see the LICENSE file in the project root.

Traveller IP notice: This software implements rules from the Traveller
roleplaying game. Any use in connection with the Traveller IP is subject
to Mongoose Publishing's Fair Use Policy, which prohibits commercial use.
The Traveller game in all forms is owned by Mongoose Publishing.
Copyright 1977-2025 Mongoose Publishing. All rights reserved.
This is an unofficial fan work, not affiliated with Mongoose Publishing.

AI assistance disclosure: developed with Claude (Anthropic).
The human author reviewed, directed, and is responsible for the code.
"""

import logging
import os
import random
import re
import secrets
from typing import Any, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_BATCH = 20
_MAX_BATCH_UPPER = 1000


def max_batch_size() -> int:
    """Return the maximum allowed batch size, from env or default."""
    try:
        size = int(os.environ.get("TRAVELLER_MAX_BATCH_SIZE", DEFAULT_MAX_BATCH))
        if 1 <= size <= _MAX_BATCH_UPPER:
            return size
    except (ValueError, OverflowError):
        pass
    return DEFAULT_MAX_BATCH


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def ok(body: Any, status_code: int = 200) -> JSONResponse:
    """Return a 200 (or custom) JSON response.

    Args:
        body: Any JSON-serialisable value.
        status_code: HTTP status code (default 200).

    Returns:
        A JSONResponse with Content-Type: application/json.
    """
    return JSONResponse(content=body, status_code=status_code)


def error(message: str, code: str, status_code: int = 400) -> JSONResponse:
    """Return a structured JSON error response.

    The body shape is::

        {"error": {"code": "<machine-readable>", "message": "<human-readable>"}}

    Args:
        message:     Human-readable description of what went wrong.
        code:        Machine-readable error code (see ERR_* constants below).
        status_code: HTTP status code (default 400 Bad Request).

    Returns:
        A JSONResponse with Content-Type: application/json.
    """
    return JSONResponse(
        content={"error": {"code": code, "message": message}},
        status_code=status_code,
    )


# ---------------------------------------------------------------------------
# Error codes (identical to azure-api/shared/helpers.py)
# ---------------------------------------------------------------------------

ERR_INVALID_SEED    = "INVALID_SEED"
ERR_INVALID_COUNT   = "INVALID_COUNT"
ERR_COUNT_TOO_LARGE = "COUNT_TOO_LARGE"
ERR_INVALID_BODY    = "INVALID_BODY"
ERR_INVALID_HEX     = "INVALID_HEX"
ERR_NAME_TOO_LONG   = "NAME_TOO_LONG"
ERR_MISSING_PARAM   = "MISSING_PARAM"
ERR_NOT_FOUND       = "NOT_FOUND"
ERR_UPSTREAM        = "UPSTREAM_ERROR"
ERR_INTERNAL        = "INTERNAL_ERROR"
ERR_PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"


# ---------------------------------------------------------------------------
# Parameter parsing helpers
# ---------------------------------------------------------------------------

MAX_NAME_LENGTH = 64


def parse_name(
    request: Request,
    body: dict,
    route_name: Optional[str] = None,
) -> Tuple[Optional[str], Optional[JSONResponse]]:
    """Extract and validate the world name.

    Priority order:
      1. Route parameter (passed in explicitly by the caller)
      2. Query string  ?name=...
      3. JSON body     {"name": "..."}
      4. None (caller should use a sensible default)

    Returns:
        (name, None)       if valid or absent.
        (None, error_resp) if present but invalid.
    """
    name = route_name
    if not name:
        name = request.query_params.get("name", "").strip() or None
    if not name:
        name = str(body.get("name", "")).strip() or None
    if name and len(name) > MAX_NAME_LENGTH:
        return None, error(
            f"World name must be {MAX_NAME_LENGTH} characters or fewer.",
            ERR_NAME_TOO_LONG,
        )
    return name, None


def parse_seed(
    request: Request,
    body: dict,
) -> Tuple[Optional[int], Optional[JSONResponse]]:
    """Extract and validate the optional random seed.

    Accepts ?seed=<int> in the query string or {"seed": <int>} in the body.

    Returns:
        (seed_int, None)   if valid or absent.
        (None, error_resp) if present but not a valid integer.
    """
    raw = request.query_params.get("seed", "").strip()
    if not raw:
        raw = str(body.get("seed", "")).strip()
    if not raw:
        return None, None
    try:
        return int(raw), None
    except ValueError:
        return None, error(
            f"'seed' must be an integer, got '{raw}'.",
            ERR_INVALID_SEED,
        )


def parse_count(
    request: Request,
    body: dict,
) -> Tuple[Optional[int], Optional[JSONResponse]]:
    """Extract and validate the optional world count for batch requests.

    Accepts ?count=<int> in the query string or {"count": <int>} in the body.
    Must be a positive integer no greater than max_batch_size().

    Returns:
        (count_int, None)  if valid or absent (caller should default to 1).
        (None, error_resp) if present but invalid.
    """
    raw = request.query_params.get("count", "").strip()
    if not raw:
        raw = str(body.get("count", "")).strip()
    if not raw:
        return None, None
    try:
        count = int(raw)
    except ValueError:
        return None, error(
            f"'count' must be a positive integer, got '{raw}'.",
            ERR_INVALID_COUNT,
        )
    if count < 1:
        return None, error("'count' must be at least 1.", ERR_INVALID_COUNT)
    limit = max_batch_size()
    if count > limit:
        return None, error(
            f"'count' must not exceed {limit}. "
            f"Request {count} worlds via multiple calls if needed.",
            ERR_COUNT_TOO_LARGE,
            status_code=422,
        )
    return count, None


def _parse_bool_param(request: Request, body: dict, key: str) -> bool:
    """Parse a named boolean flag from query string or body."""
    raw = request.query_params.get(key, "").strip().lower()
    if not raw:
        val = body.get(key)
        if isinstance(val, bool):
            return val
        raw = str(val).strip().lower() if val is not None else ""
    return raw in ("true", "1", "yes")


def parse_detail(request: Request, body: dict) -> bool:
    """Extract the optional 'detail' flag.

    When True, the caller should run attach_detail() to populate secondary
    world and satellite data before serialising.
    """
    return _parse_bool_param(request, body, "detail")


def parse_orbital_eccentricity(request: Request, body: dict) -> bool:
    """Extract the optional 'orbital_eccentricity' flag (WBH p.27)."""
    return _parse_bool_param(request, body, "orbital_eccentricity")


def parse_orbital_inclination(request: Request, body: dict) -> bool:
    """Extract the optional 'orbital_inclination' flag (WBH p.28)."""
    return _parse_bool_param(request, body, "orbital_inclination")


def parse_nhz_atmospheres(request: Request, body: dict) -> bool:
    """Extract the optional 'nhz_atmospheres' flag (WBH pp.42-48)."""
    return _parse_bool_param(request, body, "nhz_atmospheres")


def parse_runaway_greenhouse(request: Request, body: dict) -> bool:
    """Extract the optional 'runaway_greenhouse' flag (WBH p.79)."""
    return _parse_bool_param(request, body, "runaway_greenhouse")


def parse_independent_government(request: Request, body: dict) -> bool:
    """Extract the optional 'independent_government' flag (WBH p.162)."""
    return _parse_bool_param(request, body, "independent_government")


def parse_optional_biomass(request: Request, body: dict) -> bool:
    """Extract the optional 'optional_biomass_rule' flag (WBH p.131)."""
    return _parse_bool_param(request, body, "optional_biomass_rule")


def parse_optional_inhospitable(request: Request, body: dict) -> bool:
    """Extract the optional 'optional_inhospitable_rule' flag (WBH p.130)."""
    return _parse_bool_param(request, body, "optional_inhospitable_rule")


_VALID_SETTLEMENT_TYPES = frozenset(
    {"standard", "long_settled", "well_settled", "backwater", "unsettled"}
)


def parse_settlement_type(request: Request, body: dict) -> str:
    """Extract the optional 'settlement_type' parameter.

    Accepted values: 'standard' (default), 'long_settled', 'well_settled',
    'backwater', 'unsettled'. Unknown values fall back to 'standard'.
    """
    raw = request.query_params.get("settlement_type", "").strip().lower()
    if not raw:
        raw = str(body.get("settlement_type", "")).strip().lower()
    return raw if raw in _VALID_SETTLEMENT_TYPES else "standard"


def parse_social_detail(request: Request, body: dict) -> bool:
    """Extract the optional 'social_detail' flag.

    When True, the caller should run attach_government_detail() and
    attach_law_detail() to populate government profile, judicial system,
    law subcategory scores, and law profile on all inhabited worlds.
    """
    return _parse_bool_param(request, body, "social_detail")


def parse_include_mw_card(request: Request, body: dict) -> bool:
    """Extract the optional 'include_mw_card' flag.

    When True and format=html, the /api/system/full endpoint returns a JSON
    object with 'sys_html' and 'mw_html' keys instead of bare system HTML, so
    the mainworld card comes from the same generation as the system table.
    """
    return _parse_bool_param(request, body, "include_mw_card")


def parse_format(request: Request, body: dict) -> str:
    """Extract the optional 'format' parameter.

    Accepted values: 'json' (default), 'html', 'text'.
    Unknown values fall back to 'json'.
    """
    raw = request.query_params.get("format", "").strip().lower()
    if not raw:
        raw = str(body.get("format", "")).strip().lower()
    return raw if raw in ("json", "html", "text") else "json"


MAX_SECTOR_LENGTH = 64


def parse_sector(
    request: Request,
    body: dict,
) -> Tuple[Optional[str], Optional[JSONResponse]]:
    """Extract and validate the optional sector name."""
    sector = request.query_params.get("sector", "").strip() or None
    if not sector:
        sector = str(body.get("sector", "")).strip() or None
    if sector and len(sector) > MAX_SECTOR_LENGTH:
        return None, error(
            f"Sector name must be {MAX_SECTOR_LENGTH} characters or fewer.",
            ERR_INVALID_BODY,
        )
    return sector, None


_HEX_RE = re.compile(r"^[0-9A-Fa-f]{4}$")


def parse_hex_pos(
    request: Request,
    body: dict,
) -> Tuple[Optional[str], Optional[JSONResponse]]:
    """Extract and validate the optional hex-position parameter.

    Valid format: exactly four hex digits, e.g. "1910" or "0204".
    """
    hex_pos = request.query_params.get("hex", "").strip() or None
    if not hex_pos:
        hex_pos = str(body.get("hex", "")).strip() or None
    if hex_pos and not _HEX_RE.match(hex_pos):
        return None, error(
            "'hex' must be a 4-digit hex grid position (e.g. '1910').",
            ERR_INVALID_HEX,
        )
    return hex_pos, None


def parse_world_json(
    body_raw: bytes,
    body: dict,
) -> Tuple[Optional[dict], Optional[JSONResponse]]:
    """Validate a mainworld JSON object from the request body.

    The body must be a JSON object in the shape produced by World.to_dict().
    Minimal required fields: either 'uwp' or the individual characteristic
    sub-objects ('size', 'atmosphere', 'hydrographics', 'population').

    Args:
        body_raw: Raw bytes of the request body (used only to detect absence).
        body:     Already-parsed dict (empty if body was absent or invalid).

    Returns:
        (world_dict, None)   if valid.
        (None, error_resp)   if absent or invalid.
    """
    if not body_raw:
        return None, error(
            "Request body is required and must be a mainworld JSON object.",
            ERR_INVALID_BODY,
        )
    has_uwp = "uwp" in body
    has_breakdown = all(
        k in body for k in ("size", "atmosphere", "hydrographics", "population")
    )
    if not has_uwp and not has_breakdown:
        return None, error(
            "Request body must include 'uwp' or the individual world "
            "characteristic fields (size, atmosphere, hydrographics, population).",
            ERR_INVALID_BODY,
        )
    return body, None


def apply_seed(seed: Optional[int]) -> Tuple[int, random.Random]:
    """Create a seeded random.Random instance and return (seed, rng).

    If *seed* is None a cryptographically random seed is generated via
    :mod:`secrets` so that results are always reproducible.

    Returns:
        A (seed, rng) tuple where seed is the integer used and rng is a
        :class:`random.Random` instance initialised with that seed.
    """
    if seed is None:
        seed = secrets.randbelow(2 ** 31)
    rng = random.Random(seed)
    logger.debug("Random seed set to %d", seed)
    return seed, rng
