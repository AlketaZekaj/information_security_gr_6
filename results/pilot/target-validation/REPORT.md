# Target validation results — local pilot, 25 October 2026

## Scope and outcome

Tested the three existing targets: JwtBearer, JsonWebTokenHandler, and jose.
Each received the same 13-case matrix in default and hardened modes: 78 measured
requests per run. All six control gates passed before the matrix started, and
the control was checked again after each process restart. No request returned
an error status or timed out. All recorded acceptance predictions matched.

express-jwt is absent from this checkout and was not evaluated. These are local
pilot results for the three selected targets, not the team-wide main experiment or its final
metrics. The first run is preserved in this folder; the follow-up run is in
`followup/`. Its main matrix gave exactly the same acceptance decisions.

The main result is that jose's default setup accepts five tokens that violate
the shared policy, while its hardened setup rejects them. Both .NET targets
match all 13 main expectations in both modes. Separate probes show that the
.NET defaults still differ from the full zero-skew, RS256-only policy.

## Measured environment

| Target | Direct package | Validation dependency | SDK / runtime |
|---|---|---|---|
| JwtBearer | Microsoft.AspNetCore.Authentication.JwtBearer 8.0.8 | Microsoft.IdentityModel.JsonWebTokens and Tokens 7.1.2 | .NET SDK 8.0.403; ASP.NET/Core runtime 8.0.10 |
| JsonWebTokenHandler | Microsoft.IdentityModel.JsonWebTokens 8.19.1 | Microsoft.IdentityModel.Tokens 8.19.1 | .NET SDK 10.0.402; ASP.NET/Core runtime 10.0.13 |
| jose | jose 6.2.13; Express 5.3.0 | WebCrypto key imported with RS256 | Node v24.11.1 |

Windows build 26200, x64; Python 3.11; generator dependencies cryptography 50.0.2,
cffi 2.1.1, pycparser 3.12. Exact SDK output and resolved Microsoft packages are
in `followup/run.json`. Node package versions were read from the installed
packages and checked against package.json. Existing node_modules were used;
this was not an npm ci or clean-machine installation check.

Docker Desktop failed before starting the engine: it could not remove the stale
internal `userAnalyticsOtlpHttp.sock`. Therefore these measurements used native
Windows processes on loopback, sequentially on port 8080. Dockerfiles, image
tags, mounts, compose, and container execution were not validated. In particular,
the Node runtime differs from the Dockerfile's Node 22.20.0, and .NET Docker tags
8.0 / 10.0 are floating patch versions. Repeat in the intended containers before
using these as main-study results.

The .NET targets use the same validation-parameter logic but different IdentityModel
and runtime versions. Equal decisions here do not establish a controlled,
same-version library-versus-middleware comparison.

## Foundation verification

Generated synthetic RSA-2048 and EC-P256 keys with the shared make_keys.py.
Generated and verified all 13 tokens before the gates and before every
target/mode measurement. The verifier confirmed the control signature, each
single-property mutation, and the special signature rules for algorithm and
tampering cases. Logs and generation timestamps are retained. Private keys and
JWT files remain git-ignored; raw reports contain token hashes, not tokens.

The verifier checks construction, not whether a test isolates the intended
validation step. The expiration finding below demonstrates that distinction.

## Main matrix

| Target | Mode | Policy matches | False accepts / invalid | False rejects / valid | Errors |
|---|---|---:|---:|---:|---:|
| JwtBearer | default | 13/13 | 0/11 (0.00%) | 0/2 | 0 |
| JwtBearer | hardened | 13/13 | 0/11 (0.00%) | 0/2 | 0 |
| JsonWebTokenHandler | default | 13/13 | 0/11 (0.00%) | 0/2 | 0 |
| JsonWebTokenHandler | hardened | 13/13 | 0/11 (0.00%) | 0/2 | 0 |
| jose | default | 8/13 | 5/11 (45.45%) | 0/2 | 0 |
| jose | hardened | 13/13 | 0/11 (0.00%) | 0/2 | 0 |

| Test | JwtBearer default | JwtBearer hardened | Handler default | Handler hardened | jose default | jose hardened |
|---|---|---|---|---|---|---|
| CTRL-01 | accept (200) | accept (200) | accept (200) | accept (200) | accept (200) | accept (200) |
| ISS-INVALID | reject (401) | reject (401) | reject (401) | reject (401) | accept (200) | reject (401) |
| ISS-MISSING | reject (401) | reject (401) | reject (401) | reject (401) | accept (200) | reject (401) |
| AUD-INVALID | reject (401) | reject (401) | reject (401) | reject (401) | accept (200) | reject (401) |
| AUD-MISSING | reject (401) | reject (401) | reject (401) | reject (401) | accept (200) | reject (401) |
| EXP-EXPIRED | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |
| EXP-MISSING | reject (401) | reject (401) | reject (401) | reject (401) | accept (200) | reject (401) |
| NBF-FUTURE | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |
| NBF-MISSING | accept (200) | accept (200) | accept (200) | accept (200) | accept (200) | accept (200) |
| ALG-NONE | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |
| ALG-UNEXPECTED | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |
| ALG-CONFUSION | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |
| SIG-TAMPERED | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) | reject (401) |

