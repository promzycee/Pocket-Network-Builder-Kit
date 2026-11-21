# Use case: Relay Quote

**Proposal title:** Relay Quote, a reusable Pocket service starter

**Proposed service ID:** `relay-quote`

**Display name:** Relay Quote

**Repository:** https://github.com/promzycee/Pocket-Network-Builder-Kit

## Who it is for

Builders who want a small, original HTTP service they can register on Pocket Network and suppliers who need a backend that already follows the gateway rules. The service also answers a practical question: what does one relay cost in POKT at a given compute-unit price.

## What it does

Relay Quote exposes a JSON API.

- `POST /v1/estimate` applies the public formula with integers the caller supplies. The result is deterministic. Cost in uPOKT is floor of `compute_units_per_relay * compute_units_to_tokens_multiplier / compute_unit_cost_granularity`, multiplied by `relay_count`.
- `POST /v1/network-status` reads the live public REST parameters for MainNet (`chain_id` `pocket`) or Beta TestNet (`chain_id` `pocket-lego-testnet`) and can attach a one-relay quote. Those bytes change when governance changes the parameters.
- `GET /v1/version` returns the service ID `relay-quote`.
- `GET /v1/health` returns `{"status":"ok"}`.
- `GET /` and `HEAD /` answer for a root probe. `GET /` is JSON.

The owner-share figure uses the configured rate `0.025` and is labeled `configured_estimate_not_live_chain_state`. It is not presented as a live chain parameter.

## Why this ID

`relay-quote` names the capability. Checked on 2026-11-21, `GET /pokt-network/poktroll/service/service/relay-quote` returned 404 on both the MainNet and Beta public REST endpoints, while the same path returned 200 for `eth`. The ID is still free only until someone registers it. Registration makes it permanent.

## What a supplier runs

The container in this repository listens on port 8080 inside a private network. The HA RelayMiner `rest` backend is the only public path. Templates for Beta and MainNet are separate directories and pin image `ghcr.io/pokt-network/pocket-relay-miner:v0.1.6`, which was the latest release on 2026-11-21. Operators confirm the release before they deploy.

## What this proposal does not include

No customer accounts, no API keys, and no embedded supplier keys. The backend does not sign relays, stake, or submit claims. Those stay with `pocketd` and the HA RelayMiner.

## Ask

Preapprove this use case for the builder task: a public starter repository, setup docs, a clean-environment test, and a functional local example, with on-chain registration and supplier deployment left as operator steps that must be evidenced separately.
