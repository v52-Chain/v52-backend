# V52 Verifier

**Owner:** Franco

**Reviewer:** Saúl for manifest/provenance

**Status:** `PENDING`

The verifier will be independent from the UI and reject:

- modified declared files;
- missing files;
- undeclared additional files;
- invalid hashes;
- unsafe archive paths.

P0 verifies integrity, not signer identity or legal correctness. Cryptographic signatures and trusted roots are post-hackathon work.
