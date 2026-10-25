# jsonwebtoken configuration notes

> Matrix update (25 October 2026): the shared suite now has 15 cases, including
> EXP-SKEW-120 and ALG-RS512. The results below describe the earlier 13-case run;
> this target has not been rerun against the revised suite in this update.
> Use the shared generator and check_target.py to run all 15 cases. Do not
> present the older rates below as results for the expanded matrix.

| | |
|---|---|
| Component | `jsonwebtoken` `9.0.3` (`package-lock.json`, installed with `npm ci`) |
| Runtime | `node:22.20.0-slim`, pinned by digest in the `Dockerfile` |
| Doc followed for default | https://github.com/auth0/node-jsonwebtoken#jwtverifytoken-secretorpublickey-options-callback |
| Link checked | 2026-10-25, HTTP 200 |
| Measured | 2026-10-25, matrix of 13 tokens against the container, both modes |

## Pre-run predictions

Written from memory of the jsonwebtoken 9.x source and README, before any request was sent to this target. Disclosure: before writing them I had read the code of an earlier local prototype (Docker image `jwt-eval/jsonwebtoken`, source not in this repo), which used the same default call and a manual `exp` check, so the predictions are not fully independent of it. The RS384/RS512 prediction was not in that prototype. All results below were measured against the code in this directory.

**Algorithm handling.** I expect `algorithms` to be *optional*: when it is omitted, `jwt.verify` infers the allowed algorithms from the key type. For an RSA public key that is `RS256`, `RS384`, `RS512`, so the default would accept RS384 and RS512 tokens too (not covered by the 13-case matrix). I expect `alg: none` and HS256 to be rejected by that inferred list, even though the key is a PEM public key.

**Claims.** I expect `iss` and `aud` to be checked only when `issuer` / `audience` options are passed, `exp` and `nbf` to be checked only when present, and nothing to be required. The README itself says the payload is returned "if the signature is valid and optional expiration, audience, or issuer are valid".

My per-test predictions are the "Pred." columns of the results table below; they were written down before the first request.

Predicted default weak spots: `ISS-INVALID`, `ISS-MISSING`, `AUD-INVALID`, `AUD-MISSING`, `EXP-MISSING` (5 of the 11 invalid tokens accepted).

**Hardened.** I expect `issuer`, `audience` and the manual `exp` check to change behavior, and `algorithms` and `clockTolerance: 0` not to change anything on this matrix (the inferred list already excludes every wrong algorithm in it; 0 is the default tolerance).

## Gate

`CTRL-01` returned 200 in default mode with no option beyond the README call, and 200 in hardened mode, before any other token was sent.

## What the default is

The README call, unchanged:

```js
jwt.verify(token, publicKey)   // publicKey = fs.readFileSync('public.pem'), as in the README
```

Nothing was added to make `CTRL-01` pass. Everything else in `app.js` (HTTP handling, reading the key and policy, response mapping) is wrapper code, not validation configuration.

**Is `algorithms` required?** No. In `9.0.3` it is optional and inferred from the key type; the README says so (rsa: `RS256`, `RS384`, `RS512`). Measured: with the RSA public key the default accepts a correctly signed **RS384** and **RS512** token as well (see below), i.e. the default allow-list is wider than the policy's `["RS256"]`.

## Configuration changes: default vs hardened

| Setting | In default? | In hardened? | Changes behavior vs default? | Why |
|---|---|---|---|---|
| `algorithms: ['RS256']` | no (inferred from key: RS256/384/512) | yes | no on the 13-case matrix; **yes outside it** (RS384, RS512 become rejected) | Narrows the inferred list to the policy. |
| `issuer` | no | yes | **yes** | Without it `iss` is not checked. Closes `ISS-INVALID` and `ISS-MISSING`. |
| `audience` | no | yes | **yes** | Without it `aud` is not checked. Closes `AUD-INVALID` and `AUD-MISSING`. |
| manual required-claims check after `verify` | no | yes | **yes** | jsonwebtoken has no option to require `exp`. The loop covers `policy.required_claims`, but only `exp` is not already enforced by `issuer`/`audience`. Closes `EXP-MISSING`. Counted as a configuration change, and the only one that is code rather than an option. |
| `clockTolerance: 0` | no | yes | no | 0 is already the default; the setting restates the policy. |