False-accept denominator: the 11 expected-reject cases, excluding transport or
server errors. False-reject denominator: CTRL-01 and NBF-MISSING (2 cases).
Both of those acceptance checks passed separately in every target/mode.
The CSV retains unrounded rates; this report rounds only for display.
Policy matches count expected acceptances as well as expected rejections.

### Why jose default accepts five invalid tokens

The default path calls jwtVerify(token, key) without issuer, audience, or required
claims. It accepts ISS-INVALID, ISS-MISSING, AUD-INVALID, AUD-MISSING and EXP-MISSING.
It checks exp and nbf when present and rejects expired/not-yet-valid tokens.
Hardened mode supplies issuer, audience and requiredClaims, so those five cases
change from 200 to 401. This is configuration-dependent behavior under the team's
policy, not evidence of a signature-verification bug.

### Why the .NET main results are identical

Default mode supplies the RSA key, expected issuer, and expected audience.
The resolved IdentityModel defaults already enable issuer/audience/lifetime
checks and require signed tokens and expiration. Hardened mode explicitly
restates those settings and adds stricter algorithm/time policy.
NBF-MISSING is accepted in both modes because nbf is optional.

## Separate diagnostic probes

These are excluded from raw.csv, summary.csv and the main-matrix rates.
The first run contains two probes (12 requests); the follow-up adds the third
(18 requests). See `followup/probes.csv` and `followup/diagnostics.json`.

| Probe | Both .NET targets: default | Both .NET targets: hardened | jose: both modes |
|---|---|---|---|
| EXP-SKEW-120: expired 120 seconds ago; nbf precedes exp | accept (200) | reject (401) | reject (401) |
| ALG-RS512: same claims and RSA key, signed with RSA SHA-512 | accept (200) | reject (401) | reject (401) |
| EXP-PAST-3600: expired 1 hour ago; iat/nbf 2 hours ago | reject (401) | reject (401) | reject (401) |

1. **Clock tolerance matters.** The default .NET five-minute tolerance admits
   the two-minute-expired token. ClockSkew=0 rejects it. jose rejects it in both
   modes, consistent with zero tolerance by default.
2. **ES256 rejection does not prove RS256-only enforcement.** Both .NET defaults
   reject ALG-UNEXPECTED (ES256) but accept the valid same-key RS512 signature.
   ValidAlgorithms=[RS256] changes that decision. jose's imported RS256 CryptoKey
   rejects RS512 with TypeError in default mode; its explicit hardened allow-list
   rejects it earlier with ERR_JOSE_ALG_NOT_ALLOWED.
3. **The original expired case has a confound.** EXP-EXPIRED sets exp=now-3600
   while retaining nbf=now-60, so nbf is later than exp. JsonWebTokenHandler
   returns SecurityTokenInvalidLifetimeException; JwtBearer reports an invalid
   lifetime in WWW-Authenticate. Their rejection is not isolated evidence of
   expiration checking. The follow-up EXP-PAST-3600 uses a valid chronological
   interval and receives SecurityTokenExpiredException / an expired-token
   challenge, confirming expiration enforcement in both .NET modes. jose reports
   ERR_JWT_EXPIRED for both cases.

The expiration probes adjust iat and nbf as well as exp to keep the interval
well formed; that is why they are separate from the one-property main matrix.
Before the main study, the team should agree a base token whose nbf/iat are early
enough that changing only exp to one hour ago still leaves nbf < exp, and update
the generator and independent verifier together. The original matrix was kept
intact in this pilot so its limitation remains visible.

## Configuration effort

| Target | Explicit hardened assignments | Different from effective defaults | Observed acceptance-changing settings |
|---|---:|---|---|
| Each .NET target | 8 | 3: ValidateIssuerSigningKey, ValidAlgorithms, ClockSkew | 2: ValidAlgorithms and ClockSkew, shown by probes; none changes the main 13-case outcomes |
| jose | 5 | issuer, audience, requiredClaims and an explicit algorithms list; clockTolerance=0 restates a default | 3: issuer, audience, requiredClaims; algorithm list changes error reason but no tested acceptance decision with this imported key |

For .NET, five true assignments restate defaults. ValidateIssuerSigningKey
changes false to true, but no acceptance difference was observed with this raw
RSA-key setup. That setting concerns additional validation of the signing key;
it is not the switch for cryptographic signature verification. SIG-TAMPERED is
rejected in both modes. The same key/issuer/audience configuration used in both
modes is baseline setup and is not counted as a hardening change.

For jose, issuer and audience options also imply presence checks for those
claims. requiredClaims additionally makes exp mandatory. These observations
describe this setup; the probes do not exhaust all algorithms or key types.

## Rejection responses

