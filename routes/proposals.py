from flask import Blueprint,jsonify
from db.database import get_db
from routes import json_body
from services import proposals
bp=Blueprint('proposals',__name__,url_prefix='/api/projects/<int:project_id>/proposals')
@bp.get('')
def ls(project_id): return jsonify(proposals=proposals.list_pending(get_db(),project_id))
@bp.post('')
def create(project_id): return jsonify(proposal=proposals.create(get_db(),project_id,json_body())),201
@bp.post('/<int:proposal_id>/resolve')
def resolve(project_id,proposal_id): return jsonify(proposal=proposals.resolve(get_db(),project_id,proposal_id,json_body().get('accept')))
