# Expanded matrix predictions — 25 October 2026

Recorded before running the revised 15-case matrix. These predictions are informed
by the earlier pilot and its extra probes; they are not independent first-run predictions.
The two former probes now belong to the shared matrix and its metric denominators.

| Test | Both .NET targets: default | jose: default | All three: hardened |
|---|---|---|---|
| CTRL-01 | accept | accept | accept |
| ISS-INVALID | reject | accept | reject |
| ISS-MISSING | reject | accept | reject |
| AUD-INVALID | reject | accept | reject |
| AUD-MISSING | reject | accept | reject |
| EXP-EXPIRED | reject | reject | reject |
| EXP-SKEW-120 | accept | reject | reject |
| EXP-MISSING | reject | accept | reject |
| NBF-FUTURE | reject | reject | reject |
| NBF-MISSING | accept | accept | accept |
| ALG-NONE | reject | reject | reject |
| ALG-UNEXPECTED | reject | reject | reject |
| ALG-RS512 | accept | reject | reject |
| ALG-CONFUSION | reject | reject | reject |
| SIG-TAMPERED | reject | reject | reject |

Expected false accepts out of the 13 expected-reject cases: .NET default 2 each;
jose default 5; all hardened modes 0. Expected false rejects: 0 out of 2 each.
EXP-EXPIRED should now produce an expiration diagnostic in .NET because the
base iat/nbf precede its expiration; the invalid-interval confound was removed.
