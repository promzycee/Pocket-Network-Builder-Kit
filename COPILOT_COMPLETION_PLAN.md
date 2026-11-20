# Pocket Network Builder Task: 100% Completion Plan

## Purpose

Use this document as the implementation brief for GitHub Copilot. Apply it to the repository:

```text
https://github.com/promzycee/Pocket-Network-Builder-Kit
```

The repository currently provides a working, dependency-free Python starter and local validator. It does not yet prove the complete Pocket Builder Task because preapproval, service registration, HA RelayMiner deployment, public serving, and production-style evidence are missing.

Do not fabricate any transaction hash, service ID, supplier address, public URL, approval, or claim. Every evidence value must come from an observed command or live response.

---

## 1. Original task requirements

The task requires a reusable builder deliverable that includes:

1. A preapproved use case.
2. A starter repository.
3. Setup documentation.
4. A clean-environment test.
5. A runnable example or functional demo.
6. Proof through the repository, instructions, functional behavior, and validation output.
7. Reproducibility.
8. Maintenance quality.
9. Original work.
10. No embedded secrets.
11. Preapproval from the Pocket Ambassador team before final completion.
12. No more than one approved completion for the season.

The repository currently satisfies much of the reusable starter requirement, but the following completion evidence is still missing:

- written preapproval from the Pocket Ambassador team;
- a production-like service registration proof;
- a deployed HA RelayMiner supplier path;
- a public HTTPS supplier endpoint;
- an end-to-end relay through the deployed supplier;
- claim/proof settlement evidence;
- current `pocketd` card validation;
- CI or an equivalent repeatable maintenance check;
- fixes for the implementation gaps listed below.

Official references used for this plan:

- Services overview: https://docs.pocket.network/services/
- Register a Service: https://docs.pocket.network/services/register/
- Deploy a Service: https://docs.pocket.network/services/deploy/
- Service Management: https://docs.pocket.network/services/management/
- Supplier Servers: https://docs.pocket.network/services/servers/
- Pocket CLI reference: https://docs.pocket.network/pocketd/

---

## 2. Current repository baseline

At the review commit, the repository contains:

```text
card.json
.env.example
README.md
server.py
example_client.py
validate_and_test.py
pocket-network-builder-starter-kit.md
```

The current local validator was run successfully:

```bash
python3 validate_and_test.py
```

Observed passing behavior:

- secret scan;
- card JSON parsing;
- card size check;
- three card probes;
- clean local server startup;
- JSON-first-byte checks;
- `Content-Encoding: identity` checks;
- malformed JSON `400`;
- validation `422`;
- unknown route `404`;
- live MainNet query;
- live Beta TestNet query.

The current server was also tested manually:

```text
GET  /v1/version       200
GET  /v1/health        200
POST /v1/estimate      200
POST /v1/network-status {"network":"main"} 200
POST /v1/network-status {"network":"beta"} 200
```

These results prove the starter works locally and can reach the public Pocket endpoints. They do not prove supplier registration, RelayMiner operation, relay routing, or claim settlement.

---

## 3. Required implementation fixes before deployment

Implement these fixes before claiming completion.

### 3.1 Fix environment-file documentation

Current problem:

```bash
cp .env.example .env
python3 server.py
```

does not load `.env`. `server.py` reads `os.environ`, but Python's standard library does not automatically load `.env` files.

Choose one and document it consistently. Recommended dependency-free option:

```bash
set -a
. ./.env
set +a
python3 server.py
```

Update README to use that exact sequence. Do not claim that copying `.env` alone configures the process.

Alternatively, add a small `run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
set -a
[ ! -f .env ] || . ./.env
set +a
exec python3 server.py
```

Document that `run.sh` is the supported launcher.

Do not add real credentials to `.env.example`.

### 3.2 Use a threaded HTTP server

Current code uses the single-threaded `HTTPServer`. A slow live-network request can block health checks and all other requests.

Change:

```python
from http.server import BaseHTTPRequestHandler, HTTPServer
```

to:

```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
```

Change the server construction to:

```python
server = ThreadingHTTPServer((host, port), PocketServiceHandler)
```

Add a concurrency test that starts at least two simultaneous requests while one upstream request is delayed. `/v1/health` must remain responsive.

