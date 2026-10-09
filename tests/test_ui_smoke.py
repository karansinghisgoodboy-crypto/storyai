"""Runs the simulated-browser test (tests/ui/ui_smoke.js) against a real running app.

This test is optional. It runs only if Node.js 18+ is installed and you have run
`npm install` once inside tests/ui. Otherwise pytest skips it.
"""
import shutil
import subprocess
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

UI_DIR = Path(__file__).resolve().parent / "ui"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not (UI_DIR / "node_modules" / "jsdom").exists(),
    reason="needs Node.js 18+ and `npm install` inside tests/ui (optional)",
)


def test_workspace_in_a_simulated_browser(app):
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            ["node", "ui_smoke.js", f"http://127.0.0.1:{server.server_port}"],
            cwd=UI_DIR, capture_output=True, text=True, timeout=180,
        )
    finally:
        server.shutdown()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ALL UI CHECKS PASSED" in result.stdout
