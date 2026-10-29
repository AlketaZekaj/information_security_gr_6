import express from 'express';
import { importSPKI, jwtVerify } from 'jose';
import { readFile } from 'node:fs/promises';

// The public key must be PEM in SPKI format (-----BEGIN PUBLIC KEY-----).
// importSPKI throws when given a PKCS#1 key (-----BEGIN RSA PUBLIC KEY-----).
const mode = process.env.CONFIG_MODE ?? 'default';
if (!['default', 'hardened'].includes(mode)) {
  throw new Error("CONFIG_MODE must be 'default' or 'hardened'");
}

const publicKeyPath = process.env.KEYS_PUB ?? '/keys/public.pem';
const policyPath = process.env.POLICY ?? '/policy/policy.json';
const pem = await readFile(publicKeyPath, 'utf8');
const policy = JSON.parse(await readFile(policyPath, 'utf8'));
const key = await importSPKI(pem, 'RS256');

let verifyOptions;
if (mode === 'hardened') {
  verifyOptions = {
    algorithms: policy.allowed_algorithms,
    issuer: policy.issuer,
    audience: policy.audience,
    requiredClaims: policy.required_claims,
    clockTolerance: policy.clock_skew_seconds,
  };
}

const app = express();
app.get('/health', (_req, res) => res.status(200).send('ok'));
app.get('/protected', async (req, res) => {
  const authorization = req.get('authorization') ?? '';
  if (!authorization.startsWith('Bearer ')) {
    return reject(res, 'MissingBearer');
  }

  try {
    const token = authorization.slice('Bearer '.length).trim();
    if (mode === 'hardened') {
      await jwtVerify(token, key, verifyOptions);
    } else {
      await jwtVerify(token, key);
    }
    return res.status(200).send('ok');
  } catch (error) {
    const baseReason = error?.code ?? error?.constructor?.name;
    const reason = baseReason
      ? `${baseReason}${error?.claim ? `:${error.claim}` : ''}${error?.reason ? `:${error.reason}` : ''}`
      : 'TokenValidationFailed';
    return reject(res, reason);
  }
});

function reject(res, reason) {
  res.set('X-Reject-Reason', reason);
  return res.status(401).send('unauthorized');
}

console.log(`jose target starting in CONFIG_MODE=${mode}`);
app.listen(8080, '0.0.0.0', () => console.log('jose listening on 8080'));
