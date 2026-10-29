# Component selection

Evidence checked on 27 October 2026. This is a rationale for the six components already selected for the study, supported by a dated public-source snapshot; it is not a preregistered popularity ranking.

## Criteria

We use a purposive sample across Python, Node.js and .NET. Each component must validate signed JWTs, support the shared RSA public key and claims policy, expose documented configuration, and fit a small HTTP wrapper with default and hardened modes. Within that scope, adoption evidence, release history and documentation help justify inclusion. Popularity is not evidence of security.

| Component | Type | Why it is included | Documentation / source |
|---|---|---|---|
| PyJWT | Python library | Provides the Python comparison through a direct validation API. | [Project and documentation links](https://github.com/jpadilla/pyjwt) |
| JwtBearer | ASP.NET Core middleware | Represents framework-integrated bearer authentication and its HTTP authentication pipeline. | [Official package](https://www.nuget.org/packages/Microsoft.AspNetCore.Authentication.JwtBearer/8.0.8) |
| JsonWebTokenHandler | .NET library | Provides manual token validation to compare with JwtBearer integration within .NET. | [Official package](https://www.nuget.org/packages/Microsoft.IdentityModel.JsonWebTokens) |
| jsonwebtoken | Node.js library | Provides a direct Node validation API and the underlying validator used by express-jwt. | [API and options](https://github.com/auth0/node-jsonwebtoken) |
| jose | Node.js library | Adds another Node implementation with a documented JWT/JOSE API and support for Web-interoperable runtimes. | [API and supported runtimes](https://github.com/panva/jose) |
| express-jwt | Express middleware | Enables comparison of direct jsonwebtoken calls with middleware integration, required algorithm configuration and error handling. | [Usage and options](https://github.com/auth0/express-jwt) |
| golang-jwt | Go library | Adds an independent implementation in a fifth ecosystem, with a direct validation API and explicit parser options that are not on by default. | [Documentation](https://golang-jwt.github.io/jwt/usage/parse/) |

## Adoption evidence

The following are the values displayed by the source pages retrieved on the date above. GitHub counts are rounded by GitHub; NuGet totals include all versions and automated/transitive downloads. Cached pages may lag the access date. These measures are not directly comparable across registries and do not measure unique users or market share.

| Component | Observed indicator | Source |
|---|---|---|
| PyJWT | Approximately 5,700 GitHub stars | [Repository](https://github.com/jpadilla/pyjwt) |
| JwtBearer | Approximately 1.4 billion total NuGet downloads; 29,013,203 for 8.0.8 on the retrieved page | [NuGet 8.0.8 page](https://www.nuget.org/packages/Microsoft.AspNetCore.Authentication.JwtBearer/8.0.8) |
| JsonWebTokenHandler | Approximately 4.2 billion total NuGet downloads; 17,224,500 for 8.19.1 in the displayed version history | [NuGet package page](https://www.nuget.org/packages/Microsoft.IdentityModel.JsonWebTokens) |
| jsonwebtoken | Approximately 18,200 GitHub stars | [Repository](https://github.com/auth0/node-jsonwebtoken) |
| jose | Approximately 7,800 GitHub stars | [Repository](https://github.com/panva/jose) |
| express-jwt | Approximately 4,500 GitHub stars | [Repository](https://github.com/auth0/express-jwt) |

## Maintenance evidence

Release activity provides context rather than a guarantee of maintenance quality. The versions selected for the experiment are recorded in [VERSIONS.md](VERSIONS.md); a newer upstream release does not change the tested version.

| Component | Release evidence visible in the retrieved source | Source |
|---|---|---|
| PyJWT | Release 2.15.1 shown as latest, dated 28 September (2026 in the current release sequence). | [Releases](https://github.com/jpadilla/pyjwt/releases) |
| JwtBearer | Tested 8.0.8 dated 13 August 2024; the retrieved version history also shows 8.0.31 and 10.0.12 dated 8 September 2026. | [NuGet history](https://www.nuget.org/packages/Microsoft.AspNetCore.Authentication.JwtBearer/8.0.8) |
| JsonWebTokenHandler | Tested 8.19.1 dated 3 June 2026; page shows 8.23.0 dated 18 September 2026. | [NuGet history](https://www.nuget.org/packages/Microsoft.IdentityModel.JsonWebTokens) |
| jsonwebtoken | npm search snapshot identifies 9.0.3 as published about nine months before its crawl; an exact publication date was not verified from the accessible primary-source page. | [npm listing](https://www.npmjs.com/search?q=jsonwebtoken) |
| jose | Release v6.2.13 shown as latest, dated 20 October (2026 in the current release sequence). | [Releases](https://github.com/panva/jose/releases) |
| express-jwt | npm identifies 8.5.1 as latest and displays its age as two years; an exact publication date was not verified from the accessible primary-source page. | [npm version history](https://www.npmjs.com/package/express-jwt?activeTab=versions) |

The relative npm ages are recorded as displayed, not converted into invented calendar dates. In particular, express-jwt is included for its middleware comparison value despite the older release, rather than being described as frequently updated.

## Relationship to the research questions

For RQ1, each target receives the same 15-case matrix under its documented minimum setup. This compares acceptance decisions for missing/invalid claims and disallowed algorithms. For RQ2, the same targets run with explicit shared policy enforcement, and their configuration notes distinguish changed behavior from restated defaults. Selection is based on comparison value, not on whether a component produces an interesting failure.

## Interpretation limits

- This sample covers three ecosystems and six integration surfaces, not six independent cryptographic implementations or the entire JWT ecosystem.
- express-jwt uses jsonwebtoken, so matching results are expected to be possible and remain useful. Its required `algorithms` option belongs to minimum setup, not extra hardening.
- JwtBearer resolves IdentityModel 7.1.2, while the manual handler uses 8.19.1, with different .NET runtimes. A difference cannot be attributed solely to library versus middleware. See [version evidence](VERSIONS.md).
- Wrappers control some HTTP error bodies and headers. Error-response findings must distinguish wrapper behavior from library behavior, as documented in each target's `CONFIG_NOTES.md`.
- Evidence gathered for this document follows the initial pilot. It supports the rationale retrospectively and must not be described as a selection protocol fixed before testing.
