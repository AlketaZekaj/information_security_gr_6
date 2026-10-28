"""Local JWT Lab UI. Start with: python web/server.py (no new dependencies)."""
import argparse
import base64
import copy
import csv
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
LOCK = threading.Lock()
CSRF = secrets.token_urlsafe(32)
JOB = {"status": "idle", "logs": [], "targets": {}, "result": None}


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def runs():
    found = []
    for path in (ROOT / "results").rglob("raw.csv"):
        if "mock" in path.relative_to(ROOT / "results").parts:
            continue
        meta = read_json(path.parent / "run.json", {})
        found.append({"id": path.parent.relative_to(ROOT / "results").as_posix(),
                      "date": meta.get("started_at_utc", ""),
                      "label": path.parent.relative_to(ROOT / "results").as_posix()})
    return sorted(found, key=lambda item: (item["date"], item["id"]), reverse=True)


def result_path(run_id):
    # Only known result folders can be downloaded or inspected.
    if run_id not in {item["id"] for item in runs()}:
        raise ValueError("Unknown result set")
    path = (ROOT / "results" / run_id / "raw.csv").resolve()
    if not path.is_relative_to((ROOT / "results").resolve()):
        raise ValueError("Invalid result path")
    return path


def result_data(run_id):
    path = result_path(run_id)
    components = read_json(ROOT / "components.json")
    aliases = {c["target_dir"].split("/")[-1]: c["name"] for c in components}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row["component"] = aliases.get(row["component"], row["component"])
        status = row.get("actual_status", "")
        row["outcome"] = "accept" if status == "200" else "reject" if status in ("401", "403") else "error"
        row["verdict"] = "error" if row["outcome"] == "error" else "pass" if row["outcome"] == row["expected"] else "fail"
    metadata = read_json(path.parent / "run.json", {})
    # Old pilot runs store toolchain dumps; return only presentation metadata.
    return {"id": run_id, "rows": rows, "metadata": {
        key: metadata.get(key) for key in ("started_at_utc", "finished_at_utc", "git_commit",
                                          "base_commit", "launcher", "setup_failures", "cases")}}


def token_data():
    index = read_json(ROOT / "tokens" / "index.json", {})
    tokens = []
    for case in read_json(ROOT / "testmatrix.json"):
        path = ROOT / "tokens" / (case["id"] + ".jwt")
        if not path.exists():
            continue
        raw = path.read_text().strip()
        try:
            parts = raw.split(".")
            decode = lambda value: json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
            tokens.append({"id": case["id"], "raw": raw, "header": decode(parts[0]), "payload": decode(parts[1])})
        except (ValueError, IndexError):
            continue
    return {"generated_at": index.get("generated_at"), "tokens": tokens}


def snapshot():
    with LOCK:
        return copy.deepcopy(JOB)


def execute(command):
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                          creationflags=flags) as process:
        for line in process.stdout:
            line = line.rstrip()
            with LOCK:
                JOB["logs"].append(line)
                JOB["logs"] = JOB["logs"][-250:]
                for name, modes in JOB["targets"].items():
                    if line.startswith("SETUP ERROR: " + name + " /"):
                        JOB["targets"][name] = {mode: "setup failed" for mode in modes}
                    for mode in modes:
                        if line.startswith(f"{name} / {mode}:"):
                            JOB["targets"][name][mode] = "measured"
        return process.wait()


def worker(kind, selected, launcher, output):
    status = "failed"
    try:
        # make_keys never overwrites an existing key pair without --force.
        if execute([sys.executable, "generator/make_keys.py"]) != 0:
            raise RuntimeError("Key preparation failed. Check the log and generator dependencies.")
        if kind == "generate":
            for script in ("generate.py", "verify_tokens.py"):
                if execute([sys.executable, "generator/" + script]) != 0:
                    raise RuntimeError("Token generation or verification failed. See the log.")
            status = "completed"
        else:
            # The optional repository-local .NET 10 SDK is used only for its .NET 10
            # target; .NET 8 must continue using the installed system runtime.
            components = read_json(ROOT / "components.json")
            local_dotnet = ROOT / ".tools" / "dotnet" / ("dotnet.exe" if os.name == "nt" else "dotnet")
            if local_dotnet.exists():
                for component in components:
                    if component["target_dir"] == "targets/dotnet-jsonwebtokenhandler":
                        for command in ("build", "command"):
                            component["native"][command][0] = str(local_dotnet)
            output.mkdir(parents=True, exist_ok=True)
            components_path = output / "components.json"
            components_path.write_text(json.dumps(components, indent=2), encoding="utf-8")
            code = execute([sys.executable, "harness/run.py", "--launcher", launcher,
                            "--output", str(output), "--components-file", str(components_path),
                            "--components", *selected])
            if code not in (0, 2, 3):
                raise RuntimeError("Evaluation could not finish. See the log for missing dependencies or setup errors.")
            metrics_code = execute([sys.executable, "harness/metrics.py", str(output / "raw.csv")])
            status = "completed" if code == 0 and metrics_code == 0 else "completed with issues"
            with LOCK:
                JOB["result"] = output.relative_to(ROOT / "results").as_posix()
    except Exception as error:
        with LOCK:
            JOB["logs"].append(str(error))
    finally:
        with LOCK:
            for modes in JOB["targets"].values():
                for mode in modes:
                    if modes[mode] == "pending":
                        modes[mode] = "not measured"
            JOB["status"] = status


