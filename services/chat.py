import json
from db.database import now_iso
from services.common import project_exists,boolean
from services.errors import ValidationError
from services.ai_provider import configured_provider,generate_text

SYSTEM='''You are StoryAI, a story-development assistant. Help the creator develop original stories, characters, scenes, shots and continuity. Treat saved project facts as canon. Never silently change canon. When suggesting a canon change, explain it as a suggestion that requires user approval. Be concise but useful. Do not invent project facts that conflict with saved memory.'''
CHAT_MAX_OUTPUT_TOKENS = 768

def context(db,pid):
    p=db.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone(); chars=db.execute('SELECT name,role,age,build,hair,face,default_outfit,distinguishing_marks,personality,abilities FROM characters WHERE project_id=? ORDER BY id',(pid,)).fetchall(); locs=db.execute('SELECT name,description,mood FROM locations WHERE project_id=? ORDER BY id',(pid,)).fetchall(); mem=db.execute('SELECT kind,content,locked FROM memory_items WHERE project_id=? ORDER BY locked DESC,id',(pid,)).fetchall(); scenes=db.execute('SELECT id,title,summary,time_of_day,status FROM scenes WHERE project_id=? ORDER BY order_no,id',(pid,)).fetchall(); msgs=db.execute('SELECT role,content FROM chat_messages WHERE project_id=? ORDER BY id DESC LIMIT 15',(pid,)).fetchall()[::-1]
    return {'project':dict(p),'characters':[dict(x) for x in chars],'locations':[dict(x) for x in locs],'memory':[dict(x) for x in mem],'scenes':[dict(x) for x in scenes],'messages':[dict(x) for x in msgs]}

def _prompt(c):
    return SYSTEM+'\n\nPROJECT CONTEXT:\n'+json.dumps(c,ensure_ascii=False,default=str)

def call_ai(db,pid,message,search_mode=False):
    project_exists(db,pid)
    project_context=context(db,pid)
    history=project_context.pop('messages',[])
    return generate_text(
        _prompt(project_context),
        message,
        history=history,
        web_search=search_mode,
        max_output_tokens=CHAT_MAX_OUTPUT_TOKENS,
    )

def send(db,pid,message,search_mode=False):
    search_mode=boolean(search_mode,'search_mode')
    project_exists(db,pid); message=message.strip() if isinstance(message,str) else ''
    if not message: raise ValidationError('Message cannot be empty.')
    if len(message)>8000: raise ValidationError('Message must be 8000 characters or fewer.')
    reply,sources=call_ai(db,pid,message,search_mode)
    log_search=search_mode and configured_provider()=='openai'
    with db:
        now=now_iso()
        mid=db.execute('INSERT INTO chat_messages(project_id,role,content,created_at) VALUES(?,?,?,?)',(pid,'user',message,now)).lastrowid
        aid=db.execute('INSERT INTO chat_messages(project_id,role,content,sources_json,created_at) VALUES(?,?,?,?,?)',(pid,'assistant',reply,json.dumps(sources),now_iso())).lastrowid
        if log_search: db.execute('INSERT INTO search_log(project_id,message_id,query) VALUES(?,?,?)',(pid,mid,message[:1000]))
    return {'user_message_id':mid,'assistant_message_id':aid,'reply':reply,'sources':sources}
def history(db,pid):
    project_exists(db,pid); return [{'id':r['id'],'role':r['role'],'content':r['content'],'sources':json.loads(r['sources_json'] or '[]'),'created_at':r['created_at']} for r in db.execute('SELECT * FROM chat_messages WHERE project_id=? ORDER BY id',(pid,))]
