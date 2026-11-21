# Deploy

One supplier stack per network.

```text
public HTTPS hostname
        |
        v
TLS reverse proxy you control
        |
        v
HA RelayMiner relayer (host loopback :8180 or :8181)
        |
        v
private backend :8080
        |
        v
public Pocket REST and RPC, or your own full node
```

Redis sits beside the relayer and the miner. It is not a cache. `maxmemory-policy` is `noeviction`, and the volume `redis-data` keeps claims that are not proved yet. `docker compose down -v` deletes that volume.

Files:

| Network | Directory | Chain ID | Block time | Host port |
| --- | --- | --- | --- | --- |
| Beta TestNet | `deploy/beta` | `pocket-lego-testnet` | 30 seconds | `127.0.0.1:8180` |
| MainNet | `deploy/main` | `pocket` | 60 seconds | `127.0.0.1:8181` |

Both pin `ghcr.io/pokt-network/pocket-relay-miner:v0.1.6`. That tag was current on 2026-11-21. If the releases page has moved on, change the image tag in both compose files and re-read the schema before you start.

The single-process `pocketd relayminer` command is the legacy path. These templates do not use it.

## Before stake

Query the supplier minimum on the network you will use:

```bash
pocketd query supplier params --network=beta
```

Stake only with the current `pocketd tx supplier stake` help text from the binary you installed. Copy the flags from that help, not from an older guide. The endpoint you publish is the HTTPS hostname in front of the relayer.

A relay proof is a request that arrives through that public supplier path, is forwarded to this backend, and later shows up in a claim and a proof. Curling the backend is only a smoke test.

Gateway operators can add `deploy/sage-gateway.example.yaml`. Its version and health paths match `card.json`.

## What is not in this repository

No operator key, no funded account, no public hostname, and no claim transaction. Those are yours to create. Record the non-secret outputs listed in [evidence/README.md](../evidence/README.md) after you have them.
