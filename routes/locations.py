from pathlib import Path

from flask import Blueprint, jsonify, current_app, request, send_file

from db.database import get_db
from routes import json_body
from services import locations
from services.uploads import save_generic_image

bp=Blueprint('locations',__name__,url_prefix='/api/projects/<int:project_id>/locations')
@bp.get('')
def ls(project_id): return jsonify(locations=locations.list_locations(get_db(),project_id))
@bp.post('')
def create(project_id): return jsonify(location=locations.create(get_db(),project_id,json_body())),201
@bp.patch('/<int:location_id>')
def update(project_id,location_id): return jsonify(location=locations.update(get_db(),project_id,location_id,json_body()))
@bp.post('/<int:location_id>/lock')
def lock(project_id,location_id):
 d=json_body(); return jsonify(location=locations.set_lock(get_db(),project_id,location_id,d.get('locked'),d.get('updated_at')))
@bp.delete('/<int:location_id>')
def delete(project_id,location_id): locations.delete(get_db(),project_id,location_id,current_app.config['UPLOAD_DIR']); return jsonify(deleted=location_id)
@bp.post('/<int:location_id>/image')
def image(project_id,location_id): return jsonify(location=save_generic_image(get_db(),current_app.config['UPLOAD_DIR'],project_id,'location',location_id,request.files.get('image')))
@bp.get('/<int:location_id>/image')
def image_file(project_id,location_id):
    row = get_db().execute(
        "SELECT a.file_path FROM locations l JOIN assets a ON a.id=l.image_id "
        "WHERE l.id=? AND l.project_id=? AND a.project_id=l.project_id AND a.kind='location'",
        (location_id, project_id),
    ).fetchone()
    if row is None:
        from services.errors import NotFoundError
        raise NotFoundError("Location image not found.")
    base = Path(current_app.config["UPLOAD_DIR"]).resolve()
    path = (base / row["file_path"]).resolve()
    if base not in path.parents or not path.is_file():
        from services.errors import NotFoundError
        raise NotFoundError("Location image not found.")
    return send_file(path, conditional=True, max_age=0)