### 3.3 Restore useful, secret-safe logging

Current `log_message()` discards every request.

Implement structured or simple safe logging with:

- timestamp;
- method;
- path;
- status code;
- elapsed milliseconds;
- request ID if available.

Never log:

- private keys;
- mnemonics;
- authorization headers;
- cookies;
- supplier key material;
- full sensitive request bodies.

A minimal safe implementation may use Python's `logging` module. Send logs to stderr so Docker and systemd can collect them.

### 3.4 Support `GET /` and `HEAD /`

The live Pocket deployment documentation states that the RelayMiner checks the backend root and expects `GET /` and `HEAD /` to return 2xx.

Implement:

```text
GET  /   -> 200 JSON object
HEAD /   -> 200 with headers and no response body
```

Example GET response:

```json
{"service":"pocket-relay-inspector","status":"ok"}
```

Add both paths to local validation.

Do not use an HTML response for `/`.

### 3.5 Support chunked request bodies

Pocket service deployment documentation states that relay bodies can arrive with `Transfer-Encoding: chunked` and no `Content-Length`.

Current `read_object()` depends on:

```python
self.headers.get("Content-Length", "0")
```

That can reject valid chunked requests as empty.

Implement a bounded request-body reader that supports both:

- `Content-Length`;
- `Transfer-Encoding: chunked`.

Requirements:

- enforce the 1 MiB maximum after decoding;
- reject malformed chunk sizes with JSON `400`;
- reject incomplete chunks with JSON `400`;
- reject oversized bodies with JSON `422`;
- never read unbounded input into memory.

Add tests for:

1. normal `Content-Length` JSON;
2. chunked JSON;
3. malformed chunk framing;
4. chunked body exceeding 1 MiB;
5. empty body.

### 3.6 Fix live-network error classification

Current `/v1/network-status` returns `422` for upstream failures. A Pocket upstream failure is a backend failure, not a caller validation error.

Use:

- `400` for malformed JSON;
- `422` for valid JSON with invalid values;
- `502` for an upstream Pocket endpoint failure;
- `504` for an upstream timeout;
- `500` only for an unexpected local server failure.

Every error response must remain a JSON object with `Content-Encoding: identity`.

Example:

```json
{
  "error": "upstream_query_failed",
  "message": "The requested Pocket network parameter source was unavailable.",
  "network": "main"
}
```

Do not return raw exception messages that may expose URLs, internal details, or credentials.

### 3.7 Validate all numeric input consistently

Current `handle_network_status()` calls `int()` without catching `ValueError` and `TypeError`.

Invalid input must return JSON `422`, not an unhandled exception or HTML/empty `500`.

Test these bodies:

```json
{"network":"main","compute_units_per_relay":"bad"}
```

```json
{"network":"main","compute_units_per_relay":0}
```

```json
{"network":"unknown","compute_units_per_relay":5000}
```

### 3.8 Make royalty assumptions explicit or source them

Current economics code hardcodes:

```python
Decimal("0.025")
Decimal("0.975")
```

The repository must not present these as live governance values unless the current Pocket source explicitly proves them.

Choose one:

1. Query the authoritative current parameter if Pocket exposes the royalty value.
2. Make royalty configurable by environment and label it as a configured estimate.
3. Remove royalty calculations from the live response until the source is verified.

Recommended temporary representation:

```json
{
  "service_owner_royalty_pokt": "0.020217125",
  "royalty_rate": "0.025",
  "royalty_source": "configured_estimate_not_live_chain_state"
}
```

Do not call a configured assumption a live chain value.

### 3.9 Add a machine-readable OpenAPI document

The current card uses a generic `docs` spec. For a serious service listing, add a versioned OpenAPI document, for example:

```text
openapi/v1/openapi.json
```

It must describe:

- `GET /`;
- `HEAD /`;
- `GET /v1/version`;
- `GET /v1/health`;
- `POST /v1/estimate`;
- `POST /v1/network-status`;
- JSON success schemas;
- JSON error schemas;
- numeric bounds;
- MainNet/Beta network values.

Update `card.json`:

