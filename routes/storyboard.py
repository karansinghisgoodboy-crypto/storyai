from flask import Blueprint, jsonify

from db.database import get_db
from routes import json_body
from services import storyboard

bp = Blueprint(
    "storyboard",
    __name__,
    url_prefix="/api/projects/<int:project_id>/storyboard",
)


@bp.post("/generate")
def generate(project_id):
    data = json_body()
    return jsonify(storyboard=storyboard.generate(
        get_db(), project_id, data.get("direction", "")
    )), 201
