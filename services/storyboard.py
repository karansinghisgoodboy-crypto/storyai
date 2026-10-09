"""Generate validated storyboard content and append it to an existing project."""

import json

from db.database import now_iso
from services.ai_provider import generate_text
from services.chat import _prompt, context
from services.common import project_exists
from services.errors import AppError, ValidationError

MAX_SCENES = 4
MAX_SHOTS_PER_SCENE = 8
MAX_TOTAL_SHOTS = 20
MAX_OUTPUT_TOKENS = 1600

SYSTEM = (
    "Create a concise, production-usable storyboard using the supplied saved "
    "project context as canon. Keep all established character identities, "
    "appearance, personalities, events, and continuity consistent. Do not "
    "invent saved character names or contradict saved facts. Return only one "
    "JSON object with a scenes array. Each scene must have title, summary, "
    "time_of_day, character_names, and shots. character_names must contain "
    "only exact names from the saved character list. Each shot must have "
    "shot_type, camera_angle, movement, action, dialogue, lighting, and notes."
)

SCENE_FIELDS = {
    "title": 200,
    "summary": 6000,
    "time_of_day": 100,
}
SHOT_FIELDS = {
    "shot_type": 120,
    "camera_angle": 200,
    "movement": 200,
    "action": 3000,
    "dialogue": 3000,
    "lighting": 500,
    "notes": 3000,
}


def _text_field(item, key, limit, *, required=False):
    value = item.get(key)
    if not isinstance(value, str):
        raise AppError("The AI returned an invalid storyboard. Please try again.")
    value = value.strip()
    if (required and not value) or len(value) > limit:
        raise AppError("The AI returned an invalid storyboard. Please try again.")
    return value


def _validate(raw, known_characters):
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise AppError("Could not read the AI storyboard. Please try again.") from None
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
        raise AppError("The AI returned an invalid storyboard. Please try again.")
    scenes = data["scenes"]
    if not scenes or len(scenes) > MAX_SCENES:
        raise AppError("The AI returned an invalid storyboard. Please try again.")

    canonical_ids = {}
    for row in known_characters:
        canonical_ids.setdefault(row["name"], []).append(row["id"])

    validated = []
    total_shots = 0
    for scene in scenes:
        if not isinstance(scene, dict):
            raise AppError("The AI returned an invalid storyboard. Please try again.")
        result = {
            key: _text_field(scene, key, limit, required=(key == "title"))
            for key, limit in SCENE_FIELDS.items()
        }
        character_names = scene.get("character_names")
        if not isinstance(character_names, list):
            raise AppError("The AI returned an invalid storyboard. Please try again.")
        character_ids = []
        seen_names = set()
        for name in character_names:
            if (
                not isinstance(name, str)
                or name not in canonical_ids
                or name in seen_names
                or len(canonical_ids[name]) != 1
            ):
                raise AppError("The AI returned an invalid storyboard. Please try again.")
            seen_names.add(name)
            character_ids.append(canonical_ids[name][0])

        shots = scene.get("shots")
        if (
            not isinstance(shots, list)
            or not shots
            or len(shots) > MAX_SHOTS_PER_SCENE
        ):
            raise AppError("The AI returned an invalid storyboard. Please try again.")
        result["character_ids"] = character_ids
        result["shots"] = []
        for shot in shots:
            if not isinstance(shot, dict):
                raise AppError("The AI returned an invalid storyboard. Please try again.")
            result["shots"].append(
                {
                    key: _text_field(shot, key, limit, required=(key == "action"))
                    for key, limit in SHOT_FIELDS.items()
                }
            )
        total_shots += len(result["shots"])
        if total_shots > MAX_TOTAL_SHOTS:
            raise AppError("The AI returned an invalid storyboard. Please try again.")
        validated.append(result)
    return validated


def generate(db, project_id, direction):
    project_exists(db, project_id)
    if not isinstance(direction, str) or not direction.strip():
        raise ValidationError("Storyboard direction cannot be empty.")
    if len(direction) > 8000:
        raise ValidationError("Storyboard direction must be 8000 characters or fewer.")

    project_context = context(db, project_id)
    history = project_context.pop("messages", [])
    known_characters = db.execute(
        "SELECT id,name FROM characters WHERE project_id=? ORDER BY id",
        (project_id,),
    ).fetchall()
    instruction = (
        "Create 1-4 scenes with numbered shots by their array order. Use 1-8 "
        "shots per scene and no more than 20 shots total. Keep each field "
        "within the existing StoryAI field limits. Return JSON only using "
        "this exact structure: {\"scenes\":[{\"title\":\"...\","
        "\"summary\":\"...\",\"time_of_day\":\"...\","
        "\"character_names\":[\"Exact saved name\"],\"shots\":[{"
        "\"shot_type\":\"...\",\"camera_angle\":\"...\","
        "\"movement\":\"...\",\"action\":\"...\",\"dialogue\":\"...\","
        "\"lighting\":\"...\",\"notes\":\"...\"}]}]}. Use an empty "
        "character_names array when no saved character appears."
    )
    raw, _ = generate_text(
        SYSTEM + "\n\nPROJECT CONTEXT:\n" + _prompt(project_context),
        direction.strip() + "\n\n" + instruction,
        history=history,
        json_mode=True,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    generated = _validate(raw, known_characters)

    next_scene_order = db.execute(
        "SELECT COALESCE(MAX(order_no),0)+1 FROM scenes WHERE project_id=?",
        (project_id,),
    ).fetchone()[0]
    created_scene_ids = []
    with db:
        for scene_offset, scene in enumerate(generated):
            now = now_iso()
            scene_id = db.execute(
                "INSERT INTO scenes "
                "(project_id,order_no,title,summary,time_of_day,status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,'draft',?,?)",
                (
                    project_id,
                    next_scene_order + scene_offset,
                    scene["title"],
                    scene["summary"],
                    scene["time_of_day"],
                    now,
                    now,
                ),
            ).lastrowid
            created_scene_ids.append(scene_id)
            for character_id in scene["character_ids"]:
                db.execute(
                    "INSERT INTO scene_characters(scene_id,character_id,outfit_state) "
                    "VALUES(?,?,?)",
                    (scene_id, character_id, ""),
                )
            for shot_order, shot in enumerate(scene["shots"], start=1):
                now = now_iso()
                db.execute(
                    "INSERT INTO shots "
                    "(project_id,scene_id,order_no,shot_type,camera_angle,movement,"
                    "action,dialogue,lighting,notes,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        project_id,
                        scene_id,
                        shot_order,
                        shot["shot_type"],
                        shot["camera_angle"],
                        shot["movement"],
                        shot["action"],
                        shot["dialogue"],
                        shot["lighting"],
                        shot["notes"],
                        now,
                        now,
                    ),
                )

    from services.scenes import get as get_scene
    from services.shots import list_shots

    saved = []
    for scene_id in created_scene_ids:
        scene = get_scene(db, project_id, scene_id)
        scene["shots"] = list_shots(db, project_id, scene_id)
        saved.append(scene)
    return {"scenes": saved}
