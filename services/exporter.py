import base64
import html
import json
import mimetypes
from pathlib import Path

from services.common import project_exists
from services.errors import ValidationError


def _asset_file(upload_dir, relative_path):
    root = Path(upload_dir).resolve()
    path = (root / relative_path).resolve()
    if root not in path.parents or not path.is_file():
        raise ValidationError("A project image is missing or unavailable; export could not be completed.")
    return {
        "media_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }


def data(db, project_id, upload_dir):
    project_exists(db, project_id)
    project = dict(db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
    characters = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM characters WHERE project_id=? ORDER BY id", (project_id,)
        )
    ]
    locations = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM locations WHERE project_id=? ORDER BY id", (project_id,)
        )
    ]
    scenes = []
    for row in db.execute(
        "SELECT * FROM scenes WHERE project_id=? ORDER BY order_no,id", (project_id,)
    ):
        scene = dict(row)
        scene["characters"] = [
            dict(character)
            for character in db.execute(
                "SELECT c.id,c.name,sc.outfit_state FROM scene_characters sc "
                "JOIN characters c ON c.id=sc.character_id WHERE sc.scene_id=?",
                (scene["id"],),
            )
        ]
        scene["shots"] = [
            dict(shot)
            for shot in db.execute(
                "SELECT * FROM shots WHERE scene_id=? ORDER BY order_no,id",
                (scene["id"],),
            )
        ]
        for shot in scene["shots"]:
            frame = db.execute(
                "SELECT id,asset_id,created_at,updated_at FROM frames WHERE shot_id=?",
                (shot["id"],),
            ).fetchone()
            shot["frame"] = dict(frame) if frame else None
        scenes.append(scene)

    assets = []
    for row in db.execute(
        "SELECT id,project_id,kind,file_path,thumb_path,description,created_at "
        "FROM assets WHERE project_id=? ORDER BY id",
        (project_id,),
    ):
        asset = dict(row)
        original = _asset_file(upload_dir, asset.pop("file_path"))
        thumbnail = _asset_file(upload_dir, asset.pop("thumb_path"))
        asset["files"] = {"original": original, "thumbnail": thumbnail}
        assets.append(asset)

    return {
        "format": "storyai-project-backup",
        "version": 1,
        "project": project,
        "characters": characters,
        "locations": locations,
        "scenes": scenes,
        "shots": [
            dict(row)
            for row in db.execute(
                "SELECT * FROM shots WHERE project_id=? ORDER BY scene_id,order_no,id",
                (project_id,),
            )
        ],
        "memory": [
            dict(row)
            for row in db.execute(
                "SELECT * FROM memory_items WHERE project_id=? ORDER BY id",
                (project_id,),
            )
        ],
        "chat_messages": [
            dict(row)
            for row in db.execute(
                "SELECT * FROM chat_messages WHERE project_id=? ORDER BY id",
                (project_id,),
            )
        ],
        "proposals": [
            dict(row)
            for row in db.execute(
                "SELECT * FROM proposals WHERE project_id=? ORDER BY id",
                (project_id,),
            )
        ],
        "continuity_issues": [
            dict(row)
            for row in db.execute(
                "SELECT * FROM continuity_issues WHERE project_id=? ORDER BY id",
                (project_id,),
            )
        ],
        "search_log": [
            dict(row)
            for row in db.execute(
                "SELECT * FROM search_log WHERE project_id=? ORDER BY id",
                (project_id,),
            )
        ],
        "scene_characters": [
            dict(row)
            for row in db.execute(
                "SELECT sc.scene_id,sc.character_id,sc.outfit_state FROM scene_characters sc "
                "JOIN scenes s ON s.id=sc.scene_id WHERE s.project_id=? "
                "ORDER BY sc.scene_id,sc.character_id",
                (project_id,),
            )
        ],
        "frames": [
            dict(row)
            for row in db.execute(
                "SELECT * FROM frames WHERE project_id=? ORDER BY id", (project_id,)
            )
        ],
        "assets": assets,
    }


def json_export(db, project_id, upload_dir):
    return json.dumps(
        data(db, project_id, upload_dir), ensure_ascii=False, indent=2, default=str
    )


