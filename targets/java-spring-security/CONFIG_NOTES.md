# Spring Security configuration notes

| | |
|---|---|
| Component | Spring Security OAuth2 Resource Server 7.1.1 (Spring Boot 4.1.1, Nimbus JOSE + JWT), Java 21 |
| Default documentation | https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html |
| Documentation checked | 26 October 2026 |
| Response author | Spring Security's `BearerTokenAuthenticationEntryPoint` writes the HTTP 401 and its `WWW-Authenticate` header; no wrapper code is involved. |

## Default and hardened settings

The reference supplies a raw public key through the Spring Boot property
`spring.security.oauth2.resourceserver.jwt.public-key-location`, and the minimal filter
chain is `anyRequest().authenticated()` with `oauth2ResourceServer(jwt(withDefaults()))`.
The only line added for the API contract is `requestMatchers("/health").permitAll()`.
No extra setting was needed for `CTRL-01` to pass.

The issuer cannot be configured with the documented `issuer-uri` property in this setup,
because that property also discovers the keys from a running authorization server. The
hardened mode therefore replaces Spring Boot's decoder with a `JwtDecoder` bean built with
`NimbusJwtDecoder.withPublicKey`, as shown in the same reference.

| Setting | In default? | In hardened? | Changes behavior vs default? | Why |
|---|---|---|---|---|
| `public-key-location` property | yes | same | no delta | Quick-start key setting; the hardened decoder reads the same key. |
| `/health` permitted in the filter chain | yes | same | no delta | Contract endpoint, not part of the quick-start. |
| `signatureAlgorithm(RS256)` | implicit RS256 | explicit, read from policy | no | Restates Spring Boot's default; `ALG-RS512` is rejected in both modes. |
| `JwtTimestampValidator(Duration.ZERO)` | implicit 60 seconds | explicit zero, read from policy | value changes; no acceptance delta on this matrix | `EXP-SKEW-120` is already outside the 60-second default; a token expired by less than 60 seconds would differ. |
| `JwtIssuerValidator` | no | yes | yes | Rejects incorrect or missing `iss`. |
| `aud` claim validator | no | yes | yes | Rejects incorrect or missing `aud`. |
| required-claims validators (`iss`, `aud`, `exp`) | no | yes | yes | `JwtTimestampValidator` checks `exp` only when present; this closes `EXP-MISSING`. |

`nbf` remains optional. The target reads the expected values and required-claim names
from `policy.json`; it never receives the private key.

## Predictions written before the matrix run

| Cases | Default prediction | Hardened prediction | Reason |
|---|---|---|---|
| `CTRL-01`, `NBF-MISSING` | accept | accept | Valid under the shared policy. |
| `ISS-*`, `AUD-*` | accept | reject | No issuer or audience validator unless configured. |
| `EXP-MISSING` | accept | reject | `JwtTimestampValidator` checks `exp` only when present. |
| `EXP-EXPIRED`, `EXP-SKEW-120`, `NBF-FUTURE` | reject | reject | All are outside the default 60-second clock skew. |
| `ALG-*` | reject | reject | Spring Boot's decoder accepts only RS256 by default. |
| `SIG-TAMPERED` | reject | reject | Signature verification. |

## Measured results

Ran the shared 15-case matrix with `harness/run.py --components spring-security` against
the container. Both control gates passed and every prediction above matched.

| Mode | Matched expectations | False accepts | False rejects | Errors |
|---|---|---|---|---|
| default | 10/15 | 5/13 (`ISS-INVALID`, `ISS-MISSING`, `AUD-INVALID`, `AUD-MISSING`, `EXP-MISSING`) | 0/2 | 0 |
| hardened | 15/15 | 0/13 | 0/2 | 0 |

Every rejection is a 401 with an empty body and an RFC 6750 header such as
`Bearer error="invalid_token", error_description="... The iss claim is not valid"`, which
names the failed check.
