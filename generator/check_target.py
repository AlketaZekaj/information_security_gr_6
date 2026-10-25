#!/usr/bin/env python3
"""Send every token in tokens/ to one running target and compare with testmatrix.json.

Usage: python generator/check_target.py http://localhost:8001

First sends CTRL-01 as a gate: if the valid control token is not accepted, nothing else
is run (the target or the tokens are set up wrongly; regenerate the tokens first). Then
sends every token and prints the outcome next to the expected one. In default mode some
mismatches are the expected finding, so they do not change the exit code.

Exit code: 0 ran fine, 2 some response was an error (not 200/401/403), 3 gate failed.
Standard library only, so it needs no virtualenv.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get(url, token=None):
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    start = time.perf_counter()
    try:
        response = urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    except OSError as error:
        sys.exit(f"cannot reach {url}: {error}")
    body = response.read().decode("utf-8", "replace")
    return response.status, body, response.headers, (time.perf_counter() - start) * 1000


def outcome(status):
    return "accept" if status == 200 else "reject" if status in (401, 403) else "ERROR"


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python generator/check_target.py http://localhost:8001")
    base = sys.argv[1].rstrip("/")
    tokens_dir = ROOT / "tokens"

    index = json.loads((tokens_dir / "index.json").read_text())
    print(f"tokens generated at {index['generated_at']}")
    status, body, _, _ = get(base + "/health")
    print(f"health: {status} {body.strip()[:120]}")

    def send(entry):
        return get(base + "/protected", (tokens_dir / entry["file"]).read_text())

    control = next(t for t in index["tokens"] if t["id"] == "CTRL-01")
    status, _, headers, _ = send(control)
    if status != 200:
        print(f"GATE FAILED: CTRL-01 returned {status} ({headers.get('X-Reject-Reason', '')}); "
              "regenerate the tokens and check the target's configuration")
        return 3

    false_accepts = false_rejects = errors = 0
    for entry in index["tokens"]:
        status, body, headers, ms = send(entry)
        got = outcome(status)
        false_accepts += entry["expected"] == "reject" and got == "accept"
        false_rejects += entry["expected"] == "accept" and got == "reject"
        errors += got == "ERROR"
        mark = "ok" if got == entry["expected"] else "MISMATCH"
        reason = headers.get("X-Reject-Reason") or headers.get("WWW-Authenticate") or ""
        print(f"{entry['id']:<15} expected={entry['expected']:<6} got={got:<6} {status} {mark:<8} {ms:5.1f}ms  {reason[:70]}")

    invalid = sum(t["expected"] == "reject" for t in index["tokens"])
    print(f"\nfalse accepts: {false_accepts} of {invalid} invalid tokens | false rejects: {false_rejects} | errors: {errors}")
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
