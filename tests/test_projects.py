"""Project CRUD, persistence, rename conflicts and delete clean-up."""
import pytest

from app import create_app
from tests.conftest import make_project

# Every table that belongs to a project.
PROJECT_TABLES = [
    "chat_messages", "memory_items", "assets", "characters", "locations",
    "scenes", "shots", "frames", "proposals", "continuity_issues", "search_log",
]


# ---------- create ----------

def test_create_project(client):
    response = client.post("/api/projects", json={"title": "  Night   Train ", "idea": "A thief boards the wrong train."})
    assert response.status_code == 201
    project = response.get_json()["project"]
    assert project["title"] == "Night Train"  # trimmed and tidied
    assert project["logline"] == "A thief boards the wrong train."
    assert project["id"] > 0
    assert project["created_at"] and project["updated_at"]


def test_create_without_idea_is_ok(client):
    assert make_project(client, "No idea yet")["logline"] == ""


@pytest.mark.parametrize("body", [
    {}, {"title": ""}, {"title": "    "}, {"title": None}, {"title": 123}, {"title": ["x"]},
])
def test_create_requires_a_title(client, body):
    response = client.post("/api/projects", json=body)
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_create_title_length_limit(client):
    assert client.post("/api/projects", json={"title": "a" * 120}).status_code == 201
    assert client.post("/api/projects", json={"title": "a" * 121}).status_code == 400


def test_create_idea_length_limit(client):
    response = client.post("/api/projects", json={"title": "ok", "idea": "x" * 501})
    assert response.status_code == 400


def test_create_rejects_control_characters(client):
    response = client.post("/api/projects", json={"title": "bad\x00title"})
    assert response.status_code == 400


def test_create_needs_json_object(client):
    assert client.post("/api/projects", data="not json").status_code == 400
    assert client.post("/api/projects", json=["a list"]).status_code == 400


def test_html_in_title_is_stored_as_plain_text(client):
    project = make_project(client, "<script>alert(1)</script>")
    assert project["title"] == "<script>alert(1)</script>"  # escaping happens in the browser (textContent)


# ---------- list and open ----------

def test_list_projects_newest_activity_first(client):
    first = make_project(client, "First")
    second = make_project(client, "Second")
    titles = [p["title"] for p in client.get("/api/projects").get_json()["projects"]]
    assert titles == ["Second", "First"]

    client.patch(f"/api/projects/{first['id']}", json={"title": "First (renamed)"})
    titles = [p["title"] for p in client.get("/api/projects").get_json()["projects"]]
    assert titles == ["First (renamed)", "Second"]
    assert second["id"] != first["id"]


def test_open_project(client):
    created = make_project(client, "Open me", "An idea")
    response = client.get(f"/api/projects/{created['id']}")
    assert response.status_code == 200
    project = response.get_json()["project"]
    assert project["title"] == "Open me"
    assert project["logline"] == "An idea"


def test_open_missing_project_is_404(client):
    response = client.get("/api/projects/9999")
    assert response.status_code == 404
    assert response.get_json()["error"] == "Project not found."


# ---------- persistence ----------

def test_projects_survive_an_app_restart(tmp_path):
    config = {
        "TESTING": True,
        "DATABASE_PATH": tmp_path / "persist.db",
        "UPLOAD_DIR": tmp_path / "uploads",
    }
    first_run = create_app(config).test_client()
    created = make_project(first_run, "Still here tomorrow", "Saved on disk")

    second_run = create_app(config).test_client()  # a brand new app, same database file
    projects = second_run.get("/api/projects").get_json()["projects"]
    assert [p["title"] for p in projects] == ["Still here tomorrow"]
    assert second_run.get(f"/api/projects/{created['id']}").get_json()["project"]["logline"] == "Saved on disk"


# ---------- rename ----------

def test_rename_project(client):
    project = make_project(client, "Old name")
    response = client.patch(f"/api/projects/{project['id']}", json={"title": "  New   name "})
    assert response.status_code == 200
    renamed = response.get_json()["project"]
    assert renamed["title"] == "New name"
    assert renamed["updated_at"] > project["updated_at"]
    assert renamed["created_at"] == project["created_at"]


@pytest.mark.parametrize("title", ["", "   ", None, 5, "a" * 121])
def test_rename_rejects_bad_titles(client, title):
    project = make_project(client, "Keep me")
    response = client.patch(f"/api/projects/{project['id']}", json={"title": title})
    assert response.status_code == 400
    assert client.get(f"/api/projects/{project['id']}").get_json()["project"]["title"] == "Keep me"


def test_rename_missing_project_is_404(client):
    assert client.patch("/api/projects/9999", json={"title": "x"}).status_code == 404


def test_rename_with_current_updated_at_works(client):
    project = make_project(client, "A")
    response = client.patch(
        f"/api/projects/{project['id']}", json={"title": "B", "updated_at": project["updated_at"]}
    )
    assert response.status_code == 200


def test_rename_with_stale_updated_at_is_409_and_changes_nothing(client):
    project = make_project(client, "Original")
    client.patch(f"/api/projects/{project['id']}", json={"title": "Changed elsewhere"})

    response = client.patch(
        f"/api/projects/{project['id']}",
        json={"title": "My late edit", "updated_at": project["updated_at"]},  # old timestamp
    )
    assert response.status_code == 409
    assert "Reload" in response.get_json()["error"]
    assert client.get(f"/api/projects/{project['id']}").get_json()["project"]["title"] == "Changed elsewhere"


# ---------- delete ----------

