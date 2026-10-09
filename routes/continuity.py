from flask import Blueprint,jsonify
from db.database import get_db
from routes import json_body
from services import continuity
bp=Blueprint('continuity',__name__,url_prefix='/api/projects/<int:project_id>/continuity')
@bp.post('/run')
def run(project_id): return jsonify(issues=continuity.run(get_db(),project_id))
@bp.get('')
def ls(project_id): return jsonify(issues=continuity.list_issues(get_db(),project_id))
@bp.post('/<int:issue_id>/status')
def status(project_id,issue_id): return jsonify(issue=continuity.set_status(get_db(),project_id,issue_id,json_body().get('status')))
