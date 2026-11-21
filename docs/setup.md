# Setup

## Requirements

- Python 3.11 or newer on `PATH` as `python` or `python3`
- Network access only if you want live MainNet and Beta parameter reads

No virtualenv and no third-party packages are required.

## Start the backend

From the repository root.

Windows:

```powershell
copy .env.example .env
.\run.ps1
```

macOS or Linux:

```bash
cp .env.example .env
./run.sh
```

`run.ps1` and `run.sh` export `.env` and then start `python -u server.py`. The server listens on `HOST` and `PORT`, default `127.0.0.1:8080`.

The container image sets `HOST=0.0.0.0` so the RelayMiner on the same Docker network can reach it. Do not publish that port to the internet. The public address is the RelayMiner, behind HTTPS.

## Run the example

With the server already running:

```powershell
python example_client.py
```

`BASE_URL` overrides the default `http://127.0.0.1:8080`.

The fixed estimate body is:

```json
{
  "compute_units_per_relay": 1000,
  "compute_units_to_tokens_multiplier": 2,
  "compute_unit_cost_granularity": 1,
  "relay_count": 1
}
```

`cost_upokt` is `2000`. `owner_share_upokt` is `50` at the default royalty rate `0.025`.

## Run the clean-environment test

The validator starts and stops its own server on an ephemeral port.

```powershell
python validate_and_test.py --skip-live
python validate_and_test.py --live-only
python validate_and_test.py
```

`--skip-live` is what CI runs on every push. `--live-only` is the manual CI job. The default runs both.

A failing check exits non-zero and prints `FAILED:`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8080` | Bind port |
| `SERVICE_ID` | `relay-quote` | Value returned by the identity probe |
| `SERVICE_VERSION` | `1.0.0` | Value returned by `/v1/version` |
| `ROYALTY_RATE` | `0.025` | Configured owner-share estimate, from 0 to 1 |
| `MAIN_REST_URL` | Sauron MainNet REST | Public LCD base URL |
| `BETA_REST_URL` | Sauron Beta REST | Public LCD base URL |
| `UPSTREAM_DEADLINE_SECONDS` | `12` | Local deadline for one parameter read |
| `MAX_BODY_BYTES` | `1048576` | Request body cap |

`ALLOW_TEST_HOOKS` and `UPSTREAM_DELAY_SECONDS` exist so the validator can prove `/v1/health` stays responsive. Leave them unset in any deployment. The Dockerfile does not set them.
