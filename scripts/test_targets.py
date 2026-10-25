#!/usr/bin/env python3
"""Local pilot for the three implemented .NET and jose targets; does not replace the team harness.

Requires generator dependencies, installed jose dependencies, .NET 8 and .NET 10.
Writes raw HTTP evidence, predictions comparison, versions, hashes and process logs.
Uses port 8080 sequentially. Only processes started by this script are stopped.
"""
import argparse
import contextlib
import copy
import csv
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "generator"))
from generate import Signers, assemble
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

FIELDS = "component version config test_id category expected actual_status accepted correct latency_ms response_body www_authenticate".split()
TARGETS = ["dotnet-jwtbearer", "dotnet-jsonwebtokenhandler", "node-jose"]
MODES = ["default", "hardened"]
JOSE_GAPS = {"ISS-INVALID", "ISS-MISSING", "AUD-INVALID", "AUD-MISSING", "EXP-MISSING"}
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def utc():
    return datetime.now(timezone.utc).isoformat()


def command(args):
    result = subprocess.run([str(x) for x in args], cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=FLAGS, timeout=300)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {args}\n{result.stdout}")
    return result.stdout


def dump(path, value):
    # Keep portable evidence without embedding the workstation's personal paths.
    serialized = json.dumps(value, indent=2)
    for local_path, label in ((ROOT, "<repository>"), (Path.home(), "<user-home>")):
        serialized = serialized.replace(json.dumps(str(local_path))[1:-1], label)
    path.write_text(serialized + "\n", encoding="utf-8")


def write_csv(path, rows, fields=FIELDS):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def request(path, token=None):
    req = urllib.request.Request("http://127.0.0.1:8080" + path)
    if token is not None:
        req.add_header("Authorization", "Bearer " + token)
    start = time.perf_counter()
    try:
        try:
            response = HTTP.open(req, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return {"status": response.status,
                    "body": response.read().decode("utf-8", "replace"),
                    "headers": dict(response.headers.items()),
                    "latency_ms": (time.perf_counter() - start) * 1000}
    except OSError as error:
        return {"status": None, "body": str(error), "headers": {},
                "latency_ms": (time.perf_counter() - start) * 1000}


@contextlib.contextmanager
def running(component, mode, invocation, logs, phase):
    # Fail instead of accidentally sending tests to an unrelated server.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8080))
    env = os.environ.copy()
    env.update(CONFIG_MODE=mode, KEYS_PUB=str(ROOT / "keys/public.pem"),
               POLICY=str(ROOT / "policy.json"), ASPNETCORE_URLS="http://127.0.0.1:8080",
               ASPNETCORE_ENVIRONMENT="Production", DOTNET_ENVIRONMENT="Production")
    log_path = logs / f"{component}-{mode}-{phase}.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(invocation, cwd=ROOT / "targets" / component,
                                   env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=FLAGS)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"{component}/{mode} exited: see {log_path}")
                if request("/health")["status"] == 200:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError(f"{component}/{mode} health timeout: see {log_path}")
            yield
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def predicted(component, mode, case):
    if mode == "default" and component == "node-jose" and case["id"] in JOSE_GAPS:
        return "accept"
    if mode == "default" and component.startswith("dotnet") and case["id"] in {"EXP-SKEW-120", "ALG-RS512"}:
        return "accept"
    return case["expected"]


def observation(component, version, mode, case, token):
    response = request("/protected", token)
    status = response["status"]
    actual = "accept" if status == 200 else "reject" if status in (401, 403) else "error"
    headers = {k.lower(): v for k, v in response["headers"].items()}
    row = dict(component=component, version=version, config=mode,
               test_id=case["id"], category=case["category"], expected=case["expected"],
               actual_status=status if status is not None else "",
               accepted="true" if actual == "accept" else "false" if actual == "reject" else "error",
               correct=str(actual == case["expected"]).lower(),
               latency_ms=response["latency_ms"], response_body=" ".join(response["body"].split())[:500],
               www_authenticate=headers.get("www-authenticate", ""))
    detail = dict(component=component, config=mode, test_id=case["id"],
                  predicted=predicted(component, mode, case), actual=actual,
                  matches_prediction=predicted(component, mode, case) == actual,
                  token_sha256=hashlib.sha256(token.encode()).hexdigest(), response=response)
    return row, detail


