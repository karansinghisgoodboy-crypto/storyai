import io
import re
from pathlib import Path

import pytest
from PIL import Image

from tests.conftest import make_project

ROOT = Path(__file__).resolve().parent.parent


def location_payload(name="Moonlit Garden", **updates):
    data = {
        "name": name,
        "description": "A quiet garden behind an old shrine.",
        "mood": "Mist-soft, watchful, and still.",
    }
    data.update(updates)
    return data


def make_location(client, project_id, name="Moonlit Garden"):
    response = client.post(
        f"/api/projects/{project_id}/locations",
        json=location_payload(name),
    )
    assert response.status_code == 201
    return response.get_json()["location"]


def image_bytes(image_format="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (32, 24), (65, 32, 38)).save(output, image_format)
    return output.getvalue()


def upload_image(client, project_id, location_id, data=None, filename="garden.png", mime="image/png"):
    return client.post(
        f"/api/projects/{project_id}/locations/{location_id}/image",
        data={
            "image": (
                io.BytesIO(data if data is not None else image_bytes()),
                filename,
                mime,
            )
        },
        content_type="multipart/form-data",
    )


def test_location_crud_is_project_scoped_and_persistent(client, db):
    project = make_project(client, "Garden Story")
    other_project = make_project(client, "Other Story")
    location = make_location(client, project["id"])

    assert location["project_id"] == project["id"]
    assert location["locked"] is False
    assert {key: location[key] for key in ("name", "description", "mood")} == location_payload()

    listed = client.get(f"/api/projects/{project['id']}/locations")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.get_json()["locations"]] == [location["id"]]
    assert client.get(f"/api/projects/{other_project['id']}/locations").get_json()["locations"] == []

    changed = location_payload(
        "Lantern Courtyard",
        description="Rain gathers between the stepping stones.",
        mood="Warm lanterns, distant thunder.",
    )
    updated = client.patch(
        f"/api/projects/{project['id']}/locations/{location['id']}",
        json={**changed, "updated_at": location["updated_at"]},
    )
    assert updated.status_code == 200
    assert {key: updated.get_json()["location"][key] for key in changed} == changed
    assert client.get(f"/api/projects/{project['id']}/locations").get_json()["locations"][0]["name"] == "Lantern Courtyard"
    assert client.patch(
        f"/api/projects/{other_project['id']}/locations/{location['id']}",
        json=location_payload("Cross-project"),
    ).status_code == 404
    assert client.delete(f"/api/projects/{other_project['id']}/locations/{location['id']}").status_code == 404
    assert db.execute("SELECT project_id FROM locations WHERE id=?", (location["id"],)).fetchone()["project_id"] == project["id"]
    assert client.delete(f"/api/projects/{project['id']}/locations/{location['id']}").status_code == 200
    assert client.get(f"/api/projects/{project['id']}/locations").get_json()["locations"] == []


def test_location_validation_and_missing_ids(client):
    project = make_project(client)
    assert client.post(
        f"/api/projects/{project['id']}/locations",
        json=location_payload(""),
    ).status_code == 400
    assert client.post(
        f"/api/projects/{project['id']}/locations",
        json=location_payload(mood="x" * 501),
    ).status_code == 400
    assert client.get(f"/api/projects/{project['id']}/locations/not-an-id").status_code == 404
    assert client.get("/api/projects/not-an-id/locations").status_code == 404


def test_location_lock_unlock_blocks_mutation_and_persists(client):
    project = make_project(client)
    location = make_location(client, project["id"])
    locked = client.post(
        f"/api/projects/{project['id']}/locations/{location['id']}/lock",
        json={"locked": True, "updated_at": location["updated_at"]},
    )
    assert locked.status_code == 200
    locked_location = locked.get_json()["location"]
    assert client.get(f"/api/projects/{project['id']}/locations").get_json()["locations"][0]["locked"] is True

    assert client.patch(
        f"/api/projects/{project['id']}/locations/{location['id']}",
        json={**location_payload("Do not change"), "updated_at": locked_location["updated_at"]},
    ).status_code == 409
    assert client.delete(f"/api/projects/{project['id']}/locations/{location['id']}").status_code == 409
    assert upload_image(client, project["id"], location["id"]).status_code == 409

    unlocked = client.post(
        f"/api/projects/{project['id']}/locations/{location['id']}/lock",
        json={"locked": False, "updated_at": locked_location["updated_at"]},
    )
    assert unlocked.status_code == 200
    unlocked_location = unlocked.get_json()["location"]
    assert client.get(f"/api/projects/{project['id']}/locations").get_json()["locations"][0]["locked"] is False
    assert client.patch(
        f"/api/projects/{project['id']}/locations/{location['id']}",
        json={**location_payload("Editable again"), "updated_at": unlocked_location["updated_at"]},
    ).status_code == 200


