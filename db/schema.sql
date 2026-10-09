-- StoryAI database schema (SQLite).
-- Safe to run on every start: every statement uses IF NOT EXISTS.
-- Foreign keys are switched on for every connection in db/database.py.
-- Timestamps are UTC text like 2026-10-08T12:30:45.123456Z (sortable, and
-- compared as plain strings for stale-write detection).

CREATE TABLE IF NOT EXISTS projects (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    title                   TEXT NOT NULL CHECK (length(trim(title)) > 0),
    logline                 TEXT NOT NULL DEFAULT '',
    genre                   TEXT NOT NULL DEFAULT '',
    tone                    TEXT NOT NULL DEFAULT '',
    synopsis                TEXT NOT NULL DEFAULT '',
    story_text              TEXT NOT NULL DEFAULT '',
    -- Rolling chat summary (used by project memory in a later step)
    summary_text            TEXT NOT NULL DEFAULT '',
    summary_upto_message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content      TEXT NOT NULL,
    sources_json TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_project ON chat_messages(project_id, id);

CREATE TABLE IF NOT EXISTS memory_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('fact', 'rule', 'theme', 'note')),
    content    TEXT NOT NULL CHECK (length(trim(content)) > 0),
    locked     INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_memory_items_project ON memory_items(project_id);

-- Uploaded images. Paths are relative to the uploads folder (for example
-- "characters/9f3a....jpg"). A character, location or storyboard panel points
-- at its image through image_id / asset_id.
CREATE TABLE IF NOT EXISTS assets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL CHECK (kind IN ('character', 'location', 'panel')),
    file_path   TEXT NOT NULL,
    thumb_path  TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);

CREATE TABLE IF NOT EXISTS characters (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id           INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name                 TEXT NOT NULL CHECK (length(trim(name)) > 0),
    role                 TEXT NOT NULL DEFAULT '',
    -- Appearance sheet: one column per detail, so a conflict such as
    -- "hair: black" vs "hair: white" can be detected field by field.
    age                  TEXT NOT NULL DEFAULT '',
    build                TEXT NOT NULL DEFAULT '',
    hair                 TEXT NOT NULL DEFAULT '',
    face                 TEXT NOT NULL DEFAULT '',
    appearance           TEXT NOT NULL DEFAULT '',
    default_outfit       TEXT NOT NULL DEFAULT '',
    distinguishing_marks TEXT NOT NULL DEFAULT '',
    personality          TEXT NOT NULL DEFAULT '',
    backstory            TEXT NOT NULL DEFAULT '',
    voice                TEXT NOT NULL DEFAULT '',
    abilities            TEXT NOT NULL DEFAULT '',
    image_id             INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    locked               INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_characters_project ON characters(project_id);

CREATE TABLE IF NOT EXISTS locations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT NOT NULL DEFAULT '',
    mood        TEXT NOT NULL DEFAULT '',
    image_id    INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    locked      INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_locations_project ON locations(project_id);

CREATE TABLE IF NOT EXISTS scenes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    order_no    INTEGER NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    summary     TEXT NOT NULL DEFAULT '',
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    time_of_day TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'review', 'final')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_scenes_project_order ON scenes(project_id, order_no);

-- Which characters appear in a scene, plus an explicit outfit/state note
-- for that scene (for example "wounded, torn jacket").
CREATE TABLE IF NOT EXISTS scene_characters (
    scene_id     INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    outfit_state TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (scene_id, character_id)
);
CREATE INDEX IF NOT EXISTS idx_scene_characters_character ON scene_characters(character_id);

CREATE TABLE IF NOT EXISTS shots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_id     INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    order_no     INTEGER NOT NULL,
    shot_type    TEXT NOT NULL DEFAULT '',
    camera_angle TEXT NOT NULL DEFAULT '',
    movement     TEXT NOT NULL DEFAULT '',
    action       TEXT NOT NULL DEFAULT '',
    dialogue     TEXT NOT NULL DEFAULT '',
    lighting     TEXT NOT NULL DEFAULT '',
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_shots_scene_order ON shots(scene_id, order_no);
CREATE INDEX IF NOT EXISTS idx_shots_project ON shots(project_id);

-- A storyboard panel: one per shot, holding the uploaded image or sketch.
CREATE TABLE IF NOT EXISTS frames (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    shot_id    INTEGER NOT NULL UNIQUE REFERENCES shots(id) ON DELETE CASCADE,
    asset_id   INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_frames_project ON frames(project_id);

-- AI suggestions waiting for the user. Nothing here touches canon until accepted.
CREATE TABLE IF NOT EXISTS proposals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type            TEXT NOT NULL CHECK (type IN
                      ('character', 'location', 'memory', 'scene', 'shot', 'story_field')),
    action          TEXT NOT NULL CHECK (action IN ('add', 'update')),
    target_id       INTEGER,
    payload         TEXT NOT NULL DEFAULT '{}',
    reason          TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'accepted', 'rejected')),
    base_updated_at TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    resolved_at     TEXT,
    CHECK (action = 'add' OR target_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_proposals_project_status ON proposals(project_id, status);

-- Continuity problems. "fingerprint" identifies the same problem across runs
-- so a dismissed issue does not come back.
CREATE TABLE IF NOT EXISTS continuity_issues (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_id        INTEGER REFERENCES scenes(id) ON DELETE SET NULL,
    type            TEXT NOT NULL CHECK (type IN
                      ('character', 'location', 'timeline', 'object', 'dialogue', 'structure')),
    severity        TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high')),
    description     TEXT NOT NULL,
    suggested_fix   TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'open'
                      CHECK (status IN ('open', 'resolved', 'dismissed')),
    fingerprint     TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (project_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_continuity_issues_project ON continuity_issues(project_id, status);

-- One row each time web search is used in chat (to watch cost).
CREATE TABLE IF NOT EXISTS search_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    message_id INTEGER REFERENCES chat_messages(id) ON DELETE SET NULL,
    query      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_search_log_project ON search_log(project_id);