def diagnostic_tokens():
    import base64
    control = (ROOT / "tokens/CTRL-01.jwt").read_text().split(".")
    header = json.loads(base64.urlsafe_b64decode(control[0] + "=" * (-len(control[0]) % 4)))
    payload = json.loads(base64.urlsafe_b64decode(control[1] + "=" * (-len(control[1]) % 4)))
    signers = Signers(ROOT / "keys")
    old = copy.deepcopy(payload)
    # Keep the validity interval well formed; this probe is outside the one-change matrix.
    old.update(iat=payload["iat"] - 600, nbf=payload["iat"] - 600, exp=payload["iat"] - 120)
    long_expired = copy.deepcopy(payload)
    long_expired.update(iat=payload["iat"] - 7200, nbf=payload["iat"] - 7200, exp=payload["iat"] - 3600)
    other_alg = dict(header, alg="RS512")
    return {
        "EXP-SKEW-120": assemble(header, old, signers.rs256),
        "EXP-PAST-3600": assemble(header, long_expired, signers.rs256),
        "ALG-RS512": assemble(other_alg, payload, lambda data: signers.rsa_key.sign(data, padding.PKCS1v15(), hashes.SHA512())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dotnet8", default="dotnet")
    parser.add_argument("--dotnet10", default=str(ROOT / ".tools/dotnet/dotnet.exe"))
    parser.add_argument("--output", default="results/pilot/target-validation")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    logs = out / "logs"
    logs.mkdir(exist_ok=True)
    metadata = {"started_at_utc": utc(), "environment": "native Windows; Docker unavailable",
                "platform": platform.platform(), "python": sys.version,
                "base_commit": command(["git", "rev-parse", "HEAD"]).strip(),
                "components": {}, "gates": [], "token_generations": [], "completed": False,
                "excluded": {"node-express-jwt": "Target not implemented in this checkout"}}
    rows, diagnostics, extras = [], [], []
    try:
        invocations, versions = {}, {}
        for component in TARGETS:
            target = ROOT / "targets" / component
            if component == "node-jose":
                packages = {name: json.loads((target / "node_modules" / name / "package.json").read_text())["version"]
                            for name in ("jose", "express")}
                wanted = json.loads((target / "package.json").read_text())["dependencies"]
                if packages != wanted:
                    raise RuntimeError(f"Installed Node versions {packages} differ from pinned versions {wanted}")
                versions[component] = packages["jose"]
                invocations[component] = ["node", str(target / "app.js")]
                metadata["components"][component] = {"node": command(["node", "--version"]).strip(), "packages": packages}
            else:
                dotnet = args.dotnet8 if component == "dotnet-jwtbearer" else args.dotnet10
                build = ROOT / ".tools/build" / component
                if not args.skip_build:
                    print(f"Building {component}...", flush=True)
                    output = command([dotnet, "build", target / f"{component}.csproj", "-c", "Release", "-o", build, "--nologo"])
                    (logs / f"{component}-build.log").write_text(output, encoding="utf-8")
                deps = json.loads((build / f"{component}.deps.json").read_text())
                packages = {k.split("/")[0]: k.split("/")[1] for k in deps["libraries"] if "/" in k and k.startswith("Microsoft.")}
                package = "Microsoft.AspNetCore.Authentication.JwtBearer" if component == "dotnet-jwtbearer" else "Microsoft.IdentityModel.JsonWebTokens"
                versions[component] = packages[package]
                invocations[component] = [str(dotnet), str(build / f"{component}.dll")]
                metadata["components"][component] = {"dotnet_info": command([dotnet, "--info"]), "packages": packages}
        metadata["source_sha256"] = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in [ROOT / "policy.json", ROOT / "testmatrix.json", Path(__file__).resolve(),
                                               *[ROOT / "generator" / n for n in ("make_keys.py", "generate.py", "verify_tokens.py")],
                                               *[ROOT / "targets" / c / ("app.js" if c == "node-jose" else "Program.cs") for c in TARGETS]]}
        metadata["public_key_sha256"] = hashlib.sha256((ROOT / "keys/public.pem").read_bytes()).hexdigest()
        matrix = json.loads((ROOT / "testmatrix.json").read_text())
        control = next(c for c in matrix if c["id"] == "CTRL-01")

        def generate(phase):
            generated = command([sys.executable, ROOT / "generator/generate.py"])
            verified = command([sys.executable, ROOT / "generator/verify_tokens.py"])
            metadata["token_generations"].append({"phase": phase, "index": json.loads((ROOT / "tokens/index.json").read_text()), "verification": verified})
            (logs / f"foundation-{phase}.log").write_text(generated + verified, encoding="utf-8")

        # Every target must accept CTRL-01 in both modes before the matrix is measured.
        generate("preflight")
        for component in TARGETS:
            for mode in MODES:
                with running(component, mode, invocations[component], logs, "preflight"):
                    row, detail = observation(component, versions[component], mode, control, (ROOT / "tokens/CTRL-01.jwt").read_text())
                    metadata["gates"].append(detail)
                    if row["actual_status"] != 200:
                        raise RuntimeError(f"SETUP ERROR: {component}/{mode} rejected CTRL-01: {detail}")
                print(f"Control passed: {component}/{mode}", flush=True)

        for component in TARGETS:
            for mode in MODES:
                generate(f"{component}-{mode}")
                with running(component, mode, invocations[component], logs, "matrix"):
                    token = (ROOT / "tokens/CTRL-01.jwt").read_text()
                    row, detail = observation(component, versions[component], mode, control, token)
                    if row["actual_status"] != 200:
                        raise RuntimeError(f"SETUP ERROR: control failed on measurement restart for {component}/{mode}")
                    rows.append(row)
                    diagnostics.append(detail)
                    for case in matrix:
                        if case["id"] == "CTRL-01":
                            continue
                        row, detail = observation(component, versions[component], mode, case, (ROOT / "tokens" / f"{case['id']}.jwt").read_text())
                        rows.append(row)
                        diagnostics.append(detail)
                    for case_id, token in diagnostic_tokens().items():
                        case = {"id": case_id, "category": "PROBE", "expected": "reject"}
                        row, detail = observation(component, versions[component], mode, case, token)
                        extras.append(row)
                        diagnostics.append(detail)
                subset = [r for r in rows if r["component"] == component and r["config"] == mode]
                print(f"Measured {component}/{mode}: {sum(r['correct'] == 'true' for r in subset)}/13 match policy", flush=True)
        summaries = []
        for component in TARGETS:
            for mode in MODES:
                subset = [r for r in rows if r["component"] == component and r["config"] == mode]
                invalid = [r for r in subset if r["expected"] == "reject" and r["accepted"] != "error"]
                valid = [r for r in subset if r["expected"] == "accept" and r["accepted"] != "error"]
                fa = sum(r["accepted"] == "true" for r in invalid)
                fr = sum(r["accepted"] == "false" for r in valid)
                summaries.append({"component": component, "config": mode, "cases": len(subset),
                                  "policy_matches": sum(r["correct"] == "true" for r in subset),
                                  "false_accepts": fa, "invalid_non_error": len(invalid),
                                  "false_accept_rate": fa / len(invalid) if invalid else "",
                                  "false_rejects": fr, "valid_non_error": len(valid),
                                  "false_reject_rate": fr / len(valid) if valid else "",
                                  "errors": sum(r["accepted"] == "error" for r in subset)})
        write_csv(out / "summary.csv", summaries, list(summaries[0]))
        metadata["completed"] = True
        metadata["prediction_mismatches"] = [d for d in diagnostics if not d["matches_prediction"]]
        metadata["errors"] = sum(r["accepted"] == "error" for r in rows + extras)
    except Exception as error:
        metadata["failure"] = str(error)
        raise
    finally:
        metadata["finished_at_utc"] = utc()
        write_csv(out / "raw.csv", rows)
        write_csv(out / "probes.csv", extras)
        dump(out / "diagnostics.json", diagnostics)
        dump(out / "run.json", metadata)
    return 2 if metadata["errors"] or metadata["prediction_mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
