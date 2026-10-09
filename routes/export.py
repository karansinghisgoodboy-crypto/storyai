from flask import Blueprint,send_file,current_app
from db.database import get_db
from services.exporter import json_export,html_export
from services.common import project_exists
from io import BytesIO
bp=Blueprint('export',__name__,url_prefix='/api/projects/<int:project_id>/export')
@bp.get('/json')
def json_file(project_id):
 data=json_export(get_db(),project_id,current_app.config['UPLOAD_DIR']).encode(); return send_file(BytesIO(data),mimetype='application/json',as_attachment=True,download_name='storyai-backup.json')
@bp.get('/html')
def html_file(project_id):
 data=html_export(get_db(),project_id,current_app.config['UPLOAD_DIR']).encode(); return send_file(BytesIO(data),mimetype='text/html',as_attachment=True,download_name='storyboard.html')