Hardened adds 5 settings; 3 change what is accepted on the matrix (4 counting RS384/RS512). The "changes behavior" column was measured by removing one hardened setting at a time against the pinned library.

## Measured results

Each cell is the measured outcome; **bold** marks a result that differs from the prediction. There were no such differences: every prediction held, including the RS384/RS512 prediction.

| Test | Pred. default | Measured default | Pred. hardened | Measured hardened | Library error when rejected (default / hardened) |
|---|---|---|---|---|---|
| CTRL-01 | accept | accept | accept | accept | |
| ISS-INVALID | accept | accept | reject | reject | - / `JsonWebTokenError: jwt issuer invalid` |
| ISS-MISSING | accept | accept | reject | reject | - / `JsonWebTokenError: jwt issuer invalid` |
| AUD-INVALID | accept | accept | reject | reject | - / `JsonWebTokenError: jwt audience invalid` |
| AUD-MISSING | accept | accept | reject | reject | - / `JsonWebTokenError: jwt audience invalid` |
| EXP-EXPIRED | reject | reject | reject | reject | `TokenExpiredError: jwt expired` / same |
| EXP-MISSING | accept | accept | reject | reject | - / `JsonWebTokenError: jwt exp claim is required` (wrapper-thrown) |
| NBF-FUTURE | reject | reject | reject | reject | `NotBeforeError: jwt not active` / same |
| NBF-MISSING | accept | accept | accept | accept | |
| ALG-NONE | reject | reject | reject | reject | `JsonWebTokenError: jwt signature is required` / same |
| ALG-UNEXPECTED | reject | reject | reject | reject | `JsonWebTokenError: invalid algorithm` / same |
| ALG-CONFUSION | reject | reject | reject | reject | `JsonWebTokenError: invalid algorithm` / same |
| SIG-TAMPERED | reject | reject | reject | reject | `JsonWebTokenError: invalid signature` / same |

Default: 5 of 11 invalid tokens accepted (`ISS-INVALID`, `ISS-MISSING`, `AUD-INVALID`, `AUD-MISSING`, `EXP-MISSING`), 0 of 1 valid control tokens rejected. Hardened: 0 of 11 accepted, 0 of 1 rejected. No 5xx responses.

**Outside the matrix** (two extra tokens with the control payload, signed RS384 and RS512 by hand, not part of the 13 cases): default **accepted both**, hardened rejected both. This is the only place where `algorithms` changes behavior.

## Surprises and docs-versus-measured

- **The default is permissive on `iss`, `aud` and `exp` presence but not on the algorithm family**: `none`, ES256 and HS256 are all rejected with no `algorithms` option, because the RSA public key narrows the inferred list. The README documents this inference.
- **`ALG-NONE` message** is `jwt signature is required`, i.e. rejected as unsigned rather than as a disallowed algorithm.
- **No `require exp` option** exists, as the brief anticipated; the manual check is the one configuration change that is code.
- `issuer`/`audience` reject a *missing* claim as "invalid", so no separate presence option is needed for them.
- The README's `verify` text ("optional expiration, audience, or issuer") matches the measured behavior; no docs-versus-measured mismatch was found.

## Wrapper notes

401 bodies are written by `app.js`, not jsonwebtoken: the body is `unauthorized` and `X-Reject-Reason` carries `<error name>: <library message>`. This makes response-body comparison with natively generating components (JwtBearer) non-equivalent, as noted for the other wrapper targets. Errors that are not a `JsonWebTokenError` return 500 so the harness reports them as errors instead of rejections; none occurred. The `EXP-MISSING` hardened rejection comes from the wrapper's own check, not from the library.
