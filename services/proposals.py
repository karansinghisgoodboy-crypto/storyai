import json
from db.database import now_iso
from services.common import project_exists,boolean,positive_int
from services.errors import NotFoundError,ConflictError,ValidationError
ALLOWED={'character','location','memory','scene','shot','story_field'}

def list_pending(db,pid):
    project_exists(db,pid); return [dict(r) for r in db.execute('SELECT * FROM proposals WHERE project_id=? AND status="pending" ORDER BY id DESC',(pid,))]

def validate(db,pid,data):
    project_exists(db,pid)
    if not isinstance(data,dict): raise ValidationError('Invalid proposal.')
    typ=data.get('type'); action=data.get('action')
    if typ not in ALLOWED or action not in ('add','update'): raise ValidationError('Invalid proposal.')
    if not isinstance(data.get('payload',{}),dict): raise ValidationError('Proposal payload must be an object.')
    if action=='update':
        positive_int(data.get('target_id'),'target_id')
    return data

def create(db,pid,data):
    validate(db,pid,data); typ=data.get('type'); action=data.get('action')
    payload=data.get('payload',{}); reason=str(data.get('reason',''))[:2000]; target=data.get('target_id'); base=data.get('base_updated_at')
    with db:
        cur=db.execute('INSERT INTO proposals(project_id,type,action,target_id,payload,reason,base_updated_at) VALUES(?,?,?,?,?,?,?)',(pid,typ,action,target,json.dumps(payload),reason,base))
    return dict(db.execute('SELECT * FROM proposals WHERE id=?',(cur.lastrowid,)).fetchone())

def _target(db,p):
    table={'character':'characters','location':'locations','memory':'memory_items','scene':'scenes','shot':'shots'}.get(p['type'])
    if p['type']=='story_field': return db.execute('SELECT * FROM projects WHERE id=?',(p['project_id'],)).fetchone()
    if not table:return None
    return db.execute(f'SELECT * FROM {table} WHERE id=? AND project_id=?',(p['target_id'],p['project_id'])).fetchone()

def resolve(db,pid,proposal_id,accept):
    accept=boolean(accept,'accept')
    p=db.execute('SELECT * FROM proposals WHERE id=? AND project_id=?',(proposal_id,pid)).fetchone()
    if not p: raise NotFoundError('Proposal not found.')
    if p['status']!='pending': raise ConflictError('This proposal is already resolved.')
    if not accept:
        with db: db.execute('UPDATE proposals SET status="rejected",resolved_at=? WHERE id=?',(now_iso(),proposal_id))
        return dict(db.execute('SELECT * FROM proposals WHERE id=?',(proposal_id,)).fetchone())
    payload=json.loads(p['payload'] or '{}'); target=_target(db,p)
    if p['action']=='update':
        if not target: raise NotFoundError('The proposal target no longer exists.')
        if target['updated_at']!=p['base_updated_at']: raise ConflictError('Item changed since this suggestion was created. Review it before applying.')
        if 'locked' in target.keys() and target['locked']: raise ConflictError('The target is locked. Unlock it before applying this suggestion.')
    if p['type']=='story_field':
        allowed={'logline','genre','tone','synopsis','story_text'}; updates={k:v for k,v in payload.items() if k in allowed}
        if updates:
            sets=', '.join(f'{k}=?' for k in updates); vals=list(updates.values())+[now_iso(),pid,p['base_updated_at']]
            with db: cur=db.execute(f'UPDATE projects SET {sets},updated_at=? WHERE id=? AND updated_at=?',vals)
            if not cur.rowcount: raise ConflictError('Project changed since this suggestion was created.')
    elif p['type']=='memory' and p['action']=='add':
        from services.memory import create; create(db,pid,payload)
    elif p['type']=='location' and p['action']=='add':
        from services.locations import create; create(db,pid,payload)
    elif p['type']=='character':
        from services.characters import create_character, update_character
        if p['action']=='add': create_character(db,pid,payload)
        else: payload['updated_at']=p['base_updated_at']; update_character(db,pid,p['target_id'],payload)
    elif p['type']=='location':
        from services.locations import create, update
        if p['action']=='add': create(db,pid,payload)
        else: payload['updated_at']=p['base_updated_at']; update(db,pid,p['target_id'],payload)
    elif p['type']=='memory':
        from services.memory import create, update
        if p['action']=='add': create(db,pid,payload)
        else: payload['updated_at']=p['base_updated_at']; update(db,pid,p['target_id'],payload)
    elif p['type']=='scene':
        from services.scenes import create, update
        if p['action']=='add': create(db,pid,payload)
        else: payload['updated_at']=p['base_updated_at']; update(db,pid,p['target_id'],payload)
    elif p['type']=='shot':
        from services.shots import create, update
        sid=payload.pop('scene_id',None) or (target['scene_id'] if target else None)
        if p['action']=='add': create(db,pid,sid,payload)
        else: payload['updated_at']=p['base_updated_at']; update(db,pid,sid,p['target_id'],payload)
    else:
        raise ValidationError('This proposal type is not supported for automatic application yet.')
    with db: db.execute('UPDATE proposals SET status="accepted",resolved_at=? WHERE id=?',(now_iso(),proposal_id))
    return dict(db.execute('SELECT * FROM proposals WHERE id=?',(proposal_id,)).fetchone())
