import json
import logging
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from services import ai_extract, ai_provider
from services.errors import AppError, ValidationError
from tests.conftest import make_project


class FakeHTTPResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def test_ollama_helper_posts_native_chat_payload_and_reads_reply(app, monkeypatch):
    app.config.update(
        AI_PROVIDER="ollama",
        OLLAMA_BASE_URL="http://ollama.test/",
        OLLAMA_MODEL="llama3.2:3b",
    )
    observed = {}

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        observed["payload"] = json.loads(request.data)
        return FakeHTTPResponse(
            json.dumps({"message": {"role": "assistant", "content": "A new chapter."}}).encode()
        )

    monkeypatch.setattr(ai_provider, "urlopen", fake_urlopen)
    with app.app_context():
        reply, sources = ai_provider.generate_text(
            "Story system prompt",
            "Continue the story.",
            history=[{"role": "user", "content": "A storm arrives."}],
            max_output_tokens=768,
        )

    assert reply == "A new chapter."
    assert sources == []
    assert observed["url"] == "http://ollama.test/api/chat"
    assert observed["timeout"] == 300
    assert observed["payload"]["model"] == "llama3.2:3b"
    assert observed["payload"]["stream"] is False
    assert observed["payload"]["options"] == {"num_predict": 768}
    assert observed["payload"]["keep_alive"] == "5m"
    assert observed["payload"]["messages"] == [
        {"role": "system", "content": "Story system prompt"},
        {"role": "user", "content": "A storm arrives."},
        {"role": "user", "content": "Continue the story."},
    ]


def test_ollama_helper_sets_json_mode_and_rejects_malformed_response(app, monkeypatch):
    app.config["AI_PROVIDER"] = "ollama"
    observed = {}

    def fake_urlopen(request, timeout):
        observed["payload"] = json.loads(request.data)
        return FakeHTTPResponse(b"{not json")

    monkeypatch.setattr(ai_provider, "urlopen", fake_urlopen)
    with app.app_context():
        with pytest.raises(AppError, match="Ollama returned an invalid response"):
            ai_provider.generate_text("system", "proposal", json_mode=True)
    assert observed["payload"]["format"] == "json"


def test_ollama_helper_maps_unavailable_and_empty_responses_to_friendly_errors(
    app, monkeypatch, caplog
):
    app.config["AI_PROVIDER"] = "ollama"

    for transport_error, expected in [
        (URLError(TimeoutError("private timeout detail")), "Ollama took too long"),
        (
            URLError(ConnectionRefusedError("private connection detail")),
            "Could not connect to Ollama",
        ),
        (URLError(OSError("private unavailable detail")), "Ollama is unavailable"),
    ]:
        monkeypatch.setattr(
            ai_provider,
            "urlopen",
            lambda *args, _error=transport_error, **kwargs: (_ for _ in ()).throw(_error),
        )
        with app.app_context():
            with pytest.raises(AppError, match=expected) as error:
                ai_provider.generate_text("system", "message")
        assert "private" not in str(error.value)
    assert "private" not in caplog.text
    assert "reason_type=TimeoutError" in caplog.text
    assert "reason_type=ConnectionRefusedError" in caplog.text
    assert "elapsed_seconds=" in caplog.text

    monkeypatch.setattr(
        ai_provider,
        "urlopen",
        lambda *args, **kwargs: FakeHTTPResponse(b'{"message":{"content":"  "}}'),
    )
    with app.app_context():
        with pytest.raises(AppError, match="Ollama returned an empty response"):
            ai_provider.generate_text("system", "message")


def test_ollama_generation_failure_http_and_invalid_response_are_distinct(app, monkeypatch):
    from urllib.error import HTTPError

    app.config["AI_PROVIDER"] = "ollama"
    monkeypatch.setattr(
        ai_provider,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            HTTPError("http://ollama.test/api/chat", 500, "error", {}, None)
        ),
    )
    with app.app_context():
        with pytest.raises(AppError, match="Ollama could not complete the request"):
            ai_provider.generate_text("system", "message")

    monkeypatch.setattr(ai_provider, "urlopen", lambda *args, **kwargs: FakeHTTPResponse(b"{bad"))
    with app.app_context():
        with pytest.raises(AppError, match="Ollama returned an invalid response"):
            ai_provider.generate_text("system", "message")

    monkeypatch.setattr(
        ai_provider,
        "urlopen",
        lambda *args, **kwargs: FakeHTTPResponse(b'{"error":"model unavailable"}'),
    )
    with app.app_context():
        with pytest.raises(AppError, match="Ollama could not complete the request"):
            ai_provider.generate_text("system", "message")


