# Versions and reproducibility

Recorded on 27 October 2026. Package declarations describe the current repository; saved run metadata describes what was actually tested. These are separate records.

## Component versions

| Component | Direct JWT package | Framework / supporting packages | Source |
|---|---|---|---|
| PyJWT | PyJWT 2.15.1 | cryptography 50.0.2; cffi 2.1.1; pycparser 3.12 | [requirements](targets/python-pyjwt/requirements.txt) |
| JwtBearer | Microsoft.AspNetCore.Authentication.JwtBearer 8.0.8 | net8.0 | [project](targets/dotnet-jwtbearer/dotnet-jwtbearer.csproj) |
| JsonWebTokenHandler | Microsoft.IdentityModel.JsonWebTokens 8.19.1 | net10.0 | [project](targets/dotnet-jsonwebtokenhandler/dotnet-jsonwebtokenhandler.csproj) |
| jose | jose 6.2.13 | Express 5.3.0; Node >=22.12.0 | [lock file](targets/node-jose/package-lock.json) |
| jsonwebtoken | jsonwebtoken 9.0.3 | Node >=22 | [lock file](targets/node-jsonwebtoken/package-lock.json) |
| express-jwt | express-jwt 8.5.1 | Express 5.3.0; Node >=22 | [lock file](targets/node-express-jwt/package-lock.json) |

Node dependencies are installed with `npm ci`; the linked lock files record transitive versions and integrity hashes. The generator pins cryptography 50.0.2, cffi 2.1.1 and pycparser 3.12 in [its requirements](generator/requirements.txt).

## Resolved .NET packages

Read from the built images (`/app/*.deps.json`). The two .NET targets use different framework and IdentityModel versions, so their comparison cannot isolate middleware versus manual validation as the only variable.

### dotnet-jwtbearer

| Package | Version |
|---|---|
| Microsoft.AspNetCore.Authentication.JwtBearer | 8.0.8 |
| Microsoft.IdentityModel.Abstractions | 7.1.2 |
| Microsoft.IdentityModel.JsonWebTokens | 7.1.2 |
| Microsoft.IdentityModel.Logging | 7.1.2 |
| Microsoft.IdentityModel.Protocols | 7.1.2 |
| Microsoft.IdentityModel.Protocols.OpenIdConnect | 7.1.2 |
| Microsoft.IdentityModel.Tokens | 7.1.2 |
| System.IdentityModel.Tokens.Jwt | 7.1.2 |

### dotnet-jsonwebtokenhandler

| Package | Version |
|---|---|
| Microsoft.Bcl.Cryptography | 10.0.2 |
| Microsoft.IdentityModel.Abstractions | 8.19.1 |
| Microsoft.IdentityModel.JsonWebTokens | 8.19.1 |
| Microsoft.IdentityModel.Logging | 8.19.1 |
| Microsoft.IdentityModel.Tokens | 8.19.1 |

## Docker images declared in the repository

The images every target is built from.

| Target | Stage | Image reference |
|---|---|---|
| dotnet-jsonwebtokenhandler | build (SDK 10.0.403) | `mcr.microsoft.com/dotnet/sdk:10.0@sha256:de4fe90a98845d75910b9769662465c84de1a934665c431279d1382b2bddc02b` |
| dotnet-jsonwebtokenhandler | final (runtime 10.0.14) | `mcr.microsoft.com/dotnet/aspnet:10.0@sha256:de0ee358cdd672f7017a003bed21e9ac9ed48a27c922a59b18175b6e82fa7fee` |
| dotnet-jwtbearer | build (SDK 8.0.427) | `mcr.microsoft.com/dotnet/sdk:8.0@sha256:6ba9644da07bb5b560a402acec9ca38711a0762969f1b61da261df5c9f6f85da` |
| dotnet-jwtbearer | final (runtime 8.0.33) | `mcr.microsoft.com/dotnet/aspnet:8.0@sha256:ea721098d6ea2894ff9bd8387821a1659d4765d6c014b8d648bb1da16f016f5a` |
| java-spring-security | build | `maven:3.9-eclipse-temurin-21@sha256:99e61abcff91a9b1333463bd8451fb18495d6eba9250ac66a338b518f8278320` |
| java-spring-security | final | `eclipse-temurin:21-jre@sha256:227118764cccd3c3294617061aaa93a08309c63a395eefa83e6b35032992ea99` |
| node-express-jwt | runtime | `node:22.20.0-slim@sha256:b21fe589dfbe5cc39365d0544b9be3f1f33f55f3c86c87a76ff65a02f8f5848e` |
| node-jose | runtime | `node:22.20.0-slim@sha256:b21fe589dfbe5cc39365d0544b9be3f1f33f55f3c86c87a76ff65a02f8f5848e` |
| node-jsonwebtoken | runtime | `node:22.20.0-slim@sha256:b21fe589dfbe5cc39365d0544b9be3f1f33f55f3c86c87a76ff65a02f8f5848e` |
| python-pyjwt | runtime | `python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26` |

Every base image is pinned by digest, so a rebuild uses exactly the same image. The SDK and runtime versions in parentheses were read from the pinned .NET images (`dotnet --version`, `dotnet --list-runtimes`). OS packages installed by apt are not pinned.

## Capture for the final run

Keep the final run metadata with its commit, OS, interpreter versions and resolved packages. Record `docker version`, `docker compose version`, image IDs/digests and SDK/runtime versions from the built containers. Regenerate the full matrix after an environment or dependency change.
