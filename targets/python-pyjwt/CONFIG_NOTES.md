# PyJWT configuration notes

| | |
|---|---|
| Component | PyJWT `2.15.1` (pinned in `requirements.txt`), `cryptography` `50.0.2` |
| Runtime | `python:3.13.15-slim-bookworm`, pinned by digest in the `Dockerfile` |
| Doc followed for default | https://pyjwt.readthedocs.io/en/stable/usage.html#encoding-decoding-tokens-with-rs256-rsa |
| Link checked | 2026-10-25, HTTP 200 |
| Measured | 2026-10-25, matrix of 13 tokens against the container, both modes |

## Pre-run predictions

Written from memory of the PyJWT source and docs, before any request was sent to this target. Disclosure: before writing them I had read the code of an earlier local prototype (Docker image `jwt-eval/pyjwt`, source not in this repo), which already contained the `audience=` workaround, so the `CTRL-01` prediction is not independent of it. All results below were measured against the code in this directory.

**CTRL-01 in default mode.** I expected it to be **rejected** by the plain quick-start `jwt.decode(token, public_key, algorithms=["RS256"])`: when the caller passes no `audience`, PyJWT raises `InvalidAudienceError` for any token that does carry an `aud` claim. If so, `audience=` is the one line added to make the control token pass. The brief assumed PyJWT would skip `aud` when it is not configured; I did not think that was true when the claim is present.

My per-test predictions are the "Pred." columns of the results table below; they were written down before the first request.

Predicted default weak spots: `ISS-INVALID`, `ISS-MISSING`, `EXP-MISSING` (3 of the 11 invalid tokens accepted; `NBF-MISSING` is expected to be accepted). The brief also listed `AUD-*` as a possible weak spot; I predicted they are not: `audience` is needed for the control token, so it is checked in both modes.

## Gate

Default mode, plain quick-start, no `audience`: **`CTRL-01` returned 401** (`InvalidAudienceError: Invalid audience`), as predicted. After adding `audience=` it returns 200 in default and hardened mode. All other results below were taken after the gate passed.

## What the default is

The quick-start line from the docs, plus one argument:

```python
jwt.decode(token, public_key, algorithms=["RS256"], audience=policy["audience"])
#                             ^ quick-start            ^ the only line added
```

Everything else in `app.py` (HTTP handling, reading the key and policy, response mapping) is wrapper code, not validation configuration.

## Configuration changes: default vs hardened

| Setting | In default? | In hardened? | Changes behavior vs default? | Why |
|---|---|---|---|---|
| `algorithms=["RS256"]` | yes | yes | no | **Mandatory** argument of `decode()`: omitting it raises `DecodeError: It is required that you pass in a value for the "algorithms" argument`. It is part of the quick-start, not hardening. |
| `audience=` | yes (added) | yes | no | Without it, PyJWT rejects every token that carries `aud`, including `CTRL-01`. Same value in both modes. |
| `issuer=` | no | yes | **yes** | Without it `iss` is neither checked nor required. Alone, it closes `ISS-INVALID` and `ISS-MISSING`. |
| `options={"require": ["exp","iss","aud"]}` | no | yes | **yes** | Without it a missing `exp` passes. Alone, it closes `EXP-MISSING` and `ISS-MISSING`. The `iss` and `aud` entries are redundant once `issuer=`/`audience=` are passed; only `exp` is not enforced any other way. |
| `leeway=0` | no | yes | no | 0 is already PyJWT's default; the setting restates the policy. |

Hardened adds 3 settings; 2 of them change what is accepted. Closing all three default gaps needs both `issuer=` and `require` containing `exp`. The "changes behavior" column was measured by removing one hardened setting at a time against the pinned library.

## Measured results

Each cell is the measured outcome; **bold** marks a result that differs from the prediction. There were no such differences: every prediction held.

| Test | Pred. default | Measured default | Pred. hardened | Measured hardened | Library error when rejected (default / hardened) |
|---|---|---|---|---|---|
| CTRL-01 | accept | accept | accept | accept | |
| ISS-INVALID | accept | accept | reject | reject | - / `InvalidIssuerError` |
| ISS-MISSING | accept | accept | reject | reject | - / `MissingRequiredClaimError` (iss) |
| AUD-INVALID | reject | reject | reject | reject | `InvalidAudienceError` / same |
| AUD-MISSING | reject | reject | reject | reject | `MissingRequiredClaimError` (aud) / same |
| EXP-EXPIRED | reject | reject | reject | reject | `ExpiredSignatureError` / same |
| EXP-MISSING | accept | accept | reject | reject | - / `MissingRequiredClaimError` (exp) |
| NBF-FUTURE | reject | reject | reject | reject | `ImmatureSignatureError` / same |
| NBF-MISSING | accept | accept | accept | accept | |
| ALG-NONE | reject | reject | reject | reject | `InvalidAlgorithmError` / same |
| ALG-UNEXPECTED | reject | reject | reject | reject | `InvalidAlgorithmError` / same |
| ALG-CONFUSION | reject | reject | reject | reject | `InvalidAlgorithmError` / same |
| SIG-TAMPERED | reject | reject | reject | reject | `InvalidSignatureError` / same |

Default: 3 of 11 invalid tokens accepted (`ISS-INVALID`, `ISS-MISSING`, `EXP-MISSING`), 0 of 1 valid control tokens rejected. Hardened: 0 of 11 accepted, 0 of 1 rejected. No 5xx responses.

## Surprises and docs-versus-measured

- **The quick-start cannot validate a token that has `aud` unless `audience` is passed.** The docs' RS256 example signs a payload without `aud`, so the example works as written; it just does not generalise to an OIDC-style token. The audience section of the same page says a token with `aud` "MUST be rejected" if the processor does not identify itself, so the behavior matches the docs, but a developer following the RS256 example alone would hit it only when moving to real tokens.
- **`AUD-*` are not default weak spots**, contrary to the brief's guess, because `audience=` is forced by the control token. That is a result of the "minimum to pass `CTRL-01`" rule, not of PyJWT checking `aud` by default.
- **`issuer=` also enforces presence of `iss`** (`MissingRequiredClaimError`), so `require` is redundant for `iss` and `aud`.
- `ALG-NONE`, `ALG-UNEXPECTED` and `ALG-CONFUSION` are all rejected by the mandatory `algorithms` list (`InvalidAlgorithmError`). Because `decode()` refuses to run without that list, default and hardened behave identically on the `ALG` category.
- No other docs-versus-measured mismatch was found.

## Wrapper notes

401 bodies are written by `app.py`, not PyJWT: the body is `unauthorized` and `X-Reject-Reason` carries `<ErrorClass>: <library message>`. This makes response-body comparison with natively generating components (JwtBearer) non-equivalent, as noted for the other wrapper targets. Exceptions that are not `jwt.PyJWTError` return 500 so the harness reports them as errors instead of rejections; none occurred.
