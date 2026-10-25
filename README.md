# information_security_gr_6

JWT Security by Default: a comparative evaluation of claim and algorithm validation in JWT libraries and framework middleware (default vs RFC 8725 hardened configuration).

- [CONTRACT.md](CONTRACT.md): shared decisions, API contract, test matrix, CSV columns, how to run the generator.
- `targets/*/CONFIG_NOTES.md`: per-component configuration, predictions and measured results.
- [Target validation pilot report](results/pilot/target-validation/REPORT.md): measured JwtBearer, JsonWebTokenHandler and jose results in both modes, raw evidence, diagnostic probes, and reproduction commands (25 October 2026).

Current measured scope: those three targets completed the 13-case matrix in
both modes on native Windows. All hardened results matched the shared policy;
jose default accepted five expected-reject cases. Docker/container execution
and express-jwt were not evaluated. The report explains the .NET clock-skew and
algorithm findings and the expiration-test limitation that must be resolved
before the team-wide main experiment.