def test_location_rejects_stale_updates(client):
    project = make_project(client)
    location = make_location(client, project["id"])
    latest = client.patch(
        f"/api/projects/{project['id']}/locations/{location['id']}",
        json={**location_payload("Latest"), "updated_at": location["updated_at"]},
    )
    assert latest.status_code == 200
    stale = client.patch(
        f"/api/projects/{project['id']}/locations/{location['id']}",
        json={**location_payload("Stale"), "updated_at": location["updated_at"]},
    )
    assert stale.status_code == 409


@pytest.mark.parametrize(
    ("image_format", "filename", "mime"),
    [
        ("PNG", "reference.png", "image/png"),
        ("JPEG", "reference.jpg", "image/jpeg"),
        ("WEBP", "reference.webp", "image/webp"),
    ],
)
def test_location_image_upload_is_associated_and_persistent(
    client, db, app, image_format, filename, mime
):
    project = make_project(client)
    location = make_location(client, project["id"])
    response = upload_image(
        client, project["id"], location["id"], image_bytes(image_format), filename, mime
    )
    assert response.status_code == 200
    updated = response.get_json()["location"]
    assert updated["project_id"] == project["id"]
    assert updated["image_id"] is not None
    assert "file_path" not in updated
    asset = db.execute("SELECT * FROM assets WHERE id=?", (updated["image_id"],)).fetchone()
    assert asset["project_id"] == project["id"]
    assert asset["kind"] == "location"
    assert asset["created_at"]
    assert client.get(
        f"/api/projects/{project['id']}/locations/{location['id']}/image"
    ).mimetype == "image/jpeg"
    assert client.get(
        f"/api/projects/{project['id']}/locations"
    ).get_json()["locations"][0]["image_id"] == updated["image_id"]
    assert (Path(app.config["UPLOAD_DIR"]) / asset["file_path"]).is_file()


@pytest.mark.parametrize(
    ("data", "filename", "mime", "message"),
    [
        (b"not an image", "image.png", "image/png", "The uploaded file is not a valid image."),
        (b"fake", "payload.exe", "application/octet-stream", "Only PNG, JPG or WEBP images are allowed."),
        (b"fake", "image.jpg", "image/png", "The image file type does not match its extension."),
    ],
)
def test_location_image_rejects_invalid_content_or_file_type(client, data, filename, mime, message):
    project = make_project(client)
    location = make_location(client, project["id"])
    response = upload_image(client, project["id"], location["id"], data, filename, mime)
    assert response.status_code == 400
    assert response.get_json()["error"] == message


def test_location_image_rejects_corrupt_image(client):
    project = make_project(client)
    location = make_location(client, project["id"])
    corrupt = image_bytes()[:-12]
    response = upload_image(client, project["id"], location["id"], corrupt)
    assert response.status_code == 400
    assert response.get_json()["error"] == "The uploaded file is not a valid image."


def test_location_image_rejects_bad_png_chunk_checksum(client):
    project = make_project(client)
    location = make_location(client, project["id"])
    corrupt = bytearray(image_bytes())
    idat_data = corrupt.index(b"IDAT") + len(b"IDAT")
    corrupt[idat_data] ^= 0xFF

    response = upload_image(client, project["id"], location["id"], bytes(corrupt))

    assert response.status_code == 400
    assert response.get_json()["error"] == "The uploaded file is not a valid image."


def test_location_image_rejects_files_over_five_mb(client):
    project = make_project(client)
    location = make_location(client, project["id"])
    response = upload_image(client, project["id"], location["id"], b"x" * (5 * 1024 * 1024 + 1))
    assert response.status_code == 400
    assert response.get_json()["error"] == "Image must be 5 MB or smaller."


def test_location_image_cannot_be_attached_to_another_project(client, db):
    project = make_project(client)
    other = make_project(client, "Other")
    location = make_location(client, other["id"])
    response = upload_image(client, project["id"], location["id"])
    assert response.status_code == 404
    locations = client.get(
        f"/api/projects/{other['id']}/locations"
    ).get_json()["locations"]
    assert locations[0]["id"] == location["id"]
    assert locations[0]["image_id"] is None
    assert db.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0


