import pytest

from app import create_app
from db.database import connect

TEST_KEY = "fake-test-secret-value-not-a-real-key"


@pytest.fixture
def app(tmp_path):
    """A fresh app with its own temporary database and uploads folder."""
    return create_app({
        "TESTING": True,
        "DATABASE_PATH": tmp_path / "test.db",
        "UPLOAD_DIR": tmp_path / "uploads",
        "OPENAI_API_KEY": TEST_KEY,
    })


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    """A direct database connection (foreign keys ON) for checking what was stored."""
    conn = connect(app.config["DATABASE_PATH"])
    yield conn
    conn.close()


def make_project(client, title="My Story", idea=""):
    response = client.post("/api/projects", json={"title": title, "idea": idea})
    assert response.status_code == 201
    return response.get_json()["project"]
