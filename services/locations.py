from db.database import now_iso
from services.common import project_exists,text,expected_version,locked
from services.errors import ConflictError, NotFoundError, ValidationError
from services.uploads import remove_asset_files

FIELDS = {"name": 120, "description": 3000, "mood": 500}

def _get(db,pid,lid):
    r=db.execute('SELECT * FROM locations WHERE id=? AND project_id=?',(lid,pid)).fetchone()
    if not r: raise NotFoundError('Location not found.')
    d=dict(r); d['locked']=bool(d['locked']); return d

def list_locations(db,pid):
    project_exists(db,pid); return [_row(r) for r in db.execute('SELECT * FROM locations WHERE project_id=? ORDER BY id',(pid,))]
def _row(r):
    d=dict(r); d['locked']=bool(d['locked']); return d

def create(db,pid,data):
    project_exists(db,pid)
    vals=[text(data.get(k),k,m, k=='name') for k,m in FIELDS.items()]
    now=now_iso()
    with db:
        cur=db.execute('INSERT INTO locations (project_id,name,description,mood,created_at,updated_at) VALUES (?,?,?,?,?,?)',(pid,*vals,now,now))
    return _get(db,pid,cur.lastrowid)

def update(db,pid,lid,data):
    project_exists(db,pid); r=db.execute('SELECT * FROM locations WHERE id=? AND project_id=?',(lid,pid)).fetchone()
    if not r: raise NotFoundError('Location not found.')
    locked(r); expected_version(r,data)
    vals=[text(data.get(k,r[k]),k,m,k=='name') for k,m in FIELDS.items()]
    now=now_iso()
    with db:
        cur=db.execute(
            'UPDATE locations SET name=?,description=?,mood=?,updated_at=? '
            'WHERE id=? AND project_id=? AND updated_at=? AND locked=0',
            (*vals,now,lid,pid,r['updated_at']),
        )
    if not cur.rowcount: raise ConflictError('This location changed since you loaded it. Reload the latest version.')
    return _get(db,pid,lid)

def set_lock(db,pid,lid,value,updated_at=None):
    project_exists(db,pid)
    if not isinstance(value,bool): raise ValidationError('locked must be true or false.')
    r=db.execute('SELECT * FROM locations WHERE id=? AND project_id=?',(lid,pid)).fetchone()
    if not r: raise NotFoundError('Location not found.')
    if updated_at is not None and updated_at!=r['updated_at']: raise ConflictError('This location changed since you loaded it. Reload the latest version.')
    now=now_iso()
    with db:
        cur=db.execute(
            'UPDATE locations SET locked=?,updated_at=? WHERE id=? AND project_id=? AND updated_at=?',
            (int(value),now,lid,pid,r['updated_at']),
        )
    if not cur.rowcount:
        raise ConflictError('This location changed since you loaded it. Reload the latest version.')
    return _get(db,pid,lid)

def delete(db,pid,lid,upload_dir=None):
    project_exists(db,pid); r=db.execute('SELECT * FROM locations WHERE id=? AND project_id=?',(lid,pid)).fetchone()
    if not r: raise NotFoundError('Location not found.')
    locked(r)
    asset=db.execute(
        "SELECT a.id,a.project_id,a.kind,a.file_path,a.thumb_path FROM assets a "
        "WHERE a.id=? AND a.project_id=? AND a.kind='location'",
        (r['image_id'],pid),
    ).fetchone() if r['image_id'] else None
    deleted_asset=False
    with db:
        deleted=db.execute(
            'DELETE FROM locations WHERE id=? AND project_id=? AND locked=0',
            (lid,pid),
        )
        if not deleted.rowcount:
            raise ConflictError('This location is locked or changed. Reload it before deleting.')
        if asset and db.execute(
            'SELECT 1 FROM locations WHERE image_id=? LIMIT 1',
            (asset['id'],),
        ).fetchone() is None:
            removed=db.execute(
                "DELETE FROM assets WHERE id=? AND project_id=? AND kind='location'",
                (asset['id'],pid),
            )
            deleted_asset=removed.rowcount==1
    if asset and deleted_asset and upload_dir:
        remove_asset_files(upload_dir,(asset['file_path'],asset['thumb_path']))
