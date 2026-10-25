# .NET pilot observations — expanded matrix, 25 October 2026

Full evidence: [target validation report](target-validation/REPORT.md).

- Both .NET targets now match 13/15 expectations in default mode and 15/15 in
  hardened mode. Default accepts 2 of the 13 invalid tokens; hardened accepts 0.
- EXP-SKEW-120 and ALG-RS512 are part of the shared main matrix for every target.
  The former tests zero skew, the latter RS256-only policy with the same RSA key.
- All control and NBF-MISSING cases passed. All rejections were 401; no errors occurred.
- Base iat/nbf are now two hours ago. EXP-EXPIRED changes only exp and now produces
  expiration diagnostics in both modes, fixing the old invalid-lifetime confound.
- Eight explicit hardened assignments include five restated defaults. Of the three
  changed values, ClockSkew and ValidAlgorithms show acceptance changes directly
  in the main matrix. No acceptance effect was demonstrated for additional RSA
  signing-key validation; cryptographic signature checks already operate by default.
- JwtBearer 8.0.8 uses IdentityModel 7.1.2, while the manual handler uses 8.19.1.
  This is not a controlled same-version middleware-versus-library comparison.
- Native Windows execution was used. Container/clean-machine validation remains pending.
- Old 13-case results are historical and must not be combined with the new 15-case data.
