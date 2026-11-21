# Evidence

Store observed output here. Do not invent hashes or addresses.

Safe to commit after you redact it:

- `pocketd version` and `python --version`
- `validate_and_test.py` output
- service query output
- card validation output
- miner and relayer validation output
- public URLs and transaction hashes you actually received

Never commit:

- private keys or mnemonics
- `.env` contents
- `supplier-keys.local.yaml`
- authorization headers
- keyring directories

`local-validation.txt` is the local and live validator output captured when this starter was built. It is not a relay proof.
