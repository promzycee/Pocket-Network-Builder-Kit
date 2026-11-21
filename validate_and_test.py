#!/usr/bin/env python3
"""Clean-environment checks for the Relay Quote starter.

Uses the Python standard library only. By default this runs the local suite
and the live public-parameter reads. Pass --skip-live in CI. Pass --live-only
to run just the public-parameter reads.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PENALTY_PHRASES = (
    "timeout",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "connection refused",
    "connection reset",
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgho_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(
        r"(?i)(api[_-]?key|secret|password|mnemonic|private[_-]?key)\s*[:=]\s*['\"][^'\"]{8,}"
    ),
)
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv"}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
    ".example",
    ".ps1",
    ".sh",
    ".conf",
    ".gitignore",
    "",
}


class Fail(Exception):
    pass


def check(condition, message):
    if not condition:
        raise Fail(message)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server(port, extra_env=None):
    env = os.environ.copy()
    env["HOST"] = "127.0.0.1"
    env["PORT"] = str(port)
    env.pop("ALLOW_TEST_HOOKS", None)
    env.pop("UPSTREAM_DELAY_SECONDS", None)
    if extra_env:
        env.update(extra_env)
    process = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "server.py")],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    def _drain():
        process.stderr.read()

    threading.Thread(target=_drain, daemon=True).start()
    deadline = time.time() + 8
    last_error = None
    while time.time() < deadline:
        if process.poll() is not None:
            err = process.stderr.read().decode("utf-8", "replace")
            raise Fail(f"server exited early: {err}")
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/v1/health", timeout=0.5
            ) as response:
                if response.status == 200:
                    return process
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(0.05)
    process.kill()
    raise Fail(f"server did not become ready: {last_error}")


def stop_server(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def request(port, method, path, body=None, headers=None, timeout=20):
    data = None if body is None else body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    req_headers = {"Accept": "application/json"}
    if body is not None and not (headers and "Content-Type" in headers):
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)
    request_obj = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method=method,
        headers=req_headers,
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=timeout) as response:
            raw = response.read()
            return response.status, dict(response.headers), raw
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def assert_json_response(status, headers, raw, expected_status):
    check(status == expected_status, f"status {status}, expected {expected_status}, body {raw[:200]!r}")
    content_type = headers.get("Content-Type") or headers.get("content-type") or ""
    encoding = headers.get("Content-Encoding") or headers.get("content-encoding") or ""
    check("application/json" in content_type, f"content type {content_type}")
    check(encoding == "identity", f"content encoding {encoding!r}")
    check(raw.startswith(b"{"), f"body does not start with an object: {raw[:40]!r}")
    lowered = raw[:2048].decode("utf-8", "replace").lower()
    for phrase in PENALTY_PHRASES:
        check(phrase not in lowered, f"response contains gateway penalty phrase {phrase}")
    payload = json.loads(raw.decode("utf-8"))
    check(isinstance(payload, dict), "JSON top level is not an object")
    return payload


def json_path(payload, path):
    check(path.startswith("$."), f"unsupported path {path}")
    value = payload
    for part in path[2:].split("."):
        check(isinstance(value, dict) and part in value, f"missing {path}")
        value = value[part]
    return value


def expect_error(port, method, path, body, expected_status, code):
    status, headers, raw = request(port, method, path, body)
    payload = assert_json_response(status, headers, raw, expected_status)
    check(payload.get("error") == code, f"error code {payload.get('error')} != {code}")


def run_local():
    import server as backend

    check(backend.SERVICE_VERSION == "1.0.0", "SERVICE_VERSION drifted from 1.0.0")
    check("dotenv" not in (ROOT / "server.py").read_text(encoding="utf-8"), "server imports a dotenv loader")
    check("set -a" in (ROOT / "run.sh").read_text(encoding="utf-8"), "run.sh does not load .env")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    check("1.0.0" in changelog, "CHANGELOG.md is missing 1.0.0")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    check("ALLOW_TEST_HOOKS" not in dockerfile, "Dockerfile enables test hooks")
    check("USER appuser" in dockerfile, "Dockerfile does not drop root")

    port = free_port()
    process = start_server(port)
    try:
        status, headers, raw = request(port, "GET", "/")
        payload = assert_json_response(status, headers, raw, 200)
        check(payload["service"] == "relay-quote", payload)
        check(payload["status"] == "ok", payload)

        head = HTTPConnection("127.0.0.1", port, timeout=5)
        head.request("HEAD", "/")
        head_response = head.getresponse()
        head_body = head_response.read()
        check(head_response.status == 200, f"HEAD / status {head_response.status}")
        check(head_body == b"", f"HEAD / returned a body {head_body!r}")
        check(head_response.getheader("Content-Encoding") == "identity", "HEAD encoding")
        head.close()

        status, headers, raw = request(port, "GET", "/v1/version")
        payload = assert_json_response(status, headers, raw, 200)
        check(payload == {"service": "relay-quote", "version": "1.0.0"}, payload)

        status, headers, raw = request(port, "GET", "/v1/health")
        payload = assert_json_response(status, headers, raw, 200)
        check(payload == {"status": "ok"}, payload)

        estimate = {
            "compute_units_per_relay": 1000,
            "compute_units_to_tokens_multiplier": 2,
            "compute_unit_cost_granularity": 1,
            "relay_count": 1,
        }
        status, headers, raw = request(port, "POST", "/v1/estimate", estimate)
        payload = assert_json_response(status, headers, raw, 200)
        check(payload["cost_upokt"] == "2000", payload)
        check(payload["owner_share_upokt"] == "50", payload)
        check(payload["royalty_source"] == "configured_estimate_not_live_chain_state", payload)
        check(payload["division"] == "floor", payload)
        status, headers, raw = request(port, "POST", "/v1/estimate", estimate)
        again = assert_json_response(status, headers, raw, 200)
        check(again == payload, "estimate is not deterministic")

        odd = {
            "compute_units_per_relay": 5000,
            "compute_units_to_tokens_multiplier": 166742,
            "compute_unit_cost_granularity": 1000000,
        }
        status, headers, raw = request(port, "POST", "/v1/estimate", odd)
        payload = assert_json_response(status, headers, raw, 200)
        check(payload["cost_upokt"] == "833", payload)
        check(payload["relay_count"] == 1, payload)

        expect_error(port, "POST", "/v1/estimate", b"{", 400, "malformed_json")
        expect_error(port, "POST", "/v1/estimate", b"", 400, "empty_body")
        expect_error(port, "POST", "/v1/estimate", [], 422, "invalid_json_type")
        expect_error(port, "GET", "/missing", None, 404, "not_found")
        expect_error(port, "POST", "/missing", {"network": "main"}, 404, "not_found")
        expect_error(port, "POST", "/v1/network-status", {"network": "unknown"}, 422, "invalid_network")
        expect_error(
            port,
            "POST",
            "/v1/network-status",
            {"network": "main", "compute_units_per_relay": "bad"},
            422,
            "invalid_number",
        )
        expect_error(
            port,
            "POST",
            "/v1/estimate",
            {
                "compute_units_per_relay": 0,
                "compute_units_to_tokens_multiplier": 1,
                "compute_unit_cost_granularity": 1,
            },
            422,
            "number_out_of_range",
        )
        expect_error(
            port,
            "POST",
            "/v1/estimate",
            {
                "compute_units_per_relay": 1_048_577,
                "compute_units_to_tokens_multiplier": 1,
                "compute_unit_cost_granularity": 1,
            },
            422,
            "number_out_of_range",
        )
        too_big = b"{" + b"x" * (1024 * 1024)
        status, headers, raw = request(
            port,
            "POST",
            "/v1/estimate",
            too_big,
            headers={"Content-Type": "application/json"},
        )
        payload = assert_json_response(status, headers, raw, 422)
        check(payload["error"] == "body_too_large", payload)

        send_chunked(port, json.dumps(estimate).encode("utf-8"), 200, "2000")
        send_bad_chunk(port)
        send_oversized_chunks(port)

        status, headers, raw = request(port, "GET", "/openapi/v1/openapi.json")
        spec = assert_json_response(status, headers, raw, 200)
        check(spec["info"]["version"] == "1.0.0", spec["info"])
        check("/v1/estimate" in spec["paths"], "openapi missing estimate")
    finally:
        stop_server(process)

    run_concurrency()
    run_card_checks()
    run_secret_scan()


def send_chunked(port, body, expected_status, expected_cost):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.putrequest("POST", "/v1/estimate")
    conn.putheader("Transfer-Encoding", "chunked")
    conn.putheader("Content-Type", "application/json")
    conn.endheaders()
    conn.send(f"{len(body):x}\r\n".encode("ascii") + body + b"\r\n0\r\n\r\n")
    response = conn.getresponse()
    raw = response.read()
    conn.close()
    payload = assert_json_response(response.status, dict(response.headers), raw, expected_status)
    check(payload["cost_upokt"] == expected_cost, payload)


def send_bad_chunk(port):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.putrequest("POST", "/v1/estimate")
    conn.putheader("Transfer-Encoding", "chunked")
    conn.putheader("Content-Type", "application/json")
    conn.endheaders()
    conn.send(b"zz\r\n\r\n")
    response = conn.getresponse()
    raw = response.read()
    conn.close()
    payload = assert_json_response(response.status, dict(response.headers), raw, 400)
    check(payload["error"] == "malformed_chunk", payload)


def send_oversized_chunks(port):
    conn = HTTPConnection("127.0.0.1", port, timeout=10)
    conn.putrequest("POST", "/v1/estimate")
    conn.putheader("Transfer-Encoding", "chunked")
    conn.putheader("Content-Type", "application/json")
    conn.endheaders()
    # 0x100001 is 1,048,577 bytes, one past the 1 MiB cap. The server rejects
    # the size before reading the chunk, so the body is not sent.
    conn.send(b"100001\r\n")
    response = conn.getresponse()
    raw = response.read()
    conn.close()
    payload = assert_json_response(response.status, dict(response.headers), raw, 422)
    check(payload["error"] == "body_too_large", payload)


def run_concurrency():
    port = free_port()
    process = start_server(
        port,
        {"ALLOW_TEST_HOOKS": "1", "UPSTREAM_DELAY_SECONDS": "1.2"},
    )
    try:
        result = {}

        def slow():
            status, headers, raw = request(
                port,
                "POST",
                "/v1/network-status",
                {"network": "main", "test_hook": "delay"},
                timeout=5,
            )
            result["slow"] = assert_json_response(status, headers, raw, 200)

        worker = threading.Thread(target=slow)
        started = time.perf_counter()
        worker.start()
        time.sleep(0.15)
        health_started = time.perf_counter()
        status, headers, raw = request(port, "GET", "/v1/health", timeout=2)
        health_elapsed = time.perf_counter() - health_started
        payload = assert_json_response(status, headers, raw, 200)
        check(payload == {"status": "ok"}, payload)
        check(health_elapsed < 0.6, f"health waited {health_elapsed:.3f}s behind another request")
        worker.join(timeout=5)
        check(worker.is_alive() is False, "slow request did not finish")
        check(result["slow"]["hook"] == "delay", result["slow"])
        check(time.perf_counter() - started >= 1.0, "delay hook returned too quickly")
    finally:
        stop_server(process)


def run_card_checks():
    raw = (ROOT / "card.json").read_bytes()
    check(len(raw) < 4096, f"card is {len(raw)} bytes; Service Audit limit is 4096")
    card = json.loads(raw.decode("utf-8"))
    check(card["schema"] == "pocket-service-card/v1", card["schema"])
    check(card["results"] == "variable", card["results"])
    check(card["apis"] == ["relay-quote-api"], card["apis"])
    check("sha256" not in card["specs"][0], "sha256 on a moving URL is not allowed")
    openapi = json.loads((ROOT / "openapi" / "v1" / "openapi.json").read_text(encoding="utf-8"))
    check(openapi["info"]["version"] == "1.0.0", openapi["info"])
    for item in card["serving"]["healthcheck"]:
        path = item["request"]["path"]
        check(path in ("/v1/version", "/v1/health", "/v1/estimate"), path)

    port = free_port()
    process = start_server(port)
    try:
        for item in card["serving"]["healthcheck"]:
            req = item["request"]
            status, headers, body = request(
                port, req["method"], req["path"], req.get("body")
            )
            payload = assert_json_response(status, headers, body, 200)
            value = json_path(payload, item["expect"]["json_path"])
            check(
                re.search(item["expect"]["matches"], str(value)) is not None,
                f"{req['path']} value {value!r} did not match {item['expect']['matches']}",
            )
    finally:
        stop_server(process)

    gateway = (ROOT / "deploy" / "sage-gateway.example.yaml").read_text(encoding="utf-8")
    check("relay-quote" in gateway, "gateway example missing service id")
    check("/v1/version" in gateway and "/v1/health" in gateway, "gateway checks drifted")
    check("sync_allowance" not in gateway and "sync_check" not in gateway, "REST service has a block sync check")


def run_secret_scan():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for required in (".env", "*.pem", "*.key", "supplier-keys.local.yaml"):
        check(required in gitignore.splitlines(), f".gitignore missing {required}")
    scanned = 0
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".gitignore", ".env.example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        scanned += 1
        for pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            check(match is None, f"secret pattern in {path.relative_to(ROOT)}: {match.group(0)[:40] if match else ''}")
    check(scanned > 10, "secret scan did not see the repository")


def run_live(port):
    for network, chain_id in (("main", "pocket"), ("beta", "pocket-lego-testnet")):
        status, headers, raw = request(
            port,
            "POST",
            "/v1/network-status",
            {"network": network, "compute_units_per_relay": 1000},
            timeout=30,
        )
        payload = assert_json_response(status, headers, raw, 200)
        check(payload["network"] == network, payload)
        check(payload["chain_id"] == chain_id, payload)
        check(payload["parameter_source"] == "live_public_rest", payload)
        multiplier = payload["compute_units_to_tokens_multiplier"]
        granularity = payload["compute_unit_cost_granularity"]
        check(isinstance(multiplier, int) and multiplier > 0, payload)
        check(isinstance(granularity, int) and granularity > 0, payload)
        expected = str((1000 * multiplier) // granularity)
        check(payload["quote"]["cost_upokt"] == expected, payload["quote"])
        check(
            payload["quote"]["royalty_source"] == "configured_estimate_not_live_chain_state",
            payload["quote"],
        )
        print(
            f"live {network}: multiplier={multiplier} granularity={granularity} "
            f"fee_upokt={payload['add_service_fee_upokt']} quote_upokt={expected}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--live-only", action="store_true")
    args = parser.parse_args()
    check(not (args.skip_live and args.live_only), "choose one of --skip-live or --live-only")
    try:
        if not args.live_only:
            run_local()
            print("local validation passed")
        if not args.skip_live:
            port = free_port()
            process = start_server(port)
            try:
                run_live(port)
            finally:
                stop_server(process)
            print("live parameter reads passed")
    except Fail as exc:
        print(f"FAILED: {exc}")
        return 1
    print("validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
