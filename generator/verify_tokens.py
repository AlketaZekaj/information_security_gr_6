#!/usr/bin/env python3
"""Check that the generated tokens test exactly what testmatrix.json says they test.

Every token is decoded and compared with CTRL-01 property by property, where a property
is one header field or one payload claim. Each non-control token must differ from the
control in exactly one property, with the value the matrix promises.

The signature is not counted as a property of its own: it is derived from the header,
payload and key. RULES therefore also states how each token's signature must look:

  rs256     claim cases: re-signed with the RSA key, so the signature is valid
  none      ALG-NONE: empty signature part
  es256     ALG-UNEXPECTED: signed with the EC key, verifies with ec_public.pem
  hs256-pem ALG-CONFUSION: HMAC-SHA256 keyed with the bytes of public.pem
  stale     SIG-TAMPERED: the control signature, left unchanged and so no longer valid

so the alg cases legitimately change the header and the signature together.
"""
import base64
import hashlib
import hmac
import json
import re
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

ROOT = Path(__file__).resolve().parent.parent
MISSING = object()
B64URL = re.compile(r"^[A-Za-z0-9_-]*$")
HOUR = 3600


class Rule:
    def __init__(self, prop, value, signature):
        self.prop, self.value, self.signature = prop, value, signature


# Restated here on purpose: the verifier is an independent check of generate.py.
RULES = {
    "ISS-INVALID": Rule("payload.iss", "https://evil.example.test", "rs256"),
    "ISS-MISSING": Rule("payload.iss", MISSING, "rs256"),
    "AUD-INVALID": Rule("payload.aud", "other-api", "rs256"),
    "AUD-MISSING": Rule("payload.aud", MISSING, "rs256"),
    "EXP-EXPIRED": Rule("payload.exp", lambda c: c["payload.iat"] - HOUR, "rs256"),
    "EXP-MISSING": Rule("payload.exp", MISSING, "rs256"),
    "NBF-FUTURE": Rule("payload.nbf", lambda c: c["payload.iat"] + HOUR, "rs256"),
    "NBF-MISSING": Rule("payload.nbf", MISSING, "rs256"),
    "ALG-NONE": Rule("header.alg", "none", "none"),
    "ALG-UNEXPECTED": Rule("header.alg", "ES256", "es256"),
    "ALG-CONFUSION": Rule("header.alg", "HS256", "hs256-pem"),
    "SIG-TAMPERED": Rule("payload.sub", "admin", "stale"),
}


class Token:
    def __init__(self, text):
        parts = text.split(".")
        if len(parts) != 3:
            raise ValueError(f"expected 3 dot-separated parts, got {len(parts)}")
        for part in parts:
            if not B64URL.match(part):
                raise ValueError("part is not unpadded base64url")
        self.signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
        self.header = json.loads(self.decode(parts[0]))
        self.payload = json.loads(self.decode(parts[1]))
        self.signature = self.decode(parts[2])
        self.ends_with_dot = text.endswith(".")

    @staticmethod
    def decode(part):
        return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))

    def properties(self):
        props = {f"header.{k}": v for k, v in self.header.items()}
        props.update({f"payload.{k}": v for k, v in self.payload.items()})
        return props


def rsa_verifies(public_key, token):
    try:
        public_key.verify(token.signature, token.signing_input, padding.PKCS1v15(), hashes.SHA256())
        return True
    except InvalidSignature:
        return False


