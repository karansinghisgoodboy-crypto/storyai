from flask import Blueprint,jsonify
from db.database import get_db
from routes import json_body
from services import memory
bp=Blueprint('memory',__name__,url_prefix='/api/projects/<int:project_id>/memory')
@bp.get('')
def ls(project_id): return jsonify(memory=memory.list_items(get_db(),project_id))
@bp.post('')
def create(project_id): return jsonify(item=memory.create(get_db(),project_id,json_body())),201
@bp.patch('/<int:item_id>')
def update(project_id,item_id): return jsonify(item=memory.update(get_db(),project_id,item_id,json_body()))
@bp.post('/<int:item_id>/lock')
def lock(project_id,item_id): d=json_body(); return jsonify(item=memory.lock(get_db(),project_id,item_id,d.get('locked'),d.get('updated_at')))
@bp.delete('/<int:item_id>')
def delete(project_id,item_id): memory.delete(get_db(),project_id,item_id); return jsonify(deleted=item_id)
