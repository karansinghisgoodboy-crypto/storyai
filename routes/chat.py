from flask import Blueprint,jsonify
from db.database import get_db
from routes import json_body
from services import chat,ai_extract,proposals
from services.errors import ValidationError
bp=Blueprint('chat',__name__,url_prefix='/api/projects/<int:project_id>')
@bp.get('/chat')
def history(project_id): return jsonify(messages=chat.history(get_db(),project_id))
@bp.post('/chat')
def send(project_id):
 d=json_body(); return jsonify(**chat.send(get_db(),project_id,d.get('message',''),d.get('search_mode',False)))
@bp.post('/suggest')
def suggest(project_id):
 d=json_body(); arr=ai_extract.suggest(get_db(),project_id,d.get('text','')); made=[]
 if not isinstance(arr,list): raise ValidationError('The AI returned invalid suggestions. Please try again.')
 for proposal in arr: proposals.validate(get_db(),project_id,proposal)
 for proposal in arr: made.append(proposals.create(get_db(),project_id,proposal))
 return jsonify(proposals=made)