def test_delete_project(client):
    project = make_project(client, "Delete me")
    response = client.delete(f"/api/projects/{project['id']}")
    assert response.status_code == 200
    assert response.get_json() == {"deleted": project["id"]}
    assert client.get(f"/api/projects/{project['id']}").status_code == 404
    assert client.get("/api/projects").get_json()["projects"] == []


def test_delete_missing_project_is_404(client):
    assert client.delete("/api/projects/9999").status_code == 404


def _seed_everything(db, project_id, upload_dir):
    """Put one row in every project table, plus real files on disk."""
    (upload_dir / "characters").mkdir(parents=True, exist_ok=True)
    (upload_dir / "panels").mkdir(parents=True, exist_ok=True)
    files = {
        "characters/a.jpg": upload_dir / "characters" / "a.jpg",
        "characters/a_thumb.jpg": upload_dir / "characters" / "a_thumb.jpg",
        "panels/p.png": upload_dir / "panels" / "p.png",
        "panels/p_thumb.png": upload_dir / "panels" / "p_thumb.png",
    }
    for path in files.values():
        path.write_bytes(b"fake image bytes")

    q = db.execute
    message_id = q("INSERT INTO chat_messages (project_id, role, content) VALUES (?, 'user', 'hi')", (project_id,)).lastrowid
    q("UPDATE projects SET summary_upto_message_id = ? WHERE id = ?", (message_id, project_id))
    q("INSERT INTO memory_items (project_id, kind, content) VALUES (?, 'fact', 'Karan has black hair')", (project_id,))
    char_asset = q("INSERT INTO assets (project_id, kind, file_path, thumb_path) VALUES (?, 'character', 'characters/a.jpg', 'characters/a_thumb.jpg')", (project_id,)).lastrowid
    panel_asset = q("INSERT INTO assets (project_id, kind, file_path, thumb_path) VALUES (?, 'panel', 'panels/p.png', 'panels/p_thumb.png')", (project_id,)).lastrowid
    character_id = q("INSERT INTO characters (project_id, name, image_id) VALUES (?, 'Karan', ?)", (project_id, char_asset)).lastrowid
    location_id = q("INSERT INTO locations (project_id, name) VALUES (?, 'Station')", (project_id,)).lastrowid
    scene_id = q("INSERT INTO scenes (project_id, order_no, location_id) VALUES (?, 1, ?)", (project_id, location_id)).lastrowid
    q("INSERT INTO scene_characters (scene_id, character_id, outfit_state) VALUES (?, ?, 'torn jacket')", (scene_id, character_id))
    shot_id = q("INSERT INTO shots (project_id, scene_id, order_no, lighting) VALUES (?, ?, 1, 'dim')", (project_id, scene_id)).lastrowid
    q("INSERT INTO frames (project_id, shot_id, asset_id) VALUES (?, ?, ?)", (project_id, shot_id, panel_asset))
    q("INSERT INTO proposals (project_id, type, action, payload) VALUES (?, 'character', 'add', '{}')", (project_id,))
    q("INSERT INTO continuity_issues (project_id, scene_id, type, description, fingerprint) VALUES (?, ?, 'structure', 'x', 'fp1')", (project_id, scene_id))
    q("INSERT INTO search_log (project_id, message_id, query) VALUES (?, ?, 'train timetable')", (project_id, message_id))
    db.commit()
    return files


def test_delete_removes_all_project_data_and_files(client, db, app):
    project = make_project(client, "Full project")
    other = make_project(client, "Bystander")
    upload_dir = app.config["UPLOAD_DIR"]
    files = _seed_everything(db, project["id"], upload_dir)

    # A file belonging to another project must survive.
    (upload_dir / "locations").mkdir(parents=True, exist_ok=True)
    keep = upload_dir / "locations" / "keep.jpg"
    keep.write_bytes(b"x")
    db.execute("INSERT INTO assets (project_id, kind, file_path, thumb_path) VALUES (?, 'location', 'locations/keep.jpg', 'locations/keep.jpg')", (other["id"],))
    db.commit()

    assert client.delete(f"/api/projects/{project['id']}").status_code == 200

    for table in PROJECT_TABLES:
        count = db.execute(f"SELECT COUNT(*) FROM {table} WHERE project_id = ?", (project["id"],)).fetchone()[0]
        assert count == 0, f"{table} still has rows for the deleted project"
    assert db.execute("SELECT COUNT(*) FROM scene_characters").fetchone()[0] == 0
    for path in files.values():
        assert not path.exists(), f"{path.name} should have been deleted"

    # The other project and its file are untouched.
    assert keep.exists()
    assert db.execute("SELECT COUNT(*) FROM assets WHERE project_id = ?", (other["id"],)).fetchone()[0] == 1
    assert client.get(f"/api/projects/{other['id']}").status_code == 200


def test_delete_never_removes_files_outside_uploads(client, db, app, tmp_path):
    project = make_project(client, "Sneaky")
    outside = tmp_path / "outside.txt"
    outside.write_text("do not delete")
    db.execute("INSERT INTO assets (project_id, kind, file_path, thumb_path) VALUES (?, 'panel', '../outside.txt', '../outside.txt')", (project["id"],))
    db.commit()

    assert client.delete(f"/api/projects/{project['id']}").status_code == 200
    assert outside.exists()


def test_delete_with_missing_files_still_succeeds(client, db):
    project = make_project(client, "Files already gone")
    db.execute("INSERT INTO assets (project_id, kind, file_path, thumb_path) VALUES (?, 'panel', 'panels/gone.png', 'panels/gone_t.png')", (project["id"],))
    db.commit()
    assert client.delete(f"/api/projects/{project['id']}").status_code == 200
