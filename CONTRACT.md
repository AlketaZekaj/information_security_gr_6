# Shared contract

Everything the three team members must agree on. Sections 1-3 are the agreed decisions. Anything marked **(proposed)** is an interpretation made while building the foundation and needs a yes/no from the team.

## 1. Agreed decisions

1. **"Default" rule.** Copy the official quick-start and configure only the minimum so the valid control token (`CTRL-01`) is accepted. Cite the doc URL in a code comment. Write down every line that had to be added in the target's `CONFIG_NOTES.md`.
2. **Policy.** Required claims are `iss`, `aud`, `exp`. `nbf` is validated *when present* but is not required, so `NBF-MISSING` is expected to be **accepted**. (This corrects the earlier "everything except the control must be rejected".)
3. **Time-based tokens.** `EXP-EXPIRED` is 1 hour in the past and `NBF-FUTURE` is 1 hour in the future, beyond the .NET default 5-minute skew. `EXP-SKEW-120` is 2 minutes expired and specifically tests whether the default tolerance violates the policy's zero skew. Base `iat` and `nbf` are 2 hours ago so both expired tokens retain a valid chronological interval.
4. **Ports.** PyJWT 8001, JwtBearer 8002, jsonwebtoken 8003, jose 8004, express-jwt 8005, JsonWebTokenHandler 8006, Spring Security 8007, golang-jwt 8008.
5. **Mode switching.** Compose reads `CONFIG_MODE=${CONFIG_MODE:-default}`; the harness recreates the containers for each mode.
6. **Extra CSV column:** `www_authenticate`.
7. **Status handling.** 200 = accepted, 401/403 = rejected, anything else = error, reported separately and never counted as a rejection.

| Port | Target directory |
|---|---|
| 8001 | `targets/python-pyjwt` |
| 8002 | `targets/dotnet-jwtbearer` |
| 8003 | `targets/node-jsonwebtoken` |
| 8004 | `targets/node-jose` |
| 8005 | `targets/node-express-jwt` |
| 8006 | `targets/dotnet-jsonwebtokenhandler` |
| 8007 | `targets/java-spring-security` |
| 8008 | `targets/go-golang-jwt` |

The ports above are **host** ports. **(proposed)** Every container listens on 8080 internally (this is what the existing `node-jose`, `dotnet-jwtbearer` and `dotnet-jsonwebtokenhandler` targets already do) and compose maps `8001:8080`, `8002:8080`, and so on. `python-pyjwt` and `node-jsonwebtoken` follow the same rule.

## 2. Policy

`policy.json` is the single source of the expected values. Targets read it; nothing in a target hard-codes them (the quick-start line of a *default* configuration may use literals such as `"RS256"`, as its documentation does).

```json
{
  "issuer": "https://auth.example.test",
  "audience": "jwt-eval-api",
  "allowed_algorithms": ["RS256"],
  "required_claims": ["iss", "aud", "exp"],
  "clock_skew_seconds": 0
}
```

Hardened configuration enforces exactly this policy: expected issuer and audience, only RS256, `iss`/`aud`/`exp` required, zero clock tolerance. `nbf` is validated when present and never required. The expected outcomes are grounded in RFC 8725 section 3.1 (algorithm verification), 3.2 (appropriate algorithms), 3.8 (issuer) and 3.9 (audience), and in RFC 7519 section 4.1.4 / 4.1.5 for `exp` / `nbf`.

## 3. API contract (every target)

| Request | Response |
|---|---|
| `GET /health` | `200`. **(proposed)** Body SHOULD be JSON `{"status":"ok","component":"...","version":"...","config":"default\|hardened"}` so the harness can confirm which version and mode it is really talking to. Existing targets return plain `ok`; the harness must not depend on the body. |
| `GET /protected` with `Authorization: Bearer <token>` | `200` if the token is accepted, `401` if rejected. Anything else (5xx, timeout, 404) is an **error** under decision 7. |

- `CONFIG_MODE` environment variable: `default` or `hardened`; any other value stops the process at startup.
- `/keys/public.pem` and `/policy/policy.json` are mounted **read-only**. **(proposed)** Mount the single file `keys/public.pem`, not the `keys/` directory, so the private keys never reach a target container. Optional overrides: `KEYS_PUB`, `POLICY`.
- **(proposed)** Wrapper-generated responses: `200` body `ok`; `401` body `unauthorized` plus a diagnostic header `X-Reject-Reason` (error class and library message). Components that write their own 401 (JwtBearer) keep their native response; this is why the harness records `www_authenticate` and `response_body`. `X-Reject-Reason` is diagnostic only and is not compared.

Compose service shape (one per target):

```yaml
pyjwt:
  build: ./targets/python-pyjwt
  ports: ["8001:8080"]
  environment:
    CONFIG_MODE: ${CONFIG_MODE:-default}
  volumes:
    - ./keys/public.pem:/keys/public.pem:ro
    - ./policy.json:/policy/policy.json:ro
```

## 4. Test matrix and token rules

`testmatrix.json` is authoritative; this table is a summary. There are 15 cases: 2 expected acceptances and 13 expected rejections. Each non-control token changes exactly one property of `CTRL-01`. `EXP-SKEW-120` and `ALG-RS512` are main-matrix cases for every target, included in the same results and rates as the other cases.