def test_location_image_replacement_preserves_old_asset_until_success(client, db, app):
    project = make_project(client)
    location = make_location(client, project["id"])
    first = upload_image(client, project["id"], location["id"])
    assert first.status_code == 200
    old_id = first.get_json()["location"]["image_id"]
    old_asset = db.execute("SELECT * FROM assets WHERE id=?", (old_id,)).fetchone()
    old_paths = [Path(app.config["UPLOAD_DIR"]) / old_asset[key] for key in ("file_path", "thumb_path")]

    failed = upload_image(client, project["id"], location["id"], b"bad image")
    assert failed.status_code == 400
    assert all(path.is_file() for path in old_paths)
    assert db.execute("SELECT image_id FROM locations WHERE id=?", (location["id"],)).fetchone()["image_id"] == old_id

    replaced = upload_image(client, project["id"], location["id"], image_bytes("WEBP"), "replacement.webp", "image/webp")
    assert replaced.status_code == 200
    assert replaced.get_json()["location"]["image_id"] != old_id
    assert all(not path.exists() for path in old_paths)
    assert db.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1


def test_location_delete_cleans_image_but_scene_location_becomes_null(client, db, app):
    project = make_project(client)
    location = make_location(client, project["id"])
    upload = upload_image(client, project["id"], location["id"])
    assert upload.status_code == 200
    asset = db.execute(
        "SELECT * FROM assets WHERE id=?", (upload.get_json()["location"]["image_id"],)
    ).fetchone()
    paths = [Path(app.config["UPLOAD_DIR"]) / asset[key] for key in ("file_path", "thumb_path")]
    scene_id = db.execute(
        "INSERT INTO scenes(project_id,order_no,location_id) VALUES(?,?,?)",
        (project["id"], 1, location["id"]),
    ).lastrowid
    db.commit()
    assert client.delete(f"/api/projects/{project['id']}/locations/{location['id']}").status_code == 200
    assert db.execute("SELECT location_id FROM scenes WHERE id=?", (scene_id,)).fetchone()["location_id"] is None
    assert db.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0
    assert all(not path.exists() for path in paths)


def test_location_delete_does_not_remove_path_outside_upload_directory(client, db, app, tmp_path):
    project = make_project(client)
    location = make_location(client, project["id"])
    outside = tmp_path / "keep.txt"
    outside.write_text("keep")
    asset_id = db.execute(
        "INSERT INTO assets(project_id,kind,file_path,thumb_path) VALUES(?,?,?,?)",
        (project["id"], "location", "../keep.txt", "../keep.txt"),
    ).lastrowid
    db.execute("UPDATE locations SET image_id=? WHERE id=?", (asset_id, location["id"]))
    db.commit()
    assert client.delete(f"/api/projects/{project['id']}/locations/{location['id']}").status_code == 200
    assert outside.read_text() == "keep"


def test_location_image_read_rejects_asset_from_other_project(client, db):
    project = make_project(client)
    other = make_project(client, "Other")
    location = make_location(client, project["id"])
    asset_id = db.execute(
        "INSERT INTO assets(project_id,kind,file_path,thumb_path) VALUES(?,?,?,?)",
        (other["id"], "location", "locations/private.jpg", "locations/private_thumb.jpg"),
    ).lastrowid
    db.execute("UPDATE locations SET image_id=? WHERE id=?", (asset_id, location["id"]))
    db.commit()
    response = client.get(
        f"/api/projects/{project['id']}/locations/{location['id']}/image"
    )
    assert response.status_code == 404


def test_location_frontend_api_and_screen_contract():
    api = (ROOT / "static/js/api.js").read_text(encoding="utf-8")
    screen = (ROOT / "static/js/screens/locations.js").read_text(encoding="utf-8")
    workspace = (ROOT / "static/js/screens/workspace.js").read_text(encoding="utf-8")
    assert "Api.uploadLocationImage" in screen
    assert "Screens.locations=(box,p)=>LocationsScreen.render(box,p)" in workspace
    assert re.search(
        r"async uploadLocationImage\([^)]*\).*?new FormData\(\).*?"
        r"form\.append\(['\"]image['\"],file\).*?"
        r"/locations/\$\{locationId\}/image",
        api,
    )
    assert all(f'["{key}"' in screen for key in ("name", "description", "mood"))
    assert "Add Location" in screen
