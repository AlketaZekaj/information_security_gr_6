'use strict';
// Minimal protected API validating JWTs with jsonwebtoken.
//
// Default mode follows the jsonwebtoken README (jwt.verify with a public key):
// https://github.com/auth0/node-jsonwebtoken#jwtverifytoken-secretorpublickey-options-callback
// See CONFIG_NOTES.md for every line that differs between the two modes.
const fs = require('node:fs');
const http = require('node:http');
const jwt = require('jsonwebtoken');
const { version } = require('jsonwebtoken/package.json');

const mode = process.env.CONFIG_MODE ?? 'default';
if (!['default', 'hardened'].includes(mode)) {
  throw new Error("CONFIG_MODE must be 'default' or 'hardened'");
}

const publicKey = fs.readFileSync(process.env.KEYS_PUB ?? '/keys/public.pem');
const policy = JSON.parse(fs.readFileSync(process.env.POLICY ?? '/policy/policy.json', 'utf8'));

function validateDefault(token) {
  return jwt.verify(token, publicKey);
}

function validateHardened(token) {
  const claims = jwt.verify(token, publicKey, {
    algorithms: policy.allowed_algorithms,
    issuer: policy.issuer,
    audience: policy.audience,
    clockTolerance: policy.clock_skew_seconds,
  });
  // jsonwebtoken checks exp only when it is present and has no option to require it,
  // so this manual check is counted as a configuration change.
  for (const name of policy.required_claims) {
    if (claims[name] === undefined) {
      throw new jwt.JsonWebTokenError(`jwt ${name} claim is required`);
    }
  }
  return claims;
}

const validate = mode === 'default' ? validateDefault : validateHardened;

function oneLine(text) {
  // Header values must be printable ASCII on one line.
  return String(text).replace(/[^\x20-\x7e]/g, '?');
}

function respond(res, status, body, { type = 'text/plain', reason } = {}) {
  const headers = { 'Content-Type': type, 'Content-Length': Buffer.byteLength(body) };
  if (reason) headers['X-Reject-Reason'] = oneLine(reason);
  res.writeHead(status, headers);
  res.end(body);
}

const server = http.createServer((req, res) => {
  if (req.method !== 'GET') return respond(res, 405, 'method not allowed');
  if (req.url === '/health') {
    const body = JSON.stringify({ status: 'ok', component: 'jsonwebtoken', version, config: mode });
    return respond(res, 200, body, { type: 'application/json' });
  }
  if (req.url !== '/protected') return respond(res, 404, 'not found');

  const match = /^Bearer\s+(.+)$/i.exec(req.headers.authorization ?? '');
  if (!match) return respond(res, 401, 'unauthorized', { reason: 'MissingBearer' });
  try {
    validate(match[1].trim());
  } catch (error) {
    const reason = `${error.name}: ${error.message}`;
    if (error instanceof jwt.JsonWebTokenError) {
      return respond(res, 401, 'unauthorized', { reason });
    }
    // Not a validation decision: the harness reports it as an error, never as a rejection.
    return respond(res, 500, 'internal error', { reason });
  }
  return respond(res, 200, 'ok');
});

server.listen(8080, '0.0.0.0', () => {
  console.log(`jsonwebtoken ${version} listening on :8080 (CONFIG_MODE=${mode})`);
});
