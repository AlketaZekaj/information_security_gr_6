"""API integration checks using isolated fixtures, never the research evidence."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location("lab", Path(__file__).resolve().parents[1] / "server.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class LabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.old_root = lab.ROOT
        lab.ROOT = cls.root
        cls.components = [{"name": "jose", "version": "test", "target_dir": "targets/node-jose"}]
        for name, value in [("components.json", cls.components), ("policy.json", {}),
                            ("testmatrix.json", [{"id": "CTRL-01"}])]:
            (cls.root / name).write_text(json.dumps(value))
        cls.evidence = cls.root / "results" / "pilot"
        cls.evidence.mkdir(parents=True)
        (cls.evidence / "run.json").write_text(json.dumps({"started_at_utc":"2026-01-01T12:00:00Z"}))
        fields = ["component", "version", "config", "test_id", "category", "expected", "actual_status", "accepted", "correct"]
        # Deliberately contradictory accepted/correct columns: HTTP status is authoritative.
        with (cls.evidence / "raw.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for case, expected, status in [("CTRL-01","accept","200"), ("ISS-MISSING","reject","200"),
                                            ("EXP-EXPIRED","reject","401"), ("NBF-MISSING","accept","401"),
                                            ("TIMEOUT","reject",""), ("CRASH","reject","500")]:
                writer.writerow(dict(component="node-jose",version="test",config="default",test_id=case,
                                     category=case.split('-')[0],expected=expected,actual_status=status,
                                     accepted="false",correct="true"))
        mock = cls.root / "results" / "mock"
        mock.mkdir()
        (mock / "raw.csv").write_text("component\nFake\n")
        cls.server = lab.ThreadingHTTPServer(("127.0.0.1", 0), lab.Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        lab.ROOT = cls.old_root
        cls.temp.cleanup()

    def setUp(self):
        with lab.LOCK:
            lab.JOB.clear()
            lab.JOB.update(status="idle", logs=[], targets={}, result=None)

    def request(self, path, body=None, headers=None):
        request = urllib.request.Request(self.base + path,
            data=json.dumps(body).encode() if body is not None else None, headers=headers or {})
        try:
            response = self.http.open(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def test_static_app_and_repository_files_are_not_exposed(self):
        self.assertEqual(self.request("/")[0], 200)
        self.assertEqual(self.request("/app.js")[0], 200)
        for path in ("/keys/private.pem", "/.git/config", "/../policy.json", "/web/server.py"):
            self.assertEqual(self.request(path)[0], 404)

    def test_state_excludes_mock_runs(self):
        status, body, _ = self.request("/api/state")
        state = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual([run["id"] for run in state["runs"]], ["pilot"])
        self.assertEqual(state["tokens"]["tokens"], [])

    def test_status_classification_and_legacy_name_normalization(self):
        status, body, _ = self.request("/api/results?run=pilot")
        rows = json.loads(body)["rows"]
        self.assertEqual(status, 200)
        self.assertEqual([r["verdict"] for r in rows], ["pass","fail","pass","fail","error","error"])
        self.assertTrue(all(r["component"]=="jose" for r in rows))

    def test_download_preserves_original_csv(self):
        status, body, headers = self.request("/api/export?run=pilot")
        self.assertEqual(status, 200)
        self.assertEqual(body, (self.evidence / "raw.csv").read_bytes())
        self.assertIn("attachment", headers["Content-Disposition"])

    def test_path_traversal_and_unknown_run_rejected(self):
        for path in ("/api/results?run=../..", "/api/export?run=missing"):
            self.assertEqual(self.request(path)[0], 400)

    def test_host_origin_and_csrf_checks(self):
        self.assertEqual(self.request("/api/state", headers={"Host":"attacker.test"})[0], 403)
        self.assertEqual(self.request("/api/generate", {})[0], 403)
        self.assertEqual(self.request("/api/generate", {}, {"X-Lab-Token":lab.CSRF,"Origin":"https://attacker.test"})[0], 403)

    def test_bad_run_inputs_are_rejected_before_process_launch(self):
        headers = {"X-Lab-Token":lab.CSRF}
        for body in ({"components":[]}, {"components":["unknown"]}, {"components":[{}]},
                     {"components":["jose","jose"]}, {"components":["jose"],"launcher":"shell"}, []):
            self.assertEqual(self.request("/api/run",body,headers)[0],400)

    def test_concurrent_operation_is_rejected(self):
        lab.JOB["status"] = "running"
        self.assertEqual(self.request("/api/generate",{}, {"X-Lab-Token":lab.CSRF})[0],409)

    def test_worker_runs_generation_and_verification_and_reports_errors(self):
        with patch.object(lab,"execute",return_value=0) as execute:
            lab.worker("generate",[],"native",None)
            self.assertEqual(lab.snapshot()["status"],"completed")
            self.assertEqual([call.args[0][1] for call in execute.call_args_list],
                             ["generator/make_keys.py","generator/generate.py","generator/verify_tokens.py"])
        with patch.object(lab,"execute",return_value=1):
            lab.worker("generate",[],"native",None)
            self.assertEqual(lab.snapshot()["status"],"failed")

    def test_partial_run_is_not_labeled_success(self):
        output = self.root / "results" / "web" / "partial"
        lab.JOB["targets"] = {"jose":{"default":"pending","hardened":"pending"}}
        with patch.object(lab,"execute",side_effect=[0,3,0]):
            lab.worker("run",["jose"],"native",output)
        self.assertEqual(lab.snapshot()["status"],"completed with issues")
        self.assertEqual(lab.snapshot()["result"],"web/partial")
        self.assertEqual(lab.snapshot()["targets"]["jose"]["default"],"not measured")


if __name__ == "__main__":
    unittest.main()
