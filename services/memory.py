from db.database import now_iso
from services.common import project_exists,text,expected_version,boolean
from services.errors import NotFoundError,ConflictError

def list_items(db,pid):
    project_exists(db,pid); return [{**dict(r),'locked':bool(r['locked'])} for r in db.execute('SELECT * FROM memory_items WHERE project_id=? ORDER BY locked DESC,id',(pid,))]
def get(db,pid,iid):
    project_exists(db,pid); r=db.execute('SELECT * FROM memory_items WHERE id=? AND project_id=?',(iid,pid)).fetchone()
    if not r: raise NotFoundError('Memory item not found.')
    d=dict(r); d['locked']=bool(d['locked']); return d
def create(db,pid,data):
    project_exists(db,pid); kind=data.get('kind','note'); content=text(data.get('content'),'content',4000,True)
    if kind not in ('fact','rule','theme','note'): from services.errors import ValidationError; raise ValidationError('Invalid memory kind.')
    now=now_iso()
    with db: cur=db.execute('INSERT INTO memory_items(project_id,kind,content,created_at,updated_at) VALUES(?,?,?,?,?)',(pid,kind,content,now,now))
    return get(db,pid,cur.lastrowid)
def update(db,pid,iid,data):
    r=db.execute('SELECT * FROM memory_items WHERE id=? AND project_id=?',(iid,pid)).fetchone()
    if not r: raise NotFoundError('Memory item not found.')
    if r['locked']: from services.errors import ConflictError; raise ConflictError('This memory item is locked. Unlock it before editing.')
    expected_version(r,data); kind=data.get('kind',r['kind']); content=text(data.get('content',r['content']),'content',4000,True); now=now_iso()
    with db: cur=db.execute('UPDATE memory_items SET kind=?,content=?,updated_at=? WHERE id=? AND project_id=? AND updated_at=?',(kind,content,now,iid,pid,r['updated_at']))
    if not cur.rowcount: raise ConflictError('This memory item changed since you loaded it. Reload the latest version.')
    return get(db,pid,iid)
def lock(db,pid,iid,value,updated_at=None):
    value=boolean(value,'locked')
    r=db.execute('SELECT * FROM memory_items WHERE id=? AND project_id=?',(iid,pid)).fetchone()
    if not r: raise NotFoundError('Memory item not found.')
    if updated_at and updated_at!=r['updated_at']: raise ConflictError('This memory item changed since you loaded it. Reload the latest version.')
    now=now_iso()
    with db: db.execute('UPDATE memory_items SET locked=?,updated_at=? WHERE id=? AND project_id=?',(int(value),now,iid,pid))
    return get(db,pid,iid)
def delete(db,pid,iid):
    r=db.execute('SELECT * FROM memory_items WHERE id=? AND project_id=?',(iid,pid)).fetchone()
    if not r: raise NotFoundError('Memory item not found.')
    if r['locked']: from services.errors import ConflictError; raise ConflictError('Unlock this memory item before deleting it.')
    with db: db.execute('DELETE FROM memory_items WHERE id=? AND project_id=?',(iid,pid))
