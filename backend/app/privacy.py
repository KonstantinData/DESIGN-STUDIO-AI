"""Crash-safe deletion tombstones, stored independently from restorable data backups."""
import argparse,json,os
from uuid import uuid4
from pathlib import Path
from sqlalchemy import select
from .db import Session,Media,factory,now
from .security import data_dir

def ledger_dir():
    path=Path(os.getenv('DELETION_LEDGER_DIR',str(data_dir()/'deletions')))
    path.mkdir(parents=True,exist_ok=True,mode=0o700);return path

def tombstone(session):
    target=ledger_dir()/(session.id+'.json')
    if target.exists():return
    payload=json.dumps({'session_id':session.id,'tenant_id':session.tenant_id,'deleted_at':now().isoformat()},sort_keys=True).encode()
    temp=target.with_suffix('.'+str(uuid4())+'.pending')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'wb') as file:file.write(payload);file.flush();os.fsync(file.fileno())
        os.replace(temp,target)
        directory=os.open(target.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:temp.unlink(missing_ok=True)

def erase(db,session):
    tombstone(session)
    paths=list(db.scalars(select(Media.path).where(Media.session_id==session.id,Media.tenant_id==session.tenant_id)))
    db.delete(session);db.commit()
    for path in paths:Path(path).unlink(missing_ok=True)

def replay(db):
    removed=0;entries=0
    for path in ledger_dir().glob('*.json'):
        row=json.loads(path.read_text());entries+=1
        session=db.scalar(select(Session).where(Session.id==row['session_id'],Session.tenant_id==row['tenant_id']).with_for_update().execution_options(populate_existing=True))
        if session:erase(db,session);removed+=1
        else:db.commit()
    expired=list(db.scalars(select(Session).where(Session.expires_at<=now()).with_for_update().execution_options(populate_existing=True)))
    for session in expired:erase(db,session)
    return {'ledger_entries':entries,'sessions_removed':removed,'expired_sessions_removed':len(expired)}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['replay','status']);args=parser.parse_args()
    if args.action=='status':result={'ledger_entries':sum(1 for _ in ledger_dir().glob('*.json'))}
    else:
        with factory()() as db:result=replay(db)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
