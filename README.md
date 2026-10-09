# StoryAI

StoryAI is a local Flask + SQLite + vanilla JavaScript workspace for developing stories and storyboards with AI assistance.

## MVP features
- Project create/open/rename/delete and persistent story data
- Character and location sheets with locking and optimistic concurrency
- Secure image uploads for character/location/storyboard assets
- Location library with name, description and atmosphere (stored in the existing `mood` field)
- Story, scenes, characters-in-scenes and storyboard shots
- AI chat through the backend using the OpenAI Responses API
- Optional web search mode attached to chat
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

In the local `.env` file, add your own OpenAI API key to `OPENAI_API_KEY` if you
want to use AI chat or suggestions. `OPENAI_MODEL` is optional; when blank, the
application uses `gpt-5-mini`. The application can also run without an API key,
but AI features will not be available.

Start StoryAI:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000`. Run the test suite with:

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
