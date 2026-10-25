# Target validation results — expanded 15-case matrix

Date: 25 October 2026. The shared matrix now includes **EXP-SKEW-120** and
**ALG-RS512** as regular cases for every target. Both expect rejection under the
common policy. They are counted in raw.csv, summary.csv and the main rates;
there is no separate probe pass in the current runner.

## Measured outcome

Ran 15 cases against three implemented targets in two modes: **90 matrix
requests**. All six control gates passed before the matrix, and the control was
checked again after each measurement restart. No server/transport errors or
prediction mismatches occurred. Each group contains 13 expected-reject tokens
and two expected-accept tokens (CTRL-01 and NBF-MISSING).

| Target | Mode | Policy matches | Invalid tokens accepted | False-accept rate | Valid tokens rejected | Errors |
|---|---|---:|---:|---:|---:|---:|
| JwtBearer | default | 13/15 | 2/13 | 15.38% | 0/2 | 0 |
| JwtBearer | hardened | 15/15 | 0/13 | 0.00% | 0/2 | 0 |
| JsonWebTokenHandler | default | 13/15 | 2/13 | 15.38% | 0/2 | 0 |
| JsonWebTokenHandler | hardened | 15/15 | 0/13 | 0.00% | 0/2 | 0 |
| jose | default | 10/15 | 5/13 | 38.46% | 0/2 | 0 |
| jose | hardened | 15/15 | 0/13 | 0.00% | 0/2 | 0 |

Both .NET defaults now visibly miss two policy requirements in the main results:
they accept the two-minute-expired token and the same-key RS512 token. Their
hardened modes reject both. jose default still accepts the same five invalid
claim cases: wrong/missing issuer, wrong/missing audience, and missing expiration.
All three hardened configurations match all 15 expectations.

jose's false-accept rate is now 5/13 (38.46%), compared with 5/11 in the old matrix.
That lower percentage comes from adding two rejected cases to the denominator;
the target's validation behavior was not changed.

## Per-case results

| Test | JwtBearer default | JwtBearer hardened | Handler default | Handler hardened | jose default | jose hardened |
|---|---|---|---|---|---|---|
| CTRL-01 | accept (200) | accept (200) | accept (200) | accept (200) | accept (200) | accept (200) |
| ISS-INVALID | reject (401) | reject (401) | reject (401) | reject (401) | accept (200) | reject (401) |
| ISS-MISSING | reject (401) | reject (401) | reject (401) | reject (401) | accept (200) | reject (401) |
| AUD-INVALID | reject (401) | reject (401) | reject (401) | reject (401) | accept (200) | reject (401) |
| AUD-MISSING | reject (401) | reject (401) | reject (401) | reject (401) | accept (200) | reject (401) |
| EXP-EXPIRED | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |
| EXP-SKEW-120 | accept (200) | reject (401) | accept (200) | reject (401) | reject (401) | reject (401) |
| EXP-MISSING | reject (401) | reject (401) | reject (401) | reject (401) | accept (200) | reject (401) |
| NBF-FUTURE | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |
| NBF-MISSING | accept (200) | accept (200) | accept (200) | accept (200) | accept (200) | accept (200) |
| ALG-NONE | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |
| ALG-UNEXPECTED | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |
| ALG-RS512 | accept (200) | reject (401) | accept (200) | reject (401) | reject (401) | reject (401) |
| ALG-CONFUSION | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |
| SIG-TAMPERED | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |

## What changed in the test inputs

- **EXP-SKEW-120:** only exp changes to generation time minus 120 seconds.
  .NET default accepts it within its five-minute tolerance; hardened zero skew
  rejects it. jose rejects it in both modes.
- **ALG-RS512:** only the alg header changes to RS512, with the signature
  recomputed using SHA-512 and the same RSA key. This tests an algorithm
  allow-list without an RSA-versus-EC key mismatch. .NET default accepts it;
  hardened rejects it. jose's imported RS256 CryptoKey rejects it by default,
  and its hardened allow-list rejects it explicitly.
- **Chronological expiry correction:** the control's iat and nbf are both
  generation time minus 7200 seconds. exp remains generation time plus 3600.
  Both expired variants now change only exp while retaining iat <= nbf < exp.
  The one-hour-expired case now produces an actual expiration diagnostic in
  both .NET modes, rather than the old invalid-lifetime-interval diagnostic.