def test_ollama_logs_successful_request_duration(app, monkeypatch, caplog):
    app.config["AI_PROVIDER"] = "ollama"
    monkeypatch.setattr(
        ai_provider,
        "urlopen",
        lambda *args, **kwargs: FakeHTTPResponse(
            b'{"message":{"content":"READY"},"load_duration":250000000,"prompt_eval_count":12,"prompt_eval_duration":500000000,"eval_count":4,"eval_duration":2000000000}'
        ),
    )
    with caplog.at_level(logging.INFO), app.app_context():
        assert ai_provider.generate_text("system", "message") == ("READY", [])

    assert "Ollama request completed (elapsed_seconds=" in caplog.text
    assert "load_seconds=0.25" in caplog.text
    assert "prompt_tokens=12" in caplog.text
    assert "prompt_eval_seconds=0.5" in caplog.text
    assert "generated_tokens=4" in caplog.text
    assert "generation_seconds=2.0" in caplog.text
    assert "generation_tokens_per_second=2.0" in caplog.text


def test_chat_uses_ollama_context_and_stores_messages_only_after_success(client, app, db, monkeypatch):
    project = make_project(client, "Ollama chat")
    app.config.update(AI_PROVIDER="ollama", OLLAMA_MODEL="llama3.2:3b")
    db.execute(
        "INSERT INTO chat_messages(project_id,role,content) VALUES(?,?,?)",
        (project["id"], "user", "Previously saved context."),
    )
    db.commit()
    seen = {}

    def fake_urlopen(request, timeout):
        seen["payload"] = json.loads(request.data)
        return FakeHTTPResponse(
            b'{"message":{"role":"assistant","content":"The lantern glows."}}'
        )

    monkeypatch.setattr(ai_provider, "urlopen", fake_urlopen)
    response = client.post(
        f"/api/projects/{project['id']}/chat",
        json={"message": "What happens next?", "search_mode": False},
    )
    assert response.status_code == 200
    assert response.get_json()["reply"] == "The lantern glows."
    assert response.get_json()["sources"] == []
    assert [message["role"] for message in seen["payload"]["messages"]] == [
        "system", "user", "user"
    ]
    assert seen["payload"]["options"] == {"num_predict": 768}
    assert seen["payload"]["keep_alive"] == "5m"
    assert "Ollama chat" in seen["payload"]["messages"][0]["content"]
    history = client.get(f"/api/projects/{project['id']}/chat").get_json()["messages"]
    assert [message["content"] for message in history] == [
        "Previously saved context.",
        "What happens next?",
        "The lantern glows.",
    ]


def test_local_search_is_rejected_without_calling_ai_or_storing_chat(client, app, db, monkeypatch):
    project = make_project(client, "Local search")
    app.config["AI_PROVIDER"] = "ollama"
    monkeypatch.setattr(
        ai_provider,
        "urlopen",
        lambda *args, **kwargs: pytest.fail("Ollama must not receive a search request."),
    )
    response = client.post(
        f"/api/projects/{project['id']}/chat",
        json={"message": "Search for facts.", "search_mode": True},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Web search is unavailable with Ollama. Select OpenAI to use web search."
    )
    assert db.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM search_log").fetchone()[0] == 0


