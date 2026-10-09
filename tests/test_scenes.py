import base64
import io
import json
from pathlib import Path

from PIL import Image

from tests.conftest import make_project


def make_scene(client, project_id, **updates):
    body = {"title": "The meeting", "summary": "The lead reaches the harbor."}
    body.update(updates)
    response = client.post(f"/api/projects/{project_id}/scenes", json=body)
    assert response.status_code == 201
    return response.get_json()["scene"]


def test_scene_characters_are_project_scoped_persistent_and_versioned(client):
    project = make_project(client, "Harbor Story")
    other = make_project(client, "Different Story")
    character = client.post(
        f"/api/projects/{project['id']}/characters",
        json={"name": "Lead"},
    ).get_json()["character"]
    outsider = client.post(
        f"/api/projects/{other['id']}/characters",
        json={"name": "Outsider"},
    ).get_json()["character"]
    location = client.post(
        f"/api/projects/{project['id']}/locations",
        json={"name": "Harbor"},
    ).get_json()["location"]
    scene = make_scene(client, project["id"], location_id=location["id"])

    linked = client.put(
        f"/api/projects/{project['id']}/scenes/{scene['id']}/characters",
        json={
            "updated_at": scene["updated_at"],
            "characters": [
                {"character_id": character["id"], "outfit_state": "Raincoat, soaked."}
            ],
        },
    )
    assert linked.status_code == 200
    persisted = linked.get_json()["scene"]
    assert persisted["location_id"] == location["id"]
    assert persisted["characters"] == [
        {"id": character["id"], "name": "Lead", "outfit_state": "Raincoat, soaked."}
    ]

    stale = client.put(
        f"/api/projects/{project['id']}/scenes/{scene['id']}/characters",
        json={"updated_at": scene["updated_at"], "characters": []},
    )
    assert stale.status_code == 409
    assert client.get(f"/api/projects/{project['id']}/scenes/{scene['id']}").get_json()["scene"]["characters"] == persisted["characters"]

    wrong_project = client.put(
        f"/api/projects/{project['id']}/scenes/{scene['id']}/characters",
        json={
            "updated_at": persisted["updated_at"],
            "characters": [{"character_id": outsider["id"], "outfit_state": "Wrong project."}],
        },
    )
    assert wrong_project.status_code == 400
    assert client.get(f"/api/projects/{other['id']}/scenes/{scene['id']}").status_code == 404


def test_scene_and_shot_order_validation_and_api_asset_path_privacy(client, db):
    project = make_project(client)
    scene = make_scene(client, project["id"])
    invalid_scene = client.post(
        f"/api/projects/{project['id']}/scenes",
        json={"title": "Invalid", "order_no": "not-a-number"},
    )
    assert invalid_scene.status_code == 400

    shots_url = f"/api/projects/{project['id']}/scenes/{scene['id']}/shots"
    shot_response = client.post(
        shots_url,
        json={"order_no": 3, "action": "A lantern swings."},
    )
    assert shot_response.status_code == 201
    shot = shot_response.get_json()["shot"]
    assert shot["order_no"] == 3
    assert shot["frame"] is None

    bad_order = client.patch(
        f"{shots_url}/{shot['id']}",
        json={"order_no": "bad", "updated_at": shot["updated_at"]},
    )
    assert bad_order.status_code == 400

    asset_id = db.execute(
        "INSERT INTO assets(project_id,kind,file_path,thumb_path) VALUES(?,?,?,?)",
        (project["id"], "panel", "panels/private.jpg", "panels/private_thumb.jpg"),
    ).lastrowid
    db.execute(
        "INSERT INTO frames(project_id,shot_id,asset_id) VALUES(?,?,?)",
        (project["id"], shot["id"], asset_id),
    )
    db.commit()
    fetched = client.get(shots_url).get_json()["shots"][0]
    assert fetched["frame"]["asset_id"] == asset_id
    assert "file_path" not in fetched["frame"]
    assert "thumb_path" not in fetched["frame"]


def test_shot_image_upload_is_project_scoped_and_persistent(client, db, app):
    project = make_project(client, "Storyboard Story")
    other = make_project(client, "Other Story")
    scene = make_scene(client, project["id"])
    shot = client.post(
        f"/api/projects/{project['id']}/scenes/{scene['id']}/shots",
        json={"action": "A lantern swings."},
    ).get_json()["shot"]

    image = io.BytesIO()
    Image.new("RGB", (16, 16), (120, 24, 45)).save(image, "PNG")
    response = client.post(
        f"/api/projects/{project['id']}/scenes/{scene['id']}/shots/{shot['id']}/image",
        data={"image": (io.BytesIO(image.getvalue()), "panel.png", "image/png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    updated = response.get_json()["shot"]
    assert updated["id"] == shot["id"]
    listed = client.get(
        f"/api/projects/{project['id']}/scenes/{scene['id']}/shots"
    ).get_json()["shots"]
    framed_shot = next(item for item in listed if item["id"] == shot["id"])
    assert framed_shot["frame"]["asset_id"]
    assert "file_path" not in framed_shot["frame"]
    assert client.get(
        f"/api/projects/{project['id']}/scenes/{scene['id']}/shots/{shot['id']}/image"
    ).mimetype == "image/jpeg"
    assert client.get(
        f"/api/projects/{other['id']}/scenes/{scene['id']}/shots/{shot['id']}/image"
    ).status_code == 404
    asset = db.execute(
        "SELECT id,project_id,kind,file_path FROM assets WHERE id=?",
        (framed_shot["frame"]["asset_id"],),
    ).fetchone()
    assert asset["project_id"] == project["id"]
    assert asset["kind"] == "panel"
    image_path = Path(app.config["UPLOAD_DIR"]) / asset["file_path"]
    assert image_path.is_file()

    backup_response = client.get(f"/api/projects/{project['id']}/export/json")
    backup = json.loads(backup_response.get_data(as_text=True))
    exported_asset = next(item for item in backup["assets"] if item["id"] == asset["id"])
    assert "file_path" not in exported_asset and "thumb_path" not in exported_asset
    assert base64.b64decode(exported_asset["files"]["original"]["content_base64"]) == image_path.read_bytes()
    storyboard_html = client.get(f"/api/projects/{project['id']}/export/html").get_data(as_text=True)
    assert "data:image/jpeg;base64," in storyboard_html
    assert "A lantern swings." in storyboard_html


def test_project_export_rejects_asset_path_traversal(client, db):
    project = make_project(client, "Export path safety")
    scene = make_scene(client, project["id"])
    shot = client.post(
        f"/api/projects/{project['id']}/scenes/{scene['id']}/shots",
        json={"action": "A lantern swings."},
    ).get_json()["shot"]
    image = io.BytesIO()
    Image.new("RGB", (8, 8), (12, 45, 120)).save(image, "PNG")
    upload = client.post(
        f"/api/projects/{project['id']}/scenes/{scene['id']}/shots/{shot['id']}/image",
        data={"image": (io.BytesIO(image.getvalue()), "panel.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 200
    asset_id = db.execute(
        "SELECT asset_id FROM frames WHERE shot_id=?", (shot["id"],)
    ).fetchone()[0]
    db.execute("UPDATE assets SET file_path='../outside.bin' WHERE id=?", (asset_id,))
    db.commit()

    response = client.get(f"/api/projects/{project['id']}/export/json")
    assert response.status_code == 400
    assert response.get_json()["error"] == "A project image is missing or unavailable; export could not be completed."
