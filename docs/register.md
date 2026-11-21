# Register on Beta first

Registration creates an on-chain record. It does not serve traffic. The service ID cannot be renamed or deleted. Read the fee from the network you are about to use. The figures below are not fees. Query them.

Install `pocketd` from the current Pocket docs, then:

```bash
export OWNER=<owner-key-name>
export NETWORK=beta
export TX_FLAGS="--from $OWNER --network=$NETWORK --gas auto --gas-prices 1upokt --gas-adjustment 1.5"

pocketd query service params --network="$NETWORK"
pocketd query shared params --network="$NETWORK"
pocketd tx service validate-card ./card.json
```

If `validate-card` is not in your build, run `pocketd tx service --help` and record the command that exists. Do not claim the card is valid from a command you did not run.

`relay-quote` was free on MainNet and Beta on 2026-11-21. Check again immediately before you broadcast:

```bash
pocketd query service show-service relay-quote --network="$NETWORK"
```

A missing service is what you want. Then, only after you accept the fee printed by the params query:

```bash
pocketd tx service add-service \
  relay-quote \
  "Relay Quote" \
  1000 \
  --card-file ./card.json \
  $TX_FLAGS
```

`1000` is a starting compute-unit price for this small JSON service, not a fee. You can choose another integer from 1 to 1,048,576. The name `Relay Quote` matches the card's human-readable intent. The on-chain name allows letters, digits, spaces, hyphens, and underscores.

Read the record back and save the output under `evidence/` without keys or mnemonics:

```bash
pocketd query service show-service relay-quote --network="$NETWORK"
pocketd version
```

The OpenAPI URL in `card.json` tracks the `main` branch and has no `sha256`. Before a MainNet listing, tag the release and add `sha256` only for that immutable URL.

Switch `$NETWORK` to `main` only after Beta behaves the way you expect. MainNet spends real POKT.
