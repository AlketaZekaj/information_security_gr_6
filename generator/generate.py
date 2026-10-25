#!/usr/bin/env python3
"""Generate the synthetic JWTs described in testmatrix.json.

Every token is built by hand (base64url + hmac + raw signing primitives), never with a
JWT library: libraries refuse to produce alg=none or HS256-with-a-public-key tokens, and
the library under test must not also be the one that makes its test input.

For each case the base token is deep-copied and exactly one thing is changed. All
timestamps derive from a single `now`, so every claim other than the one under test is
identical to CTRL-01. Run this right before each test run: exp is now + 3600.

Output (tokens/ is not committed):
  tokens/<ID>.jwt, tokens/index.json, tokens/generated_at.txt
"""
import base64
import copy
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

ROOT = Path(__file__).resolve().parent.parent

OTHER_ISSUER = "https://evil.example.test"
OTHER_AUDIENCE = "other-api"
SUBJECT = "test-user"
TAMPERED_SUBJECT = "admin"
HOUR = 3600


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def encode_part(obj) -> str:
    return b64url(json.dumps(obj, separators=(",", ":")).encode("utf-8"))


def load_private(path):
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


class Signers:
    """The four ways a token's signature part is produced."""

    def __init__(self, keys_dir):
        for name in ("private.pem", "public.pem", "ec_private.pem"):
            if not (keys_dir / name).exists():
                sys.exit(f"missing {keys_dir / name}: run `python generator/make_keys.py` first")
        self.rsa_key = load_private(keys_dir / "private.pem")
        self.ec_key = load_private(keys_dir / "ec_private.pem")
        # Secret for ALG-CONFUSION: the exact bytes of the file a server would load as its key.
        self.public_pem_bytes = (keys_dir / "public.pem").read_bytes()

    def rs256(self, signing_input: bytes) -> bytes:
        return self.rsa_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())

    def es256(self, signing_input: bytes) -> bytes:
        # JWS wants raw r || s (32 bytes each), not the DER encoding cryptography returns.
        der = self.ec_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")

    def hs256_public_pem(self, signing_input: bytes) -> bytes:
        return hmac.new(self.public_pem_bytes, signing_input, hashlib.sha256).digest()

    @staticmethod
    def none(_signing_input: bytes) -> bytes:
        return b""


def assemble(header, payload, sign) -> str:
    signing_input = f"{encode_part(header)}.{encode_part(payload)}"
    return f"{signing_input}.{b64url(sign(signing_input.encode('ascii')))}"


def build_cases(policy, now, signers):
    """Return {id: (mutate(header, payload), signer)}. Each mutate changes exactly one thing."""
    base_header = {"alg": "RS256", "typ": "JWT"}
    base_payload = {
        "iss": policy["issuer"],
        "aud": policy["audience"],
        "sub": SUBJECT,
        "iat": now,
        "nbf": now - 60,
        "exp": now + HOUR,
    }
    control_signature = signers.rs256(
        f"{encode_part(base_header)}.{encode_part(base_payload)}".encode("ascii")
    )

    def claim(name, value):
        def mutate(_header, payload):
            payload[name] = value
        return mutate

    def remove(name):
        def mutate(_header, payload):
            del payload[name]
        return mutate

    def alg(name):
        def mutate(header, _payload):
            header["alg"] = name
        return mutate

    cases = {
        "CTRL-01": (lambda h, p: None, signers.rs256),
        "ISS-INVALID": (claim("iss", OTHER_ISSUER), signers.rs256),
        "ISS-MISSING": (remove("iss"), signers.rs256),
        "AUD-INVALID": (claim("aud", OTHER_AUDIENCE), signers.rs256),
        "AUD-MISSING": (remove("aud"), signers.rs256),
        "EXP-EXPIRED": (claim("exp", now - HOUR), signers.rs256),
        "EXP-MISSING": (remove("exp"), signers.rs256),
        "NBF-FUTURE": (claim("nbf", now + HOUR), signers.rs256),
        "NBF-MISSING": (remove("nbf"), signers.rs256),
        "ALG-NONE": (alg("none"), signers.none),
        "ALG-UNEXPECTED": (alg("ES256"), signers.es256),
        "ALG-CONFUSION": (alg("HS256"), signers.hs256_public_pem),
        # Payload edited after signing: the control signature is reattached unchanged.
        "SIG-TAMPERED": (claim("sub", TAMPERED_SUBJECT), lambda _signing_input: control_signature),
    }
    return base_header, base_payload, cases


def main():
    out = ROOT / "tokens"
    policy = json.loads((ROOT / "policy.json").read_text())
    matrix = json.loads((ROOT / "testmatrix.json").read_text())
    now = int(time.time())

    base_header, base_payload, cases = build_cases(policy, now, Signers(ROOT / "keys"))
    matrix_ids = [entry["id"] for entry in matrix]
    if set(matrix_ids) != set(cases):
        sys.exit(f"testmatrix.json and generate.py disagree: {sorted(set(matrix_ids) ^ set(cases))}")

    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.jwt"):
        stale.unlink()

    index = []
    for entry in matrix:
        mutate, sign = cases[entry["id"]]
        header, payload = copy.deepcopy(base_header), copy.deepcopy(base_payload)
        mutate(header, payload)
        # No trailing newline: the token file is the exact Authorization bearer value.
        (out / f"{entry['id']}.jwt").write_text(assemble(header, payload, sign))
        index.append({
            "id": entry["id"],
            "file": f"{entry['id']}.jwt",
            "category": entry["category"],
            "expected": entry["expected"],
        })

    generated_at = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (out / "index.json").write_text(
        json.dumps({"generated_at": generated_at, "now": now, "tokens": index}, indent=2) + "\n"
    )
    (out / "generated_at.txt").write_text(f"{generated_at}\nepoch={now}\n")
    print(f"generated {len(index)} tokens in {out} at {generated_at} (exp = now + {HOUR}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
