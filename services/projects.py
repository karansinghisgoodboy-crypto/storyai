"""Project business logic: create, list, open, rename, delete.

Routes stay thin and call these functions. Nothing here knows about HTTP.
"""
import logging
from pathlib import Path

from db.database import now_iso
from services.errors import ConflictError, NotFoundError, ValidationError

log = logging.getLogger(__name__)

TITLE_MAX = 120
IDEA_MAX = 500


def _clean_text(value, label, max_len, required):
    """Trim, collapse whitespace, and check length. Returns a clean string."""
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be text.")
    text = " ".join(value.split())
    if required and not text:
        raise ValidationError(f"{label} is required.")
    if len(text) > max_len:
        raise ValidationError(f"{label} must be {max_len} characters or fewer.")
    if not text.isprintable() and text:
        raise ValidationError(f"{label} contains characters that are not allowed.")
    return text


def list_projects(db):
    rows = db.execute(
        "SELECT id, title, logline, created_at, updated_at FROM projects "
        "ORDER BY updated_at DESC, id DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def get_project(db, project_id):
    row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise NotFoundError("Project not found.")
    return dict(row)


def create_project(db, title, idea=None):
    """Create a project. The optional one-line idea is saved as the logline."""
    title = _clean_text(title, "Title", TITLE_MAX, required=True)
    idea = _clean_text(idea, "Idea", IDEA_MAX, required=False)
    now = now_iso()
    with db:  # commits on success, rolls back on error
        cursor = db.execute(
            "INSERT INTO projects (title, logline, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, idea, now, now),
        )
    return get_project(db, cursor.lastrowid)


def rename_project(db, project_id, title, expected_updated_at=None):
    """Rename a project.

    If expected_updated_at is given and the project has changed since then,
    nothing is written and a ConflictError (HTTP 409) is raised.
    """
    title = _clean_text(title, "Title", TITLE_MAX, required=True)
    if expected_updated_at is not None and not isinstance(expected_updated_at, str):
        raise ValidationError("updated_at must be text.")

    now = now_iso()
    with db:
        if expected_updated_at is None:
            cursor = db.execute(
                "UPDATE projects SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, project_id),
            )
        else:
            cursor = db.execute(
                "UPDATE projects SET title = ?, updated_at = ? WHERE id = ? AND updated_at = ?",
                (title, now, project_id, expected_updated_at),
            )

    if cursor.rowcount == 0:
        get_project(db, project_id)  # raises NotFoundError if it is gone
        raise ConflictError("This project changed since you loaded it. Reload the latest version.")
    return get_project(db, project_id)


def delete_project(db, project_id, upload_dir):
    """Delete a project, all its data (foreign keys cascade) and its image files."""
    get_project(db, project_id)  # 404 if missing

    files = db.execute(
        "SELECT file_path, thumb_path FROM assets WHERE project_id = ?", (project_id,)
    ).fetchall()

    with db:
        db.execute("DELETE FROM projects WHERE id = ?", (project_id,))

    # Remove files only after the database delete succeeded.
    for row in files:
        _remove_upload(upload_dir, row["file_path"])
        _remove_upload(upload_dir, row["thumb_path"])


def _remove_upload(upload_dir, relative_path):
    """Delete one uploaded file, but never anything outside the uploads folder."""
    base = Path(upload_dir).resolve()
    target = (base / relative_path).resolve()
    if base not in target.parents:
        log.warning("Refusing to delete a file outside the uploads folder: %s", relative_path)
        return
    try:
        target.unlink(missing_ok=True)
    except OSError:
        log.warning("Could not delete uploaded file: %s", target)