The generator and independent verifier both support the new cases. The verifier
checks SHA-512 against the same public key and checks chronological ordering
for both expired cases. A negative check confirmed that a SHA-256 signature
mislabelled RS512 is rejected by the verifier.

The generation timestamp is stored separately in tokens/index.json; it is no
longer equal to iat. Generator/check_target.py automatically sends all cases
listed in that index, so the expanded suite is available to every target.

## Configuration interpretation

The target validation code was not changed for this extension.

- Each .NET hardened branch has eight assignments. Five restate defaults;
  ValidateIssuerSigningKey, ValidAlgorithms, and ClockSkew change parameter
  values. ValidAlgorithms and ClockSkew now show acceptance differences directly
  in the main matrix. No difference attributable to ValidateIssuerSigningKey was
  demonstrated with these raw RSA keys. Signature verification operates in both modes.
- jose has five hardened settings. Issuer, audience and requiredClaims change
  tested acceptance. Its algorithm list changes diagnostic reasons but not tested
  acceptance with the imported RS256 key. Zero clock tolerance restates its default.

All rejections returned 401. JwtBearer supplies WWW-Authenticate and an empty
body. The manual .NET wrapper supplies an empty body and X-Reject-Reason. The
jose wrapper supplies `unauthorized` and X-Reject-Reason. HTTP body/header
comparisons therefore include wrapper and framework choices. Full responses
are retained in expanded-matrix/diagnostics.json.

## Scope and versions

| Target | Package versions | Execution environment |
|---|---|---|
| JwtBearer | JwtBearer 8.0.8; IdentityModel 7.1.2 | .NET SDK 8.0.403, runtime 8.0.10 |
| JsonWebTokenHandler | IdentityModel 8.19.1 | .NET SDK 10.0.402, runtime 10.0.13 |
| jose | jose 6.2.13; Express 5.3.0 | Node v24.11.1 |

Execution was native Windows on loopback, sequentially on port 8080. Previously
built .NET binaries were reused because target code was unchanged. Docker was
unavailable in the preceding setup and was not retried for this extension.
These are local pilot results, not a container or clean-machine validation.
The .NET library/runtime versions differ between targets, so the study does not
isolate middleware versus direct-library behavior at a single shared version.

PyJWT and jsonwebtoken use the same expanded matrix through the shared generator
and check_target.py, but were not rerun in this extension. Their existing
13-case notes are historical; no new measured results are claimed for them.
express-jwt remains unimplemented. Only the three targets in the table above
are included in this report and its metrics.

## Evidence and rerun

- [Expanded predictions](expanded-matrix/PREDICTIONS.md), informed by the preceding pilot.
- [Raw matrix results](expanded-matrix/raw.csv).
- [Summary](expanded-matrix/summary.csv), computed from the raw rows.
- [Full HTTP evidence](expanded-matrix/diagnostics.json).
- [Run metadata](expanded-matrix/run.json): versions, gates, timestamps, source hashes,
  generated-token metadata, and a snapshot of the exact 15-case matrix.
- [Historical 13-case report](REPORT-13-cases.md), with original rows in this
  directory and its followup/ subdirectory. Those older reports describe the
  earlier matrix and timestamp construction; do not pool them with this run.

Run from the repository root in PowerShell, with port 8080 free:

```powershell
.\.venv\Scripts\python.exe generator/make_keys.py
.\.venv\Scripts\python.exe -u scripts/test_targets.py --output results/pilot/target-validation-rerun
```

The runner rebuilds by default, regenerates/verifies tokens before each mode,
and stops only its own processes. --skip-build reuses .tools/build binaries.
Use --dotnet8 and --dotnet10 to override SDK executable paths. Prerequisites are
the generator requirements, the recorded .NET SDKs, and installed pinned jose
dependencies. Use a new output directory to preserve prior evidence.

CSV/JSON evidence, reports, source code, and dependency lockfiles are retained
for Git. Generated logs, private keys, tokens, local SDKs/dependencies, build
output, and editor/environment settings remain ignored. Workstation paths in
JSON are replaced with placeholders. Single-request timings are diagnostic,
not a latency benchmark.

Case-level rejection counts use 13 invalid cases. They are not counts of
independent requirements. If grouped R1-R7 coverage is calculated later,
EXP-SKEW-120 belongs to expiry enforcement (R3) and ALG-RS512 to algorithm
restrictions (R6). Errors must remain separately reported.
