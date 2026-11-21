# Operator runbook

Relay Quote is a private HTTP backend. The HA RelayMiner is what gateways talk to.

## Process

1. Build the image from the repository root: `docker build -t relay-quote:1.0.0 .`
2. Pick one network directory: `deploy/beta` or `deploy/main`. Do not point both at the same Redis or the same operator key.
3. Create `supplier-keys.local.yaml` in that directory. Keep it out of git. The image user for the RelayMiner examples is uid 1000, and the file mode should be `0600`.
4. Shape, with your own key and not a sample:

```yaml
keys:
  - "<operator private key, 64 hex characters>"
```

5. Validate before starting, using the `pocket-relay-miner` binary that matches image tag `v0.1.6` or the newer release you actually run:

```bash
pocket-relay-miner miner validate --config miner.yaml
pocket-relay-miner relayer validate --config relayer.yaml --check-stake
```

6. Start the stack from that directory:

```bash
docker compose -p relay-quote-beta up -d
```

Use project name `relay-quote-main` for MainNet.

7. Confirm the backend yourself from inside the network. A curl to `127.0.0.1:8080` on the host will fail on purpose, because that port is not published:

```bash
docker compose -p relay-quote-beta exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/v1/health').read())"
```

8. The relayer listens on container port 8080, published on the host only at `127.0.0.1:8180` (Beta) or `127.0.0.1:8181` (MainNet). Terminate TLS on a hostname you control and proxy to that loopback port. The supplier endpoint you stake is `https://<hostname>`, not an IP and not plain HTTP.
9. Readiness for the relayer is `GET /ready` on its health port inside the container. Do not publish that port.

## Backend contract

| Request | Result |
| --- | --- |
| `GET /v1/health` | `200` and a JSON object whose status is `ok` |
| `GET /v1/version` | `200` and `"service": "relay-quote"` |
| `POST /v1/estimate` | deterministic quote |
| Body larger than 1 MiB | `422` JSON |
| Upstream parameter read failed | `502` JSON |
| Upstream parameter read past the local deadline | `504` JSON |

The RelayMiner health probe expects the substring `"ok"` from `GET /v1/health`.

Leave `sync_check` and `sync_allowance` unset. This is not a blockchain RPC service.

## Memory

The backend container limit in the compose file is 256 MB. Redis in the starter file is capped at 256 MB with `maxmemory-policy noeviction` and RDB snapshots. That is a laptop-sized starter. The RelayMiner capacity report used much larger Redis for high relay rates. Raise `maxmemory` and the container limit together before you take production traffic, and keep `maxmemory` below the container limit.

Redis 8.10.1 is the version the v0.1.6 miner was measured with. Older Redis is refused by that release.

## Logs

The backend logs to stderr: timestamp, method, path, status, elapsed milliseconds, and a request id. It does not log bodies, cookies, or authorization headers.
