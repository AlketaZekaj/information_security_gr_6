"""Minimal protected API validating JWTs with PyJWT.

Default mode follows the PyJWT usage docs (RS256 example):
https://pyjwt.readthedocs.io/en/stable/usage.html#encoding-decoding-tokens-with-rs256-rsa
See CONFIG_NOTES.md for every line that differs between the two modes.
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt

MODE = os.environ.get("CONFIG_MODE", "default")
KEYS_PUB = os.environ.get("KEYS_PUB", "/keys/public.pem")
POLICY = os.environ.get("POLICY", "/policy/policy.json")

if MODE not in ("default", "hardened"):
    sys.exit("CONFIG_MODE must be 'default' or 'hardened'")

with open(KEYS_PUB, "rb") as f:
    public_key = f.read()
with open(POLICY, encoding="utf-8") as f:
    policy = json.load(f)


def validate_default(token):
    # algorithms= is a mandatory argument of decode(), so it is part of the quick-start.
    # audience= is the one line added so CTRL-01 passes: with no audience configured, PyJWT
    # rejects any token that carries an aud claim (InvalidAudienceError).
    return jwt.decode(token, public_key, algorithms=["RS256"], audience=policy["audience"])


def validate_hardened(token):
    return jwt.decode(
        token,
        public_key,
        algorithms=policy["allowed_algorithms"],
        issuer=policy["issuer"],
        audience=policy["audience"],
        leeway=policy["clock_skew_seconds"],
        options={"require": policy["required_claims"]},
    )


validate = validate_default if MODE == "default" else validate_hardened


def one_line(text):
    # Header values must be printable ASCII on one line.
    return re.sub(r"[^\x20-\x7e]", "?", text)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def respond(self, status, body, content_type="text/plain", reason=None):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if reason:
            self.send_header("X-Reject-Reason", one_line(reason))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            body = {"status": "ok", "component": "pyjwt", "version": jwt.__version__, "config": MODE}
            return self.respond(200, json.dumps(body), "application/json")
        if self.path != "/protected":
            return self.respond(404, "not found")

        scheme, _, token = self.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return self.respond(401, "unauthorized", reason="MissingBearer")
        try:
            validate(token.strip())
        except jwt.PyJWTError as error:
            return self.respond(401, "unauthorized", reason=f"{type(error).__name__}: {error}")
        except Exception as error:  # not a validation decision: the harness reports it as an error
            return self.respond(500, "internal error", reason=f"{type(error).__name__}: {error}")
        self.respond(200, "ok")


if __name__ == "__main__":
    print(f"pyjwt {jwt.__version__} listening on :8080 (CONFIG_MODE={MODE})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
