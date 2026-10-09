"""The database itself: tables, the six approved fixes, foreign keys and constraints."""
import sqlite3

import pytest

from tests.conftest import make_project

EXPECTED_TABLES = {
    "projects", "chat_messages", "memory_items", "characters", "locations", "scenes",
    "scene_characters", "shots", "frames", "assets", "proposals", "continuity_issues",
    "search_log",
}


def columns(db, table):
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}


@pytest.fixture
def pid(client):
    return make_project(client, "Schema test")["id"]


# ---------- structure ----------

def test_all_tables_exist(db):
    names = {r["name"] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert EXPECTED_TABLES <= names


def test_foreign_keys_are_switched_on(db):
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_fix_1_shots_have_lighting(db):
    assert "lighting" in columns(db, "shots")


def test_fix_2_search_log_table(db):
    assert {"project_id", "message_id", "query", "created_at"} <= columns(db, "search_log")


def test_fix_3_projects_have_rolling_summary_columns(db):
    assert {"summary_text", "summary_upto_message_id"} <= columns(db, "projects")


def test_fix_4_continuity_issue_fingerprint(db):
    assert "fingerprint" in columns(db, "continuity_issues")


def test_fix_6_character_appearance_columns(db):
    needed = {"name", "role", "age", "build", "hair", "face", "appearance", "default_outfit",
              "distinguishing_marks", "personality", "backstory", "voice", "abilities",
              "image_id", "locked"}
    assert needed <= columns(db, "characters")


def test_every_project_owned_table_has_project_id_and_timestamps(db):
    for table in ["chat_messages", "memory_items", "assets", "characters", "locations",
                  "scenes", "shots", "frames", "proposals", "continuity_issues", "search_log"]:
        assert "project_id" in columns(db, table), table
    for table in ["projects", "memory_items", "characters", "locations", "scenes", "shots",
                  "frames", "continuity_issues"]:
        assert {"created_at", "updated_at"} <= columns(db, table), table


def test_schema_can_run_twice(app):
    from db.database import init_db
    init_db(app)  # must not fail or wipe anything
    init_db(app)


# ---------- foreign keys ----------

def test_cannot_reference_a_missing_project(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO characters (project_id, name) VALUES (999, 'Ghost')")


def test_cannot_reference_a_missing_scene_or_character(db, pid):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO shots (project_id, scene_id, order_no) VALUES (?, 999, 1)", (pid,))
    scene = db.execute("INSERT INTO scenes (project_id, order_no) VALUES (?, 1)", (pid,)).lastrowid
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO scene_characters (scene_id, character_id) VALUES (?, 999)", (scene,))


def test_deleting_a_character_removes_its_scene_links(db, pid):
    scene = db.execute("INSERT INTO scenes (project_id, order_no) VALUES (?, 1)", (pid,)).lastrowid
    char = db.execute("INSERT INTO characters (project_id, name) VALUES (?, 'A')", (pid,)).lastrowid
    db.execute("INSERT INTO scene_characters (scene_id, character_id) VALUES (?, ?)", (scene, char))
    db.execute("DELETE FROM characters WHERE id = ?", (char,))
    assert db.execute("SELECT COUNT(*) FROM scene_characters").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM scenes WHERE id = ?", (scene,)).fetchone()[0] == 1


def test_deleting_a_location_clears_the_scene_location(db, pid):
    loc = db.execute("INSERT INTO locations (project_id, name) VALUES (?, 'Roof')", (pid,)).lastrowid
    scene = db.execute("INSERT INTO scenes (project_id, order_no, location_id) VALUES (?, 1, ?)", (pid, loc)).lastrowid
    db.execute("DELETE FROM locations WHERE id = ?", (loc,))
    assert db.execute("SELECT location_id FROM scenes WHERE id = ?", (scene,)).fetchone()[0] is None


def test_deleting_an_asset_clears_image_links(db, pid):
    asset = db.execute("INSERT INTO assets (project_id, kind, file_path, thumb_path) VALUES (?, 'character', 'a', 'b')", (pid,)).lastrowid
    char = db.execute("INSERT INTO characters (project_id, name, image_id) VALUES (?, 'A', ?)", (pid, asset)).lastrowid
    db.execute("DELETE FROM assets WHERE id = ?", (asset,))
    assert db.execute("SELECT image_id FROM characters WHERE id = ?", (char,)).fetchone()[0] is None


def test_deleting_a_shot_removes_its_frame(db, pid):
    scene = db.execute("INSERT INTO scenes (project_id, order_no) VALUES (?, 1)", (pid,)).lastrowid
    shot = db.execute("INSERT INTO shots (project_id, scene_id, order_no) VALUES (?, ?, 1)", (pid, scene)).lastrowid
    db.execute("INSERT INTO frames (project_id, shot_id) VALUES (?, ?)", (pid, shot))
    db.execute("DELETE FROM shots WHERE id = ?", (shot,))
    assert db.execute("SELECT COUNT(*) FROM frames").fetchone()[0] == 0


def test_a_shot_can_only_have_one_frame(db, pid):
    scene = db.execute("INSERT INTO scenes (project_id, order_no) VALUES (?, 1)", (pid,)).lastrowid
    shot = db.execute("INSERT INTO shots (project_id, scene_id, order_no) VALUES (?, ?, 1)", (pid, scene)).lastrowid
    db.execute("INSERT INTO frames (project_id, shot_id) VALUES (?, ?)", (pid, shot))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO frames (project_id, shot_id) VALUES (?, ?)", (pid, shot))


# ---------- constraints ----------

BAD_ROWS = [
    ("blank project title", "INSERT INTO projects (title) VALUES ('   ')"),
    ("bad chat role", "INSERT INTO chat_messages (project_id, role, content) VALUES ({p}, 'system', 'x')"),
    ("bad memory kind", "INSERT INTO memory_items (project_id, kind, content) VALUES ({p}, 'opinion', 'x')"),
    ("empty memory content", "INSERT INTO memory_items (project_id, kind, content) VALUES ({p}, 'fact', '  ')"),
    ("locked must be 0 or 1", "INSERT INTO memory_items (project_id, kind, content, locked) VALUES ({p}, 'fact', 'x', 2)"),
    ("blank character name", "INSERT INTO characters (project_id, name) VALUES ({p}, '')"),
    ("blank location name", "INSERT INTO locations (project_id, name) VALUES ({p}, '')"),
    ("bad scene status", "INSERT INTO scenes (project_id, order_no, status) VALUES ({p}, 1, 'finished')"),
    ("bad asset kind", "INSERT INTO assets (project_id, kind, file_path, thumb_path) VALUES ({p}, 'video', 'a', 'b')"),
    ("bad proposal type", "INSERT INTO proposals (project_id, type, action) VALUES ({p}, 'scenery', 'add')"),
    ("bad proposal action", "INSERT INTO proposals (project_id, type, action) VALUES ({p}, 'character', 'delete')"),
    ("bad proposal status", "INSERT INTO proposals (project_id, type, action, status) VALUES ({p}, 'character', 'add', 'maybe')"),
    ("update proposal needs a target", "INSERT INTO proposals (project_id, type, action) VALUES ({p}, 'character', 'update')"),
    ("bad issue type", "INSERT INTO continuity_issues (project_id, type, description, fingerprint) VALUES ({p}, 'vibes', 'x', 'f')"),
    ("bad issue severity", "INSERT INTO continuity_issues (project_id, type, severity, description, fingerprint) VALUES ({p}, 'timeline', 'huge', 'x', 'f')"),
    ("bad issue status", "INSERT INTO continuity_issues (project_id, type, status, description, fingerprint) VALUES ({p}, 'timeline', 'ignored', 'x', 'f')"),
]


@pytest.mark.parametrize("label,sql", BAD_ROWS, ids=[b[0] for b in BAD_ROWS])
def test_database_rejects_bad_rows(db, pid, label, sql):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql.format(p=pid))


def test_valid_proposal_defaults_to_pending(db, pid):
    row_id = db.execute("INSERT INTO proposals (project_id, type, action, payload) VALUES (?, 'character', 'add', '{}')", (pid,)).lastrowid
    assert db.execute("SELECT status FROM proposals WHERE id = ?", (row_id,)).fetchone()[0] == "pending"


def test_same_issue_fingerprint_cannot_repeat_in_one_project(db, client, pid):
    db.execute("INSERT INTO continuity_issues (project_id, type, description, fingerprint) VALUES (?, 'timeline', 'x', 'abc')", (pid,))
    db.commit()  # release the write lock before the API writes below
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO continuity_issues (project_id, type, description, fingerprint) VALUES (?, 'timeline', 'y', 'abc')", (pid,))
    db.rollback()  # the failed insert left a transaction open; close it before the API writes
    other = make_project(client, "Other project")["id"]  # same fingerprint is fine in another project
    db.execute("INSERT INTO continuity_issues (project_id, type, description, fingerprint) VALUES (?, 'timeline', 'x', 'abc')", (other,))
