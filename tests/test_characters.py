import io
import re
from pathlib import Path

import pytest
from PIL import Image
from tests.conftest import make_project

FIELDS = ["name","role","age","build","hair","face","appearance","default_outfit","distinguishing_marks","personality","backstory","voice","abilities"]
ROOT = Path(__file__).resolve().parent.parent

def payload(name="Karan"):
    return {f:(name if f=="name" else f"{f} value") for f in FIELDS}

def image_bytes(image_format="PNG"):
    out=io.BytesIO(); Image.new("RGB",(20,20),(20,40,60)).save(out,image_format); return out.getvalue()

def upload_image(client, project_id, character_id, data=None, filename="ref.png", content_type="image/png"):
    return client.post(
        f"/api/projects/{project_id}/characters/{character_id}/image",
        data={"image":(io.BytesIO(data if data is not None else image_bytes()),filename,content_type)},
        content_type="multipart/form-data",
    )

def test_create_character_persists_project_id(client, db):
    project = make_project(client)
    assert project["id"] == 1

    response = client.post(
        f'/api/projects/{project["id"]}/characters',
        json=payload(),
    )

    assert response.status_code == 201
    character = response.get_json()["character"]
    assert character["project_id"] == 1
    row = db.execute(
        "SELECT project_id FROM characters WHERE id=?",
        (character["id"],),
    ).fetchone()
    assert row["project_id"] == 1

def test_character_crud_and_project_scope(client):
    p=make_project(client); other=make_project(client,"Other")
    r=client.post(f'/api/projects/{p["id"]}/characters',json=payload()); assert r.status_code==201
    c=r.get_json()["character"]; assert c["name"]=="Karan" and c["locked"] is False
    r=client.get(f'/api/projects/{p["id"]}/characters'); assert r.status_code==200 and len(r.get_json()["characters"])==1
    edited=payload("New")
    edited.update(age="42",build="athletic",hair="silver",face="scarred",appearance="tall",default_outfit="coat",distinguishing_marks="ring",personality="brave",backstory="traveler",voice="soft",abilities="tracking")
    r=client.patch(f'/api/projects/{p["id"]}/characters/{c["id"]}',json={**edited,"updated_at":c["updated_at"]}); assert r.status_code==200; c=r.get_json()["character"]
    assert {field:c[field] for field in FIELDS}==edited
    assert client.get(f'/api/projects/{p["id"]}/characters').get_json()["characters"][0]["hair"]=="silver"
    assert client.get(f'/api/projects/{other["id"]}/characters/{c["id"]}').status_code==404
    assert client.delete(f'/api/projects/{p["id"]}/characters/{c["id"]}').status_code==200

def test_character_validation(client):
    p=make_project(client)
    assert client.post(f'/api/projects/{p["id"]}/characters',json=payload("")).status_code==400
    bad=payload(); bad["name"]="x"*121
    assert client.post(f'/api/projects/{p["id"]}/characters',json=bad).status_code==400

def test_lock_protects_edit_and_delete(client):
    p=make_project(client); c=client.post(f'/api/projects/{p["id"]}/characters',json=payload()).get_json()["character"]
    r=client.post(f'/api/projects/{p["id"]}/characters/{c["id"]}/lock',json={"locked":True,"updated_at":c["updated_at"]}); assert r.status_code==200; c=r.get_json()["character"]
    assert client.get(f'/api/projects/{p["id"]}/characters').get_json()["characters"][0]["locked"] is True
    assert client.patch(f'/api/projects/{p["id"]}/characters/{c["id"]}',json={**payload("x"),"updated_at":c["updated_at"]}).status_code==409
    assert client.delete(f'/api/projects/{p["id"]}/characters/{c["id"]}').status_code==409
    r=client.post(f'/api/projects/{p["id"]}/characters/{c["id"]}/lock',json={"locked":False,"updated_at":c["updated_at"]}); assert r.status_code==200
    c=r.get_json()["character"]
    assert c["locked"] is False
    assert client.get(f'/api/projects/{p["id"]}/characters').get_json()["characters"][0]["locked"] is False
    assert client.patch(f'/api/projects/{p["id"]}/characters/{c["id"]}',json={**payload("unlocked"),"updated_at":c["updated_at"]}).status_code==200
    assert client.get(f'/api/projects/{p["id"]}/characters/{c["id"]}').get_json()["character"]["name"]=="unlocked"
    assert client.delete(f'/api/projects/{p["id"]}/characters/{c["id"]}').status_code==200

