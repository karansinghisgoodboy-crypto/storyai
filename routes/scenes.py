from flask import Blueprint,jsonify
from db.database import get_db
from routes import json_body
from services import scenes
bp=Blueprint('scenes',__name__,url_prefix='/api/projects/<int:project_id>/scenes')
@bp.get('')
def ls(project_id): return jsonify(scenes=scenes.list_scenes(get_db(),project_id))
@bp.post('')
def create(project_id): return jsonify(scene=scenes.create(get_db(),project_id,json_body())),201
@bp.get('/<int:scene_id>')
def get(project_id,scene_id): return jsonify(scene=scenes.get(get_db(),project_id,scene_id))
@bp.patch('/<int:scene_id>')
def update(project_id,scene_id): return jsonify(scene=scenes.update(get_db(),project_id,scene_id,json_body()))
@bp.put('/<int:scene_id>/characters')
def set_chars(project_id,scene_id):
    body=json_body()
    return jsonify(scene=scenes.set_characters(get_db(),project_id,scene_id,body.get('characters',[]),body.get('updated_at')))
@bp.delete('/<int:scene_id>')
def delete(project_id,scene_id): scenes.delete(get_db(),project_id,scene_id); return jsonify(deleted=scene_id)
