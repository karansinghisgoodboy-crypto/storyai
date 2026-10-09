import json
from services.chat import _prompt, context
from services.common import project_exists
from services.ai_provider import generate_text
from services.errors import AppError,ValidationError

PROPOSAL_TYPES={"character","location","memory","scene","shot","story_field"}

def _validate_proposals(proposals):
    if not isinstance(proposals,list):
        raise AppError("The AI returned invalid suggestions. Please try again.")
    for proposal in proposals:
        if not isinstance(proposal,dict) or not {
            "type","action","target_id","payload","reason"
        }.issubset(proposal):
            raise AppError("The AI returned invalid suggestions. Please try again.")
        if proposal["type"] not in PROPOSAL_TYPES or proposal["action"] not in ("add","update"):
            raise AppError("The AI returned invalid suggestions. Please try again.")
        if not isinstance(proposal["payload"],dict) or not isinstance(proposal["reason"],str):
            raise AppError("The AI returned invalid suggestions. Please try again.")
        target_id=proposal["target_id"]
        if proposal["action"]=="update":
            if isinstance(target_id,bool) or not isinstance(target_id,int) or target_id<1:
                raise AppError("The AI returned invalid suggestions. Please try again.")
        elif target_id is not None and (
            isinstance(target_id,bool) or not isinstance(target_id,int) or target_id<1
        ):
            raise AppError("The AI returned invalid suggestions. Please try again.")
    return proposals

def suggest(db,pid,text_input):
    project_exists(db,pid)
    if not isinstance(text_input,str) or not text_input.strip():
        raise ValidationError("Suggestion text cannot be empty.")
    if len(text_input)>8000:
        raise ValidationError("Suggestion text must be 8000 characters or fewer.")

    project_context=context(db,pid)
    history=project_context.pop("messages",[])
    instruction=(
        "Analyze the creator's latest message. Return ONLY a valid JSON array. "
        "Each proposal object must contain exactly these fields: type "
        "(character/location/memory/scene/shot/story_field), action (add/update), "
        "target_id (integer for updates, otherwise null unless clearly known), "
        "payload (object), and reason (string). Never invent IDs. Only suggest "
        "clear, useful changes. These are proposals only; do not claim changes "
        "have been applied."
    )
    raw,_=generate_text(
        _prompt(project_context)+"\n\n"+instruction,
        text_input.strip(),
        history=history,
        json_mode=True,
    )
    try:
        proposals=json.loads(raw)
    except (TypeError,json.JSONDecodeError):
        raise AppError("Couldn’t read the AI suggestions. Please try again.") from None
    return _validate_proposals(proposals)
