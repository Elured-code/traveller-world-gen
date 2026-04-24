"""
shared/helpers.py
=================
Utility functions shared across all Azure Function endpoints.

Responsibilities:
  - Parse and validate inbound query-string / JSON-body parameters.
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

import json
import logging
import os
import random
import re
import secrets
from typing import Any, Optional, Tuple

import azure.functions as func

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum worlds that may be requested in a single batch call.
# Overridable via the TRAVELLER_MAX_BATCH_SIZE environment variable so that
# the limit can be adjusted in Azure App Settings without redeploying.
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

def ok(body: Any, status_code: int = 200) -> func.HttpResponse:
    """Return a 200 (or custom) JSON response.

    Args:
        body: Any JSON-serialisable value.
        status_code: HTTP status code (default 200).

    Returns:
        An HttpResponse with Content-Type: application/json.
    """
    return func.HttpResponse(
        body=json.dumps(body, ensure_ascii=False),
        status_code=status_code,
        mimetype="application/json",
        charset="utf-8",
    )


def error(message: str, code: str, status_code: int = 400) -> func.HttpResponse:
    """Return a structured JSON error response.

    The body shape is:
        {
            "error": {
                "code":    "<machine-readable error code>",
                "message": "<human-readable description>"
            }
        }

    Args:
        message:     Human-readable description of what went wrong.
        code:        Machine-readable error code (see ERROR_* constants below).
        status_code: HTTP status code (default 400 Bad Request).

    Returns:
        An HttpResponse with Content-Type: application/json.
    """
    body = {"error": {"code": code, "message": message}}
    return func.HttpResponse(
        body=json.dumps(body, ensure_ascii=False),
        status_code=status_code,
        mimetype="application/json",
        charset="utf-8",
    )


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

ERR_INVALID_SEED       = "INVALID_SEED"
ERR_INVALID_COUNT      = "INVALID_COUNT"
ERR_COUNT_TOO_LARGE    = "COUNT_TOO_LARGE"
ERR_INVALID_BODY       = "INVALID_BODY"
ERR_INVALID_HEX        = "INVALID_HEX"
ERR_NAME_TOO_LONG      = "NAME_TOO_LONG"
ERR_MISSING_PARAM      = "MISSING_PARAM"
ERR_NOT_FOUND          = "NOT_FOUND"
ERR_UPSTREAM           = "UPSTREAM_ERROR"
ERR_INTERNAL           = "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Parameter parsing helpers
# ---------------------------------------------------------------------------

# Maximum length for a world name (prevents absurdly long strings).
MAX_NAME_LENGTH = 64


def parse_name(
    req: func.HttpRequest,
    route_name: Optional[str] = None,
) -> Tuple[Optional[str], Optional[func.HttpResponse]]:
    """Extract and validate the world name.

    Priority order:
      1. Route parameter (e.g. /api/world/{name})
      2. Query string  ?name=...
      3. JSON body     {"name": "..."}
      4. None (caller should use a sensible default)

    Returns:
        (name, None)       if valid or absent.
        (None, error_resp) if present but invalid.
    """
    # 1. Route parameter (passed in explicitly by the caller after extraction)
    name = route_name

    # 2. Query string
    if not name:
        name = req.params.get("name", "").strip() or None

    # 3. JSON body
    if not name:
        try:
            body = req.get_json()
            if isinstance(body, dict):
                name = str(body.get("name", "")).strip() or None
        except (ValueError, TypeError):
            pass  # body absent or non-JSON; handled elsewhere if needed

    if name and len(name) > MAX_NAME_LENGTH:
        return None, error(
            f"World name must be {MAX_NAME_LENGTH} characters or fewer.",
            ERR_NAME_TOO_LONG,
        )

    return name, None


def parse_seed(req: func.HttpRequest) -> Tuple[Optional[int], Optional[func.HttpResponse]]:
    """Extract and validate the optional random seed.

    Accepts ?seed=<int> in the query string or {"seed": <int>} in the body.

    Returns:
        (seed_int, None)   if valid or absent.
        (None, error_resp) if present but not a valid integer.
    """
    raw = req.params.get("seed", "").strip()

    if not raw:
        try:
            body = req.get_json()
            if isinstance(body, dict):
                raw = str(body.get("seed", "")).strip()
        except (ValueError, TypeError):
            pass

    if not raw:
        return None, None   # seed is optional

    try:
        return int(raw), None
    except ValueError:
        return None, error(
            f"'seed' must be an integer, got '{raw}'.",
            ERR_INVALID_SEED,
        )


def parse_count(req: func.HttpRequest) -> Tuple[Optional[int], Optional[func.HttpResponse]]:
    """Extract and validate the optional world count for batch requests.

    Accepts ?count=<int> in the query string or {"count": <int>} in the body.
    Must be a positive integer no greater than max_batch_size().

    Returns:
        (count_int, None)  if valid or absent (caller should default to 1).
        (None, error_resp) if present but invalid.
    """
    raw = req.params.get("count", "").strip()

    if not raw:
        try:
            body = req.get_json()
            if isinstance(body, dict):
                raw = str(body.get("count", "")).strip()
        except (ValueError, TypeError):
            pass

    if not raw:
        return None, None   # count is optional; caller defaults to 1

    try:
        count = int(raw)
    except ValueError:
        return None, error(
            f"'count' must be a positive integer, got '{raw}'.",
            ERR_INVALID_COUNT,
        )

    if count < 1:
        return None, error(
            "'count' must be at least 1.",
            ERR_INVALID_COUNT,
        )

    limit = max_batch_size()
    if count > limit:
        return None, error(
            f"'count' must not exceed {limit}. "
            f"Request {count} worlds via multiple calls if needed.",
            ERR_COUNT_TOO_LARGE,
            status_code=422,
        )

    return count, None


def parse_detail(req: func.HttpRequest) -> bool:
    """Extract the optional 'detail' flag.

    When True, the caller should run attach_detail() to populate secondary
    world and satellite data before serialising.  Accepts ?detail=true/1/yes
    in the query string or {"detail": true} in the body.  Defaults to False.

    Returns:
        True if detail generation was requested, False otherwise.
    """
    raw = req.params.get("detail", "").strip().lower()
    if not raw:
        try:
            body = req.get_json()
            if isinstance(body, dict):
                val = body.get("detail")
                if isinstance(val, bool):
                    return val
                raw = str(val).strip().lower() if val is not None else ""
        except (ValueError, TypeError):
            pass
    return raw in ("true", "1", "yes")

def parse_format(req: func.HttpRequest) -> str:
    """Extract the optional 'format' parameter.

    Accepted values: 'json' (default), 'html', 'text'.
    Accepts ?format=... in the query string or {"format": "..."} in the body.
    Unknown values fall back to 'json'.

    Returns:
        One of 'json', 'html', 'text'.
    """
    raw = req.params.get("format", "").strip().lower()
    if not raw:
        try:
            body = req.get_json()
            if isinstance(body, dict):
                raw = str(body.get("format", "")).strip().lower()
        except (ValueError, TypeError):
            pass
    return raw if raw in ("json", "html", "text") else "json"


MAX_SECTOR_LENGTH = 64


def parse_sector(
    req: func.HttpRequest,
) -> Tuple[Optional[str], Optional[func.HttpResponse]]:
    """Extract and validate the optional sector name.

    Accepts ?sector=... in the query string or {"sector": "..."} in the body.

    Returns:
        (sector_str, None)   if valid or absent.
        (None, error_resp)   if present but exceeds MAX_SECTOR_LENGTH.
    """
    sector = req.params.get("sector", "").strip() or None
    if not sector:
        try:
            body = req.get_json()
            if isinstance(body, dict):
                sector = str(body.get("sector", "")).strip() or None
        except (ValueError, TypeError):
            pass
    if sector and len(sector) > MAX_SECTOR_LENGTH:
        return None, error(
            f"Sector name must be {MAX_SECTOR_LENGTH} characters or fewer.",
            ERR_INVALID_BODY,
        )
    return sector, None


_HEX_RE = re.compile(r"^[0-9A-Fa-f]{4}$")


def parse_hex_pos(
    req: func.HttpRequest,
    body: Optional[dict] = None,
) -> Tuple[Optional[str], Optional[func.HttpResponse]]:
    """Extract and validate the optional hex-position parameter.

    Accepts ?hex=... in the query string or {"hex": "..."} in the body.
    Valid format: exactly four hex digits, e.g. "1910" or "0204".

    Returns:
        (hex_str, None)    if valid or absent.
        (None, error_resp) if present but not a valid 4-digit hex position.
    """
    hex_pos = req.params.get("hex", "").strip() or None
    if not hex_pos and body and isinstance(body, dict):
        hex_pos = str(body.get("hex", "")).strip() or None
    if hex_pos and not _HEX_RE.match(hex_pos):
        return None, error(
            "'hex' must be a 4-digit hex grid position (e.g. '1910').",
            ERR_INVALID_HEX,
        )
    return hex_pos, None


def parse_world_json(
    req: func.HttpRequest,
) -> Tuple[Optional[dict], Optional[func.HttpResponse]]:
    """Extract and validate a mainworld JSON object from the request body.

    The body must be a JSON object in the shape produced by World.to_dict().
    Minimal required fields: 'name' plus either 'uwp' or the individual
    characteristic sub-objects ('size', 'atmosphere', 'hydrographics',
    'population').

    Returns:
        (world_dict, None)   if valid.
        (None, error_resp)   if absent or invalid.
    """
    if not req.get_body():
        return None, error(
            "Request body is required and must be a mainworld JSON object.",
            ERR_INVALID_BODY,
        )
    try:
        data = req.get_json()
    except (ValueError, TypeError):
        return None, error("Request body is not valid JSON.", ERR_INVALID_BODY)

    if not isinstance(data, dict):
        return None, error(
            "Request body must be a JSON object (mainworld data).",
            ERR_INVALID_BODY,
        )

    has_uwp = "uwp" in data
    has_breakdown = all(k in data for k in ("size", "atmosphere", "hydrographics", "population"))
    if not has_uwp and not has_breakdown:
        return None, error(
            "Request body must include 'uwp' or the individual world "
            "characteristic fields (size, atmosphere, hydrographics, population).",
            ERR_INVALID_BODY,
        )

    return data, None


def apply_seed(seed: Optional[int]) -> int:
    """Seed the global random state and return the seed used.

    If *seed* is None a cryptographically random seed is generated via
    :mod:`secrets` so that results are always reproducible: callers can
    record the returned value and pass it back to reproduce the same output.

    Azure Functions runs one worker per invocation in the consumption plan,
    so there is no cross-request state leak, but note that in a Premium/
    Dedicated plan with warm instances the seed would affect all subsequent
    calls on that instance.  For production use at scale, consider passing
    the seed through to the generation logic rather than using global state.

    Returns:
        The integer seed that was applied to :func:`random.seed`.
    """
    if seed is None:
        seed = secrets.randbelow(2 ** 31)
    random.seed(seed)
    logger.debug("Random seed set to %d", seed)
    return seed
