# Pocket Network Builder Kit

Reusable starter for publishing a JSON service on Pocket Network. The reference service is **Relay Quote** (`relay-quote`): it turns the public compute-unit formula into a quote a supplier can serve behind the HA RelayMiner.

This repository is the starter, the setup docs, the clean-environment test, and the functional example. It does not claim an ambassador approval, an on-chain registration, or a settled relay. Those steps stay outside the code until you run them and keep the output.

Official references:

- [Services](https://docs.pocket.network/services/)
- [Register a Service](https://docs.pocket.network/services/register/)
- [Deploy a Service](https://docs.pocket.network/services/deploy/)

## What you can verify here

| State | How |
| --- | --- |
| Local starter | `python validate_and_test.py --skip-live` |
| Live public parameter reads | `python validate_and_test.py --live-only` |
| Registered service | Not done. See [docs/register.md](docs/register.md). |
| Supplier, relay, and settlement | Not done. See [docs/deploy.md](docs/deploy.md). |

## Clean environment

Python 3.11 or newer. No pip packages.

Windows:

```powershell
copy .env.example .env
.\run.ps1
```

In a second terminal:

```powershell
python validate_and_test.py
python example_client.py
```

macOS or Linux:

```bash
cp .env.example .env
chmod +x run.sh
./run.sh
```

```bash
python3 validate_and_test.py
python3 example_client.py
```

`server.py` reads the process environment. Copying `.env` does nothing until `run.ps1` or `run.sh` loads it. The validator starts its own server and does not need `.env`.

## Example

`example_client.py` calls a running local server:

- `GET /`, `GET /v1/version`, `GET /v1/health`
- `POST /v1/estimate` with a fixed body whose floor-division cost is `2000` uPOKT
- `POST /v1/network-status` for `main` and `beta`

A call to `127.0.0.1` is a backend demo. It is not a Pocket relay.

## Layout

| Path | Role |
| --- | --- |
| `server.py` | Threaded JSON backend |
| `example_client.py` | Functional demo |
| `validate_and_test.py` | Clean-environment test |
| `card.json` | `pocket-service-card/v1` metadata |
| `openapi/v1/openapi.json` | API document, version 1.0.0 |
| `docs/use-case.md` | Use case to send for preapproval |
| `docs/setup.md` | Setup and local demo |
| `docs/preapproval.md` | How to ask for preapproval |
| `docs/register.md` | Beta registration commands |
| `docs/operators.md` | Supplier runbook |
| `docs/deploy.md` | HA RelayMiner layout |
| `deploy/beta`, `deploy/main` | Separate stack templates |
| `.github/workflows/ci.yml` | Local checks on every push; live checks on manual dispatch |

## Service behavior

`POST /v1/estimate` is deterministic. Cost in uPOKT is

```text
floor(compute_units_per_relay * compute_units_to_tokens_multiplier / compute_unit_cost_granularity) * relay_count
```

The caller supplies the two pricing integers, so the bytes do not depend on chain state. `POST /v1/network-status` reads them from the public REST API and is variable.

The owner share uses `ROYALTY_RATE` (default `0.025`). The field `royalty_source` is `configured_estimate_not_live_chain_state`. The Services overview describes a 2.5% owner share; this process does not query that rate from the chain.

Every response, including errors, is a JSON object with `Content-Encoding: identity`. Client mistakes are 400 or 422. A failed public parameter read is 502. A local deadline on that read is 504. The body does not use the gateway penalty phrases (`timeout`, `bad gateway`, `service unavailable`, `gateway timeout`, `connection refused`, `connection reset`).

## Verified limitations

- The backend does not verify ring signatures.
- The backend does not submit claims or proofs.
- The backend does not register a service or stake a supplier.
- Public REST endpoints can fail or change.
- Royalty is a configured estimate.
- Direct local HTTP is not a Pocket relay test.
- `card.json` has not been passed through `pocketd tx service validate-card` on this machine until you install the CLI and run it.
- The OpenAPI URL in the card points at the `main` branch and has no `sha256`. Add a hash only after you tag a release.

## Maintenance

Version 1.0.0 is the service version, the OpenAPI `info.version`, and the current changelog entry. CI compiles the Python files and runs the local validator on Python 3.12. Run the live job from the Actions tab when you want a fresh parameter read.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/acceptance.md](docs/acceptance.md).
