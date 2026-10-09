"""Image validation and persistence for characters, locations, and storyboard frames."""
import logging
import secrets
import warnings
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from db.database import now_iso
from services.errors import ConflictError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)
MAX_BYTES = 5 * 1024 * 1024
EXTENSION_FORMATS = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".webp": "WEBP",
}
FORMAT_MIMES = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}


def _process(upload_dir, subfolder, kind, project_id, file_storage):
    if not file_storage or not file_storage.filename:
        raise ValidationError("Please choose an image.")

    expected_format = EXTENSION_FORMATS.get(Path(file_storage.filename).suffix.lower())
    if expected_format is None:
        raise ValidationError("Only PNG, JPG or WEBP images are allowed.")
    if file_storage.mimetype != FORMAT_MIMES[expected_format]:
        raise ValidationError("The image file type does not match its extension.")

    data = file_storage.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValidationError("Image must be 5 MB or smaller.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
            image.verify()
            image = Image.open(BytesIO(data))
            image.load()
        if image.format != expected_format:
            raise ValidationError("The image file type does not match its extension.")
    except ValidationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        EOFError,
        ValueError,
    ):
        raise ValidationError("The uploaded file is not a valid image.")

    base = Path(upload_dir).resolve()
    folder = base / subfolder
    folder.mkdir(parents=True, exist_ok=True)
    stem = secrets.token_hex(16)
    main_rel = f"{subfolder}/{stem}.jpg"
    thumb_rel = f"{subfolder}/{stem}_thumb.jpg"
    main = folder / f"{stem}.jpg"
    thumb = folder / f"{stem}_thumb.jpg"

    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    try:
        image.save(main, "JPEG", quality=90, optimize=True)
        thumbnail = image.copy()
        thumbnail.thumbnail((400, 400), Image.Resampling.LANCZOS)
        thumbnail.save(thumb, "JPEG", quality=85, optimize=True)
    except OSError:
        remove_asset_files(base, (main_rel, thumb_rel))
        raise

    return main_rel, thumb_rel, now_iso()


def remove_asset_files(upload_dir, paths):
    base = Path(upload_dir).resolve()
    for relative_path in paths:
        if not relative_path:
            continue
        target = (base / relative_path).resolve()
        if base not in target.parents:
            continue
        try:
            target.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove uploaded asset file %s", target, exc_info=True)


def save_generic_image(db, upload_dir, project_id, kind, item_id, file_storage):
    tables = {"location": "locations", "character": "characters"}
    if kind not in tables:
        raise ValidationError("Unsupported image type.")

    table = tables[kind]
    row = db.execute(
        f"SELECT * FROM {table} WHERE id=? AND project_id=?",
        (item_id, project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError(f"{kind.title()} not found.")
    if row["locked"]:
        raise ConflictError(f"This {kind} is locked. Unlock it before changing its image.")

    subfolder = "locations" if kind == "location" else "characters"
    main, thumb, now = _process(upload_dir, subfolder, kind, project_id, file_storage)
    old = (
        db.execute(
            "SELECT id, file_path, thumb_path FROM assets "
            "WHERE id=? AND project_id=? AND kind=?",
            (row["image_id"], project_id, kind),
        ).fetchone()
        if row["image_id"]
        else None
    )

    deleted_old = False
    try:
        with db:
            asset_id = db.execute(
                "INSERT INTO assets(project_id,kind,file_path,thumb_path,created_at) "
                "VALUES(?,?,?,?,?)",
                (project_id, kind, main, thumb, now),
            ).lastrowid
            updated = db.execute(
                f"UPDATE {table} SET image_id=?,updated_at=? "
                "WHERE id=? AND project_id=? AND locked=0",
                (asset_id, now, item_id, project_id),
            )
            if updated.rowcount != 1:
                raise ConflictError(
                    f"This {kind} is locked or changed. Reload it before changing its image."
                )
            if old and db.execute(
                f"SELECT 1 FROM {table} WHERE image_id=? AND id<>?",
                (old["id"], item_id),
            ).fetchone() is None:
                db.execute("DELETE FROM assets WHERE id=?", (old["id"],))
                deleted_old = True
    except Exception:
        remove_asset_files(upload_dir, (main, thumb))
        raise

    if deleted_old:
        remove_asset_files(upload_dir, (old["file_path"], old["thumb_path"]))

    return dict(
        db.execute(
            f"SELECT * FROM {table} WHERE id=? AND project_id=?",
            (item_id, project_id),
        ).fetchone()
    )


def save_character_image(db, upload_dir, project_id, character_id, file_storage):
    return save_generic_image(
        db, upload_dir, project_id, "character", character_id, file_storage
    )


def save_frame_image(db, upload_dir, project_id, scene_id, shot_id, file_storage):
    row = db.execute(
        "SELECT * FROM shots WHERE id=? AND scene_id=? AND project_id=?",
        (shot_id, scene_id, project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("Shot not found.")

    main, thumb, now = _process(upload_dir, "panels", "panel", project_id, file_storage)
    old = db.execute(
        "SELECT fr.id,fr.asset_id,a.file_path,a.thumb_path "
        "FROM frames fr LEFT JOIN assets a ON a.id=fr.asset_id WHERE fr.shot_id=?",
        (shot_id,),
    ).fetchone()
    deleted_old = False
    try:
        with db:
            asset_id = db.execute(
                "INSERT INTO assets(project_id,kind,file_path,thumb_path,created_at) "
                "VALUES(?,?,?,?,?)",
                (project_id, "panel", main, thumb, now),
            ).lastrowid
            if old:
                db.execute(
                    "UPDATE frames SET asset_id=?,updated_at=? WHERE id=?",
                    (asset_id, now, old["id"]),
                )
            else:
                db.execute(
                    "INSERT INTO frames(project_id,shot_id,asset_id,created_at,updated_at) "
                    "VALUES(?,?,?,?,?)",
                    (project_id, shot_id, asset_id, now, now),
                )
            if old and old["asset_id"]:
                db.execute("DELETE FROM assets WHERE id=?", (old["asset_id"],))
                deleted_old = True
    except Exception:
        remove_asset_files(upload_dir, (main, thumb))
        raise

    if old and deleted_old:
        remove_asset_files(upload_dir, (old["file_path"], old["thumb_path"]))

    return dict(db.execute("SELECT * FROM shots WHERE id=?", (shot_id,)).fetchone())