def start_job(kind, body):
    selected = body.get("components", [])
    available = {c["name"] for c in read_json(ROOT / "components.json")}
    # In Docker Compose every target already runs in both modes, so the web service reaches
    # them over the compose network (JWT_LAB_LAUNCHER=network) instead of starting them.
    launcher = os.environ.get("JWT_LAB_LAUNCHER") or body.get("launcher", "native")
    if kind == "run" and (not isinstance(selected, list) or not selected
                          or any(not isinstance(c, str) or c not in available for c in selected)
                          or len(selected) != len(set(selected))):
        raise ValueError("Select one or more known targets, without duplicates")
    if launcher not in ("native", "docker", "network"):
        raise ValueError("Launcher must be native, docker or network")
    output = ROOT / "results" / "web" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    with LOCK:
        if JOB["status"] == "running":
            raise RuntimeError("An operation is already running")
        JOB.clear()
        JOB.update(status="running", kind=kind, logs=[], result=None,
                   targets={c: {"default": "pending", "hardened": "pending"} for c in selected} if kind == "run" else {})
    threading.Thread(target=worker, args=(kind, selected, launcher, output), daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def send(self, data, status=200, content_type="application/json; charset=utf-8", filename=None):
        payload = json.dumps(data).encode() if content_type.startswith("application/json") else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(payload)

    def valid_host(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def do_GET(self):
        if not self.valid_host():
            return self.send({"error": "Local access only"}, 403)
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/state":
                return self.send({"csrf": CSRF, "components": read_json(ROOT / "components.json"),
                                  "matrix": read_json(ROOT / "testmatrix.json"), "policy": read_json(ROOT / "policy.json"),
                                  "runs": runs(), "job": snapshot(), "tokens": token_data(),
                                  "runtime": {name: bool(shutil.which(name)) for name in ("node", "dotnet", "docker")}})
            if parsed.path == "/api/job":
                return self.send(snapshot())
            if parsed.path in ("/api/results", "/api/export"):
                run_id = parse_qs(parsed.query).get("run", [""])[0]
                if parsed.path == "/api/export":
                    return self.send(result_path(run_id).read_bytes(), content_type="text/csv; charset=utf-8", filename="jwt-lab-results.csv")
                return self.send(result_data(run_id))
            files = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
            if parsed.path in files:
                name, mime = files[parsed.path]
                return self.send((STATIC / name).read_bytes(), content_type=mime + "; charset=utf-8")
            self.send({"error": "Not found"}, 404)
        except (ValueError, OSError) as error:
            self.send({"error": str(error)}, 400)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if (not self.valid_host() or self.headers.get("X-Lab-Token") != CSRF or
                origin not in (None, f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}")):
            return self.send({"error": "Refresh JWT Lab and try again"}, 403)
        if self.path not in ("/api/generate", "/api/run"):
            return self.send({"error": "Not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 10000:
                raise ValueError("Invalid request size")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
            start_job(self.path.rsplit("/", 1)[1], body)
            self.send(snapshot(), 202)
        except (ValueError, TypeError) as error:
            self.send({"error": str(error)}, 400)
        except RuntimeError as error:
            self.send({"error": str(error)}, 409)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1",
                        help="address to listen on; 0.0.0.0 only inside a container published on loopback")
    parser.add_argument("--open", action="store_true", help="open JWT Lab in your default browser")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"JWT Lab: http://127.0.0.1:{server.server_port}", flush=True)
    if args.open:
        threading.Timer(0.3, lambda: webbrowser.open(f"http://127.0.0.1:{server.server_port}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
