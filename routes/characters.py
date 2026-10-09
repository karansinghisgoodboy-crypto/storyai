from flask import Blueprint, jsonify, request, current_app, send_file
from db.database import get_db
from routes import json_body
from services import characters as service
from services.uploads import save_character_image

bp = Blueprint("characters", __name__, url_prefix="/api/projects/<int:project_id>/characters")

@bp.get("")
def list_characters(project_id): return jsonify(characters=service.list_characters(get_db(), project_id))

@bp.post("")
def create(project_id): return jsonify(character=service.create_character(get_db(), project_id, json_body())), 201

@bp.get("/<int:character_id>")
def get(project_id, character_id): return jsonify(character=service.get_character(get_db(), project_id, character_id))

@bp.patch("/<int:character_id>")
def update(project_id, character_id): return jsonify(character=service.update_character(get_db(), project_id, character_id, json_body()))

@bp.post("/<int:character_id>/lock")
def lock(project_id, character_id):
    data=json_body(); return jsonify(character=service.set_lock(get_db(), project_id, character_id, data.get("locked"), data.get("updated_at")))

@bp.delete("/<int:character_id>")
def delete(project_id, character_id):
    service.delete_character(get_db(), project_id, character_id, current_app.config["UPLOAD_DIR"]); return jsonify(deleted=character_id)

@bp.post("/<int:character_id>/image")
def image(project_id, character_id):
    result=save_character_image(get_db(), current_app.config["UPLOAD_DIR"], project_id, character_id, request.files.get("image"))
    return jsonify(character=result)

@bp.get("/<int:character_id>/image")
def image_file(project_id, character_id):
    row = get_db().execute(
        "SELECT a.file_path FROM characters c JOIN assets a ON a.id=c.image_id "
        "WHERE c.id=? AND c.project_id=? AND a.project_id=c.project_id AND a.kind='character'",
        (character_id, project_id),
    ).fetchone()
    if row is None: from services.errors import NotFoundError; raise NotFoundError("Character image not found.")
    from pathlib import Path
    base=Path(current_app.config["UPLOAD_DIR"]).resolve(); path=(base/row["file_path"]).resolve()
    if base not in path.parents or not path.is_file(): from services.errors import NotFoundError; raise NotFoundError("Character image not found.")
    return send_file(path, conditional=True, max_age=0)
