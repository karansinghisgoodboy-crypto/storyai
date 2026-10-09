"""Secrets, safe rendering, honest buttons and clean errors."""
import re
from pathlib import Path

from tests.conftest import TEST_KEY, make_project

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_FILES = [p for p in list((ROOT / "static").rglob("*")) + list((ROOT / "templates").rglob("*")) if p.is_file()]


# ---------- the API key never reaches the browser ----------

def test_gitignore_has_the_required_entries():
    lines = {line.strip() for line in (ROOT / ".gitignore").read_text().splitlines()}
    for entry in [".env", "*.db", "uploads/", "__pycache__/", ".pytest_cache/"]:
        assert entry in lines, f"{entry} missing from .gitignore"


def test_env_example_contains_no_real_key():
    text = (ROOT / ".env.example").read_text()
    assert "sk-" not in text
    for line in text.splitlines():
        if line.startswith("OPENAI_API_KEY="):
            assert line.split("=", 1)[1].strip() == ""


def test_frontend_files_never_mention_the_key():
    assert FRONTEND_FILES, "no frontend files found"
    for path in FRONTEND_FILES:
        text = path.read_text(encoding="utf-8").lower()
        assert "openai" not in text, path.name
        assert "api_key" not in text and "apikey" not in text, path.name
        assert "sk-" not in text, path.name


def test_responses_never_contain_the_key(client):
    project = make_project(client, "Secret check")
    urls = ["/", "/api/projects", f"/api/projects/{project['id']}", "/api/projects/9999",
            "/nope", "/static/js/api.js", "/static/js/app.js"]
    for url in urls:
        response = client.get(url)
        assert TEST_KEY.encode() not in response.data, url
        assert TEST_KEY not in str(response.headers), url


def test_key_is_not_stored_in_the_database(client, app):
    make_project(client, "Another")
    assert TEST_KEY.encode() not in Path(app.config["DATABASE_PATH"]).read_bytes()


# ---------- safe rendering ----------

def test_frontend_never_uses_unsafe_html_apis():
    banned = ["innerhtml", "outerhtml", "insertadjacenthtml", "document.write", "eval(", "new function"]
    for path in FRONTEND_FILES:
        if path.suffix in {".js", ".html"}:
            text = path.read_text(encoding="utf-8").lower()
            for word in banned:
                assert word not in text, f"{word} found in {path.name}"


def test_security_headers_are_set(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert client.get("/api/projects").headers["Cache-Control"] == "no-store"


# ---------- no fake buttons ----------

def test_page_has_no_hand_written_buttons():
    html = (ROOT / "templates" / "index.html").read_text().lower()
    assert "<button" not in html and "<input type=\"button\"" not in html


def test_every_button_is_made_by_the_helper_that_requires_a_handler():
    for path in (ROOT / "static" / "js").rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        if path.name == "dom.js":
            assert "Every button needs a click handler" in text
            assert "A disabled button needs a reason." in text
            continue
        assert not re.search(r"""createElement\(\s*["']button""", text), path.name
        assert not re.search(r"""Dom\.el\(\s*["']button""", text), path.name


# ---------- errors are friendly ----------

def test_unknown_api_route_returns_json(client):
    response = client.get("/api/nothing-here")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Not found."}


def test_wrong_method_returns_json(client):
    response = client.put("/api/projects")
    assert response.status_code == 405
    assert "error" in response.get_json()


def test_unexpected_errors_hide_technical_details(client, monkeypatch):
    import routes.projects as routes_projects

    def explode(db):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(routes_projects.project_service, "list_projects", explode)
    response = client.get("/api/projects")
    assert response.status_code == 500
    body = response.get_data(as_text=True)
    assert "secret internal detail" not in body and "Traceback" not in body
    assert response.get_json()["error"].startswith("Something went wrong")


def test_oversized_request_is_rejected_cleanly(client):
    response = client.post("/api/projects", data=b"x" * (9 * 1024 * 1024), content_type="application/json")
    assert response.status_code == 413
    assert response.get_json() == {"error": "That request is too large."}
