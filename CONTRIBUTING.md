# Contributing

Keep the starter reproducible.

- Python changes stay on the standard library.
- `SERVICE_VERSION`, `openapi/v1/openapi.json` `info.version`, and `CHANGELOG.md` move together.
- Do not commit `.env`, key files, PEM files, or `supplier-keys.local.yaml`.
- Do not put a real supplier key, mnemonic, or transaction signature in docs or tests.
- Do not record a `sha256` for a URL whose content still changes.
- Run `python validate_and_test.py --skip-live` before opening a pull request.
- If you change a health path, update `card.json` and `deploy/sage-gateway.example.yaml` in the same change.
- New public responses stay JSON objects and avoid the gateway penalty phrases listed in the README.
