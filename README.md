# StoryAI

StoryAI is a local Flask + SQLite + vanilla JavaScript workspace for developing stories and storyboards with AI assistance.

## MVP features
- Project create/open/rename/delete and persistent story data
- Character and location sheets with locking and optimistic concurrency
- Secure image uploads for character/location/storyboard assets
- Location library with name, description and atmosphere (stored in the existing `mood` field)
- Story, scenes, characters-in-scenes and storyboard shots
- AI chat and suggestions through local Ollama by default, with optional OpenAI provider
- Optional OpenAI web search mode (not available through local Ollama)
- Suggestion/proposal workflow: AI suggestions never become canon automatically
- Structured memory
- Rule-based continuity checker with dismiss fingerprints
- Complete project JSON backup (including uploaded image/thumbnail bytes without disk paths) and self-contained printable HTML storyboard export
- Security headers and backend-only API key handling

## Run on Windows (PowerShell)

From the project folder, create a virtual environment, copy the example settings,
and install the dependencies:

```powershell
py -m venv .venv
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The default provider uses Ollama locally and does not need an OpenAI API key or
credits. In one PowerShell window, start Ollama:

```powershell
ollama serve
```

In a second PowerShell window, from the StoryAI project folder, download the
configured model and start StoryAI:

```powershell
ollama pull llama3.2:3b
.\.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000`. `AI_PROVIDER`, `OLLAMA_BASE_URL`, and
`OLLAMA_MODEL` can be adjusted in the local `.env` if needed. Ollama search mode
is not supported; select OpenAI to use web search.

To use OpenAI instead, set `AI_PROVIDER=openai` in `.env` and provide your own
`OPENAI_API_KEY`. `OPENAI_MODEL` is optional and defaults to `gpt-5-mini`.

Run the test suite with:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Security

Keep `.env` on your local machine. **Never share it, upload it, or commit it**:
it may contain your API key. `.env.example` contains placeholders only and is
safe to keep with the project. The API key is read by backend configuration and
must not be added to browser JavaScript, HTML, or client-visible responses.
Local databases, uploads, logs, caches, virtual environments, and generated
release archives are excluded by `.gitignore`.
