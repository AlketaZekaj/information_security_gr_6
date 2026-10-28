#!/usr/bin/env python3
"""Send the test matrix to every component in both configurations and write raw.csv.

  python harness/run.py                           # all components, default + hardened
  python harness/run.py --components PyJWT jose   # a subset
  python harness/run.py --pilot                   # pilot subset, written to results/pilot/
  python harness/run.py --launcher native --components-file harness/mock_components.json \\
      --output results/mock

For each component and configuration: start the target, regenerate the tokens, send the
valid control token (CTRL-01) as a gate, then send every case and record one row per
request. A component whose control token is not accepted, or that reports a different
mode than the one requested, is stopped and left out of raw.csv entirely, so data from a
failed setup never reaches the metrics.

Launchers (how a target is started):
  docker  (default) build the component's docker-compose.yml service, then recreate its
          container with CONFIG_MODE set for each configuration; needs Docker Compose
  native  start the target as a local process, as described in components.json; the
          toolchain (Python, Node, .NET) must be installed and the targets' dependencies
          present (pip install / npm ci)
  none    the targets are already running on their components.json ports; only one
          --configs value is allowed, because the harness cannot switch their mode

Run it with the Python that has generator/requirements.txt installed.
Exit code: 0 all fine, 1 run aborted (nothing written), 2 some responses were errors,
3 a component failed its setup and was left out.
"""
import argparse
import contextlib
import csv
import http.client
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
TOKENS = ROOT / "tokens"
CONFIGS = ("default", "hardened")
FIELDS = ("component version config test_id category expected actual_status accepted "
          "correct latency_ms response_body www_authenticate").split()
PILOT_COMPONENTS = ("PyJWT", "JwtBearer", "jsonwebtoken")
PILOT_CASES = ("CTRL-01", "ISS-INVALID", "EXP-EXPIRED", "ALG-NONE", "NBF-MISSING")
# Every target runs on this machine, so proxy settings from the environment must not apply.
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class SetupError(Exception):
    """A component is set up wrongly; it is stopped and its data is not used."""


class AbortRun(Exception):
    """Something every component depends on failed; the run stops and writes nothing."""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def relative(path):
    """Path relative to the repository, so messages and run.json hold no personal paths."""
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def get(url, token=None, timeout=5.0):
    """GET url, retrying once on a connection error; return (status, body, headers, latency_ms).

    status is None when no HTTP response arrived (refused, reset, timeout); body then holds
    the error so the row still explains what happened."""
    request = urllib.request.Request(url)
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    for attempt in (1, 2):
        start = time.perf_counter()
        try:
            try:
                response = HTTP.open(request, timeout=timeout)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                body = response.read().decode("utf-8", "replace")
                return response.status, body, response.headers, (time.perf_counter() - start) * 1000
        except (OSError, http.client.HTTPException) as error:
            # urllib wraps connection failures in URLError; the cause is in .reason.
            reason = getattr(error, "reason", error)
            if attempt == 1 and isinstance(reason, ConnectionError):
                continue
            return None, f"{type(reason).__name__}: {reason}", {}, (time.perf_counter() - start) * 1000


def outcome(status):
    """200 is accept, 401/403 reject, anything else (including no response) an error."""
    return "accept" if status == 200 else "reject" if status in (401, 403) else "error"


def make_row(component, config, case, status, body, headers, latency_ms):
    result = outcome(status)
    return {
        "component": component["name"],
        "version": component["version"],
        "config": config,
        "test_id": case["id"],
        "category": case["category"],
        "expected": case["expected"],
        "actual_status": "" if status is None else status,
        # CONTRACT.md section 5: both columns stay empty for an error, which is neither an
        # acceptance nor a rejection.
        "accepted": {"accept": "true", "reject": "false"}.get(result, ""),
        "correct": "" if result == "error" else str(result == case["expected"]).lower(),
        "latency_ms": latency_ms,
        "response_body": " ".join(body.split())[:500],
        "www_authenticate": headers.get("WWW-Authenticate", ""),
    }