def html_export(db, project_id, upload_dir):
    backup = data(db, project_id, upload_dir)
    project = backup["project"]
    assets = {asset["id"]: asset for asset in backup["assets"]}
    output = [
        "<!doctype html><html><head><meta charset=\"utf-8\">",
        f"<title>{html.escape(project['title'])}</title>",
        "<style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 20px}"
        "section{border:1px solid #ddd;border-radius:10px;padding:18px;margin:16px 0}"
        "li{margin:5px 0}.shot{padding:10px;background:#f6f6f6;margin:8px 0}"
        "img{max-width:100%;height:auto}@media print{body{max-width:none;margin:0}}"
        "</style></head><body>",
        f"<h1>{html.escape(project['title'])}</h1>",
        f"<p>{html.escape(project['logline'])}</p>",
        "<section><h2>Story</h2>",
        f"<p><b>Genre:</b> {html.escape(project['genre'])}</p>",
        f"<p><b>Tone:</b> {html.escape(project['tone'])}</p>",
        f"<p><b>Synopsis:</b> {html.escape(project['synopsis'])}</p>",
        f"<pre>{html.escape(project['story_text'])}</pre></section>",
        "<section><h2>Characters</h2><ul>",
    ]
    for character in backup["characters"]:
        details = (
            "role", "age", "build", "hair", "face", "appearance", "default_outfit",
            "distinguishing_marks", "personality", "backstory", "voice", "abilities",
        )
        output.append(f"<li><b>{html.escape(character['name'])}</b>")
        for field in details:
            if character[field]:
                output.append(
                    f"<br><b>{html.escape(field.replace('_', ' ').title())}:</b> "
                    f"{html.escape(character[field])}"
                )
        if character["image_id"]:
            asset = assets.get(character["image_id"])
            if asset:
                image = asset["files"]["original"]
                output.append(
                    f'<br><img alt="Reference image for {html.escape(character["name"])}" '
                    f'src="data:{image["media_type"]};base64,{image["content_base64"]}">'
                )
        output.append("</li>")
    output.append("</ul></section><section><h2>Locations</h2><ul>")
    for location in backup["locations"]:
        output.append(
            f"<li><b>{html.escape(location['name'])}</b> — "
            f"{html.escape(location['description'])} "
            f"{html.escape(location['mood'])}</li>"
        )
        if location["image_id"] and location["image_id"] in assets:
            image = assets[location["image_id"]]["files"]["original"]
            output.append(
                f'<img alt="Reference image for {html.escape(location["name"])}" '
                f'src="data:{image["media_type"]};base64,{image["content_base64"]}">'
            )
    output.append("</ul></section>")
    for scene in backup["scenes"]:
        location = next(
            (item for item in backup["locations"] if item["id"] == scene["location_id"]),
            None,
        )
        output.extend(
            [
                f"<section><h2>Scene {scene['order_no']}: {html.escape(scene['title'])}</h2>",
                f"<p>{html.escape(scene['summary'])}</p>",
                f"<p><b>Time:</b> {html.escape(scene['time_of_day'])}</p>",
                f"<p><b>Location:</b> {html.escape(location['name'] if location else '')}</p>",
                "<h3>Characters</h3><ul>",
            ]
        )
        for character in scene["characters"]:
            output.append(
                f"<li>{html.escape(character['name'])}: "
                f"{html.escape(character['outfit_state'])}</li>"
            )
        output.append("</ul><h3>Shots</h3>")
        for shot in scene["shots"]:
            output.extend(
                [
                    f'<div class="shot"><b>Shot {shot["order_no"]}</b>',
                    f"<p>{html.escape(shot['shot_type'])} · "
                    f"{html.escape(shot['camera_angle'])} · "
                    f"{html.escape(shot['movement'])}</p>",
                    f"<p>{html.escape(shot['action'])}</p>",
                    f"<p><b>Dialogue:</b> {html.escape(shot['dialogue'])}</p>",
                    f"<p><b>Lighting:</b> {html.escape(shot['lighting'])}</p>",
                    f"<p><b>Notes:</b> {html.escape(shot['notes'])}</p>",
                ]
            )
            if shot["frame"] and shot["frame"]["asset_id"] in assets:
                image = assets[shot["frame"]["asset_id"]]["files"]["original"]
                output.append(
                    f'<img alt="Storyboard frame for shot {shot["order_no"]}" '
                    f'src="data:{image["media_type"]};base64,{image["content_base64"]}">'
                )
            output.append("</div>")
        output.append("</section>")
    output.append("</body></html>")
    return "".join(output)