def es256_verifies(public_key, token):
    if len(token.signature) != 64:
        return False
    r, s = int.from_bytes(token.signature[:32], "big"), int.from_bytes(token.signature[32:], "big")
    try:
        public_key.verify(encode_dss_signature(r, s), token.signing_input, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


def main():
    keys = ROOT / "keys"
    tokens_dir = ROOT / "tokens"
    policy = json.loads((ROOT / "policy.json").read_text())
    matrix = json.loads((ROOT / "testmatrix.json").read_text())
    index = json.loads((tokens_dir / "index.json").read_text())
    public_pem = (keys / "public.pem").read_bytes()
    rsa_public = serialization.load_pem_public_key(public_pem)
    ec_public = serialization.load_pem_public_key((keys / "ec_public.pem").read_bytes())

    failures = []

    def fail(case_id, message):
        failures.append(f"FAIL {case_id}: {message}")

    ids = [entry["id"] for entry in matrix]
    known = {"CTRL-01", *RULES}
    if len(ids) != len(set(ids)) or set(ids) != known:
        fail("matrix", f"testmatrix.json ids do not match the verifier rules: {sorted(set(ids) ^ known)}")
    if [t["id"] for t in index["tokens"]] != ids:
        fail("index", "tokens/index.json does not list the same ids, in the same order, as testmatrix.json")

    tokens = {}
    for entry in matrix:
        path = tokens_dir / f"{entry['id']}.jwt"
        try:
            tokens[entry["id"]] = Token(path.read_text())
        except (OSError, ValueError) as error:
            fail(entry["id"], f"cannot read {path.name}: {error}")

    control = tokens.get("CTRL-01")
    if control is None:
        fail("CTRL-01", "control token missing; cannot compare the others")
    else:
        c = control.properties()
        now = c.get("payload.iat")
        expected_control = {
            "header.alg": "RS256", "header.typ": "JWT",
            "payload.iss": policy["issuer"], "payload.aud": policy["audience"],
            "payload.sub": "test-user", "payload.iat": now,
            "payload.nbf": (now or 0) - 60, "payload.exp": (now or 0) + HOUR,
        }
        if c != expected_control:
            fail("CTRL-01", f"unexpected header/claims: {c} (expected {expected_control})")
        if not isinstance(now, int) or now != index["now"]:
            fail("CTRL-01", f"payload.iat ({now}) does not match index.json now ({index['now']})")
        if not rsa_verifies(rsa_public, control):
            fail("CTRL-01", "signature does not verify against keys/public.pem")

        for case_id, rule in RULES.items():
            token = tokens.get(case_id)
            if token is None:
                continue
            props = token.properties()
            changed = sorted(k for k in c.keys() | props.keys() if c.get(k, MISSING) != props.get(k, MISSING))
            if changed != [rule.prop]:
                fail(case_id, f"expected only {rule.prop} to differ from CTRL-01, but differing properties are {changed}")
                continue
            want = rule.value(c) if callable(rule.value) else rule.value
            got = props.get(rule.prop, MISSING)
            if got != want:
                fail(case_id, f"{rule.prop} is {got!r}, expected {'absent' if want is MISSING else repr(want)}")

            if rule.signature == "rs256" and not rsa_verifies(rsa_public, token):
                fail(case_id, "signature must verify against keys/public.pem")
            elif rule.signature == "none" and not (token.signature == b"" and token.ends_with_dot):
                fail(case_id, "signature part must be empty (token ends with '.')")
            elif rule.signature == "es256" and not es256_verifies(ec_public, token):
                fail(case_id, "signature must verify against keys/ec_public.pem as ES256 (raw r||s)")
            elif rule.signature == "hs256-pem":
                mac = hmac.new(public_pem, token.signing_input, hashlib.sha256).digest()
                if not hmac.compare_digest(mac, token.signature):
                    fail(case_id, "signature must be HMAC-SHA256 keyed with the bytes of keys/public.pem")
            elif rule.signature == "stale":
                if token.signature != control.signature:
                    fail(case_id, "signature must be the unchanged CTRL-01 signature")
                if rsa_verifies(rsa_public, token):
                    fail(case_id, "tampered token still verifies; the edit did not invalidate the signature")

    if failures:
        print("\n".join(failures))
        print(f"\n{len(failures)} check(s) failed")
        return 1
    print(f"OK: CTRL-01 verifies against public.pem; {len(RULES)} other tokens each differ from it in exactly one property")
    for case_id, rule in RULES.items():
        print(f"  {case_id:<15} {rule.prop:<14} signature={rule.signature}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
