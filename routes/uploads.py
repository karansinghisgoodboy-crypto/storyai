from flask import Blueprint,jsonify,current_app,request
from db.database import get_db
from routes import json_body
from services.uploads import save_generic_image
bp=Blueprint('uploads',__name__,url_prefix='/api/projects/<int:project_id>/uploads')
