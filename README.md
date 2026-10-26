# JWT Security by Default: A Comparative Evaluation of Claim and Algorithm Validation

## Overview

A comparative evaluation of claim and algorithm validation in JWT libraries and framework
middleware, under their default configuration and under a hardened configuration based on
RFC 8725.

A JWT is only safe to trust if the server checks more than its signature: it must also
check who issued it, who it is for, when it expires and which algorithm signed it. This
project measures which of those checks popular JWT libraries and middleware perform out of
the box, and what has to be configured to make them enforce one common policy.

- **RQ1:** "Under default configuration, which JWT libraries and framework middleware accept
  tokens with invalid or missing registered claims (`iss`, `aud`, `exp`, `nbf`) or unexpected
  signing algorithms (`alg`)?"
- **RQ2:** "How does their validation behavior change when configured according to applicable
  RFC 8725 recommendations, and what configuration changes are required?"

## How it works

1. Every component under test (a *target*) is wrapped in the same minimal API:
   `GET /health` and `GET /protected`, which returns 200 if the bearer token is accepted
   and 401 if it is rejected.
2. Each target runs in two modes, selected with `CONFIG_MODE`:
   - `default`: the official quick-start, with only the minimum needed for the valid
     control token to be accepted.
   - `hardened`: the common policy in [`policy.json`](policy.json): expected issuer and
     audience, RS256 only, `iss`/`aud`/`exp` required, zero clock skew.
3. A generator creates synthetic tokens: one valid control token and variants that each
   change exactly one property.
4. The harness sends every token to every target in both modes and records each response.
5. The metrics script computes the results from those records.

The shared rules (policy, API contract, token rules, CSV columns, counting rules) are in
[`CONTRACT.md`](CONTRACT.md).

## Traceability

| Research question | Test categories | Metrics | Produced by |
|---|---|---|---|
| RQ1 (default behavior) | ISS, AUD, EXP, NBF, ALG, SIG | false-accept rate, false-reject rate, coverage, error response consistency | `harness/run.py` (default) → `harness/metrics.py` |
| RQ2 (hardened behavior and changes needed) | same cases, hardened config | false-accept rate, configuration effort | `harness/run.py` (hardened) → `harness/metrics.py` + `targets/*/CONFIG_NOTES.md` |

## Test matrix

[`testmatrix.json`](testmatrix.json) is authoritative.

| ID | Changes only this | Expected | Requirement |
|---|---|---|---|
| CTRL-01 | nothing, valid token | accept | setup check |
| ISS-INVALID | `iss` = another issuer | reject | R1 issuer validated |
| ISS-MISSING | `iss` removed | reject | R1 |
| AUD-INVALID | `aud` = another audience | reject | R2 audience validated |
| AUD-MISSING | `aud` removed | reject | R2 |
| EXP-EXPIRED | `exp` = 1 hour ago | reject | R3 expiry validated |
| EXP-SKEW-120 | `exp` = 2 minutes ago | reject | R3 |
| EXP-MISSING | `exp` removed | reject | R4 expiry required |
| NBF-FUTURE | `nbf` = 1 hour ahead | reject | R5 nbf validated |
| NBF-MISSING | `nbf` removed | accept | acceptance check (`nbf` is optional) |
| ALG-NONE | `alg: none`, empty signature | reject | R6 algorithm restricted |
| ALG-UNEXPECTED | ES256 with an EC key | reject | R6 |
| ALG-RS512 | RS512 with the same RSA key | reject | R6 |
| ALG-CONFUSION | HS256 keyed with the RSA public key | reject | R6 |
| SIG-TAMPERED | payload edited after signing | reject | R7 signature verified |

## Components

| Component | Ecosystem | Type | Version | Port | Target |
|---|---|---|---|---|---|
| PyJWT | Python | library | 2.15.1 | 8001 | [`targets/python-pyjwt`](targets/python-pyjwt) |
| JwtBearer (`Microsoft.AspNetCore.Authentication.JwtBearer`) | .NET 8 | middleware | 8.0.8 | 8002 | [`targets/dotnet-jwtbearer`](targets/dotnet-jwtbearer) |
| jsonwebtoken | Node.js | library | 9.0.3 | 8003 | [`targets/node-jsonwebtoken`](targets/node-jsonwebtoken) |
| jose | Node.js | library | 6.2.13 | 8004 | [`targets/node-jose`](targets/node-jose) |
| express-jwt | Node.js | middleware | 8.5.1 | 8005 | [`targets/node-express-jwt`](targets/node-express-jwt) |
| JsonWebTokenHandler (`Microsoft.IdentityModel.JsonWebTokens`) | .NET 10 | library | 8.19.1 | 8006 | [`targets/dotnet-jsonwebtokenhandler`](targets/dotnet-jsonwebtokenhandler) |

Each target documents its default and hardened settings, its predictions and its measured
results in its own `CONFIG_NOTES.md`. The same list, with launch details for the harness,
is in [`components.json`](components.json).

## Repository layout

