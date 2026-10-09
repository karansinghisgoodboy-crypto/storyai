"""Character business logic for Step 6."""
import json
from db.database import now_iso
from services.errors import ConflictError, NotFoundError, ValidationError

FIELDS = ["name","role","age","build","hair","face","appearance","default_outfit","distinguishing_marks","personality","backstory","voice","abilities"]
MAX = {"name":120,"role":120,"age":40,"build":200,"hair":200,"face":300,"appearance":1000,"default_outfit":500,"distinguishing_marks":500,"personality":1000,"backstory":4000,"voice":500,"abilities":1500}


def _text(value, field):
    if value is None: value = ""
    if not isinstance(value, str): raise ValidationError(f"{field} must be text.")
    value = value.strip()
    if len(value) > MAX[field]: raise ValidationError(f"{field} must be {MAX[field]} characters or fewer.")
    return value


def _project_exists(db, project_id):
    if db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone() is None:
        raise NotFoundError("Project not found.")


def _row(row):
    d = dict(row)
    d["locked"] = bool(d["locked"])
    return d


def list_characters(db, project_id):
    _project_exists(db, project_id)
    return [_row(r) for r in db.execute("SELECT * FROM characters WHERE project_id=? ORDER BY id", (project_id,)).fetchall()]


def get_character(db, project_id, character_id):
    _project_exists(db, project_id)
    row = db.execute("SELECT * FROM characters WHERE id=? AND project_id=?", (character_id, project_id)).fetchone()
    if row is None: raise NotFoundError("Character not found.")
    return _row(row)


def create_character(db, project_id, data):
    if isinstance(project_id, bool) or not isinstance(project_id, int):
        raise ValidationError("Project ID must be an integer.")
    _project_exists(db, project_id)
    if not isinstance(data, dict): raise ValidationError("Character data must be an object.")
    vals = [_text(data.get(f), f) for f in FIELDS]
    if not vals[0]: raise ValidationError("Name is required.")
    now = now_iso()
    cols = ", ".join(["project_id"] + FIELDS + ["created_at","updated_at"])
    qs = ", ".join(["?"] * (len(FIELDS)+3))
    with db:
        cur = db.execute(
            f"INSERT INTO characters ({cols}) VALUES ({qs})",
            [project_id] + vals + [now, now],
        )
    return get_character(db, project_id, cur.lastrowid)


def update_character(db, project_id, character_id, data):
    _project_exists(db, project_id)
    if not isinstance(data, dict): raise ValidationError("Character data must be an object.")
    row = db.execute("SELECT * FROM characters WHERE id=? AND project_id=?", (character_id, project_id)).fetchone()
    if row is None: raise NotFoundError("Character not found.")
    if row["locked"]: raise ConflictError("This character is locked. Unlock it before editing.")
    expected = data.get("updated_at")
    if expected is not None and not isinstance(expected, str): raise ValidationError("updated_at must be text.")
    vals = [_text(data.get(f, row[f]), f) for f in FIELDS]
    if not vals[0]: raise ValidationError("Name is required.")
    now = now_iso()
    where = "id=? AND project_id=? AND locked=0"
    params = vals + [now, character_id, project_id]
    if expected is not None:
        where += " AND updated_at=?"; params.append(expected)
    with db:
        cur = db.execute(f"UPDATE characters SET {', '.join(f+'=?' for f in FIELDS)}, updated_at=? WHERE {where}", params)
    if cur.rowcount == 0:
        raise ConflictError("This character changed since you loaded it. Reload the latest version.")
    return get_character(db, project_id, character_id)


def set_lock(db, project_id, character_id, locked, expected_updated_at=None):
    _project_exists(db, project_id)
    if not isinstance(locked, bool): raise ValidationError("locked must be true or false.")
    row = db.execute("SELECT * FROM characters WHERE id=? AND project_id=?", (character_id, project_id)).fetchone()
    if row is None: raise NotFoundError("Character not found.")
    if expected_updated_at is not None and row["updated_at"] != expected_updated_at: raise ConflictError("This character changed since you loaded it. Reload the latest version.")
    now=now_iso()
    with db: db.execute("UPDATE characters SET locked=?, updated_at=? WHERE id=? AND project_id=?", (int(locked),now,character_id,project_id))
    return get_character(db, project_id, character_id)


def delete_character(db, project_id, character_id, upload_dir=None):
    _project_exists(db, project_id)
    row = db.execute("SELECT locked FROM characters WHERE id=? AND project_id=?", (character_id, project_id)).fetchone()
    if row is None: raise NotFoundError("Character not found.")
    if row["locked"]: raise ConflictError("This character is locked. Unlock it before deleting.")
    asset = db.execute(
        "SELECT a.id, a.file_path, a.thumb_path FROM assets a "
        "JOIN characters c ON c.image_id=a.id "
        "WHERE c.id=? AND c.project_id=? AND a.project_id=c.project_id AND a.kind='character'",
        (character_id, project_id),
    ).fetchone()
    deleted_asset = False
    with db:
        deleted = db.execute(
            "DELETE FROM characters WHERE id=? AND project_id=? AND locked=0",
            (character_id, project_id),
        )
        if deleted.rowcount != 1:
            raise ConflictError("This character is locked or changed. Reload it before deleting.")
        if asset and db.execute(
            "SELECT 1 FROM characters WHERE image_id=? LIMIT 1",
            (asset["id"],),
        ).fetchone() is None:
            removed = db.execute(
                "DELETE FROM assets WHERE id=? AND project_id=? AND kind='character'",
                (asset["id"], project_id),
            )
            deleted_asset = removed.rowcount == 1
    if asset and deleted_asset and upload_dir:
        import logging
        from pathlib import Path

        base = Path(upload_dir).resolve()
        for rel in (asset["file_path"], asset["thumb_path"]):
            target = (base / rel).resolve()
            if base not in target.parents:
                continue
            try:
                target.unlink(missing_ok=True)
            except OSError:
                logging.getLogger(__name__).warning(
                    "Could not remove character image file %s", target, exc_info=True
                )
