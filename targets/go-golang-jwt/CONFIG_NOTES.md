# golang-jwt configuration notes

| | |
|---|---|
| Component | `github.com/golang-jwt/jwt/v5` `v5.3.1` (`go.mod` / `go.sum`) |
| Runtime | `golang:1.26-bookworm` build stage, pinned by digest in the `Dockerfile`; static binary in a `scratch` final image |
| Doc followed for default | https://golang-jwt.github.io/jwt/usage/parse/ ("Keyfunc" section), and the `Parse` example linked from the README: https://pkg.go.dev/github.com/golang-jwt/jwt/v5#example-Parse-Hmac |
| Link checked | 2026-10-29, HTTP 200 |
| Measured | 2026-10-29, matrix of 15 tokens against the container, both modes (`results/compose/go-golang-jwt-check`, not committed) |

## Pre-run predictions

Written on 2026-10-29 from knowledge of golang-jwt v5 behavior, before any request was sent to this target. The library source was not read for this; the only checks made were that the code compiles against `v5.3.1` (so the option names below exist) and that the documentation page was fetched. The page's code samples could not be extracted, so only its section headings and option table were read.

**Algorithm handling.** I expect `WithValidMethods` to be *optional*: when it is omitted, `jwt.Parse` accepts any signing method that can verify with the key the key function returns. With an `*rsa.PublicKey` that is `RS256`, `RS384` and `RS512`, so the default would accept the `ALG-RS512` token. I expect `alg: none` to be rejected (the `none` method refuses unless a special sentinel key is used), and ES256 and HS256 to be rejected as an invalid key type for an RSA public key.

**Claims.** I expect `iss` and `aud` to be checked only when `WithIssuer` / `WithAudience` are passed, `exp` and `nbf` to be checked only when present, and nothing to be required. I expect `WithExpirationRequired` to exist and to be the only option that makes a missing `exp` fail. The default leeway is 0, so `EXP-SKEW-120` is rejected by default.

Per-test predictions are the "Pred." columns of the table below, written before the first request.

Predicted default weak spots: `ISS-INVALID`, `ISS-MISSING`, `AUD-INVALID`, `AUD-MISSING`, `EXP-MISSING`, `ALG-RS512` (6 of the 13 invalid tokens accepted).

**Hardened.** I expect all four of `WithValidMethods`, `WithIssuer`, `WithAudience` and `WithExpirationRequired` to change behavior on this matrix, and `WithLeeway(0)` not to change anything (0 is already the default).

## Gate

`CTRL-01` returned 200 in default mode with no option beyond the documented call, and 200 in hardened mode.

## What the default is

The documented call, with a key function that returns the public key:

```go
jwt.Parse(token, keyFunc) // keyFunc returns the *rsa.PublicKey
```

Nothing beyond the key function and the key parsing was added to make `CTRL-01` pass. The `pkg.go.dev` `Parse` example (HMAC) checks `token.Method` inside its key function. That check was not copied: `CTRL-01` passes without it, and for an RSA key it would only restrict the method to the RSA family, which is what the key type already does. Everything else in `main.go` (HTTP handling, reading the key and policy, response mapping) is wrapper code, not validation configuration.

**Is `WithValidMethods` required?** No. Measured: with the RSA public key the default accepts a correctly signed **RS512** token (`ALG-RS512`), i.e. the default allow-list is wider than the policy's `["RS256"]`. `none`, ES256 and HS256 are still rejected without the option, by the key-type check.

## Configuration changes: default vs hardened

| Setting | In default? | In hardened? | Changes behavior vs default? | Why |
|---|---|---|---|---|
| `jwt.WithValidMethods(allowed_algorithms)` | no (any RSA method the key can verify) | yes | **yes** | Narrows the accepted methods to the policy's `RS256`. Closes `ALG-RS512`. |
| `jwt.WithIssuer(issuer)` | no | yes | **yes** | Without it `iss` is not checked. Closes `ISS-INVALID` and `ISS-MISSING`. |
| `jwt.WithAudience(audience)` | no | yes | **yes** | Without it `aud` is not checked. Closes `AUD-INVALID` and `AUD-MISSING`. |
| `jwt.WithExpirationRequired()` | no | yes | **yes** | Without it a token with no `exp` is accepted. Closes `EXP-MISSING`. |
| `jwt.WithLeeway(clock_skew_seconds)` | no (0) | yes | no | 0 is already the default; the setting restates the policy. |

