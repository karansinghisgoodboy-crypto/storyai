# StoryAI development rules

- Preserve Flask + SQLite + vanilla JS architecture.
- Never expose OPENAI_API_KEY to the browser or commit `.env`.
- AI suggestions are proposals; never silently modify canon.
- Respect locked records and optimistic concurrency (`updated_at` / HTTP 409).
- Keep routes thin and business logic in services.
- Run `pytest` after changes when dependencies are installed.
- MVP first; do not add V2 features unless explicitly requested.