```json
"specs": [
  {
    "kind": "openapi",
    "api": "pocket-relay-inspector-api",
    "url": "https://<immutable-public-host>/openapi/v1/openapi.json",
    "sha256": "<sha256-of-the-versioned-document>"
  }
]
```

Only add `sha256` when the URL is immutable or version-addressed. Do not hash a URL whose content will be overwritten.

The public URL and SHA must be real values from the deployed service. Do not use placeholders in the final card.

### 3.10 Update the card accurately

Keep:

```json
"schema": "pocket-service-card/v1"
```

Confirm the current official limit before final registration. The current Pocket documentation distinguishes the protocol maximum from the Service Audit requirement. The repository should state both accurately:

- protocol/card maximum: verify from current docs and current `pocketd`;
- Service Audit / Agentic Portal target: under 4 KiB if that remains current at submission time.

The card should accurately describe:

- request shapes;
- response shapes;
- deterministic versus variable results;
- backend startup behavior;
- `GET /` and `HEAD /` support;
- healthcheck paths;
- HTTPS/public supplier expectations;
- OpenAPI URL and version.

Run the current CLI validator, not only a local JSON parser:

```bash
pocketd tx service validate-card ./card.json
```

If the installed CLI uses a different subcommand in the current release, record the exact output and update the README with the current command. Do not claim card validation from a command that was not actually run.

---

## 4. Add tests that cover the actual task

Extend `validate_and_test.py` or add a standard-library test module. The final command must be deterministic and exit nonzero on failure.

### 4.1 Local API tests

Required checks:

```text
GET  /                  -> 200 JSON object
HEAD /                  -> 200 and no body
GET  /v1/version        -> 200 JSON identity
GET  /v1/health         -> 200 JSON readiness
POST /v1/estimate       -> 200 deterministic response
POST /v1/network-status -> live MainNet response
POST /v1/network-status -> live Beta response
```

### 4.2 Error tests

Required:

```text
malformed JSON                 -> 400 JSON
empty body                     -> 400 JSON
JSON array top level           -> 422 JSON
unknown GET path               -> 404 JSON
unknown POST path              -> 404 JSON
bad network                    -> 422 JSON
bad numeric field              -> 422 JSON
compute units below 1          -> 422 JSON
compute units above 1,048,576  -> 422 JSON
body above 1 MiB               -> 422 JSON
```

### 4.3 Gateway response tests

For every success and error response, assert:

```text
Content-Type contains application/json
Content-Encoding == identity
body begins with {
body parses as a JSON object
```

For `200` responses, scan the first 2 KiB for the gateway penalty phrases documented by Pocket. Keep the phrase list synchronized with current Pocket docs.

### 4.4 Chunked-body tests

Send a request with `Transfer-Encoding: chunked` and no `Content-Length`. Confirm that `/v1/estimate` accepts it and returns the same result as a normal body.

### 4.5 Concurrency tests

Run a slow upstream request and a concurrent health request. Confirm health remains responsive.

### 4.6 Card tests

Check:

- schema;
- size;
- OpenAPI URL availability;
- OpenAPI SHA if present;
- all healthcheck paths;
- exact expected response values;
- card and gateway health checks are synchronized.

### 4.7 Secret tests

Scan tracked text files and exclude only documented false positives. Do not use a regex that silently misses common secret formats. Confirm `.env`, key files, PEM files, mnemonics, and supplier keyrings are ignored by Git.

---

## 5. Add CI and maintenance proof

Add `.github/workflows/ci.yml` that runs on pull requests and pushes:

```yaml
name: validate

on:
  push:
  pull_request:

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Compile Python files
        run: python -m py_compile server.py example_client.py validate_and_test.py
      - name: Run local validation
        run: python validate_and_test.py
```

If live-network checks are unstable in CI, split them:

- deterministic local job required on every PR;
- live-network job allowed to be manually dispatched or marked as an external integration check;
- never make the live check silently disappear.

Document the exact commit, Python version, and validator output used for submission.

Add a `CHANGELOG.md` and a release/version policy. The current `SERVICE_VERSION` must match the documented implementation version.

---

## 6. Build a real deployable backend image

Add a minimal `Dockerfile` using a supported Python image and a non-root user. Do not put secrets in the image.

Minimum properties:

