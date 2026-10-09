import json

import pytest

from services.errors import AppError
from tests.conftest import make_project


def _storyboard(character_name="Mara"):
    return {
        "scenes": [
            {
                "title": "The Harbor Bell",
                "summary": "Mara reaches the harbor as the warning bell sounds.",
                "time_of_day": "Dusk",
                "character_names": [character_name],
                "shots": [
                    {
                        "shot_type": "Wide",
                        "camera_angle": "High angle",
                        "movement": "Slow push in",
                        "action": "Mara crosses the rain-darkened pier.",
                        "dialogue": "",
                        "lighting": "Cold dusk light",
                        "notes": "Establish the harbor before the reveal.",
                    }
                ],
            }
        ]
    }


def test_storyboard_generation_appends_persisted_scenes_and_shots(client, db, monkeypatch):
    project = make_project(client, "Harbor story")
    character = client.post(
        f"/api/projects/{project['id']}/characters", json={"name": "Mara"}
    ).get_json()["character"]
    existing_scene = client.post(
        f"/api/projects/{project['id']}/scenes",
        json={"title": "Existing scene", "summary": "Keep this."},
    ).get_json()["scene"]
    client.post(
        f"/api/projects/{project['id']}/scenes/{existing_scene['id']}/shots",
        json={"action": "Existing shot."},
    )
    db.execute(
        "INSERT INTO chat_messages(project_id,role,content) VALUES(?,?,?)",
        (project["id"], "user", "The harbor bell is important."),
    )
    db.commit()
    observed = {}

    def fake_generate(system, prompt, **kwargs):
        observed.update(system=system, prompt=prompt, **kwargs)
        return json.dumps(_storyboard()), []

    monkeypatch.setattr("services.storyboard.generate_text", fake_generate)
    response = client.post(
        f"/api/projects/{project['id']}/storyboard/generate",
        json={"direction": "Storyboard the harbor arrival."},
    )

    assert response.status_code == 201
    storyboard = response.get_json()["storyboard"]
    generated_scene = storyboard["scenes"][0]
    assert generated_scene["title"] == "The Harbor Bell"
    assert generated_scene["order_no"] == existing_scene["order_no"] + 1
    assert generated_scene["characters"] == [
        {"id": character["id"], "name": "Mara", "outfit_state": ""}
    ]
    assert len(generated_scene["shots"]) == 1
    assert generated_scene["shots"][0]["order_no"] == 1
    assert generated_scene["shots"][0]["action"] == "Mara crosses the rain-darkened pier."
    assert observed["json_mode"] is True
    assert observed["max_output_tokens"] == 1600
    assert observed["history"] == [
        {"role": "user", "content": "The harbor bell is important."}
    ]
    assert "Harbor story" in observed["system"]
    assert "Mara" in observed["system"]

    saved_scenes = client.get(f"/api/projects/{project['id']}/scenes").get_json()["scenes"]
    assert [scene["title"] for scene in saved_scenes] == [
        "Existing scene",
        "The Harbor Bell",
    ]
    assert db.execute(
        "SELECT COUNT(*) FROM shots WHERE project_id=?", (project["id"],)
    ).fetchone()[0] == 2


@pytest.mark.parametrize(
    "data",
    [
        {"scenes": []},
        {"scenes": [{"title": "No shots", "summary": "", "time_of_day": "", "character_names": [], "shots": []}]},
        _storyboard(character_name="Invented person"),
    ],
)
def test_invalid_storyboard_output_does_not_write_any_rows(client, db, monkeypatch, data):
    project = make_project(client, "Keep existing data")
    existing = client.post(
        f"/api/projects/{project['id']}/scenes",
        json={"title": "Saved scene", "summary": "Untouched."},
    ).get_json()["scene"]
    monkeypatch.setattr(
        "services.storyboard.generate_text",
        lambda *args, **kwargs: (json.dumps(data), []),
    )

    response = client.post(
        f"/api/projects/{project['id']}/storyboard/generate",
        json={"direction": "Add a new sequence."},
    )

    assert response.status_code == 400
    assert [scene["title"] for scene in client.get(
        f"/api/projects/{project['id']}/scenes"
    ).get_json()["scenes"]] == [existing["title"]]
    assert db.execute(
        "SELECT COUNT(*) FROM shots WHERE project_id=?", (project["id"],)
    ).fetchone()[0] == 0


def test_storyboard_generation_validates_request_before_ai_call(client, monkeypatch):
    project = make_project(client, "Validate storyboard")
    monkeypatch.setattr(
        "services.storyboard.generate_text",
        lambda *args, **kwargs: pytest.fail("AI should not be called for invalid direction."),
    )
    response = client.post(
        f"/api/projects/{project['id']}/storyboard/generate",
        json={"direction": " "},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Storyboard direction cannot be empty."


def test_storyboard_provider_failure_leaves_existing_content_untouched(client, db, monkeypatch):
    project = make_project(client, "Storyboard provider failure")
    scene = client.post(
        f"/api/projects/{project['id']}/scenes",
        json={"title": "Existing", "summary": ""},
    ).get_json()["scene"]

    def fail(*args, **kwargs):
        raise AppError("Ollama took too long to respond.")

    monkeypatch.setattr("services.storyboard.generate_text", fail)
    response = client.post(
        f"/api/projects/{project['id']}/storyboard/generate",
        json={"direction": "A quiet opening."},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Ollama took too long to respond."
    assert client.get(f"/api/projects/{project['id']}/scenes").get_json()["scenes"][0]["id"] == scene["id"]
    assert db.execute(
        "SELECT COUNT(*) FROM scenes WHERE project_id=?", (project["id"],)
    ).fetchone()[0] == 1
