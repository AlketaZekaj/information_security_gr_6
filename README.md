# information_security_gr_6

JWT Security by Default: a comparative evaluation of claim and algorithm validation
in JWT libraries and framework middleware (default vs RFC 8725 hardened configuration).

- [CONTRACT.md](CONTRACT.md): shared policy, API contract, 15-case matrix and CSV rules.
- [testmatrix.json](testmatrix.json): shared cases for every target; 2 expected acceptances
  and 13 expected rejections, including EXP-SKEW-120 and ALG-RS512.
- [Target validation report](results/pilot/target-validation/REPORT.md): current measurements,
  interpretation, raw evidence and rerun commands (25 October 2026).
- `targets/*/CONFIG_NOTES.md`: per-component settings, predictions and measurement scope.

Current measured scope: JwtBearer, JsonWebTokenHandler and jose each completed
all 15 cases in default and hardened modes on native Windows (90 matrix requests).
Both .NET defaults accepted 2/13 invalid tokens; jose default accepted 5/13.
All hardened modes matched all 15 expectations, with no false rejects or errors.

The two new cases are main tests, not separate probes. Base iat/nbf are two hours
ago so both expiry cases change only exp and retain a valid chronological interval.
The independent verifier checks every mutation and the new same-key RS512 signature.

PyJWT/jsonwebtoken's existing notes describe earlier 13-case measurements; their
15-case reruns are pending. express-jwt is absent. Docker/container execution
was not evaluated in the current local pilot. Historical results are clearly
separate from the expanded suite's evidence.
