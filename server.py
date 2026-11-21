#!/usr/bin/env python3
"""Relay Quote, a Pocket-ready JSON backend.

The process reads configuration from the environment only. It does not open
.env. Use run.ps1 or run.sh, which load that file before starting Python.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SERVICE_ID = os.environ.get("SERVICE_ID", "relay-quote")
SERVICE_VERSION = os.environ.get("SERVICE_VERSION", "1.0.0")
HOST = os.environ.get("HOST", "127.0.0.1")
MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", str(1024 * 1024)))
ROYALTY_SOURCE = "configured_estimate_not_live_chain_state"
MAIN_REST_URL = os.environ.get(
    "MAIN_REST_URL", "https://sauron-api.infra.pocket.network"
).rstrip("/")
BETA_REST_URL = os.environ.get(
    "BETA_REST_URL", "https://sauron-api.beta.infra.pocket.network"
).rstrip("/")
UPSTREAM_DEADLINE_SECONDS = float(os.environ.get("UPSTREAM_DEADLINE_SECONDS", "12"))
UPSTREAM_DELAY_SECONDS = float(os.environ.get("UPSTREAM_DELAY_SECONDS", "0"))
ALLOW_TEST_HOOKS = os.environ.get("ALLOW_TEST_HOOKS", "") == "1"
CU_MIN = 1
CU_MAX = 1_048_576
COUNT_MAX = 1_000_000
INT_MAX = 10**18

ROOT = os.path.dirname(os.path.abspath(__file__))
OPENAPI_FILE = os.environ.get(
    "OPENAPI_PATH", os.path.join(ROOT, "openapi", "v1", "openapi.json")
)

NETWORKS = {
    "main": {"chain_id": "pocket", "rest_url": MAIN_REST_URL},
    "beta": {"chain_id": "pocket-lego-testnet", "rest_url": BETA_REST_URL},
}

LOG = logging.getLogger("relay-quote")


class RequestError(Exception):
    def __init__(self, status, code, message, extra=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}


def load_port():
    raw = os.environ.get("PORT", "8080")
    try:
        port = int(raw)
    except ValueError as exc:
        raise SystemExit("PORT must be an integer") from exc
    if port < 0 or port > 65535:
        raise SystemExit("PORT must be from 0 to 65535")
    return port


def load_royalty_rate():
    raw = os.environ.get("ROYALTY_RATE", "0.025")
    try:
        rate = Decimal(raw)
    except InvalidOperation as exc:
        raise SystemExit("ROYALTY_RATE must be a decimal") from exc
    if rate < 0 or rate > 1:
        raise SystemExit("ROYALTY_RATE must be from 0 to 1")
    return rate


ROYALTY_RATE = load_royalty_rate()
PORT = load_port()


def format_pokt(upokt):
    sign = "-" if upokt < 0 else ""
    whole, frac = divmod(abs(int(upokt)), 1_000_000)
    return f"{sign}{whole}.{frac:06d}"


def quote(compute_units, multiplier, granularity, relay_count, rate):
    per_relay = (compute_units * multiplier) // granularity
    cost = per_relay * relay_count
    share = (Decimal(cost) * rate).to_integral_value(rounding=ROUND_DOWN)
    return {
        "service": SERVICE_ID,
        "compute_units_per_relay": compute_units,
        "relay_count": relay_count,
        "compute_units_to_tokens_multiplier": multiplier,
        "compute_unit_cost_granularity": granularity,
        "cost_upokt": str(cost),
        "cost_pokt": format_pokt(cost),
        "owner_share_upokt": str(int(share)),
        "owner_share_pokt": format_pokt(int(share)),
        "royalty_rate": format(rate, "f"),
        "royalty_source": ROYALTY_SOURCE,
        "division": "floor",
    }


def as_int(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int):
        raise RequestError(422, "invalid_number", f"{name} must be an integer.")
    if value < low or value > high:
        raise RequestError(
            422,
            "number_out_of_range",
            f"{name} must be from {low} to {high}.",
        )
    return value


def require_int(body, name, low, high):
    if name not in body:
        raise RequestError(422, "missing_field", f"Missing integer field {name}.")
    return as_int(body[name], name, low, high)


def optional_int(body, name, low, high, default):
    if name not in body:
        return default
    return as_int(body[name], name, low, high)


def fetch_json(url):
    if UPSTREAM_DELAY_SECONDS > 0:
        time.sleep(UPSTREAM_DELAY_SECONDS)
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"relay-quote/{SERVICE_VERSION}",
        },
    )
    try:
        with urlopen(request, timeout=UPSTREAM_DEADLINE_SECONDS) as response:
            raw = response.read(MAX_BODY_BYTES + 1)
    except TimeoutError as exc:
        raise RequestError(
            504,
            "upstream_deadline",
            "The Pocket parameter source did not answer before the local deadline.",
        ) from exc
    except (HTTPError, URLError, OSError) as exc:
        raise RequestError(
            502,
            "upstream_query_failed",
            "The requested Pocket network parameter source was unavailable.",
        ) from exc
    if len(raw) > MAX_BODY_BYTES:
        raise RequestError(
            502,
            "upstream_query_failed",
            "The requested Pocket network parameter source was unavailable.",
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestError(
            502,
            "upstream_query_failed",
            "The requested Pocket network parameter source was unavailable.",
        ) from exc
    if not isinstance(payload, dict):
        raise RequestError(
            502,
            "upstream_query_failed",
            "The requested Pocket network parameter source was unavailable.",
        )
    return payload


def live_status(network, compute_units):
    if ALLOW_TEST_HOOKS and network == "delay":
        time.sleep(UPSTREAM_DELAY_SECONDS or 1)
        return {"service": SERVICE_ID, "status": "ok", "hook": "delay"}
    if network not in NETWORKS:
        raise RequestError(
            422,
            "invalid_network",
            "network must be main or beta.",
        )
    spec = NETWORKS[network]
    shared = fetch_json(spec["rest_url"] + "/pokt-network/poktroll/shared/params")
    service = fetch_json(spec["rest_url"] + "/pokt-network/poktroll/service/params")
    try:
        shared_params = shared["params"]
        multiplier = int(shared_params["compute_units_to_tokens_multiplier"])
        granularity = int(shared_params["compute_unit_cost_granularity"])
        blocks = int(shared_params["num_blocks_per_session"])
        fee = service["params"]["add_service_fee"]
        fee_amount = str(fee["amount"])
        fee_denom = str(fee["denom"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RequestError(
            502,
            "upstream_query_failed",
            "The requested Pocket network parameter source was unavailable.",
        ) from exc
    if granularity < 1:
        raise RequestError(
            502,
            "upstream_query_failed",
            "The requested Pocket network parameter source was unavailable.",
        )
    body = {
        "service": SERVICE_ID,
        "network": network,
        "chain_id": spec["chain_id"],
        "compute_units_to_tokens_multiplier": multiplier,
        "compute_unit_cost_granularity": granularity,
        "num_blocks_per_session": blocks,
        "add_service_fee_upokt": fee_amount,
        "add_service_fee_denom": fee_denom,
        "parameter_source": "live_public_rest",
    }
    if compute_units is not None:
        body["quote"] = quote(
            compute_units, multiplier, granularity, 1, ROYALTY_RATE
        )
    return body


class RelayQuoteHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "relay-quote/" + SERVICE_VERSION

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        self._dispatch(head=False)

    def do_HEAD(self):
        self._dispatch(head=True)

    def do_POST(self):
        self._dispatch(head=False)

    def do_PUT(self):
        self._method_not_allowed()

    def do_DELETE(self):
        self._method_not_allowed()

    def do_PATCH(self):
        self._method_not_allowed()

    def _method_not_allowed(self):
        self._send_json(
            405,
            {
                "error": "method_not_allowed",
                "message": "Use GET, HEAD, or POST.",
            },
            head=False,
        )

    def _dispatch(self, head):
        started = time.perf_counter()
        request_id = uuid.uuid4().hex[:16]
        status = 500
        try:
            status, payload = self._route(head)
            self._send_json(status, payload, head=head, request_id=request_id)
        except RequestError as exc:
            status = exc.status
            payload = {"error": exc.code, "message": exc.message}
            payload.update(exc.extra)
            self._send_json(status, payload, head=head, request_id=request_id)
        except Exception:
            LOG.exception("request_id=%s unhandled path=%s", request_id, self.path)
            status = 500
            self._send_json(
                500,
                {
                    "error": "internal_error",
                    "message": "The server failed while handling the request.",
                },
                head=head,
                request_id=request_id,
            )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        LOG.info(
            "request_id=%s method=%s path=%s status=%s elapsed_ms=%s",
            request_id,
            self.command,
            self.path.split("?", 1)[0],
            status,
            elapsed_ms,
        )

    def _route(self, head):
        path = self.path.split("?", 1)[0]
        method = self.command
        if path == "/" and method in ("GET", "HEAD"):
            return 200, {"service": SERVICE_ID, "status": "ok"}
        if path == "/v1/version" and method in ("GET", "HEAD"):
            return 200, {"service": SERVICE_ID, "version": SERVICE_VERSION}
        if path == "/v1/health" and method in ("GET", "HEAD"):
            return 200, {"status": "ok"}
        if path == "/openapi/v1/openapi.json" and method in ("GET", "HEAD"):
            return 200, self._openapi()
        if path == "/v1/estimate":
            if method != "POST":
                raise RequestError(405, "method_not_allowed", "Use POST for this path.")
            return 200, self._estimate()
        if path == "/v1/network-status":
            if method != "POST":
                raise RequestError(405, "method_not_allowed", "Use POST for this path.")
            return 200, self._network_status()
        raise RequestError(404, "not_found", "No resource exists at this path.")

    def _openapi(self):
        try:
            with open(OPENAPI_FILE, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise RequestError(
                500,
                "internal_error",
                "The server failed while handling the request.",
            ) from exc
        if not isinstance(payload, dict):
            raise RequestError(
                500,
                "internal_error",
                "The server failed while handling the request.",
            )
        return payload

    def _estimate(self):
        body = self._read_object()
        compute_units = require_int(
            body, "compute_units_per_relay", CU_MIN, CU_MAX
        )
        multiplier = require_int(
            body, "compute_units_to_tokens_multiplier", 1, INT_MAX
        )
        granularity = require_int(
            body, "compute_unit_cost_granularity", 1, INT_MAX
        )
        relay_count = optional_int(body, "relay_count", 1, COUNT_MAX, 1)
        return quote(
            compute_units, multiplier, granularity, relay_count, ROYALTY_RATE
        )

    def _network_status(self):
        body = self._read_object()
        if ALLOW_TEST_HOOKS and body.get("test_hook") == "delay":
            return live_status("delay", None)
        network = body.get("network")
        if not isinstance(network, str):
            raise RequestError(422, "invalid_network", "network must be main or beta.")
        compute_units = None
        if "compute_units_per_relay" in body:
            compute_units = as_int(
                body["compute_units_per_relay"],
                "compute_units_per_relay",
                CU_MIN,
                CU_MAX,
            )
        try:
            return live_status(network, compute_units)
        except RequestError as exc:
            exc.extra.setdefault("network", network)
            raise

    def _read_object(self):
        raw = self._read_body()
        if raw.strip() == b"":
            raise RequestError(400, "empty_body", "The request body is empty.")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RequestError(
                400, "malformed_json", "The request body is not valid JSON."
            ) from exc
        if not isinstance(value, dict):
            raise RequestError(
                422,
                "invalid_json_type",
                "The request body must be a JSON object.",
            )
        return value

    def _read_body(self):
        transfer = (self.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" in transfer:
            return self._read_chunked()
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return b""
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise RequestError(
                400, "malformed_body", "Content-Length is not an integer."
            ) from exc
        if length < 0:
            raise RequestError(400, "malformed_body", "Content-Length is invalid.")
        if length > MAX_BODY_BYTES:
            raise RequestError(
                422, "body_too_large", "The request body exceeds 1 MiB."
            )
        data = self.rfile.read(length)
        if len(data) != length:
            raise RequestError(
                400, "malformed_body", "The request body ended early."
            )
        return data

    def _read_line(self):
        buf = bytearray()
        while len(buf) <= 4096:
            piece = self.rfile.read(1)
            if not piece:
                raise RequestError(
                    400, "malformed_chunk", "The chunked body ended early."
                )
            buf += piece
            if buf.endswith(b"\r\n"):
                return bytes(buf[:-2])
        raise RequestError(400, "malformed_chunk", "A chunk header is too long.")

    def _read_chunked(self):
        out = bytearray()
        while True:
            line = self._read_line()
            size_token = line.split(b";", 1)[0].strip()
            if size_token == b"":
                raise RequestError(400, "malformed_chunk", "A chunk size is missing.")
            try:
                size = int(size_token, 16)
            except ValueError as exc:
                raise RequestError(
                    400, "malformed_chunk", "A chunk size is not hexadecimal."
                ) from exc
            if size == 0:
                while self._read_line() != b"":
                    continue
                return bytes(out)
            if len(out) + size > MAX_BODY_BYTES:
                raise RequestError(
                    422, "body_too_large", "The request body exceeds 1 MiB."
                )
            chunk = self.rfile.read(size)
            if len(chunk) != size:
                raise RequestError(
                    400, "malformed_chunk", "A chunk ended early."
                )
            if self.rfile.read(2) != b"\r\n":
                raise RequestError(
                    400, "malformed_chunk", "A chunk is missing its terminator."
                )
            out += chunk

    def _send_json(self, status, payload, head, request_id=""):
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Encoding", "identity")
        # HEAD carries the same length a GET would send, and no body bytes.
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if request_id:
            self.send_header("X-Request-Id", request_id)
        self.end_headers()
        if not head:
            self.wfile.write(raw)


class RelayQuoteServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    server = RelayQuoteServer((HOST, PORT), RelayQuoteHandler)
    LOG.info(
        "listening host=%s port=%s service=%s version=%s",
        HOST,
        PORT,
        SERVICE_ID,
        SERVICE_VERSION,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
