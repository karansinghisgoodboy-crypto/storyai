from db.database import now_iso
from services.errors import NotFoundError, ValidationError, ConflictError


def project_exists(db, project_id):
    if db.execute('SELECT 1 FROM projects WHERE id=?',(project_id,)).fetchone() is None:
        raise NotFoundError('Project not found.')


def row_dict(row):
    return dict(row) if row else None


def text(value, field, max_len=4000, required=False):
    if value is None: value=''
    if not isinstance(value,str): raise ValidationError(f'{field} must be text.')
    value=value.strip()
    if required and not value: raise ValidationError(f'{field} is required.')
    if len(value)>max_len: raise ValidationError(f'{field} must be {max_len} characters or fewer.')
    return value


def positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f'{field} must be a positive integer.')
    return value


def boolean(value, field):
    if not isinstance(value, bool):
        raise ValidationError(f'{field} must be true or false.')
    return value


def expected_version(row, data):
    expected=data.get('updated_at')
    if expected is not None and not isinstance(expected,str): raise ValidationError('updated_at must be text.')
    if expected is not None and expected != row['updated_at']:
        raise ConflictError('This item changed since you loaded it. Reload the latest version.')
    return expected


def locked(row):
    if row and row['locked']:
        raise ConflictError('This item is locked. Unlock it before editing.')


def touch(db, table, item_id, fields, values, where='id=?'):
    now=now_iso(); assignments=', '.join(f'{f}=?' for f in fields)
    with db:
        cur=db.execute(f'UPDATE {table} SET {assignments}, updated_at=? WHERE {where}', list(values)+[now,item_id])
    return cur.rowcount
