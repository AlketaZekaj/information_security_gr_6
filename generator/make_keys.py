#!/usr/bin/env python3
"""Generate the synthetic RSA and EC test key pairs into keys/.

RSA 2048 (private.pem / public.pem) signs and verifies every RS256 token.
EC P-256 (ec_private.pem / ec_public.pem) is only used for ALG-UNEXPECTED.
Targets receive public.pem only.
"""
import argparse
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "keys"
NAMES = ("private.pem", "public.pem", "ec_private.pem", "ec_public.pem")


def private_pem(key):
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def public_pem(key):
    # SPKI ("BEGIN PUBLIC KEY"): the form every target library can import.
    return key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def write(path, data, mode):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(path, mode)  # os.open's mode is masked by umask and ignored for existing files


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="replace existing keys")
    args = parser.parse_args()

    existing = [n for n in NAMES if (OUT / n).exists()]
    if existing and not args.force:
        print(f"keys already exist in {OUT} ({', '.join(existing)}); use --force to replace them")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ec_key = ec.generate_private_key(ec.SECP256R1())

    write(OUT / "private.pem", private_pem(rsa_key), 0o600)
    write(OUT / "public.pem", public_pem(rsa_key), 0o644)
    write(OUT / "ec_private.pem", private_pem(ec_key), 0o600)
    write(OUT / "ec_public.pem", public_pem(ec_key), 0o644)
    print(f"wrote RSA 2048 and EC P-256 test key pairs to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