Hardened adds 5 settings; 4 change what is accepted on the matrix. The "changes behavior" column is inferred from the hardened rejection messages below, each of which names the option that rejected the token. It was not measured by removing one hardened setting at a time.

## Measured results

Each cell is the measured outcome. There were no differences from the predictions: every prediction held, 30 of 30.

| Test | Pred. default | Measured default | Pred. hardened | Measured hardened | Library error when rejected (default / hardened) |
|---|---|---|---|---|---|
| CTRL-01 | accept | accept | accept | accept | |
| ISS-INVALID | accept | accept | reject | reject | - / `token has invalid issuer` |
| ISS-MISSING | accept | accept | reject | reject | - / `token is missing required claim: iss claim is required` |
| AUD-INVALID | accept | accept | reject | reject | - / `token has invalid audience` |
| AUD-MISSING | accept | accept | reject | reject | - / `token is missing required claim: aud claim is required` |
| EXP-EXPIRED | reject | reject | reject | reject | `token is expired` / same |
| EXP-SKEW-120 | reject | reject | reject | reject | `token is expired` / same |
| EXP-MISSING | accept | accept | reject | reject | - / `token is missing required claim: exp claim is required` |
| NBF-FUTURE | reject | reject | reject | reject | `token is not valid yet` / same |
| NBF-MISSING | accept | accept | accept | accept | |
| ALG-NONE | reject | reject | reject | reject | `'none' signature type is not allowed` / `signing method none is invalid` |
| ALG-UNEXPECTED | reject | reject | reject | reject | `key is of invalid type: ECDSA verify expects *ecdsa.PublicKey` / `signing method ES256 is invalid` |
| ALG-RS512 | accept | accept | reject | reject | - / `signing method RS512 is invalid` |
| ALG-CONFUSION | reject | reject | reject | reject | `key is of invalid type: HMAC verify expects []byte` / `signing method HS256 is invalid` |
| SIG-TAMPERED | reject | reject | reject | reject | `crypto/rsa: verification error` / same |

Default: 6 of 13 invalid tokens accepted (`ISS-INVALID`, `ISS-MISSING`, `AUD-INVALID`, `AUD-MISSING`, `EXP-MISSING`, `ALG-RS512`), 0 of 2 valid tokens rejected. Hardened: 0 of 13 accepted, 0 of 2 rejected. No 5xx responses.

## Surprises and docs-versus-measured

- **The default is permissive on `iss`, `aud` and `exp` presence and on the RSA algorithm family**, but not on other algorithm families: `none`, ES256 and HS256 are rejected with no `WithValidMethods`, because the key type does not match. In hardened mode the same tokens are rejected earlier, by the method list.
- **A missing `iss` or `aud` is rejected by `WithIssuer` / `WithAudience`** as a missing required claim, so no separate presence option is needed for them; `exp` is the only claim that needs its own option.
- **`WithExpirationRequired` is not in the option table of the documentation page** that was followed (checked 2026-10-29), although it exists in `v5.3.1` and works as predicted. The page's code samples could not be extracted, so this is a statement about its option table only.
- `EXP-SKEW-120` is rejected by the default because the default leeway is 0, so `WithLeeway(0)` restates the policy and changes nothing.

## Wrapper notes

401 bodies are written by `main.go`, not golang-jwt: the body is `unauthorized` and `X-Reject-Reason` carries the library's error message. This makes response-body comparison with natively generating components (JwtBearer, Spring Security) non-equivalent, as noted for the other wrapper targets. The key function cannot fail, so every error returned by `jwt.Parse` is a validation decision and maps to 401; there is no 5xx path for validation. The final image has no shell or curl, so the healthcheck is the binary itself (`/server -healthcheck`).