Every rejection in this run returned 401. JwtBearer generated an empty body and
a WWW-Authenticate Bearer challenge, usually including an error description.
JsonWebTokenHandler's wrapper generated an empty body and X-Reject-Reason with
the exception type; it did not supply WWW-Authenticate. jose's wrapper returned
`unauthorized` and X-Reject-Reason with an error code and, where available,
claim/reason details. Comparing bodies therefore compares wrappers/framework
responses as well as validator behavior. The full headers are in diagnostics.json.

An algorithm-policy rejection can appear as a signature-key-not-found error in
the .NET targets. The HTTP message is not a reliable one-to-one description of
which validation rule failed.

## Changes made for the test

- JsonWebTokenHandler now honors KEYS_PUB and POLICY, as JwtBearer and jose
  already do, while keeping the container path defaults.
- Added scripts/test_targets.py to build, gate, start/stop, measure, and
  save evidence for these three targets locally. It stops only its own processes.
- Added .tools/, bin/, and obj/ to .gitignore; installed .NET 10 in .tools and
  the generator dependencies in .venv. No target package versions were changed.
- Updated the three CONFIG_NOTES.md files with versions and measured tables.

Both .NET builds completed with zero warnings and zero errors. The target
validation logic and shared test matrix were unchanged.

## Reproduce on this Windows workspace

Use PowerShell in the repository root. The run requires port 8080 to be free.
The saved run used installed .NET 8 and the local .NET 10 SDK mentioned above.

```powershell
.\.venv\Scripts\python.exe generator/make_keys.py
.\.venv\Scripts\python.exe -u scripts/test_targets.py --output results/pilot/target-validation-rerun
```

The runner regenerates and verifies tokens itself. By default it builds both
.NET targets. --skip-build reuses existing .tools/build outputs. If SDK paths
differ, pass --dotnet8 and --dotnet10 with the appropriate executable paths.
For a fresh setup, create the virtual environment and install
generator/requirements.txt, install the recorded SDKs, and run npm ci in
targets/node-jose. Use a new --output directory to retain previous evidence.

No results depend on the ignored private keys being committed: the generator
can make fresh synthetic keys and inputs for a new run. Exact old signed bytes
are not archived; their hashes and generation times identify the recorded run.

## Evidence files and study limitations

- PREDICTIONS.md: recorded expectations, including the later expiration probe.
- raw.csv / summary.csv / probes.csv / diagnostics.json / run.json: first run.
- followup/: second run with the extra chronological-expiration probe.
- logs/: local-only initial build, foundation, and process logs; ignored by Git.
- followup/logs/: local-only follow-up logs; ignored by Git. Builds were reused.
- run.json files: UTC run times, base commit, source hashes, public-key fingerprint,
  package versions, control gates, and token generation records.

Commit the CSV results, JSON evidence/metadata, Markdown reports, source code,
dependency manifests/lockfiles, and reusable test runner. Process logs, generated
keys/tokens, SDK downloads, virtual environments, node_modules, build output,
editor settings, and local environment files are excluded by .gitignore.
The JSON metadata replaces workstation paths with placeholders. Recorded source
hashes describe the tested contents before the later naming cleanup; the script
path was normalized to its current general name without changing those hashes.

There are two complete pilot runs, not one 156-case independent experiment.
Do not concatenate their rows to inflate the test-case count. Do not interpret
single-request latency values as a performance benchmark.

The task sheet for Zana defines seven requirement groups, while CONTRACT.md's
proposed coverage metric uses eleven invalid cases. This report labels its
counts as case-level policy matches and does not silently choose a coverage
denominator. In addition, counting all three ALG cases as rejected would
incorrectly suggest that the .NET default enforces RS256-only. Resolve the
coverage definition and the expiration input before the main study.

## Documentation and source checks

Checked 25 October 2026. The measured outcomes agree with the relevant defaults
in the versioned IdentityModel source and installed jose package. No tested
documentation-versus-runtime contradiction was found; the expiration-input
problem is a test-design issue.

- [IdentityModel 7.1.2 TokenValidationParameters](https://github.com/AzureAD/azure-activedirectory-identitymodel-extensions-for-dotnet/blob/7.1.2/src/Microsoft.IdentityModel.Tokens/TokenValidationParameters.cs)
- [IdentityModel 8.19.1 TokenValidationParameters](https://github.com/AzureAD/azure-activedirectory-identitymodel-extensions-for-dotnet/blob/8.19.1/src/Microsoft.IdentityModel.Tokens/TokenValidationParameters.cs)
- [Microsoft TokenValidationParameters API](https://learn.microsoft.com/en-us/dotnet/api/microsoft.identitymodel.tokens.tokenvalidationparameters)
- [Official jose README](https://github.com/panva/jose)
- [Official jose claim option declarations](https://github.com/panva/jose/blob/main/src/types.d.ts)

The exact v6.2.13 documentation URL could not be retrieved through the web tool.
Version-specific jose checks used its installed dist/types/types.d.ts and
dist/webapi/lib/jwt_claims_set.js. The current online documentation is supporting
context, not evidence of which version was executed.
