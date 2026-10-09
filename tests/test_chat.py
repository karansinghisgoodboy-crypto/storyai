from services.errors import AppError
from tests.conftest import make_project


def test_chat_failure_does_not_persist_an_unpaired_user_message(client, db, monkeypatch):
    project = make_project(client, "Chat story")

    def fail(*args, **kwargs):
        raise AppError("AI is not configured yet.")

    monkeypatch.setattr("services.chat.call_ai", fail)
    response = client.post(
        f"/api/projects/{project['id']}/chat",
        json={"message": "Continue the story.", "search_mode": False},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "AI is not configured yet."}
    assert client.get(f"/api/projects/{project['id']}/chat").get_json()["messages"] == []
    assert db.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0] == 0


def test_chat_retry_saves_exactly_one_user_and_assistant_pair(client, monkeypatch):
    project = make_project(client, "Chat retry")
    attempts = 0

    def sometimes_fails(db, project_id, message, search_mode):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AppError("Temporary AI error.")
        return "A lantern appears.", [{"title": "Source", "url": "https://example.test"}]

    monkeypatch.setattr("services.chat.call_ai", sometimes_fails)
    url = f"/api/projects/{project['id']}/chat"
    payload = {"message": "Continue the story.", "search_mode": True}

    first = client.post(url, json=payload)
    assert first.status_code == 400
    assert client.get(url).get_json()["messages"] == []

    second = client.post(url, json=payload)
    assert second.status_code == 200
    history = client.get(url).get_json()["messages"]
    assert [(item["role"], item["content"]) for item in history] == [
        ("user", "Continue the story."),
        ("assistant", "A lantern appears."),
    ]
    assert history[1]["sources"] == [{"title": "Source", "url": "https://example.test"}]


def test_chat_rejects_string_search_flag_without_calling_ai(client, monkeypatch):
    project = make_project(client, "Search flag")
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Chat provider should not be called for invalid input.")

    monkeypatch.setattr("services.chat.call_ai", fail_if_called)
    response = client.post(
        f"/api/projects/{project['id']}/chat",
        json={"message": "Question", "search_mode": "false"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "search_mode must be true or false."}
    assert not called


def test_invalid_ai_suggestion_is_reported_without_silently_skipping(client, monkeypatch):
    project = make_project(client, "Suggestions")
    monkeypatch.setattr(
        "routes.chat.ai_extract.suggest",
        lambda *args: [
            {
                "type": "memory",
                "action": "add",
                "payload": {"kind": "fact", "content": "A useful fact."},
                "reason": "Remember it.",
            },
            {"type": "unknown", "action": "add", "payload": {}},
        ],
    )

    response = client.post(
        f"/api/projects/{project['id']}/suggest",
        json={"text": "A useful fact."},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid proposal."
    assert client.get(f"/api/projects/{project['id']}/proposals").get_json()["proposals"] == []