def test_stale_update_is_409(client):
    p=make_project(client); c=client.post(f'/api/projects/{p["id"]}/characters',json=payload()).get_json()["character"]
    fresh=client.patch(f'/api/projects/{p["id"]}/characters/{c["id"]}',json={**payload("fresh"),"updated_at":c["updated_at"]}); assert fresh.status_code==200
    stale=client.patch(f'/api/projects/{p["id"]}/characters/{c["id"]}',json={**payload("stale"),"updated_at":c["updated_at"]}); assert stale.status_code==409

@pytest.mark.parametrize(("image_format","filename","content_type"),[
    ("PNG","ref.png","image/png"),
    ("JPEG","ref.jpg","image/jpeg"),
    ("WEBP","ref.webp","image/webp"),
])
def test_character_image_upload_and_get(client, db, app, image_format, filename, content_type):
    p=make_project(client); c=client.post(f'/api/projects/{p["id"]}/characters',json=payload()).get_json()["character"]
    r=upload_image(client,p["id"],c["id"],image_bytes(image_format),filename,content_type)
    assert r.status_code==200; c=r.get_json()["character"]; assert c["image_id"]
    assert c["project_id"]==p["id"] and "file_path" not in c
    asset=db.execute("SELECT * FROM assets WHERE id=?",(c["image_id"],)).fetchone()
    assert asset["project_id"]==p["id"] and asset["kind"]=="character"
    assert asset["created_at"] and c["updated_at"]>=asset["created_at"]
    assert Path(asset["file_path"]).name not in filename
    image=client.get(f'/api/projects/{p["id"]}/characters/{c["id"]}/image'); assert image.status_code==200; assert image.mimetype=="image/jpeg"
    listed=client.get(f'/api/projects/{p["id"]}/characters').get_json()["characters"][0]
    assert listed["image_id"]==c["image_id"]
    stored=Path(app.config["UPLOAD_DIR"])/asset["file_path"]
    assert stored.is_file()

def test_locked_character_rejects_image(client):
    p=make_project(client); c=client.post(f'/api/projects/{p["id"]}/characters',json=payload()).get_json()["character"]
    c=client.post(f'/api/projects/{p["id"]}/characters/{c["id"]}/lock',json={"locked":True,"updated_at":c["updated_at"]}).get_json()["character"]
    r=upload_image(client,p["id"],c["id"]); assert r.status_code==409
    assert client.get(f'/api/projects/{p["id"]}/characters/{c["id"]}').get_json()["character"]["image_id"] is None

def test_character_image_rejects_invalid_type_and_content(client):
    p=make_project(client); c=client.post(f'/api/projects/{p["id"]}/characters',json=payload()).get_json()["character"]
    invalid_extension=upload_image(client,p["id"],c["id"],filename="payload.exe",content_type="application/octet-stream")
    assert invalid_extension.status_code==400
    assert invalid_extension.get_json()["error"]=="Only PNG, JPG or WEBP images are allowed."
    mismatch=upload_image(client,p["id"],c["id"],image_bytes("PNG"),"payload.jpg","image/jpeg")
    assert mismatch.status_code==400
    assert "type does not match" in mismatch.get_json()["error"]
    invalid_content=upload_image(client,p["id"],c["id"],b"not an image")
    assert invalid_content.status_code==400
    assert invalid_content.get_json()["error"]=="The uploaded file is not a valid image."

def test_character_image_rejects_files_over_five_mb(client):
    p=make_project(client); c=client.post(f'/api/projects/{p["id"]}/characters',json=payload()).get_json()["character"]
    result=upload_image(client,p["id"],c["id"],b"x"*(5*1024*1024+1))
    assert result.status_code==400
    assert result.get_json()["error"]=="Image must be 5 MB or smaller."