- listens on `0.0.0.0:8080` inside the container;
- exposes only the backend port internally;
- has a healthcheck for `/v1/health`;
- uses `python -u` or equivalent for logs;
- runs as non-root;
- has a bounded memory expectation documented;
- does not publish the backend directly to the public internet.

Example shape, to be tested rather than copied blindly:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN useradd --create-home --uid 10001 appuser
COPY server.py /app/server.py
COPY card.json /app/card.json

USER appuser
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --retries=3 CMD python - <<'PY'
import urllib.request
urllib.request.urlopen('http://127.0.0.1:8080/v1/health', timeout=3)
PY

CMD ["python", "-u", "server.py"]
```

The container must bind to `0.0.0.0`, for example through environment variables:

```bash
HOST=0.0.0.0 PORT=8080
```

---

## 7. Deploy the HA RelayMiner correctly

The current Pocket deployment documentation requires the HA RelayMiner, not the deprecated single-process `pocketd relayminer` path.

Use the current pinned HA RelayMiner version from the official release/docs at deployment time. The docs currently show examples using:

```text
ghcr.io/pokt-network/pocket-relay-miner:v0.1.0
```

Do not assume that tag is still current without checking the live docs/release page.

Required architecture:

```text
public HTTPS hostname
        |
        v
reverse proxy / TLS
        |
        v
HA RelayMiner relayer
        |
        v
private backend:8080
        |
        v
Pocket public REST/RPC or operator full node
```

Required infrastructure:

- one supplier stack per network;
- separate Beta and MainNet directories/configs;
- Redis 8.10 or newer;
- Redis persistence;
- `maxmemory-policy noeviction`;
- same RelayMiner version for miner and relayer;
- backend on the private Docker network;
- backend healthcheck at `/v1/health`;
- RelayMiner health and metrics bound to loopback or private interfaces;
- public HTTPS endpoint for the supplier;
- no exposed backend port;
- operator key backup performed by the owner outside the repository.

Do not commit operator keys or supplier keyrings.

### 7.1 HA RelayMiner validation commands

Use the exact current binary and config paths from the chosen release:

```bash
pocket-relay-miner miner validate --config miner.yaml
pocket-relay-miner relayer validate --config relayer.yaml --check-stake
docker compose -p pocket-supplier up -d
```

Then verify:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8081/ready
curl -s http://127.0.0.1:8081/ready/<service-id>
```

The relayer readiness endpoint must not be treated as healthy until the miner is running and the backend health state is healthy.

### 7.2 Required `relayer.yaml` properties

Follow the current official schema and validate it. The service entry must contain the current service ID, the REST backend, and the correct network-specific routing. The deployment docs show this shape:

```yaml
services:
  <your-service-id>:
    validation_mode: eager
    timeout_profile: fast
    max_body_size_bytes: 20971520
    default_backend: rest
    backends:
      rest:
        url: "http://backend:8080"
        health_check:
          enabled: true
          endpoint: "/v1/health"
          expected_body: '"ok"'
          interval_seconds: 10
          timeout_seconds: 5
          unhealthy_threshold: 3
          healthy_threshold: 2
```

Verify the exact current config schema against the installed RelayMiner release before deploying. If the schema has changed, use the release's schema, not this example.

Do not add `sync_check` or `sync_allowance` for a non-blockchain REST service. The live docs explicitly warn that those settings assume a block height and can mark a healthy non-blockchain service unhealthy.

### 7.3 Required `miner.yaml` properties

Configure:

- network-specific `chain_id`;
- Beta: current Beta chain ID from Pocket Networks docs;
- MainNet: `pocket`;
- current block-time setting from the docs;
- operator key reference outside Git;
- Redis URL and persistent storage;
- public supplier endpoint;
- service ID in the staked service list.

Validate with the current HA RelayMiner binary:

```bash
pocket-relay-miner miner validate --config miner.yaml
```

---

## 8. Register the service on Beta first

Pocket registration creates an on-chain record only. It does not make the service reachable. Registration is permissionless, but an owner account must pay the registration fee and gas.

### 8.1 Check current parameters first

Use the network you are actually operating on:

```bash
NETWORK=beta
pocketd query service params --network="$NETWORK"
pocketd query shared params --network="$NETWORK"
```

