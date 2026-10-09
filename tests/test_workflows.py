import json

from tests.conftest import make_project


def test_story_updates_are_project_scoped_and_versioned(client):
    project = make_project(client, "Story one")
    other = make_project(client, "Story two")
    url = f"/api/projects/{project['id']}/story"
    original = client.get(url).get_json()["story"]
    values = {
        "logline": "A harbor hides a secret.",
        "genre": "Fantasy",
        "tone": "Hopeful",
        "synopsis": "A courier finds an old map.",
        "story_text": "The rain began before dawn.",
        "updated_at": original["updated_at"],
    }
    updated = client.patch(url, json=values)
    assert updated.status_code == 200
    assert {key: updated.get_json()["story"][key] for key in values if key != "updated_at"} == {
        key: values[key] for key in values if key != "updated_at"
    }
    stale = client.patch(url, json={**values, "logline": "Stale."})
    assert stale.status_code == 409
    assert client.get(f"/api/projects/{other['id']}/story").get_json()["story"]["logline"] == ""


def test_proposals_require_real_boolean_approval_and_only_apply_when_accepted(client):
    project = make_project(client, "Approval story")
    url = f"/api/projects/{project['id']}/proposals"
    created = client.post(
        url,
        json={
            "type": "memory",
            "action": "add",
            "payload": {"kind": "fact", "content": "The harbor bell rings at dusk."},
            "reason": "Preserve a story fact.",
        },
    )
    assert created.status_code == 201
    proposal = created.get_json()["proposal"]
    assert client.get(f"/api/projects/{project['id']}/memory").get_json()["memory"] == []

    invalid = client.post(
        f"{url}/{proposal['id']}/resolve",
        json={"accept": "false"},
    )
    assert invalid.status_code == 400
    assert client.get(f"/api/projects/{project['id']}/memory").get_json()["memory"] == []

    accepted = client.post(
        f"{url}/{proposal['id']}/resolve",
        json={"accept": True},
    )
    assert accepted.status_code == 200
    assert accepted.get_json()["proposal"]["status"] == "accepted"
    memory = client.get(f"/api/projects/{project['id']}/memory").get_json()["memory"]
    assert [(item["kind"], item["content"]) for item in memory] == [
        ("fact", "The harbor bell rings at dusk.")
    ]


def test_memory_lock_rejects_non_boolean_values(client):
    project = make_project(client, "Memory story")
    memory = client.post(
        f"/api/projects/{project['id']}/memory",
        json={"kind": "rule", "content": "Keep the lighthouse lit."},
    ).get_json()["item"]
    response = client.post(
        f"/api/projects/{project['id']}/memory/{memory['id']}/lock",
        json={"locked": "false", "updated_at": memory["updated_at"]},
    )
    assert response.status_code == 400
    assert client.get(f"/api/projects/{project['id']}/memory").get_json()["memory"][0]["locked"] is False


def test_continuity_fingerprints_and_export_escape_and_scope_project_data(client):
    project = make_project(client, "<script>alert(1)</script>")
    other = make_project(client, "Private other story")
    client.patch(
        f"/api/projects/{project['id']}/story",
        json={
            "logline": "<img src=x onerror=alert(1)>",
            "story_text": "<script>run()</script>",
        },
    )
    scene = client.post(
        f"/api/projects/{project['id']}/scenes",
        json={"title": "<svg onload=alert(1)>", "summary": ""},
    ).get_json()["scene"]
    first_run = client.post(f"/api/projects/{project['id']}/continuity/run").get_json()["issues"]
    assert first_run
    issue = first_run[0]
    assert client.post(
        f"/api/projects/{project['id']}/continuity/{issue['id']}/status",
        json={"status": "dismissed"},
    ).status_code == 200
    second_run = client.post(f"/api/projects/{project['id']}/continuity/run").get_json()["issues"]
    assert issue["id"] not in {item["id"] for item in second_run}

    backup = client.get(f"/api/projects/{project['id']}/export/json")
    assert backup.status_code == 200
    parsed = json.loads(backup.get_data(as_text=True))
    assert {
        "project", "characters", "locations", "scenes", "scene_characters",
        "shots", "frames", "assets", "memory", "chat_messages", "proposals",
        "continuity_issues", "search_log",
    } <= parsed.keys()
    assert parsed["project"]["id"] == project["id"]
    assert parsed["project"]["logline"] == "<img src=x onerror=alert(1)>"
    assert "Private other story" not in backup.get_data(as_text=True)

    printable = client.get(f"/api/projects/{project['id']}/export/html")
    html = printable.get_data(as_text=True)
    assert printable.mimetype == "text/html"
    assert "<script>alert(1)</script>" not in html
    assert "<script>run()</script>" not in html
    assert "<svg onload=alert(1)>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;script&gt;run()&lt;/script&gt;" in html
    assert client.get(f"/api/projects/{other['id']}/export/json").get_json()["project"]["id"] == other["id"]
