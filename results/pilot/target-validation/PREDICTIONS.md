# Predictions recorded before the local run

Date: 2026-10-25. These are hypotheses, not measured results. The jose predictions
already existed in its CONFIG_NOTES.md. The .NET predictions below follow the
task sheet and require confirmation against the two different pinned versions.

| Case | Both .NET targets: default | jose: default | All three: hardened |
|---|---|---|---|
| CTRL-01 | accept | accept | accept |
| ISS-INVALID | reject | accept | reject |
| ISS-MISSING | reject | accept | reject |
| AUD-INVALID | reject | accept | reject |
| AUD-MISSING | reject | accept | reject |
| EXP-EXPIRED | reject | reject | reject |
| EXP-MISSING | reject | accept | reject |
| NBF-FUTURE | reject | reject | reject |
| NBF-MISSING | accept | accept | accept |
| ALG-NONE | reject | reject | reject |
| ALG-UNEXPECTED | reject | reject | reject |
| ALG-CONFUSION | reject | reject | reject |
| SIG-TAMPERED | reject | reject | reject |

Separate diagnostic probes (excluded from the 13-case matrix and its rates):

| Probe | Both .NET targets: default | jose: default | All three: hardened |
|---|---|---|---|
| EXP-SKEW-120: expired 120 seconds ago, with nbf before exp | accept | reject | reject |
| ALG-RS512: RSA SHA-512 signature with the same RSA key | accept | reject | reject |

The first probe tests the .NET five-minute clock tolerance. The second separates
an algorithm policy from rejecting ES256 because it cannot be verified by an RSA
key. jose imports its key as a WebCrypto RS256 CryptoKey; that binding is expected
to reject RS512 even before an explicit algorithms allow-list is supplied.

## Follow-up prediction, before the second run

The first run found that EXP-EXPIRED has nbf later than exp. Both .NET targets
rejected it with an invalid-lifetime error, so it did not isolate expiration.
Add EXP-PAST-3600 outside the main matrix: iat and nbf are 7200 seconds ago,
exp is 3600 seconds ago. Prediction: all three targets reject it in both modes;
the .NET rejection should now be an expiration error. Rerun the same unchanged
13-case matrix with this third diagnostic probe and retain the first run.