Do not copy the current fee or multiplier from this document. Query them immediately before the transaction.

### 8.2 Validate the card with the current CLI

```bash
pocketd tx service validate-card ./card.json
```

If the installed `pocketd` release uses a different command, run:

```bash
pocketd tx service --help
pocketd tx service validate-card --help
```

Record the exact successful command and CLI version in the evidence file.

### 8.3 Register

Use the official current syntax:

```bash
OWNER=<owner-key-name>
NETWORK=beta
TX_FLAGS="--from $OWNER --network=$NETWORK --gas auto --gas-prices 1upokt --gas-adjustment 1.5"

pocketd tx service add-service \
  <service-id> \
  "<service-name>" \
  <compute-units-per-relay> \
  --card-file ./card.json \
  $TX_FLAGS
```

Do not put a private key, mnemonic, or secret in the command, shell history, README, or evidence file.

The service ID is permanent and cannot be renamed or deleted. Confirm it before broadcasting.

### 8.4 Read the record back

```bash
pocketd query service show-service <service-id> --network="$NETWORK"
pocketd query service card <service-id> --network="$NETWORK"
pocketd query service card <service-id> --network="$NETWORK" --raw > /tmp/stored-card.json
sha256sum card.json /tmp/stored-card.json
```

The stored card must match the intended card byte-for-byte after accounting for the exact CLI output format. If the CLI returns encoded or formatted output, use the current documented raw-output method and record how the comparison was made.

Confirm the service appears in the Pocket explorer after the transaction is indexed:

```text
https://explorer.pocket.network/services
```

Record:

- network;
- service ID;
- transaction hash;
- owner address;
- registered name;
- compute units per relay;
- stored card hash;
- block height.

---

## 9. Stake and deploy a supplier

Registration alone is not a functional service. A supplier must stake against the service and run the HA RelayMiner.

Before staking, query current supplier parameters on the target network:

```bash
pocketd query supplier params --network=beta
```

Do not copy the current minimum stake from documentation. The live docs explicitly say the minimum is governance-controlled and must be queried.

Use the current official supplier-staking command from the installed `pocketd` release:

```bash
pocketd tx supplier --help
pocketd tx supplier stake --help
```

The exact command and flags must be recorded from the installed version. Do not invent a staking command from an older Pocket release.

Use separate operator keys and stack directories for Beta and MainNet. Do not run one shared stack for both networks.

Required supplier evidence:

- supplier operator address;
- supplier endpoint;
- network;
- service ID in the stake list;
- staking transaction hash;
- current stake query;
- RelayMiner version;
- miner and relayer validation output;
- readiness output;
- backend health output.

---

## 10. Public HTTPS and gateway routing

A public supplier endpoint must use:

```text
https://<supplier-hostname>
```

Do not use a raw IP or plain HTTP for the final supplier endpoint. Terminate TLS at Caddy, nginx, or another reverse proxy, then proxy internally to the RelayMiner.

Keep these private:

- backend port 8080;
- Redis;
- RelayMiner health port;
- RelayMiner metrics port;
- operator key paths.

The current deployment docs require the SAGE gateway service entry to mirror the card health checks. The configuration should include the current service ID and REST transport, with checks equivalent to:

```yaml
gateway_config:
  services:
    - id: <your-service-id>
      type: passthrough
      rpc_types: ["rest"]
      timeout_config:
        relay_timeout: 30s
      active_health_checks:
        local:
          - service_id: <your-service-id>
            enabled: true
            checks:
              - name: version
                type: rest
                method: GET
                path: /v1/version
                expected_status_code: 200
                reputation_signal: critical_error
                timeout: 5s
              - name: health
                type: rest
                method: GET
                path: /v1/health
                expected_status_code: 200
                reputation_signal: major_error
                timeout: 5s
```

Use the exact current SAGE schema. Keep the gateway checks and card `serving.healthcheck` synchronized.

Do not add blockchain `sync_check` or `sync_allowance` to this ordinary REST service.

---

## 11. Prove a real relay, not just a local HTTP response

The final functional proof must go through the deployed supplier path, not directly to `server.py`.

Required sequence:

