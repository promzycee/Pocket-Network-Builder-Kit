# Task acceptance

The task is to publish reusable code and documentation for builders: a preapproved use case, a starter repository, setup docs, a clean-environment test, and an example. Proof is the repository, the instructions, a functional demo, and validation. The work must be reproducible, maintained, original, and free of embedded secrets.

| Requirement | Where it lives | Status |
| --- | --- | --- |
| Use case ready to preapprove | `docs/use-case.md` | Written. Approval not received. |
| Starter repository | this repo | Present |
| Setup docs | `README.md`, `docs/setup.md` | Present |
| Clean-environment test | `validate_and_test.py` | Runs with Python only |
| Functional example | `example_client.py` | Calls the local API |
| Reproducible | stdlib server, pinned CI Python | Present |
| Maintained | `CHANGELOG.md`, `CONTRIBUTING.md`, `.github/workflows/ci.yml` | Present |
| Original | Relay Quote implementation in this repo | Present |
| No embedded secrets | `.gitignore`, `.env.example`, secret scan in the validator | Present |
| On-chain registration | `docs/register.md` | Not executed |
| HA RelayMiner on a public HTTPS host | `deploy/` | Template only |
| Settled claim and proof | | Not executed |
| Ambassador approval | `docs/preapproval.md`, `evidence/preapproval.md` | Not received |

Do not mark the external rows complete from local tests.