def wait_healthy(base_url, timeout, process=None, log_path=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise SetupError(f"target exited with code {process.returncode}; see {relative(log_path)}")
        if get(base_url + "/health", timeout=2)[0] == 200:
            return
        time.sleep(0.25)
    where = f"; see {relative(log_path)}" if log_path else ""
    raise SetupError(f"{base_url}/health did not return 200 within {timeout:g} s{where}")


def port_in_use(port):
    with contextlib.suppress(OSError), socket.create_connection(("127.0.0.1", port), timeout=1):
        return True
    return False


def expand(command, port):
    return [sys.executable if arg == "{python}" else arg.replace("{port}", str(port)) for arg in command]


def stop_native_process(process, port):
    """Stop only the owned target, including Windows virtualenv launcher children."""
    if process.poll() is None:
        if os.name == "nt":
            # python.exe in a Windows venv is a redirector. Terminating only that
            # parent can leave its actual interpreter listening between modes.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    # Socket teardown can finish after process exit on Windows. The next mode
    # still performs its independent port-in-use check before launching.
    deadline = time.monotonic() + 3
    while port_in_use(port) and time.monotonic() < deadline:
        time.sleep(0.1)


def build_native(component, logs):
    command = component.get("native", {}).get("build")
    if not command:
        return
    log_path = logs / f"{component['name']}-build.log"
    print(f"{component['name']}: building...", flush=True)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT / component["target_dir"], stdout=log,
                                    stderr=subprocess.STDOUT, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SetupError(f"build command {command[0]!r} failed: {error}") from None
    if result.returncode:
        raise SetupError(f"build failed with code {result.returncode}; see {relative(log_path)}")


@contextlib.contextmanager
def native_target(component, config, logs, health_timeout):
    port = component["native"]["port"]
    # Refuse to measure an unrelated server that happens to listen on the same port.
    if port_in_use(port):
        raise SetupError(f"port {port} is already in use; stop whatever is listening there")
    env = dict(os.environ, CONFIG_MODE=config,
               KEYS_PUB=str(ROOT / "keys" / "public.pem"), POLICY=str(ROOT / "policy.json"),
               ASPNETCORE_URLS=f"http://127.0.0.1:{port}",
               ASPNETCORE_ENVIRONMENT="Production", DOTNET_ENVIRONMENT="Production")
    log_path = logs / f"{component['name']}-{config}.log"
    with log_path.open("w", encoding="utf-8") as log:
        try:
            process = subprocess.Popen(expand(component["native"]["command"], port),
                                       cwd=ROOT / component["target_dir"], env=env,
                                       stdout=log, stderr=subprocess.STDOUT)
        except OSError as error:
            raise SetupError(f"cannot start target: {error}") from None
        try:
            base_url = f"http://127.0.0.1:{port}"
            wait_healthy(base_url, health_timeout, process, log_path)
            yield base_url
        finally:
            stop_native_process(process, port)


def compose(arguments, log, config="default", timeout=600):
    """Run `docker compose ...` in the repository with output to log; return True on success."""
    # compose reads CONFIG_MODE=${CONFIG_MODE:-default}, so the mode is passed through the environment.
    try:
        result = subprocess.run(["docker", "compose", *arguments], cwd=ROOT, env=dict(os.environ, CONFIG_MODE=config),
                                stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        log.write(f"\nharness: docker compose {arguments[0]} failed: {error}\n")
        return False
    return result.returncode == 0


def compose_available():
    try:
        return subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0
    except OSError:
        return False


def compose_service(component):
    service = component.get("service")
    if not service:
        raise SetupError("no docker compose service in the components file")
    return service


def build_docker(component, logs):
    service = compose_service(component)
    log_path = logs / f"{component['name']}-build.log"
    print(f"{component['name']}: building image...", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        if not compose(["build", service], log):
            raise SetupError(f"docker compose build failed; see {relative(log_path)}")


@contextlib.contextmanager
def docker_target(component, config, logs, health_timeout):
    service = compose_service(component)
    log_path = logs / f"{component['name']}-{config}.log"
    with log_path.open("w", encoding="utf-8") as log:
        try:
            # --force-recreate: a running container keeps its old CONFIG_MODE otherwise.
            if not compose(["up", "--detach", "--force-recreate", "--no-build", "--no-deps", service],
                           log, config, timeout=180):
                raise SetupError(f"docker compose up failed; see {relative(log_path)}")
            base_url = f"http://127.0.0.1:{component['port']}"
            wait_healthy(base_url, health_timeout, log_path=log_path)
            yield base_url
        finally:
            log.flush()
            compose(["logs", "--no-color", service], log, timeout=60)
            compose(["stop", service], log, timeout=60)


@contextlib.contextmanager
def running_target(component, config, logs, health_timeout):
    base_url = f"http://127.0.0.1:{component['port']}"
    wait_healthy(base_url, health_timeout)
    yield base_url


LAUNCHERS = {"docker": docker_target, "native": native_target, "none": running_target}
BUILDERS = {"docker": build_docker, "native": build_native}


def fresh_tokens(case_ids):
    """Regenerate and verify the tokens; return ({case id: token}, generated_at)."""
    for script in ("generate.py", "verify_tokens.py"):
        result = subprocess.run([sys.executable, str(ROOT / "generator" / script)], cwd=ROOT,
                                capture_output=True, text=True)
        if result.returncode:
            raise AbortRun(f"generator/{script} failed:\n{result.stdout}{result.stderr}".rstrip())
    index = json.loads((TOKENS / "index.json").read_text())
    tokens = {entry["id"]: (TOKENS / entry["file"]).read_text().strip() for entry in index["tokens"]}
    missing = [case_id for case_id in case_ids if case_id not in tokens]
    if missing:
        raise AbortRun(f"tokens/index.json has no token for {', '.join(missing)}")
    return tokens, index["generated_at"]


def gate_message(status, body):
    if status in (401, 403):
        return f"control token rejected with {status}: setup error"
    if status is None:
        return f"control token got no response ({body}): setup error"
    return f"control token returned {status}: setup error"


def reported_mode(base_url):
    """The mode a target reports on /health when its body is JSON with a 'config' field, else None."""
    body = get(base_url + "/health", timeout=2)[1]
    try:
        return json.loads(body).get("config")
    except (ValueError, AttributeError):
        return None


def measure(component, config, cases, args, logs, generations):
    """Run every case against one component in one configuration; return its rows."""
    launcher = LAUNCHERS[args.launcher]
    with launcher(component, config, logs, args.health_timeout) as base_url:
        mode = reported_mode(base_url)
        if mode is not None and mode != config:
            raise SetupError(f"target reports mode {mode!r} instead of {config!r}: setup error")
        tokens, generated_at = fresh_tokens([case["id"] for case in cases])
        generations.append({"component": component["name"], "config": config, "generated_at": generated_at})
        status, body, _, _ = get(base_url + "/protected", tokens["CTRL-01"], args.request_timeout)
        if status != 200:
            raise SetupError(gate_message(status, body))
        return [make_row(component, config, case,
                         *get(base_url + "/protected", tokens[case["id"]], args.request_timeout))
                for case in cases]


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AbortRun(f"cannot read {path}: {error}") from None


def select_components(available, names):
    by_name = {component["name"].lower(): component for component in available}
    unknown = [name for name in names if name.lower() not in by_name]
    if unknown:
        raise AbortRun(f"unknown component(s) {', '.join(unknown)}; "
                       f"available: {', '.join(c['name'] for c in available)}")
    return [by_name[name.lower()] for name in names]


def git_commit():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def write_csv(path, rows):
    # Write to a temporary file first so an existing raw.csv is never left half-written.
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--components", nargs="+", metavar="NAME", help="only these components (by name)")
    parser.add_argument("--components-file", default=str(ROOT / "components.json"))
    parser.add_argument("--configs", nargs="+", choices=CONFIGS, default=list(CONFIGS))
    parser.add_argument("--pilot", action="store_true",
                        help=f"cases {', '.join(PILOT_CASES)} on {', '.join(PILOT_COMPONENTS)} "
                             "(unless --components is given); output defaults to results/pilot/")
    parser.add_argument("--output", help="output directory (default results/, or results/pilot/ with --pilot)")
    parser.add_argument("--launcher", choices=sorted(LAUNCHERS), default="docker")
    parser.add_argument("--health-timeout", type=float, default=60.0, help="seconds to wait for /health")
    parser.add_argument("--request-timeout", type=float, default=5.0, help="seconds per request")
    args = parser.parse_args()
    if args.launcher == "none" and len(args.configs) != 1:
        parser.error("--launcher none cannot switch modes: pass exactly one --configs value")
    return args


def main():
    args = parse_args()
    out = Path(args.output) if args.output else ROOT / "results" / ("pilot" if args.pilot else "")
    started_at = utc_now()
    try:
        available = load_json(args.components_file)
        names = args.components or ([c["name"] for c in available if c["name"] in PILOT_COMPONENTS]
                                    if args.pilot else [c["name"] for c in available])
        components = select_components(available, names)
        if not components:
            raise AbortRun("no components selected")
        matrix = load_json(ROOT / "testmatrix.json")
        cases = [case for case in matrix if not args.pilot or case["id"] in PILOT_CASES]
        if not any(case["id"] == "CTRL-01" for case in cases):
            raise AbortRun("testmatrix.json has no CTRL-01, so the setup gate cannot run")
        # A missing key would otherwise surface as one confusing failure per component.
        if not (ROOT / "keys" / "public.pem").is_file():
            raise AbortRun("keys/public.pem is missing or not a file: run python generator/make_keys.py")
        if args.launcher == "docker" and not compose_available():
            raise AbortRun("docker compose is not available: install Docker or use --launcher native")
    except AbortRun as error:
        print(f"ABORTED: {error}", file=sys.stderr)
        return 1

    logs = out / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    if args.launcher == "none":
        print(f"launcher none: make sure every target is running in {args.configs[0]} mode", flush=True)

    rows, failures, generations = [], [], []
    try:
        for component in components:
            name, component_rows, step = component["name"], [], "build"
            try:
                if args.launcher in BUILDERS:
                    BUILDERS[args.launcher](component, logs)
                for step in args.configs:
                    config_rows = measure(component, step, cases, args, logs, generations)
                    as_expected = sum(row["correct"] == "true" for row in config_rows)
                    errors = sum(row["accepted"] == "" for row in config_rows)
                    print(f"{name} / {step}: {as_expected}/{len(config_rows)} as expected, {errors} errors",
                          flush=True)
                    component_rows.extend(config_rows)
            except SetupError as error:
                message = f"{name} / {step}: {error}"
                print(f"SETUP ERROR: {message}. {name} is left out of the results.", flush=True)
                failures.append({"component": name, "message": message})
                continue
            rows.extend(component_rows)
    except AbortRun as error:
        print(f"ABORTED: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("ABORTED: interrupted; nothing written", file=sys.stderr)
        return 1

    write_csv(out / "raw.csv", rows)
    measured = [c for c in components if c["name"] not in {f["component"] for f in failures}]
    metadata = {
        "started_at_utc": started_at,
        "finished_at_utc": utc_now(),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "launcher": args.launcher,
        "configs": args.configs,
        "pilot": args.pilot,
        "cases": [case["id"] for case in cases],
        "components": [{"name": c["name"], "version": c["version"]} for c in measured],
        "setup_failures": failures,
        "token_generations": generations,
    }
    (out / "run.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    errors = sum(row["accepted"] == "" for row in rows)
    print(f"\nwrote {len(rows)} rows for {len(measured)} component(s) to {relative(out / 'raw.csv')}"
          f" | errors: {errors} | setup failures: {len(failures)}")
    return 3 if failures else 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