def test_openai_provider_keeps_optional_web_search_and_sources(app, monkeypatch):
    app.config.update(
        AI_PROVIDER="openai",
        OPENAI_API_KEY="non-secret-test-placeholder",
        OPENAI_MODEL="test-model",
    )
    observed = {}

    class FakeResponses:
        @staticmethod
        def create(**kwargs):
            observed["options"] = kwargs
            return SimpleNamespace(
                output_text="An answer.",
                output=[
                    SimpleNamespace(
                        content=[
                            SimpleNamespace(
                                type="web_search_result",
                                title="Reference",
                                url="https://example.test/source",
                            )
                        ]
                    )
                ],
            )

    class FakeClient:
        def __init__(self, api_key, timeout):
            observed["timeout"] = timeout

            class Responses:
                create = staticmethod(FakeResponses.create)

            self.responses = Responses()

    monkeypatch.setattr("openai.OpenAI", FakeClient)
    with app.app_context():
        reply, sources = ai_provider.generate_text(
            "system", "question", history=[{"role": "assistant", "content": "Earlier."}],
            web_search=True,
        )
    assert reply == "An answer."
    assert sources == [{"title": "Reference", "url": "https://example.test/source"}]
    assert observed["options"]["model"] == "test-model"
    assert observed["options"]["tools"] == [{"type": "web_search_preview"}]
    assert observed["options"]["input"][1] == {"role": "assistant", "content": "Earlier."}
    assert observed["timeout"] == ai_provider.OPENAI_REQUEST_TIMEOUT_SECONDS


def test_provider_selection_defaults_to_ollama_and_rejects_unknown_values(app):
    with app.app_context():
        app.config.pop("AI_PROVIDER", None)
        assert ai_provider.configured_provider() == "ollama"
        app.config["AI_PROVIDER"] = "something-else"
        with pytest.raises(ValidationError, match="AI_PROVIDER"):
            ai_provider.configured_provider()


def test_suggestions_use_provider_json_mode_and_validate_parsed_objects(client, app, monkeypatch):
    project = make_project(client, "Proposal JSON")
    app.config["AI_PROVIDER"] = "ollama"
    valid_proposal = {
        "type": "memory",
        "action": "add",
        "target_id": None,
        "payload": {"kind": "fact", "content": "The bell rings at dusk."},
        "reason": "Retain a creator-provided story fact.",
    }
    observed = {}

    def fake_generate(system_prompt, user_prompt, history=None, web_search=False, json_mode=False):
        observed.update(
            system=system_prompt,
            prompt=user_prompt,
            history=history,
            web_search=web_search,
            json_mode=json_mode,
        )
        return json.dumps([valid_proposal]), []

    monkeypatch.setattr(ai_extract, "generate_text", fake_generate)
    response = client.post(
        f"/api/projects/{project['id']}/suggest",
        json={"text": "The bell rings at dusk."},
    )
    assert response.status_code == 200
    assert json.loads(response.get_json()["proposals"][0]["payload"]) == valid_proposal["payload"]
    assert observed["json_mode"] is True
    assert observed["web_search"] is False
    assert client.get(f"/api/projects/{project['id']}/memory").get_json()["memory"] == []


@pytest.mark.parametrize(
    "model_text",
    [
        "not json",
        '{"type":"memory"}',
        '[{"type":"unknown","action":"add","target_id":null,"payload":{},"reason":"x"}]',
        '[{"type":"memory","action":"update","target_id":null,"payload":{},"reason":"x"}]',
    ],
)
def test_malformed_ai_suggestion_content_is_rejected(client, app, monkeypatch, model_text):
    project = make_project(client, "Malformed proposal")
    app.config["AI_PROVIDER"] = "ollama"
    monkeypatch.setattr(
        ai_extract,
        "generate_text",
        lambda *args, **kwargs: (model_text, []),
    )
    response = client.post(
        f"/api/projects/{project['id']}/suggest",
        json={"text": "Suggest a story fact."},
    )
    assert response.status_code == 400
    assert "suggestions" in response.get_json()["error"].lower()
    assert client.get(f"/api/projects/{project['id']}/proposals").get_json()["proposals"] == []


def test_suggestions_report_ollama_unavailable_without_creating_proposals(
    client, app, monkeypatch
):
    project = make_project(client, "Unavailable suggestions")
    app.config["AI_PROVIDER"] = "ollama"
    monkeypatch.setattr(
        ai_provider,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(URLError("offline")),
    )
    response = client.post(
        f"/api/projects/{project['id']}/suggest",
        json={"text": "Suggest a detail."},
    )
    assert response.status_code == 400
    assert response.get_json()["error"].startswith("Ollama is unavailable.")
    assert client.get(f"/api/projects/{project['id']}/proposals").get_json()["proposals"] == []
