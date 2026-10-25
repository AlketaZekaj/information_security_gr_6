#!/usr/bin/env python3
"""Fake target for developing the harness without the real components.

Usage: CONFIG_MODE=default python harness/mock_server.py --port 9001 --behavior lenient

Implements the target contract (GET /health, GET /protected) and decides by looking the
presented token up in tokens/index.json, so the outcome of every test case is fixed:

  strict       accepts exactly the cases testmatrix.json expects to be accepted
  lenient      like strict, but in default mode also accepts ISS-*, AUD-* and EXP-MISSING
  error        like strict, but SIG-TAMPERED returns 500 (exercises the "error" class)
  bad-control  like strict, but CTRL-01 is rejected in hardened mode (exercises the gate)

An unknown or missing token is rejected. Standard library only.
"""
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOKENS = Path(__file__).resolve().parents[1] / "tokens"
LENIENT_DEFAULT = {"ISS-INVALID", "ISS-MISSING", "AUD-INVALID", "AUD-MISSING", "EXP-MISSING"}


def case_for(token):
    """Return the tokens/index.json entry whose token file holds this token, or None."""
    # Read on every request: the harness regenerates the tokens while the mock is running.
    index = json.loads((TOKENS / "index.json").read_text())
    for entry in index["tokens"]:
        if (TOKENS / entry["file"]).read_text().strip() == token:
            return entry
    return None


def decide(behavior, mode, entry):
    """Return the HTTP status for a token belonging to this index entry."""
    case_id = entry["id"]
    if behavior == "error" and case_id == "SIG-TAMPERED":
        return 500
    if behavior == "bad-control" and mode == "hardened" and case_id == "CTRL-01":
        return 401
    if behavior == "lenient" and mode == "default" and case_id in LENIENT_DEFAULT:
        return 200
    return 200 if entry["expected"] == "accept" else 401


def make_handler(behavior, mode):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                return self.reply(200, "ok")
            if self.path != "/protected":
                return self.reply(404, "not found")
            header = self.headers.get("Authorization", "")
            entry = case_for(header[len("Bearer "):].strip()) if header.startswith("Bearer ") else None
            if entry is None:
                return self.reply(401, "unauthorized", "mock:unknown-token")
            status = decide(behavior, mode, entry)
            body = {200: "ok", 401: "unauthorized"}.get(status, "mock error")
            return self.reply(status, body, f"mock:{entry['id']}" if status == 401 else None)

        def reply(self, status, body, reason=None):
            data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            if reason:
                self.send_header("X-Reject-Reason", reason)
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--behavior", choices=["strict", "lenient", "error", "bad-control"], default="strict")
    args = parser.parse_args()
    mode = os.environ.get("CONFIG_MODE", "default")
    if mode not in ("default", "hardened"):
        sys.exit(f"CONFIG_MODE must be default or hardened, got {mode!r}")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.behavior, mode))
    print(f"mock ({args.behavior}) listening on :{args.port} (CONFIG_MODE={mode})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
