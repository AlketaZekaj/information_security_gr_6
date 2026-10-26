# express-jwt configuration notes

| | |
|---|---|
| Component | `express-jwt` 8.5.1, Node 22 or newer |
| Default documentation | https://github.com/auth0/express-jwt#usage |
| Documentation checked | 26 October 2026 |
| Response author | `express-jwt` signals an error; this target's Express error handler writes the HTTP 401 body and header. |

## Default and hardened settings

The README requires both `secret` and `algorithms`, so the default uses the RSA public
key and `algorithms: ['RS256']`. The algorithm list is a mandatory setup parameter,
not an added hardening setting. No extra setting was needed for `CTRL-01` to pass.

| Setting | In default? | In hardened? | Changes behavior vs default? | Why |
|---|---|---|---|---|
| `secret: publicKey` | yes | yes | no | Mandatory key for signature verification. |
| `algorithms: ['RS256']` | yes | yes, read from policy | no | Mandatory option; already matches the policy. |
| `issuer` | no | yes | yes | Rejects incorrect or missing `iss`. |
| `audience` | no | yes | yes | Rejects incorrect or missing `aud`. |
| `clockTolerance: 0` | no | yes | no | Restates the default tolerance. |
| manual required-claims check | no | yes | yes | The middleware checks `exp` when present but has no option to require it. `iss` and `aud` are also checked for presence here. |

`nbf` remains optional. The target reads the expected values and required-claim names
from `policy.json`; it never receives the private key.

## Predictions written before the matrix run

| Cases | Default prediction | Hardened prediction | Reason |
|---|---|---|---|
| `CTRL-01`, `NBF-MISSING` | accept | accept | Valid under the shared policy. |
| `ISS-*`, `AUD-*`, `EXP-MISSING` | accept | reject | Default has no issuer/audience policy and does not require `exp`. |
| `EXP-EXPIRED`, `EXP-SKEW-120`, `NBF-FUTURE` | reject | reject | Standard time checks with zero tolerance. |
| `ALG-*`, `SIG-TAMPERED` | reject | reject | RS256 allow-list and signature verification. |

## Local verification

Ran the shared 15-case matrix with `harness/run.py --components express-jwt` on
26 October 2026. Both control gates passed. Default matched 10/15 expectations:
it accepted `ISS-INVALID`, `ISS-MISSING`, `AUD-INVALID`, `AUD-MISSING`, and
`EXP-MISSING` (5/13 false accepts). Hardened matched 15/15 expectations
(0/13 false accepts). Neither mode had a false rejection or server error.
All predictions above matched the observed acceptance decisions.

This was a native local run; the container has not yet been verified. The
error handler returns 500 for unexpected failures so the harness does not count
a server error as token rejection. The temporary result rows were removed after
verification and must be regenerated for the team's final results.
