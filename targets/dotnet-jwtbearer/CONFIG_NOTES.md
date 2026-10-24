# JwtBearer configuration notes

Default mode follows the minimum explicit setup from the official ASP.NET Core JWT bearer guidance:

https://learn.microsoft.com/en-us/aspnet/core/security/authentication/configure-jwt-bearer-authentication

The key and policy files supply the RSA verification key, issuer, and audience. Supplying `ValidIssuer` and `ValidAudience` is data configuration; the effective validation behavior must be confirmed by the pilot measurements because `TokenValidationParameters` also has framework defaults.

| Setting | In default? | In hardened? | Changes behavior vs default? | Why |
|---|---:|---:|---:|---|
| `IssuerSigningKey` | yes | yes | yes | Supplies the key used to verify the signature. |
| `ValidIssuer` | yes | yes | yes | Supplies the expected issuer value. |
| `ValidAudience` | yes | yes | yes | Supplies the expected audience value. |
| `ValidateIssuer` | no | true | To measure | Explicitly exposes issuer validation in hardened mode. |
| `ValidateAudience` | no | true | To measure | Explicitly exposes audience validation in hardened mode. |
| `ValidateLifetime` | no | true | To measure | Explicitly exposes lifetime validation in hardened mode. |
| `ValidateIssuerSigningKey` | no | true | To measure | Explicitly exposes signing-key validation in hardened mode. |
| `RequireSignedTokens` | no | true | To measure | Explicitly requires a signed token. |
| `RequireExpirationTime` | no | true | To measure | Explicitly requires `exp`. |
| `ValidAlgorithms = [RS256]` | no | yes | yes | Restricts the accepted signing algorithm. |
| `ClockSkew = TimeSpan.Zero` | no | yes | yes | Removes the framework's default clock tolerance. |

`nbf` is validated when present but is not made a required claim. Requiring it would need a custom `OnTokenValidated` check.

The default and hardened behavior, response `WWW-Authenticate` values, package version, and any docs-versus-measured differences are recorded after the pilot matrix is run.
