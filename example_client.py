#!/usr/bin/env python3
"""Functional demo for Relay Quote.

Start the server first, then run this file. It calls the local backend only.
A direct HTTP call is not a Pocket relay.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8080").rstrip("/")
ESTIMATE = {
    "compute_units_per_relay": 1000,
    "compute_units_to_tokens_multiplier": 2,
    "compute_unit_cost_granularity": 1,
    "relay_count": 1,
}


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            encoding = response.headers.get("Content-Encoding", "")
            content_type = response.headers.get("Content-Type", "")
            status = response.status
    except urllib.error.URLError as exc:
        print(f"Could not reach {BASE_URL}. Start the server with .\\run.ps1 or ./run.sh.")
        print(exc)
        return 2
    print(f"{method} {path} -> {status} encoding={encoding} type={content_type}")
    if raw:
        print(raw.decode("utf-8"))
    if status != 200 or not raw.startswith(b"{") or "identity" not in encoding.lower():
        return 1
    if "application/json" not in content_type:
        return 1
    return 0


def main():
    steps = [
        ("GET", "/", None),
        ("GET", "/v1/version", None),
        ("GET", "/v1/health", None),
        ("POST", "/v1/estimate", ESTIMATE),
        ("POST", "/v1/network-status", {"network": "main", "compute_units_per_relay": 1000}),
        ("POST", "/v1/network-status", {"network": "beta", "compute_units_per_relay": 1000}),
    ]
    failed = 0
    for method, path, body in steps:
        result = call(method, path, body)
        if result == 2:
            return 2
        failed += result
    if failed:
        print(f"{failed} demo call(s) failed")
        return 1
    payload = json.dumps(ESTIMATE)
    print("Demo quote input: " + payload)
    print("Expected cost_upokt for this input is 2000.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
