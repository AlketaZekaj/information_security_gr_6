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

## Saved native pilot: 25 October 2026

Source: [expanded-matrix run.json](results/pilot/target-validation/expanded-matrix/run.json). This run covers both .NET targets and jose, with 15 cases in each of two modes. It ran on Windows 10.0.26200, x64, using Python 3.11.0. Docker was unavailable.

| Target | Build/runtime recorded in the pilot |
|---|---|
| JwtBearer | SDK 8.0.403; .NET and ASP.NET Core runtime 8.0.10 |
| JsonWebTokenHandler | SDK 10.0.402; .NET and ASP.NET Core runtime 10.0.13 |
| jose | Node v24.11.1 |

The two .NET targets use different framework and IdentityModel versions. Their comparison cannot isolate middleware versus manual validation as the only variable.

### Resolved .NET packages in that pilot

#### dotnet-jwtbearer

| Package | Version |
|---|---|
| Microsoft.AspNetCore.Authentication.JwtBearer | 8.0.8 |
| Microsoft.IdentityModel.Abstractions | 7.1.2 |
| Microsoft.IdentityModel.JsonWebTokens | 7.1.2 |
| Microsoft.IdentityModel.Logging | 7.1.2 |
| Microsoft.IdentityModel.Protocols | 7.1.2 |
| Microsoft.IdentityModel.Protocols.OpenIdConnect | 7.1.2 |
| Microsoft.IdentityModel.Tokens | 7.1.2 |

#### dotnet-jsonwebtokenhandler

| Package | Version |
|---|---|
| Microsoft.Bcl.Cryptography | 10.0.2 |
| Microsoft.IdentityModel.Abstractions | 8.19.1 |
| Microsoft.IdentityModel.JsonWebTokens | 8.19.1 |
| Microsoft.IdentityModel.Logging | 8.19.1 |
| Microsoft.IdentityModel.Tokens | 8.19.1 |

## Docker images declared in the repository

These are configured image references, not proof of a successful container run. Container and clean-machine validation remain pending in the saved pilot notes.

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

## Local environment inspected on 27 October 2026

`dotnet --list-sdks` reports 7.0.101, 8.0.403 and 10.0.403. Relevant installed .NET/ASP.NET Core runtimes are 8.0.10 and 10.0.14. `node --version` reports v24.11.1; the repository virtual environment reports Python 3.11.0. The current machine therefore differs from the saved .NET 10 pilot. No root `global.json` pins SDK selection.

The current `dotnet --info` command printed SDK 10.0.403 and host 10.0.14 but also reported access denied while inspecting Windows services. The successful SDK/runtime listing commands above were used for today's inventory. Complete successful `dotnet --info` output from each pilot toolchain is preserved below.

### Pilot dotnet --info: dotnet-jwtbearer

```text
.NET SDK:
 Version:           8.0.403
 Commit:            c64aa40a71
 Workload version:  8.0.400-manifests.18f19b92
 MSBuild version:   17.11.9+a69bbaaf5

Runtime Environment:
 OS Name:     Windows
 OS Version:  10.0.26200
 OS Platform: Windows
 RID:         win-x64
 Base Path:   C:\Program Files\dotnet\sdk\8.0.403\

.NET workloads installed:
Configured to use loose manifests when installing new manifests.
There are no installed workloads to display.

Host:
  Version:      8.0.10
  Architecture: x64
  Commit:       81cabf2857

.NET SDKs installed:
  7.0.101 [C:\Program Files\dotnet\sdk]
  8.0.403 [C:\Program Files\dotnet\sdk]

.NET runtimes installed:
  Microsoft.AspNetCore.App 6.0.12 [C:\Program Files\dotnet\shared\Microsoft.AspNetCore.App]
  Microsoft.AspNetCore.App 7.0.1 [C:\Program Files\dotnet\shared\Microsoft.AspNetCore.App]
  Microsoft.AspNetCore.App 8.0.10 [C:\Program Files\dotnet\shared\Microsoft.AspNetCore.App]
  Microsoft.NETCore.App 6.0.12 [C:\Program Files\dotnet\shared\Microsoft.NETCore.App]
  Microsoft.NETCore.App 7.0.0 [C:\Program Files\dotnet\shared\Microsoft.NETCore.App]
  Microsoft.NETCore.App 7.0.1 [C:\Program Files\dotnet\shared\Microsoft.NETCore.App]
  Microsoft.NETCore.App 8.0.10 [C:\Program Files\dotnet\shared\Microsoft.NETCore.App]
  Microsoft.WindowsDesktop.App 6.0.12 [C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App]
  Microsoft.WindowsDesktop.App 7.0.0 [C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App]
  Microsoft.WindowsDesktop.App 7.0.1 [C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App]
  Microsoft.WindowsDesktop.App 8.0.10 [C:\Program Files\dotnet\shared\Microsoft.WindowsDesktop.App]

Other architectures found:
  x86   [C:\Program Files (x86)\dotnet]
    registered at [HKLM\SOFTWARE\dotnet\Setup\InstalledVersions\x86\InstallLocation]

Environment variables:
  Not set

global.json file:
  Not found

Learn more:
  https://aka.ms/dotnet/info

Download .NET:
  https://aka.ms/dotnet/download
```

### Pilot dotnet --info: dotnet-jsonwebtokenhandler

```text
.NET SDK:
 Version:           10.0.402
 Commit:            a8dd0577c5
 Workload version:  10.0.400-manifests.da132f47
 MSBuild version:   18.9.15+a8dd0577c

Runtime Environment:
 OS Name:     Windows
 OS Version:  10.0.26200
 OS Platform: Windows
 RID:         win-x64
 Base Path:   <repository>\.tools\dotnet\sdk\10.0.402\

.NET workloads installed:
There are no installed workloads to display.
Configured to use workload sets when installing new manifests.
No workload sets are installed. Run "dotnet workload restore" to install a workload set.

Host:
  Version:      10.0.13
  Architecture: x64
  Commit:       4099f83977

.NET SDKs installed:
  10.0.402 [<repository>\.tools\dotnet\sdk]

.NET runtimes installed:
  Microsoft.AspNetCore.App 10.0.13 [<repository>\.tools\dotnet\shared\Microsoft.AspNetCore.App]
  Microsoft.NETCore.App 10.0.13 [<repository>\.tools\dotnet\shared\Microsoft.NETCore.App]
  Microsoft.WindowsDesktop.App 10.0.13 [<repository>\.tools\dotnet\shared\Microsoft.WindowsDesktop.App]

Other architectures found:
  x86   [C:\Program Files (x86)\dotnet]
    registered at [HKLM\SOFTWARE\dotnet\Setup\InstalledVersions\x86\InstallLocation]

Environment variables:
  Not set

global.json file:
  Not found

Learn more:
  https://aka.ms/dotnet/info

Download .NET:
  https://aka.ms/dotnet/download
```

## Capture for the final run

Keep the final run metadata with its commit, OS, interpreter versions and resolved packages. Record `docker version`, `docker compose version`, image IDs/digests and SDK/runtime versions from the built containers. Regenerate the full matrix after an environment or dependency change; the existing pilot is not evidence for untested container versions.
