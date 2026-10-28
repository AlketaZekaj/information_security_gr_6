"""Regression: a Windows virtualenv target must release its port between modes."""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest

spec = importlib.util.spec_from_file_location("harness_run", Path(__file__).resolve().parents[2] / "harness" / "run.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class NativeCleanupTests(unittest.TestCase):
    def test_owned_python_server_releases_port_between_configurations(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        for _ in range(2):
            process = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                deadline = time.monotonic() + 5
                while not harness.port_in_use(port) and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(harness.port_in_use(port), "test server did not become ready")
            finally:
                harness.stop_native_process(process, port)
            self.assertIsNotNone(process.poll())
            self.assertFalse(harness.port_in_use(port), "target child still holds its port")


if __name__ == "__main__":
    unittest.main()
