from db.database import now_iso
from services.common import project_exists,text,expected_version
from services.errors import NotFoundError,ConflictError
FIELDS={'logline':1000,'genre':200,'tone':500,'synopsis':6000,'story_text':30000}

def get(db,pid): project_exists(db,pid); return dict(db.execute('SELECT id,title,logline,genre,tone,synopsis,story_text,updated_at FROM projects WHERE id=?',(pid,)).fetchone())
def update(db,pid,data):
    r=db.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
    if not r: raise NotFoundError('Project not found.')
    expected_version(r,data); vals=[text(data.get(k,r[k]),k,m) for k,m in FIELDS.items()]; now=now_iso()
    with db:
        cur=db.execute('UPDATE projects SET logline=?,genre=?,tone=?,synopsis=?,story_text=?,updated_at=? WHERE id=? AND updated_at=?',(*vals,now,pid,r['updated_at']))
    if not cur.rowcount: raise ConflictError('The story changed since you loaded it. Reload the latest version.')
    return get(db,pid)
