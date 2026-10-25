# JsonWebTokenHandler configuration notes

## Setup and evidence

Default reference: https://learn.microsoft.com/en-us/dotnet/api/microsoft.identitymodel.jsonwebtokens.jsonwebtokenhandler.validatetokenasync

This target adapts the documented validation API to locally generated keys.
Default supplies exactly IssuerSigningKey, ValidIssuer and ValidAudience in
TokenValidationParameters. No Validate* flag, algorithm list or clock skew is
explicitly set in that branch. Those three supplied values are baseline setup.

Tested 2026-10-25: **IdentityModel.JsonWebTokens/Tokens 8.19.1; SDK 10.0.402; runtime 10.0.13**, native Windows. Both modes accepted CTRL-01.
See [full report](../../results/pilot/target-validation/REPORT.md),
[raw follow-up results](../../results/pilot/target-validation/followup/raw.csv), and
[pre-run predictions](../../results/pilot/target-validation/PREDICTIONS.md).
Container execution is untested because Docker Desktop failed to start.

The effective defaults were checked against the
[versioned source](https://github.com/AzureAD/azure-activedirectory-identitymodel-extensions-for-dotnet/blob/8.19.1/src/Microsoft.IdentityModel.Tokens/TokenValidationParameters.cs)
on 2026-10-25 and compared with HTTP measurements.

## Configuration changes

| Setting | In default? | In hardened? | Changes behavior vs default? | Why |
|---|---|---|---|---|
| IssuerSigningKey | explicit RSA key | same | no delta | Baseline verification key. |
| ValidIssuer | explicit policy value | same | no delta | Baseline expected issuer. |
| ValidAudience | explicit policy value | same | no delta | Baseline expected audience. |
| ValidateIssuer | implicit true | explicit true | no | Restates default; wrong/missing issuer rejected in both. |
| ValidateAudience | implicit true | explicit true | no | Restates default; wrong/missing audience rejected in both. |
| ValidateLifetime | implicit true | explicit true | no | Restates default; chronological expired probe rejects in both. |
| ValidateIssuerSigningKey | implicit false | explicit true | value changes; no acceptance delta observed | Additional key validation, separate from verifying the JWT signature. |
| RequireSignedTokens | implicit true | explicit true | no | Restates default. |
| RequireExpirationTime | implicit true | explicit true | no | Restates default; EXP-MISSING rejected in both. |
| ValidAlgorithms | unset | [RS256] | yes, demonstrated by RS512 probe | Default accepts same-key RS512; hardened rejects. |
| ClockSkew | implicit 300 seconds | explicit zero | yes, demonstrated by 120-second expiry probe | Removes clock tolerance. |

Eight assignments in the hardened branch: five restate defaults; three change
effective parameter values. Of those three, two change acceptance in the
diagnostic probes. No assignment changes acceptance in the original 13-case
matrix. The effect of ValidateIssuerSigningKey on other key types was not tested.
Signature verification occurs in both modes: SIG-TAMPERED returns 401.
nbf remains optional; NBF-MISSING returns 200.

## Predicted versus measured

| Test | Predicted default | Measured default | Predicted hardened | Measured hardened |
|---|---|---|---|---|
| CTRL-01 | accept | accept (200) | accept | accept (200) |
| ISS-INVALID | reject | reject (401) | reject | reject (401) |
| ISS-MISSING | reject | reject (401) | reject | reject (401) |
| AUD-INVALID | reject | reject (401) | reject | reject (401) |
| AUD-MISSING | reject | reject (401) | reject | reject (401) |
| EXP-EXPIRED | reject | reject (401) | reject | reject (401) |
| EXP-MISSING | reject | reject (401) | reject | reject (401) |
| NBF-FUTURE | reject | reject (401) | reject | reject (401) |
| NBF-MISSING | accept | accept (200) | accept | accept (200) |
| ALG-NONE | reject | reject (401) | reject | reject (401) |
| ALG-UNEXPECTED | reject | reject (401) | reject | reject (401) |
| ALG-CONFUSION | reject | reject (401) | reject | reject (401) |
| SIG-TAMPERED | reject | reject (401) | reject | reject (401) |

All acceptance predictions matched. Both modes have 0/11 false accepts, 0/2
false rejects, and zero errors in the main matrix. This describes the selected
cases, not complete enforcement of the stricter policy by default.

## Diagnostic findings

- EXP-SKEW-120: 200 default, 401 hardened. Clock tolerance affects acceptance.
- ALG-RS512: 200 default, 401 hardened. ES256 rejection alone does not establish
  RS256-only enforcement; the same RSA key can verify RS512 in default mode.
- EXP-EXPIRED returns an invalid-lifetime diagnostic because nbf is later than
  exp. The separate, chronologically valid EXP-PAST-3600 probe returns 401 with
  an expired-token diagnostic in both modes. Keep this test-design limitation
  visible when reporting expiry coverage.

See [probe rows](../../results/pilot/target-validation/followup/probes.csv) and
[complete headers](../../results/pilot/target-validation/followup/diagnostics.json).

## Response and interpretation limits

The wrapper returns 401 with an empty body and an X-Reject-Reason exception type. The library supplies a validation result, not an HTTP response. There is no WWW-Authenticate header in this wrapper. Algorithm restrictions may surface as a
signature-key-not-found error; a rejection reason is not a one-to-one mapping to
the validation rule. The two .NET targets use different IdentityModel/runtime
versions, so identical outcomes do not isolate the middleware-versus-library
factor. No observed acceptance behavior contradicted the checked defaults.

For local runs, KEYS_PUB and POLICY select files. When unset, the paths remain
/keys/public.pem and /policy/policy.json. See the report for rerun commands and
the Docker limitation. Startup logs record CONFIG_MODE.
