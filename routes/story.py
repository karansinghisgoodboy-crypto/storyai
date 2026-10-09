from flask import Blueprint,jsonify
from db.database import get_db
from routes import json_body
from services import story
bp=Blueprint('story',__name__,url_prefix='/api/projects/<int:project_id>/story')
@bp.get('')
def get(project_id): return jsonify(story=story.get(get_db(),project_id))
@bp.patch('')
def update(project_id): return jsonify(story=story.update(get_db(),project_id,json_body()))
