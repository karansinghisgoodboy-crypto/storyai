"""Project endpoints. Thin: read the request, call the service, return JSON."""
from flask import Blueprint, current_app, jsonify

from db.database import get_db
from routes import json_body
from services import projects as project_service

bp = Blueprint("projects", __name__, url_prefix="/api/projects")


@bp.get("")
def list_projects():
    return jsonify(projects=project_service.list_projects(get_db()))


@bp.post("")
def create_project():
    data = json_body()
    project = project_service.create_project(get_db(), data.get("title"), data.get("idea"))
    return jsonify(project=project), 201


@bp.get("/<int:project_id>")
def get_project(project_id):
    return jsonify(project=project_service.get_project(get_db(), project_id))


@bp.patch("/<int:project_id>")
def rename_project(project_id):
    data = json_body()
    project = project_service.rename_project(
        get_db(), project_id, data.get("title"), data.get("updated_at")
    )
    return jsonify(project=project)


@bp.delete("/<int:project_id>")
def delete_project(project_id):
    project_service.delete_project(get_db(), project_id, current_app.config["UPLOAD_DIR"])
    return jsonify(deleted=project_id)