1. Register service on Beta.
2. Stake supplier on Beta.
3. Start Redis, miner, relayer, backend, and TLS proxy.
4. Wait until RelayMiner readiness is healthy.
5. Send a relay through the official Pocket gateway/client path.
6. Confirm the backend receives the request.
7. Confirm the client receives the correct JSON response.
8. Confirm no gateway penalty/circuit-break occurs.
9. Wait for the relevant session boundary.
10. Confirm a claim and proof settle on chain.

The evidence must include:

```text
client command or request
supplier endpoint
service ID
network
request body
response body
HTTP status
block height
relay/session identifier if available
claim transaction hash
proof transaction hash
explorer links
```

Do not call a direct `curl http://127.0.0.1:8080/...` a Pocket relay proof. That is only a backend smoke test.

---

## 12. Preapproval evidence

The task requires preapproval before final completion. Add a redacted evidence file, for example:

```text
evidence/preapproval.md
```

It must contain:

- date of request;
- Pocket Ambassador team contact/channel;
- exact proposal title;
- exact use case;
- repository URL;
- approval response or approval reference;
- any scope limitations;
- reviewer name or public identifier when allowed;
- links to the original communication where permitted.

Do not fabricate approval. If approval has not been granted, the task is not 100% complete.

The existing proposal template is not approval evidence.

---

## 13. Submission evidence package

Create an `evidence/` directory containing only non-secret, reproducible artifacts:

```text
evidence/
├── preapproval.md
├── repo-commit.txt
├── environment.txt
├── local-validation.txt
├── card-validation.txt
├── beta-registration.txt
├── beta-service-query.txt
├── beta-card-raw.sha256
├── supplier-stake-query.txt
├── miner-validate.txt
├── relayer-validate.txt
├── readiness.txt
├── backend-probe.txt
├── gateway-relay.txt
├── claim-proof.txt
├── openapi.sha256
└── links.md
```

`environment.txt` should record safe metadata only:

```bash
python3 --version
pocketd version
pocket-relay-miner version
docker --version
docker compose version
git rev-parse HEAD
```

Never include:

- private keys;
- mnemonics;
- `.env` contents;
- supplier keyrings;
- authorization headers;
- full secret-bearing config files.

`links.md` should contain:

- GitHub repository URL;
- exact commit SHA;
- public supplier URL;
- service explorer URL;
- Beta transaction URLs;
- MainNet transaction URLs if deployed;
- OpenAPI URL;
- documentation URL.

---

## 14. README corrections required

Update the README so it does not overclaim. It should distinguish four states:

1. `local starter verified`;
2. `live Pocket parameter reads verified`;
3. `registered service verified`;
4. `deployed supplier and settled relay verified`.

Do not call the project production-grade until state 4 is evidenced.

Update the quick start to correctly load configuration:

```bash
cp .env.example .env
set -a
. ./.env
set +a
python3 validate_and_test.py
```

Document that `server.py` does not automatically parse `.env` unless you add the launcher described above.

Document the current exact versions used by CI and deployment.

Add a section called `Verified limitations` that states:

- no ring-signature verification is performed by the backend;
- no claims are submitted by the backend;
- no service registration is performed automatically;
- live network endpoints can fail or change;
- royalty values are estimates unless sourced live;
- direct local HTTP tests are not Pocket relay tests.

---

## 15. Final acceptance gate

The task is complete only when every item below is true and backed by evidence:

### Repository

- [ ] GitHub repository is public or shared with the reviewers.
- [ ] README matches the actual implementation.
- [ ] No stale or fabricated validation output remains.
- [ ] CI runs on every push and pull request.
- [ ] Version and changelog are present.
- [ ] Repository contains no secrets.

### Starter implementation

- [ ] Python syntax compiles.
- [ ] Server uses a threaded or production HTTP server.
- [ ] `GET /` returns JSON `200`.
- [ ] `HEAD /` returns `2xx` with no body.
- [ ] `/v1/version` works.
- [ ] `/v1/health` works.
- [ ] `/v1/estimate` is deterministic.
- [ ] `/v1/network-status` handles MainNet and Beta.
- [ ] Chunked request bodies are supported.
- [ ] Request size is bounded.
- [ ] All errors are JSON objects.
- [ ] Upstream failures use correct `5xx` classification.
- [ ] Safe request logging exists.
- [ ] Config loading is documented and actually works.

