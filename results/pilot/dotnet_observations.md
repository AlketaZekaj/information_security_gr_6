# .NET pilot observations — 25 October 2026

Full evidence and reproduction commands: [target validation report](target-validation/REPORT.md).

- JwtBearer 8.0.8 (IdentityModel 7.1.2) and JsonWebTokenHandler 8.19.1 each
  matched all 13 main cases in default and hardened modes. Both control gates
  passed, and every rejection returned 401. No server/transport errors occurred.
- Default .NET accepted a token expired by 120 seconds and a same-key RS512
  token. Hardened rejected both. Main-matrix perfection does not demonstrate
  zero clock skew or RS256-only enforcement.
- EXP-EXPIRED has nbf later than exp and triggered invalid-lifetime diagnostics.
  A separate chronologically valid token expired by one hour triggered expiry
  rejection in both modes. Coordinate a generator/verifier input correction
  before the main study.
- Hardened adds eight parameter assignments: five restate defaults; three
  change parameter values. Two showed an acceptance effect in the probes.
  ValidateIssuerSigningKey changes value but showed no acceptance effect for
  the raw RSA keys; signature verification already operates in default mode.
- JwtBearer's native 401 carries WWW-Authenticate. The manual handler's wrapper
  supplies an empty 401 and X-Reject-Reason. Preserve both kinds of evidence.
- Versions differ between targets, so this is not a same-version middleware
  comparison. Measurements were native Windows because Docker failed to start.
- The main coverage definition is still inconsistent: CONTRACT.md proposes
  eleven invalid cases, while the task split defines seven requirement groups.
  Resolve that definition and the algorithm-coverage caveat before aggregation.

The main matrix and probes are stored separately. These pilot rows must not be
mixed with the eventual main experiment. express-jwt is still unimplemented.
