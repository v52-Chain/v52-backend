# Fixtures

**Owner:** Franco

**Reviewer:** Saúl for raw/provenance integrity

**Status:** `PENDING`

## Directories

- `known_case/` — public Uniswap V3 transaction and expected result.
- `misleading_claim/` — claim that incorrectly attributes protocol volume to the subject.
- `tampered_package/` — altered evidence/package used to prove verifier failure.

## Rules

- Never present a fixture as live data.
- Preserve source, retrieval time, request and adapter version.
- Remove credentials, not evidentiary content.
- Document expected output before relying on a fixture as a test oracle.
- Keep large/raw data minimal and justified.
