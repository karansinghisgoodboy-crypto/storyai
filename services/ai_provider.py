"""Shared text-generation interface for configured StoryAI AI providers."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app

from services.errors import AppError, ValidationError

OLLAMA_REQUEST_TIMEOUT_SECONDS = 300
OPENAI_REQUEST_TIMEOUT_SECONDS = 60
SUPPORTED_PROVIDERS = {"ollama", "openai"}


def configured_provider():
    provider = current_app.config.get("AI_PROVIDER", "ollama")
    provider = provider.strip().lower() if isinstance(provider, str) else ""
    provider = provider or "ollama"
    if provider not in SUPPORTED_PROVIDERS:
        raise ValidationError("AI_PROVIDER must be set to 'ollama' or 'openai'.")
    return provider


def _messages(system_prompt, history, user_prompt):
    messages = [{"role": "system", "content": system_prompt}]
    for item in history or []:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})
    return messages


def _ollama_text(system_prompt, user_prompt, history, json_mode, max_output_tokens):
    base_url = current_app.config.get(
        "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
    ).rstrip("/")
    model = current_app.config.get("OLLAMA_MODEL", "llama3.2:3b")
    if not base_url or not isinstance(model, str) or not model.strip():
        raise ValidationError("OLLAMA_BASE_URL and OLLAMA_MODEL must be configured.")

    payload = {
        "model": model.strip(),
        "messages": _messages(system_prompt, history, user_prompt),
        "stream": False,
        "keep_alive": "5m",
    }
    if max_output_tokens is not None:
        if (
            not isinstance(max_output_tokens, int)
            or isinstance(max_output_tokens, bool)
            or max_output_tokens < 1
        ):
            raise ValidationError("max_output_tokens must be a positive integer.")
        payload["options"] = {"num_predict": max_output_tokens}
    if json_mode:
        payload["format"] = "json"
    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started_at = time.monotonic()
    try:
        with urlopen(request, timeout=OLLAMA_REQUEST_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        current_app.logger.warning(
            "Ollama request failed (HTTP status=%s, elapsed_seconds=%.2f).",
            error.code,
            time.monotonic() - started_at,
        )
        raise AppError(
            "Ollama could not complete the request. Check the local model and try again."
        ) from None
    except (URLError, TimeoutError, ConnectionError) as error:
        reason = error.reason if isinstance(error, URLError) else error
        if isinstance(reason, TimeoutError):
            current_app.logger.warning(
                "Ollama request timed out (reason_type=%s, elapsed_seconds=%.2f).",
                type(reason).__name__,
                time.monotonic() - started_at,
            )
            raise AppError(
                "Ollama took too long to respond. Try again when the computer is less busy."
            ) from None
        if isinstance(reason, ConnectionError):
            current_app.logger.warning(
                "Ollama connection failed (reason_type=%s, elapsed_seconds=%.2f).",
                type(reason).__name__,
                time.monotonic() - started_at,
            )
            raise AppError(
                "Could not connect to Ollama. Check that its local server is running."
            ) from None
        current_app.logger.warning(
            "Ollama is unavailable (transport_error=%s, reason_type=%s, "
            "elapsed_seconds=%.2f).",
            type(error).__name__,
            type(reason).__name__,
            time.monotonic() - started_at,
        )
        raise AppError(
            "Ollama is unavailable. Start Ollama and confirm the local model is installed."
        ) from None
    except ConnectionError as error:
        current_app.logger.warning(
            "Ollama connection failed (reason_type=%s, elapsed_seconds=%.2f).",
            type(error).__name__,
            time.monotonic() - started_at,
        )
        raise AppError(
            "Could not connect to Ollama. Check that its local server is running."
        ) from None
    except TimeoutError:
        current_app.logger.warning(
            "Ollama request timed out (elapsed_seconds=%.2f).",
            time.monotonic() - started_at,
        )
        raise AppError(
            "Ollama took too long to respond. Try again when the computer is less busy."
        ) from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        current_app.logger.warning(
            "Ollama returned an invalid response (elapsed_seconds=%.2f).",
            time.monotonic() - started_at,
        )
        raise AppError("Ollama returned an invalid response. Please try again.") from None
    except OSError as error:
        current_app.logger.warning(
            "Ollama request failed (local_io_error=%s, elapsed_seconds=%.2f).",
            type(error).__name__,
            time.monotonic() - started_at,
        )
        raise AppError(
            "Ollama is unavailable. Start Ollama and confirm the local model is installed."
        ) from None

    if not isinstance(result, dict):
        raise AppError("Ollama returned an invalid response. Please try again.")
    prompt_eval_count = result.get("prompt_eval_count")
    prompt_eval_duration = result.get("prompt_eval_duration")
    eval_count = result.get("eval_count")
    eval_duration = result.get("eval_duration")
    tokens_per_second = None
    if isinstance(eval_count, int) and isinstance(eval_duration, int) and eval_duration > 0:
        tokens_per_second = eval_count / (eval_duration / 1_000_000_000)
    current_app.logger.info(
        "Ollama request completed (elapsed_seconds=%.2f, load_seconds=%s, "
        "prompt_tokens=%s, prompt_eval_seconds=%s, generated_tokens=%s, "
        "generation_seconds=%s, generation_tokens_per_second=%s).",
        time.monotonic() - started_at,
        _duration_seconds(result.get("load_duration")),
        prompt_eval_count,
        _duration_seconds(prompt_eval_duration),
        eval_count,
        _duration_seconds(eval_duration),
        round(tokens_per_second, 2) if tokens_per_second is not None else None,
    )
    if result.get("error"):
        current_app.logger.warning("Ollama returned a model/API error response.")
        raise AppError(
            "Ollama could not complete the request. Check that the configured local model is available."
        )
    message = result.get("message")
    text = message.get("content") if isinstance(message, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise AppError("Ollama returned an empty response. Please try again.")
    return text.strip(), []


def _duration_seconds(value):
    if isinstance(value, int) and value >= 0:
        return round(value / 1_000_000_000, 2)
    return None


def _openai_text(system_prompt, user_prompt, history, web_search, json_mode):
    api_key = current_app.config.get("OPENAI_API_KEY", "")
    if not api_key:
        raise AppError(
            "OpenAI is selected but OPENAI_API_KEY is missing from the local .env file."
        )
    model = current_app.config.get("OPENAI_MODEL", "") or "gpt-5-mini"
    input_messages = _messages(system_prompt, history, user_prompt)
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=OPENAI_REQUEST_TIMEOUT_SECONDS)
        options = {"model": model, "input": input_messages}
        if web_search:
            options["tools"] = [{"type": "web_search_preview"}]
        if json_mode:
            options["text"] = {"format": {"type": "json_object"}}
        response = client.responses.create(**options)
    except Exception as error:
        current_app.logger.warning(
            "OpenAI request failed (error type: %s).", type(error).__name__
        )
        raise AppError(
            "The OpenAI request failed. Check the configured key/model or try again."
        ) from None

    text = getattr(response, "output_text", None)
    if not isinstance(text, str) or not text.strip():
        raise AppError("OpenAI returned an empty response. Please try again.")

    sources = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") in ("web_search_call", "web_search_result"):
                url = getattr(content, "url", None)
                title = getattr(content, "title", None)
                if url:
                    sources.append({"title": title or url, "url": url})
    return text.strip(), sources


def generate_text(
    system_prompt,
    user_prompt,
    history=None,
    web_search=False,
    json_mode=False,
    max_output_tokens=None,
):
    provider = configured_provider()
    if provider == "ollama":
        if web_search:
            raise ValidationError(
                "Web search is unavailable with Ollama. Select OpenAI to use web search."
            )
        return _ollama_text(
            system_prompt, user_prompt, history, json_mode, max_output_tokens
        )
    return _openai_text(system_prompt, user_prompt, history, web_search, json_mode)
