import hashlib,json
from db.database import now_iso
from services.common import project_exists

def fingerprint(scene,typ,desc): return hashlib.sha256(f'{scene}|{typ}|{desc}'.encode()).hexdigest()
def run(db,pid):
    project_exists(db,pid); issues=[]
    scenes=db.execute('SELECT * FROM scenes WHERE project_id=? ORDER BY order_no,id',(pid,)).fetchall(); chars={r['id']:dict(r) for r in db.execute('SELECT * FROM characters WHERE project_id=?',(pid,))}; locs={r['id']:dict(r) for r in db.execute('SELECT * FROM locations WHERE project_id=?',(pid,))}
    for s in scenes:
        if not s['summary'].strip(): issues.append((s['id'],'structure','medium','Scene has no summary.','Add a short scene summary.'))
        if s['location_id'] is None: issues.append((s['id'],'location','low','Scene has no location.','Assign a location or explicitly leave it unset.'))
        sc=db.execute('SELECT character_id FROM scene_characters WHERE scene_id=?',(s['id'],)).fetchall()
        for x in sc:
            c=chars.get(x['character_id'])
            if not c: continue
            if not c['hair'] or not c['default_outfit'] or not c['face']:
                issues.append((s['id'],'character','medium',f'Character {c["name"]} has an incomplete appearance sheet.','Complete hair, face and default outfit.'))
        shots=db.execute('SELECT * FROM shots WHERE scene_id=? ORDER BY order_no,id',(s['id'],)).fetchall()
        if not shots: issues.append((s['id'],'structure','medium','Scene has no storyboard shots.','Add at least one shot.'))
        for sh in shots:
            if not sh['action'].strip(): issues.append((s['id'],'structure','low',f'Shot {sh["order_no"]} has no action.','Describe the visual action.'))
    out=[]
    with db:
        for sid,typ,sev,desc,fix in issues:
            fp=fingerprint(sid,typ,desc); old=db.execute('SELECT * FROM continuity_issues WHERE project_id=? AND fingerprint=?',(pid,fp)).fetchone()
            if old:
                if old['status']=='dismissed': continue
                db.execute('UPDATE continuity_issues SET severity=?,suggested_fix=?,status="open",updated_at=? WHERE id=?',(sev,fix,now_iso(),old['id']))
                out.append(dict(db.execute('SELECT * FROM continuity_issues WHERE id=?',(old['id'],)).fetchone()))
            else:
                cur=db.execute('INSERT INTO continuity_issues(project_id,scene_id,type,severity,description,suggested_fix,fingerprint) VALUES(?,?,?,?,?,?,?)',(pid,sid,typ,sev,desc,fix,fp)); out.append(dict(db.execute('SELECT * FROM continuity_issues WHERE id=?',(cur.lastrowid,)).fetchone()))
    return out

def list_issues(db,pid,status=None):
    project_exists(db,pid); q='SELECT * FROM continuity_issues WHERE project_id=?'; args=[pid]
    if status: q+=' AND status=?'; args.append(status)
    q+=' ORDER BY CASE severity WHEN "high" THEN 1 WHEN "medium" THEN 2 ELSE 3 END,id'; return [dict(r) for r in db.execute(q,args)]
def set_status(db,pid,iid,status):
    if status not in ('resolved','dismissed'): from services.errors import ValidationError; raise ValidationError('Invalid issue status.')
    with db: cur=db.execute('UPDATE continuity_issues SET status=?,updated_at=? WHERE id=? AND project_id=?',(status,now_iso(),iid,pid))
    if not cur.rowcount: from services.errors import NotFoundError; raise NotFoundError('Continuity issue not found.')
    return dict(db.execute('SELECT * FROM continuity_issues WHERE id=?',(iid,)).fetchone())
