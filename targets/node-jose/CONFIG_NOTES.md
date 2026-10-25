# jose configuration notes

## Setup and evidence

Default follows [the official jose README](https://github.com/panva/jose): import
the SPKI RSA public key with importSPKI(pem, 'RS256'), then jwtVerify(token, key).
No issuer, audience, requiredClaims, algorithm allow-list or clock tolerance is
passed to jwtVerify in default mode.

Tested 2026-10-25 on native Windows: jose 6.2.13, Express 5.3.0, Node v24.11.1.
Installed package versions matched package.json. package-lock.json is present.
Both modes accepted CTRL-01. This run used the existing installed dependencies;
it did not test npm ci or the Node 22.20.0 Docker image.

See [full report](../../results/pilot/target-validation/REPORT.md),
[raw follow-up results](../../results/pilot/target-validation/followup/raw.csv), and
[pre-run predictions](../../results/pilot/target-validation/PREDICTIONS.md).

## Configuration changes

| Setting | In default? | In hardened? | Changes behavior vs default? | Why |
|---|---|---|---|---|
| importSPKI(pem, 'RS256') | yes | same | no delta | Imports a WebCrypto key bound to RS256. |
| algorithms: ['RS256'] | omitted | explicit | no tested acceptance delta; diagnostics change | Imported key already rejects tested incompatible algorithms; hardened returns ERR_JOSE_ALG_NOT_ALLOWED. |
| issuer | omitted | policy issuer | yes | Wrong/missing issuer changes 200 to 401. |
| audience | omitted | policy audience | yes | Wrong/missing audience changes 200 to 401. |
| requiredClaims: ['iss','aud','exp'] | omitted | explicit | yes | Missing exp changes 200 to 401. Issuer/audience options also imply presence of their claims. |
| clockTolerance: 0 | implicit zero | explicit zero | no | Restates the default; 120-second-expired probe rejects in both. |

Five hardened settings, three with an observed acceptance effect in this setup.
This is not a claim that algorithm allow-lists are unnecessary for other key
representations or algorithms.

## Predicted versus measured

| Test | Predicted default | Measured default | Predicted hardened | Measured hardened |
|---|---|---|---|---|
| CTRL-01 | accept | accept (200) | accept | accept (200) |
| ISS-INVALID | accept | accept (200) | reject | reject (401) |
| ISS-MISSING | accept | accept (200) | reject | reject (401) |
| AUD-INVALID | accept | accept (200) | reject | reject (401) |
| AUD-MISSING | accept | accept (200) | reject | reject (401) |
| EXP-EXPIRED | reject | reject (401) | reject | reject (401) |
| EXP-MISSING | accept | accept (200) | reject | reject (401) |
| NBF-FUTURE | reject | reject (401) | reject | reject (401) |
| NBF-MISSING | accept | accept (200) | accept | accept (200) |
| ALG-NONE | reject | reject (401) | reject | reject (401) |
| ALG-UNEXPECTED | reject | reject (401) | reject | reject (401) |
| ALG-CONFUSION | reject | reject (401) | reject | reject (401) |
| SIG-TAMPERED | reject | reject (401) | reject | reject (401) |

All acceptance predictions matched. Default: 5/11 false accepts (45.45%),
0/2 false rejects, zero errors. Hardened: 0/11 false accepts, 0/2 false rejects,
zero errors. The five changes are ISS-INVALID, ISS-MISSING, AUD-INVALID,
AUD-MISSING and EXP-MISSING. nbf is validated when present and stays optional.

## Diagnostic findings

- EXP-SKEW-120 and EXP-PAST-3600: 401 in both modes, ERR_JWT_EXPIRED.
- ALG-RS512: 401 in both modes. Default exposes TypeError from the imported
  CryptoKey/algorithm mismatch; hardened exposes ERR_JOSE_ALG_NOT_ALLOWED.
- The original EXP-EXPIRED token has nbf later than exp. jose reports expiration,
  whereas .NET reports the invalid interval. This is a limitation of comparing
  validation reasons using that input, documented in the shared pilot report.

## Responses and source verification

All 401 bodies (`unauthorized`) and X-Reject-Reason headers are wrapper-generated.
The header uses `<code>[:<claim>[:<reason>]]`, falling back to the error type.
There is no WWW-Authenticate header in this wrapper. Body-shape comparisons with
JwtBearer also compare wrapper/framework choices, not only JWT libraries.

Checked on 2026-10-25: official README and current upstream type documentation.
The exact [v6.2.13 API link](https://github.com/panva/jose/blob/v6.2.13/docs/functions/jwt_verify.jwtVerify.md)
could not be retrieved by the web tool. Version-specific checks instead read the
installed package's dist/types/types.d.ts and dist/webapi/lib/jwt_claims_set.js.
The measured behavior agrees with that source; no contradiction was observed.

Local runs support KEYS_PUB and POLICY; container defaults are /keys/public.pem
and /policy/policy.json. See the report for reproduction commands. Docker and a
fresh npm ci install still need validation before the team-wide main run.
