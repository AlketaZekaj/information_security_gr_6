import express from 'express';
import { importSPKI, jwtVerify } from 'jose';
import { readFile } from 'node:fs/promises';

const mode = process.env.CONFIG_MODE ?? 'default';
if (!['default', 'hardened'].includes(mode)) {
  throw new Error("CONFIG_MODE must be 'default' or 'hardened'");
}

const publicKeyPath = process.env.KEYS_PUB ?? '/keys/public.pem';
const policyPath = process.env.POLICY ?? '/policy/policy.json';
const pem = await readFile(publicKeyPath, 'utf8');
const policy = JSON.parse(await readFile(policyPath, 'utf8'));
const key = await importSPKI(pem, 'RS256');

const verifyOptions = mode === 'hardened'
  ? {
      algorithms: ['RS256'],
      issuer: policy.issuer,
      audience: policy.audience,
      requiredClaims: ['iss', 'aud', 'exp'],
      clockTolerance: 0,
    }
  : undefined;

const app = express();
app.get('/health', (_req, res) => res.status(200).send('ok'));
app.get('/protected', async (req, res) => {
  const authorization = req.get('authorization') ?? '';
  if (!authorization.startsWith('Bearer ')) {
    return reject(res, 'MissingBearer');
  }

  try {
    await jwtVerify(authorization.slice('Bearer '.length).trim(), key, verifyOptions);
    return res.status(200).send('ok');
  } catch (error) {
    return reject(res, error?.constructor?.name ?? 'TokenValidationFailed');
  }
});

function reject(res, reason) {
  res.set('X-Reject-Reason', reason);
  return res.status(401).send('unauthorized');
}

console.log(`jose target starting in CONFIG_MODE=${mode}`);
app.listen(8080, '0.0.0.0', () => console.log('jose listening on 8080'));
