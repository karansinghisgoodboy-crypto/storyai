from db.database import now_iso
from services.common import project_exists,text,expected_version,positive_int
from services.errors import NotFoundError,ValidationError,ConflictError

def _row(db,r):
    d=dict(r); d['characters']=[dict(x) for x in db.execute('SELECT c.id,c.name,sc.outfit_state FROM scene_characters sc JOIN characters c ON c.id=sc.character_id WHERE sc.scene_id=? ORDER BY c.name',(r['id'],))]; return d

def list_scenes(db,pid):
    project_exists(db,pid); return [_row(db,r) for r in db.execute('SELECT * FROM scenes WHERE project_id=? ORDER BY order_no,id',(pid,))]
def get(db,pid,sid):
    project_exists(db,pid); r=db.execute('SELECT * FROM scenes WHERE id=? AND project_id=?',(sid,pid)).fetchone()
    if not r: raise NotFoundError('Scene not found.')
    return _row(db,r)
def _order(db,pid): return (db.execute('SELECT COALESCE(MAX(order_no),0)+1 n FROM scenes WHERE project_id=?',(pid,)).fetchone()['n'])
def create(db,pid,data):
    project_exists(db,pid); title=text(data.get('title'),'title',200); summary=text(data.get('summary'),'summary',6000); tod=text(data.get('time_of_day'),'time_of_day',100); status=data.get('status','draft')
    if status not in ('draft','review','final'): raise ValidationError('Invalid scene status.')
    loc=data.get('location_id');
    if loc is not None: loc=positive_int(loc,'location_id')
    if loc is not None and db.execute('SELECT 1 FROM locations WHERE id=? AND project_id=?',(loc,pid)).fetchone() is None: raise ValidationError('Location does not belong to this project.')
    order=data.get('order_no')
    order=_order(db,pid) if order is None else positive_int(order,'order_no')
    now=now_iso()
    with db:
        cur=db.execute('INSERT INTO scenes (project_id,order_no,title,summary,location_id,time_of_day,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',(pid,order,title,summary,loc,tod,status,now,now))
    return get(db,pid,cur.lastrowid)
def update(db,pid,sid,data):
    r=db.execute('SELECT * FROM scenes WHERE id=? AND project_id=?',(sid,pid)).fetchone()
    if not r: raise NotFoundError('Scene not found.')
    expected_version(r,data)
    loc=data.get('location_id',r['location_id'])
    if loc is not None: loc=positive_int(loc,'location_id')
    vals=[text(data.get('title',r['title']),'title',200),text(data.get('summary',r['summary']),'summary',6000),loc,text(data.get('time_of_day',r['time_of_day']),'time_of_day',100),data.get('status',r['status']),positive_int(data.get('order_no',r['order_no']),'order_no')]
    if vals[2] is not None and db.execute('SELECT 1 FROM locations WHERE id=? AND project_id=?',(vals[2],pid)).fetchone() is None: raise ValidationError('Location does not belong to this project.')
    if vals[4] not in ('draft','review','final'): raise ValidationError('Invalid scene status.')
    now=now_iso()
    with db: cur=db.execute('UPDATE scenes SET title=?,summary=?,location_id=?,time_of_day=?,status=?,order_no=?,updated_at=? WHERE id=? AND project_id=? AND updated_at=?',(*vals,now,sid,pid,r['updated_at']))
    if not cur.rowcount: raise ConflictError('This scene changed since you loaded it. Reload the latest version.')
    return get(db,pid,sid)
def set_characters(db,pid,sid,items,updated_at=None):
    scene=db.execute('SELECT * FROM scenes WHERE id=? AND project_id=?',(sid,pid)).fetchone()
    if not scene:
        raise NotFoundError('Scene not found.')
    expected_version(scene,{'updated_at':updated_at})
    if not isinstance(items,list): raise ValidationError('characters must be a list.')
    validated=[]
    seen=set()
    for item in items:
        if not isinstance(item,dict): raise ValidationError('Each scene character must be an object.')
        cid=positive_int(item.get('character_id'),'character_id')
        if cid in seen: raise ValidationError('A character can only be linked to a scene once.')
        seen.add(cid)
        state=text(item.get('outfit_state'),'outfit_state',1000)
        if db.execute('SELECT 1 FROM characters WHERE id=? AND project_id=?',(cid,pid)).fetchone() is None: raise ValidationError('Character does not belong to this project.')
        validated.append((cid,state))
    with db:
        now=now_iso()
        cur=db.execute('UPDATE scenes SET updated_at=? WHERE id=? AND project_id=? AND updated_at=?',(now,sid,pid,scene['updated_at']))
        if cur.rowcount != 1:
            raise ConflictError('This scene changed since you loaded it. Reload the latest version.')
        db.execute('DELETE FROM scene_characters WHERE scene_id=?',(sid,))
        for cid,state in validated:
            db.execute('INSERT INTO scene_characters(scene_id,character_id,outfit_state) VALUES(?,?,?)',(sid,cid,state))
    return get(db,pid,sid)
def delete(db,pid,sid):
    r=db.execute('SELECT * FROM scenes WHERE id=? AND project_id=?',(sid,pid)).fetchone()
    if not r: raise NotFoundError('Scene not found.')
    with db: db.execute('DELETE FROM scenes WHERE id=? AND project_id=?',(sid,pid))
