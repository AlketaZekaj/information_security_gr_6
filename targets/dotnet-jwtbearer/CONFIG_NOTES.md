# JwtBearer configuration notes

## Setup and evidence

Default reference: https://learn.microsoft.com/en-us/aspnet/core/security/authentication/configure-jwt-bearer-authentication

This target adapts the documented validation API to locally generated keys.
Default supplies exactly IssuerSigningKey, ValidIssuer and ValidAudience in
TokenValidationParameters. No Validate* flag, algorithm list or clock skew is
explicitly set in that branch. Those three supplied values are baseline setup.

Tested 2026-10-25: **JwtBearer 8.0.8; IdentityModel.JsonWebTokens/Tokens 7.1.2; SDK 8.0.403; runtime 8.0.10**, native Windows. Both modes accepted CTRL-01.
See [full report](../../results/pilot/target-validation/REPORT.md),
[raw 15-case results](../../results/pilot/target-validation/expanded-matrix/raw.csv), and
[pre-run predictions](../../results/pilot/target-validation/expanded-matrix/PREDICTIONS.md).
Container execution is untested because Docker Desktop failed to start.

The effective defaults were checked against the
[versioned source](https://github.com/AzureAD/azure-activedirectory-identitymodel-extensions-for-dotnet/blob/7.1.2/src/Microsoft.IdentityModel.Tokens/TokenValidationParameters.cs)
on 2026-10-25 and compared with HTTP measurements.

## Configuration changes

| Setting | In default? | In hardened? | Changes behavior vs default? | Why |
|---|---|---|---|---|
| IssuerSigningKey | explicit RSA key | same | no delta | Baseline verification key. |
| ValidIssuer | explicit policy value | same | no delta | Baseline expected issuer. |
| ValidAudience | explicit policy value | same | no delta | Baseline expected audience. |
| ValidateIssuer | implicit true | explicit true | no | Restates default; wrong/missing issuer rejected in both. |
| ValidateAudience | implicit true | explicit true | no | Restates default; wrong/missing audience rejected in both. |
| ValidateLifetime | implicit true | explicit true | no | Restates default; chronological expired case rejects in both. |
| ValidateIssuerSigningKey | implicit false | explicit true | value changes; no acceptance delta observed | Additional key validation, separate from verifying the JWT signature. |
| RequireSignedTokens | implicit true | explicit true | no | Restates default. |
| RequireExpirationTime | implicit true | explicit true | no | Restates default; EXP-MISSING rejected in both. |
| ValidAlgorithms | unset | [RS256] | yes, demonstrated by ALG-RS512 | Default accepts same-key RS512; hardened rejects. |
| ClockSkew | implicit 300 seconds | explicit zero | yes, demonstrated by EXP-SKEW-120 | Removes clock tolerance. |

Eight assignments in the hardened branch: five restate defaults; three change
effective parameter values. Two change acceptance in the expanded main matrix:
ValidAlgorithms and ClockSkew. ValidateIssuerSigningKey changes value but showed
no acceptance effect with the raw RSA keys. Signature verification operates in
both modes. nbf remains optional; NBF-MISSING returns 200.

## Predicted versus measured

| Test | Predicted default | Measured default | Predicted hardened | Measured hardened |
|---|---|---|---|---|
| CTRL-01 | accept | accept (200) | accept | accept (200) |
| ISS-INVALID | reject | reject (401) | reject | reject (401) |
| ISS-MISSING | reject | reject (401) | reject | reject (401) |
| AUD-INVALID | reject | reject (401) | reject | reject (401) |
| AUD-MISSING | reject | reject (401) | reject | reject (401) |
| EXP-EXPIRED | reject | reject (401) | reject | reject (401) |
| EXP-SKEW-120 | accept | accept (200) | reject | reject (401) |
| EXP-MISSING | reject | reject (401) | reject | reject (401) |
| NBF-FUTURE | reject | reject (401) | reject | reject (401) |
| NBF-MISSING | accept | accept (200) | accept | accept (200) |
| ALG-NONE | reject | reject (401) | reject | reject (401) |
| ALG-UNEXPECTED | reject | reject (401) | reject | reject (401) |
| ALG-RS512 | accept | accept (200) | reject | reject (401) |
| ALG-CONFUSION | reject | reject (401) | reject | reject (401) |
| SIG-TAMPERED | reject | reject (401) | reject | reject (401) |

All acceptance predictions matched. On the current 15-case matrix, default has
2/13 false accepts (15.38%), 0/2 false rejects, and zero errors. Hardened has
0/13 false accepts, 0/2 false rejects, and zero errors. These predictions were
informed by the earlier pilot and its probes, not an independent first run.

## Main-matrix findings

- EXP-SKEW-120: 200 default, 401 hardened. Clock tolerance affects acceptance.
- ALG-RS512: 200 default, 401 hardened. The same RSA key verifies RS512 by default;
  the hardened RS256-only list rejects it.
- EXP-EXPIRED: 401 with an expiration diagnostic in both modes. The revised base
  iat/nbf are two hours ago, removing the earlier invalid-interval confound.
- Both new cases now count in raw.csv and summary.csv. They are not separate probes.

See [matrix rows](../../results/pilot/target-validation/expanded-matrix/raw.csv) and
[complete headers](../../results/pilot/target-validation/expanded-matrix/diagnostics.json).

## Response and interpretation limits

JwtBearer generates the 401 response: empty body and WWW-Authenticate. The harness must preserve that header. Algorithm restrictions may surface as a
signature-key-not-found error; a rejection reason is not a one-to-one mapping to
the validation rule. The two .NET targets use different IdentityModel/runtime
versions, so identical outcomes do not isolate the middleware-versus-library
factor. No observed acceptance behavior contradicted the checked defaults.

For local runs, KEYS_PUB and POLICY select files. When unset, the paths remain
/keys/public.pem and /policy/policy.json. See the report for rerun commands and
the Docker limitation. Startup logs record CONFIG_MODE.