| ID | Changes only this | Expected |
|---|---|---|
| CTRL-01 | nothing, valid token | accept |
| ISS-INVALID | `iss` = another issuer | reject |
| ISS-MISSING | `iss` removed | reject |
| AUD-INVALID | `aud` = another audience | reject |
| AUD-MISSING | `aud` removed | reject |
| EXP-EXPIRED | `exp` = now - 3600 | reject |
| EXP-SKEW-120 | `exp` = now - 120 | reject |
| EXP-MISSING | `exp` removed | reject |
| NBF-FUTURE | `nbf` = now + 3600 | reject |
| NBF-MISSING | `nbf` removed | **accept** |
| ALG-NONE | header `alg: none`, empty signature | reject |
| ALG-UNEXPECTED | signed ES256 with the EC key | reject |
| ALG-RS512 | `alg: RS512`, signed with the same RSA key and SHA-512 | reject |
| ALG-CONFUSION | HS256, HMAC secret = RSA public key PEM bytes | reject |
| SIG-TAMPERED | valid token, payload edited after signing | reject |

- Missing and invalid claims are separate rows.
- `category` is the ID prefix: `CTRL`, `ISS`, `AUD`, `EXP`, `NBF`, `ALG`, `SIG`.
- Base token: header `{"alg":"RS256","typ":"JWT"}`; payload `iss`, `aud`, `sub`, `iat` = now - 7200, `nbf` = now - 7200, `exp` = now + 3600. `now` is the generation timestamp in `tokens/index.json`, not `iat`. Both expired cases change only `exp` and retain `iat <= nbf < exp < now`; this avoids testing an invalid lifetime interval instead of expiration.
- **One property differs per token.** The signature is derived data, not a property of its own: claim cases are re-signed with the RSA key. The four `ALG-*` cases legitimately change the header and the signature together (the `alg` value decides how the signature is made), and `SIG-TAMPERED` changes the payload and leaves the old signature stale. `generator/verify_tokens.py` encodes these rules, including same-key SHA-512 verification for `ALG-RS512`.
- Awkward tokens (`ALG-NONE`, `ALG-CONFUSION`, `SIG-TAMPERED`) are built by hand with base64url and `hmac`, because libraries refuse to produce them. No JWT library is used anywhere in the generator.
- Tokens contain timestamps relative to generation time: **run `python generator/generate.py` right before each test run.** The generation time is written to `tokens/generated_at.txt`. `tokens/` and `keys/*.pem` are not committed.

## 5. Results CSV

`component, version, config, test_id, category, expected, actual_status, accepted, correct, latency_ms, response_body, www_authenticate`

| Column | Meaning **(proposed)** |
|---|---|
| `component`, `version` | Library under test and its measured version (for example `PyJWT`, `2.15.1`) |
| `config` | `default` or `hardened` |
| `test_id`, `category` | From `testmatrix.json` |
| `expected` | `accept` or `reject`, from `testmatrix.json` |
| `actual_status` | HTTP status code; empty if there was no response |
| `accepted` | `true` for 200, `false` for 401/403, **empty for an error** |
| `correct` | `true` if `accepted` matches `expected`; empty for an error |
| `latency_ms` | Client-measured round trip of the single request |
| `response_body` | First 500 characters of the body, whitespace collapsed |
| `www_authenticate` | Value of the `WWW-Authenticate` response header, empty if absent |

Counting rules **(proposed)**:

- **False-accept rate** (per category): rows with `expected=reject` and `accepted=true`, over rows with `expected=reject` and a non-error status.
- **False-reject rate**: rows with `expected=accept` and `accepted=false`, reported for `CTRL-01` (setup check) and `NBF-MISSING` (policy deviation) separately.
- **Case-level rejection coverage**: number of expected-reject cases rejected in default mode divided by all non-error expected-reject cases (13 in an error-free run). Report the error count separately. This is a case-level measure, not a count of independent requirements. If the team uses the seven requirement groups in the task split, include `EXP-SKEW-120` in expiry enforcement (R3) and `ALG-RS512` in algorithm restrictions (R6), and report that grouped measure separately.
- Error rows are listed separately and excluded from every rate.
- **Gate:** `CTRL-01` must return 200 in both modes before anything else is run for that target.

## 6. What each target documents

`CONFIG_NOTES.md` in every target directory, containing:

- the doc URL followed for the default, the tested version, and the date the link was checked;
- every line added to the quick-start to make `CTRL-01` pass;
- this table, one row per setting that differs or that the default needs:

  | Setting | In default? | In hardened? | Changes behavior vs default? | Why |
  |---|---|---|---|---|

- predictions written **before** the matrix was run, then the measured result next to each prediction;
- surprises and any docs-versus-measured mismatch.

Dockerfiles pin the base image (tag and digest) and install from a lock file.

## 7. Running the foundation

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r generator/requirements.txt
python generator/make_keys.py                                  # keys/*.pem, git-ignored; --force replaces them
python generator/generate.py && python generator/verify_tokens.py
```

`verify_tokens.py` fails with a message naming the token and the property if any token differs from `CTRL-01` in more or fewer properties than its row promises, or if `CTRL-01` does not verify against `keys/public.pem`.

### Running a target

Same pattern for every target (the example is PyJWT on host port 8001; jsonwebtoken is 8003). Regenerate the tokens first.

```
docker build -t pyjwt targets/python-pyjwt
docker run -d --rm --name pyjwt -p 8001:8080 -e CONFIG_MODE=default \
  -v "$PWD/keys/public.pem:/keys/public.pem:ro" -v "$PWD/policy.json:/policy/policy.json:ro" pyjwt
python generator/check_target.py http://localhost:8001
docker stop pyjwt
```