def test_character_image_cannot_be_attached_across_projects(client, db):
    first=make_project(client); second=make_project(client,"Other")
    other=client.post(f'/api/projects/{second["id"]}/characters',json=payload()).get_json()["character"]
    result=upload_image(client,first["id"],other["id"])
    assert result.status_code==404
    assert client.get(f'/api/projects/{second["id"]}/characters/{other["id"]}').get_json()["character"]["image_id"] is None
    assert db.execute("SELECT COUNT(*) FROM assets").fetchone()[0]==0

def test_character_image_replacement_and_delete_clean_owned_assets(client, db, app):
    p=make_project(client)
    first=client.post(f'/api/projects/{p["id"]}/characters',json=payload()).get_json()["character"]
    untouched=client.post(f'/api/projects/{p["id"]}/characters',json=payload("Other")).get_json()["character"]
    upload_image(client,p["id"],first["id"])
    old=db.execute("SELECT file_path,thumb_path FROM assets WHERE id=?",(client.get(f'/api/projects/{p["id"]}/characters/{first["id"]}').get_json()["character"]["image_id"],)).fetchone()
    old_paths=[Path(app.config["UPLOAD_DIR"])/old[name] for name in ("file_path","thumb_path")]
    replaced=upload_image(client,p["id"],first["id"],image_bytes("WEBP"),"new.webp","image/webp")
    assert replaced.status_code==200
    assert all(not path.exists() for path in old_paths)
    assert db.execute("SELECT COUNT(*) FROM assets").fetchone()[0]==1
    new_id=replaced.get_json()["character"]["image_id"]
    new_asset=db.execute("SELECT file_path,thumb_path FROM assets WHERE id=?",(new_id,)).fetchone()
    new_paths=[Path(app.config["UPLOAD_DIR"])/new_asset[name] for name in ("file_path","thumb_path")]
    assert all(path.is_file() for path in new_paths)
    assert client.delete(f'/api/projects/{p["id"]}/characters/{first["id"]}').status_code==200
    assert all(not path.exists() for path in new_paths)
    assert client.get(f'/api/projects/{p["id"]}/characters/{untouched["id"]}').status_code==200
    assert db.execute("SELECT COUNT(*) FROM assets").fetchone()[0]==0

def test_character_image_read_rejects_asset_from_another_project(client, db):
    first=make_project(client); second=make_project(client,"Other")
    character=client.post(f'/api/projects/{first["id"]}/characters',json=payload()).get_json()["character"]
    asset=db.execute(
        "INSERT INTO assets(project_id,kind,file_path,thumb_path) VALUES(?,?,?,?)",
        (second["id"],"character","characters/private.jpg","characters/private_thumb.jpg"),
    ).lastrowid
    db.execute("UPDATE characters SET image_id=? WHERE id=?",(asset,character["id"]))
    db.commit()
    result=client.get(f'/api/projects/{first["id"]}/characters/{character["id"]}/image')
    assert result.status_code==404

def test_character_image_replacement_does_not_delete_outside_upload_directory(client, db, app, tmp_path):
    p=make_project(client)
    character=client.post(f'/api/projects/{p["id"]}/characters',json=payload()).get_json()["character"]
    outside=tmp_path/"keep.txt"; outside.write_text("keep")
    asset=db.execute(
        "INSERT INTO assets(project_id,kind,file_path,thumb_path) VALUES(?,?,?,?)",
        (p["id"],"character","../keep.txt","../keep.txt"),
    ).lastrowid
    db.execute("UPDATE characters SET image_id=? WHERE id=?",(asset,character["id"]))
    db.commit()
    assert upload_image(client,p["id"],character["id"]).status_code==200
    assert outside.read_text()=="keep"

def test_character_image_api_uses_existing_multipart_route():
    api=(ROOT/"static/js/api.js").read_text(encoding="utf-8")
    ui=(ROOT/"static/js/screens/characters.js").read_text(encoding="utf-8")
    assert "Api.uploadCharacterImage" in ui
    assert re.search(
        r"async uploadCharacterImage\([^)]*\).*?new FormData\(\).*?"
        r"form\.append\(['\"]image['\"],file\).*?"
        r"/characters/\$\{characterId\}/image",
        api,
    )
