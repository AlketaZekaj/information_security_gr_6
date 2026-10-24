# JsonWebTokenHandler configuration notes

The validation parameters intentionally match the JwtBearer target. The manual endpoint calls `ValidateTokenAsync` and checks `TokenValidationResult.IsValid`, as documented at:

https://learn.microsoft.com/en-us/dotnet/api/microsoft.identitymodel.jsonwebtokens.jsonwebtokenhandler.validatetokenasync

| Setting | In default? | In hardened? | Changes behavior vs default? | Why |
|---|---:|---:|---:|---|
| `IssuerSigningKey` | yes | yes | yes | Supplies the RSA verification key. |
| `ValidIssuer` | yes | yes | yes | Supplies the expected issuer. |
| `ValidAudience` | yes | yes | yes | Supplies the expected audience. |
| `ValidateIssuer` | no | true | To measure | Explicit hardened policy. |
| `ValidateAudience` | no | true | To measure | Explicit hardened policy. |
| `ValidateLifetime` | no | true | To measure | Explicit hardened policy. |
| `ValidateIssuerSigningKey` | no | true | To measure | Explicit hardened policy. |
| `RequireSignedTokens` | no | true | To measure | Explicit signed-token requirement. |
| `RequireExpirationTime` | no | true | To measure | Explicit `exp` requirement. |
| `ValidAlgorithms = [RS256]` | no | yes | yes | Explicit algorithm allow-list. |
| `ClockSkew = TimeSpan.Zero` | no | yes | yes | Removes clock tolerance. |

Unlike JwtBearer, the 401 body and `X-Reject-Reason` header are produced by wrapper code. The library returns validation failures in `TokenValidationResult.Exception`; this makes the response-body comparison non-equivalent and is a limitation of the error-consistency metric.

`nbf` remains optional and is validated when present. Pilot results, package versions, and docs-versus-measured differences are added after the matrix run.
