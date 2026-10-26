'use strict';
const fs = require('node:fs');
const express = require('express');
const { expressjwt } = require('express-jwt');
const { version } = require('express-jwt/package.json');

const mode = process.env.CONFIG_MODE ?? 'default';
if (!['default', 'hardened'].includes(mode)) {
  throw new Error("CONFIG_MODE must be 'default' or 'hardened'");
}

const publicKey = fs.readFileSync(process.env.KEYS_PUB ?? '/keys/public.pem');
const policy = JSON.parse(fs.readFileSync(process.env.POLICY ?? '/policy/policy.json', 'utf8'));

// Default follows the express-jwt README: secret and algorithms are mandatory.
// https://github.com/auth0/express-jwt#usage
const options = { secret: publicKey, algorithms: ['RS256'] };
if (mode === 'hardened') {
  options.algorithms = policy.allowed_algorithms;
  options.issuer = policy.issuer;
  options.audience = policy.audience;
  options.clockTolerance = policy.clock_skew_seconds;
}

const app = express();
app.get('/health', (_req, res) => res.status(200).json({
  status: 'ok', component: 'express-jwt', version, config: mode,
}));

app.get('/protected', expressjwt(options), (req, res, next) => {
  if (mode === 'hardened') {
    const missing = policy.required_claims.find(name => req.auth?.[name] === undefined);
    if (missing) {
      const error = new Error(`jwt ${missing} claim is required`);
      error.name = 'RequiredClaimMissing';
      error.status = 401;
      return next(error);
    }
  }
  return res.status(200).send('ok');
});

// Express-jwt passes UnauthorizedError to Express. Map only validation failures to
// 401; unexpected failures remain 500 and are counted as errors by the harness.
app.use((error, _req, res, _next) => {
  const status = error.name === 'UnauthorizedError' || error.name === 'RequiredClaimMissing' ? 401 : 500;
  const reason = String(`${error.name}: ${error.message}`).replace(/[^\x20-\x7e]/g, '?');
  res.set('X-Reject-Reason', reason);
  return res.status(status).send(status === 401 ? 'unauthorized' : 'internal error');
});

app.listen(8080, '0.0.0.0', () => {
  console.log(`express-jwt ${version} listening on :8080 (CONFIG_MODE=${mode})`);
});
