from flask import Blueprint,jsonify,current_app,request,send_file
from db.database import get_db
from routes import json_body
from services import shots
from services.uploads import save_frame_image
from pathlib import Path
bp=Blueprint('shots',__name__,url_prefix='/api/projects/<int:project_id>/scenes/<int:scene_id>/shots')
@bp.get('')
def ls(project_id,scene_id): return jsonify(shots=shots.list_shots(get_db(),project_id,scene_id))
@bp.post('')
def create(project_id,scene_id): return jsonify(shot=shots.create(get_db(),project_id,scene_id,json_body())),201
@bp.patch('/<int:shot_id>')
def update(project_id,scene_id,shot_id): return jsonify(shot=shots.update(get_db(),project_id,scene_id,shot_id,json_body()))
@bp.delete('/<int:shot_id>')
def delete(project_id,scene_id,shot_id): shots.delete(get_db(),project_id,scene_id,shot_id); return jsonify(deleted=shot_id)
@bp.post('/<int:shot_id>/image')
def image(project_id,scene_id,shot_id): return jsonify(shot=save_frame_image(get_db(),current_app.config['UPLOAD_DIR'],project_id,scene_id,shot_id,request.files.get('image')))
@bp.get('/<int:shot_id>/image')
def image_file(project_id,scene_id,shot_id):
 r=get_db().execute('SELECT a.file_path FROM frames f JOIN assets a ON a.id=f.asset_id WHERE f.shot_id=? AND f.project_id=?',(shot_id,project_id)).fetchone()
 if not r: from services.errors import NotFoundError; raise NotFoundError('Storyboard image not found.')
 base=Path(current_app.config['UPLOAD_DIR']).resolve(); p=(base/r['file_path']).resolve()
 if base not in p.parents or not p.is_file(): from services.errors import NotFoundError; raise NotFoundError('Storyboard image not found.')
 return send_file(p,conditional=True,max_age=0)
