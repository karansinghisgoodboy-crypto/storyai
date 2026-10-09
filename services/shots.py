from db.database import now_iso
from services.common import project_exists,text,expected_version,positive_int
from services.errors import NotFoundError,ValidationError,ConflictError
FIELDS={'shot_type':120,'camera_angle':200,'movement':200,'action':3000,'dialogue':3000,'lighting':500,'notes':3000}
def _get(db,pid,sid,shotid):
    r=db.execute('SELECT * FROM shots WHERE id=? AND project_id=? AND scene_id=?',(shotid,pid,sid)).fetchone()
    if not r: raise NotFoundError('Shot not found.')
    d=dict(r); f=db.execute('SELECT fr.id,fr.asset_id,fr.created_at,fr.updated_at FROM frames fr WHERE fr.shot_id=?',(shotid,)).fetchone(); d['frame']=dict(f) if f else None; return d
def list_shots(db,pid,sid):
    project_exists(db,pid)
    if not db.execute('SELECT 1 FROM scenes WHERE id=? AND project_id=?',(sid,pid)).fetchone(): raise NotFoundError('Scene not found.')
    return [_shot(db,r) for r in db.execute('SELECT * FROM shots WHERE scene_id=? AND project_id=? ORDER BY order_no,id',(sid,pid,))]
def _shot(db,r):
    d=dict(r); f=db.execute('SELECT fr.id,fr.asset_id,fr.created_at,fr.updated_at FROM frames fr WHERE fr.shot_id=?',(r['id'],)).fetchone(); d['frame']=dict(f) if f else None; return d
def create(db,pid,sid,data):
    list_shots(db,pid,sid); vals=[text(data.get(k),k,m) for k,m in FIELDS.items()]; order=data.get('order_no'); order=positive_int(order,'order_no') if order is not None else db.execute('SELECT COALESCE(MAX(order_no),0)+1 n FROM shots WHERE scene_id=?',(sid,)).fetchone()['n']; now=now_iso()
    with db: cur=db.execute('INSERT INTO shots(project_id,scene_id,order_no,shot_type,camera_angle,movement,action,dialogue,lighting,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,sid,order,*vals,now,now))
    return _get(db,pid,sid,cur.lastrowid)
def update(db,pid,sid,shotid,data):
    r=db.execute('SELECT * FROM shots WHERE id=? AND project_id=? AND scene_id=?',(shotid,pid,sid)).fetchone()
    if not r: raise NotFoundError('Shot not found.')
    expected_version(r,data); vals=[text(data.get(k,r[k]),k,m) for k,m in FIELDS.items()]; order=positive_int(data.get('order_no',r['order_no']),'order_no'); now=now_iso()
    with db: cur=db.execute('UPDATE shots SET order_no=?,shot_type=?,camera_angle=?,movement=?,action=?,dialogue=?,lighting=?,notes=?,updated_at=? WHERE id=? AND project_id=? AND scene_id=? AND updated_at=?',(order,*vals,now,shotid,pid,sid,r['updated_at']))
    if not cur.rowcount: raise ConflictError('This shot changed since you loaded it. Reload the latest version.')
    return _get(db,pid,sid,shotid)
def delete(db,pid,sid,shotid):
    if not db.execute('SELECT 1 FROM shots WHERE id=? AND project_id=? AND scene_id=?',(shotid,pid,sid)).fetchone(): raise NotFoundError('Shot not found.')
    with db: db.execute('DELETE FROM shots WHERE id=? AND project_id=? AND scene_id=?',(shotid,pid,sid))