### Card

- [ ] Card validates with the current `pocketd`.
- [ ] Card is under the current Service Audit limit.
- [ ] Card has accurate `rpc_types`.
- [ ] Card has accurate `apis`.
- [ ] Card has a real docs URL.
- [ ] Card has a versioned OpenAPI URL where required.
- [ ] Card healthchecks match the backend and gateway checks.
- [ ] Card stored on chain matches the intended file.

### Pocket deployment

- [ ] Beta service registered.
- [ ] Beta record read back.
- [ ] Beta card read back byte-checked.
- [ ] Beta supplier staked.
- [ ] HA RelayMiner deployed.
- [ ] Redis is persistent and `noeviction`.
- [ ] Backend is private behind RelayMiner.
- [ ] Public HTTPS supplier endpoint exists.
- [ ] Miner config validates.
- [ ] Relayer config validates with `--check-stake`.
- [ ] RelayMiner readiness is healthy.
- [ ] Gateway routing is configured.
- [ ] Real relay reaches the backend through Pocket.
- [ ] Claim transaction settles.
- [ ] Proof transaction settles.
- [ ] Evidence links are recorded.

### Task administration

- [ ] Preapproval request exists.
- [ ] Preapproval response is attached.
- [ ] Scope matches the approved use case.
- [ ] Final submission links the repo, docs, demo, and evidence.
- [ ] The team has not claimed more than the permitted seasonal completion.

If any checked item is missing, report the deliverable as partial completion, not 100% completion.

---

## 16. Copilot execution prompt

Paste the following into GitHub Copilot Chat from the repository root:

```text
You are completing the Pocket Network Builder Task for this repository.

Read these files first:
- README.md
- server.py
- validate_and_test.py
- card.json
- .env.example
- COPILOT_COMPLETION_PLAN.md

Read the current official Pocket docs before changing deployment or registration syntax:
- https://docs.pocket.network/services/
- https://docs.pocket.network/services/register/
- https://docs.pocket.network/services/deploy/
- https://docs.pocket.network/services/management/
- https://docs.pocket.network/services/servers/

Do not invent transaction hashes, service IDs, addresses, approval, stake values, RelayMiner versions, or public URLs.
Do not commit credentials, private keys, mnemonics, .env contents, PEM files, or supplier keyrings.

Implement the unchecked items in COPILOT_COMPLETION_PLAN.md in this order:

1. Fix server correctness:
   - ThreadingHTTPServer or production server.
   - GET / and HEAD / JSON-compatible probes.
   - bounded Content-Length and chunked request-body support.
   - safe structured logging.
   - correct 400, 422, 502, 504, and 500 classification.
   - consistent numeric validation.
   - correct config loading documentation or launcher.
   - explicit royalty provenance.

2. Add and validate a versioned OpenAPI document.

3. Extend local tests for all routes, errors, chunked bodies, concurrency, card checks, and secret scanning.

4. Add CI.

5. Add Dockerfile and deployment documentation.

6. Register Beta only after the owner supplies and verifies the real service ID and owner account.
   Use the current commands from the official docs and record every observed output.

7. Deploy the HA RelayMiner and Redis according to the current official docs.
   Do not use the deprecated single-process pocketd relayminer.

8. Stake a real supplier only when the owner explicitly provides the operator account and approves the transaction.
   Never generate or guess keys.

9. Prove a real Pocket relay through the gateway and wait for claim/proof settlement.

10. Save redacted evidence under evidence/ and update README with verified status.

After each phase:
- run the relevant tests;
- inspect the diff;
- report failures honestly;
- do not mark the phase complete until its acceptance criteria pass.

At the end run:
- python3 -m py_compile server.py example_client.py validate_and_test.py
- python3 validate_and_test.py
- current pocketd card validation
- CI-equivalent tests
- current deployment validation

Report a final checklist with PASS, PARTIAL, BLOCKED, or UNPROVEN for every requirement.
```

## Final submission rule

Do not submit this as a 100% completion until preapproval, registration, supplier deployment, real gateway relay, and claim/proof evidence all exist. The current repository is a good starter kit, but those external-state requirements cannot be replaced by local tests or prose claims.