| Path | Contents |
|---|---|
| [`CONTRACT.md`](CONTRACT.md) | Shared decisions, policy, API contract, token rules, CSV columns, counting rules |
| [`policy.json`](policy.json) | The common validation policy every target reads |
| [`testmatrix.json`](testmatrix.json) | The test cases |
| [`components.json`](components.json) | Components under test: name, version, type, port, how to start them |
| [`generator/`](generator) | Synthetic keys (`make_keys.py`), tokens (`generate.py`), a verifier that checks each token changes exactly one property (`verify_tokens.py`), and a manual check of one running target (`check_target.py`) |
| [`targets/`](targets) | One minimal API per component, with a Dockerfile and `CONFIG_NOTES.md` |
| [`harness/`](harness) | `run.py` runs the matrix and writes `raw.csv`; `metrics.py` computes the metrics; `mock_server.py` and `mock_components.json` are fake targets for testing the harness |
| [`scripts/`](scripts) | Local runner used for the initial target validation |
| [`results/`](results) | Measurement results |

`keys/` and `tokens/` are generated at run time and are not committed.

## Getting started

### Prerequisites

- Python 3.11 or newer
- Node.js 22
- .NET SDK 8 and .NET SDK 10
- Docker (optional, for running targets in containers)

### Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r generator/requirements.txt -r targets/python-pyjwt/requirements.txt
(cd targets/node-jose && npm ci)
(cd targets/node-jsonwebtoken && npm ci)
(cd targets/node-express-jwt && npm ci)
python generator/make_keys.py
```

### Run the evaluation

```bash
python harness/run.py          # all components, default and hardened; writes results/raw.csv
python harness/metrics.py      # reads results/raw.csv and writes the summary files beside it
```

The harness starts each target as a local process, one at a time on port 8080, so nothing
else may be listening there. It regenerates the tokens before each component and mode so
the time-based tokens are always fresh.

```bash
python harness/run.py --components PyJWT jose     # only some components
python harness/run.py --pilot                     # pilot subset, written to results/pilot/
python harness/run.py --output /tmp/try           # write somewhere else
python harness/run.py --help
```

### Test the harness without the real targets

```bash
python harness/run.py --components-file harness/mock_components.json --output results/mock
python harness/metrics.py results/mock/raw.csv --components-file harness/mock_components.json
```

One of the mock targets rejects the control token on purpose, so this run ends with exit
code 3 and shows the setup check stopping that target.

### Run a single target in Docker

Generate the keys first; otherwise Docker creates `keys/public.pem` as a directory.

```bash
docker build -t jose targets/node-jose
docker run -d --rm --name jose -p 8004:8080 -e CONFIG_MODE=default \
  -v "$PWD/keys/public.pem:/keys/public.pem:ro" -v "$PWD/policy.json:/policy/policy.json:ro" jose
python generator/generate.py && python generator/check_target.py http://localhost:8004
docker stop jose
```

## Classification and metrics

Each response is classified as **accepted** (200), **rejected** (401 or 403) or an
**error** (anything else, including a timeout). Errors are listed separately and never
counted as rejections, because a crash is not validation.

Before any test token is sent, the control token `CTRL-01` must be accepted. If it is not,
the target is stopped with a message such as
`PyJWT / hardened: control token rejected with 401: setup error`, and none of its data is
used. A target that rejects everything would otherwise look perfectly secure.

| Metric | Definition |
|---|---|
| False-accept rate | Expected-reject tokens that were accepted, over expected-reject tokens without an error |
| False-reject rate | Expected-accept tokens that were rejected; `CTRL-01` and `NBF-MISSING` are reported separately |
| Case-level coverage | Expected-reject cases rejected, over those without an error |
| Requirement coverage | Requirements R1-R7 enforced, over 7; a requirement is enforced only when all of its cases are rejected |
| Configuration effort | Settings that differ between default and hardened in each target's `CONFIG_NOTES.md`, and how many of them change behavior |
| Error response consistency | Status codes, body shape and `WWW-Authenticate` of rejections per component |
| Latency | Median and p95 per component and mode |

All numbers are computed from `raw.csv`. Rates are stored unrounded and rounded only for
display.

| Output file | Contents |
|---|---|
| `raw.csv` | One row per request, with the columns from `CONTRACT.md` |
| `run.json` | Run metadata: commit, Python version, components, setup failures, token generation times |
| `summary.csv` | False-accept and false-reject rates per component, config and category |
| `coverage.csv` | Case-level coverage, and each requirement as enforced, not enforced or undetermined |
| `errors.csv` | Every error row, when there are any |
| `responses.csv` | How each component rejects tokens |
| `latency.csv` | Median and p95 latency |
| `config_effort.csv` | Every setting from the targets' `CONFIG_NOTES.md` and how it was counted |

## Contributors

-  [Zana Ademi](https://github.com/Zanaad)
-  [Alketa Zekaj](https://github.com/AlketaZekaj)
-  [Yllkë Berisha](https://github.com/yllkeberisha)
