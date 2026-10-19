"""Real PostgreSQL lifecycle checks; controlled outgoing handoff transport only.
Never calls an image/text provider. Requires migrated private QA DATABASE_URL.
"""
import os,json,tempfile
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app import main
from app.db import factory,Session,Studio,Job,Media,Revision,Reservation,Account,Tenant,now
from app.security import seed,store_media,digest
from app.worker import maintain
assert os.getenv('PROVIDER_ENABLED','false')!='true'
checks=[]
def check(name,ok):
 assert ok,name
 checks.append(name)

os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='studio-qa-private-')
configs=json.loads(os.environ['TENANTS_JSON']); configs[0]['handoff_url']='https://qa-handoff.invalid/accept'
os.environ['TENANTS_JSON']=json.dumps(configs);os.environ['HANDOFF_AUTH_MEIN_KUECHENEXPERTE']='qa-controlled-auth'
os.environ['ALLOW_LOCAL_HTTP']='false'
with TestClient(main.app,base_url='https://localhost') as c:
 session=c.get('/api/session').json();h={'Origin':'https://localhost','X-CSRF-Token':session['csrf_token'],'Idempotency-Key':'qa-handoff'}
 with main.DB() as db:
  st=Studio(tenant_id='mein-kuechenexperte',session_id=session['id'],status='completed',prompt='qa',source_kind='text',brief={'room':{'version':99},'concepts':{'A':'FORBIDDEN_A'},'room_history':['FORBIDDEN_HISTORY']});db.add(st);db.flush()
  selected=store_media(db,'mein-kuechenexperte',session['id'],b'QA SELECTED ONLY');other=store_media(db,'mein-kuechenexperte',session['id'],b'FORBIDDEN OTHER MEDIA')
  rev=Revision(studio_id=st.id,tenant_id='mein-kuechenexperte',concept='B',number=1,kind='initial',media_id=selected.id,curation=['a','b','c'],room_version=1,profile={'briefing':{'room':{'version':1},'user_brief':'chosen briefing','assumptions':[],'concepts':{'A':{'title':'FORBIDDEN_A'},'B':{'title':'CHOSEN_B'},'C':{'title':'FORBIDDEN_C'}},'room_history':['FORBIDDEN_HISTORY']}});db.add(rev);db.commit()
  sid=st.id;rid=rev.id;mid=selected.id;otherid=other.id;paths=[selected.path,other.path]
 calls=[]
 class Target:
  def __init__(self,*a,**k):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):calls.append(kw);return httpx.Response(200,json={'accepted':True},request=httpx.Request('POST',url))
 body={'revision_id':rid,'media_ids':[mid],'name':'QA','email':'qa@example.invalid','consent':True}
 with patch.object(main.httpx,'AsyncClient',Target):
  a=c.post('/api/studios/'+sid+'/handoff',headers=h,json=body)
  check('handoff accepted with controlled acknowledgement',a.status_code==200)
  b=c.post('/api/studios/'+sid+'/handoff',headers=h,json=body)
  check('handoff replay exactly one transport call',b.json()==a.json() and len(calls)==1)
  wrong=c.post('/api/studios/'+sid+'/handoff',headers={**h,'Idempotency-Key':'qa-wrong-media'},json={**body,'media_ids':[otherid]})
  check('discarded media rejected',wrong.status_code==422)
 sent=calls[0]['json']; encoded=json.dumps(sent)
 check('no other concept or history leak',not any(x in encoded for x in ['FORBIDDEN_A','FORBIDDEN_C','FORBIDDEN_HISTORY','FORBIDDEN OTHER MEDIA']))
 check('only chosen media',len(sent['media'])==1 and sent['media'][0]['id']==mid)
 check('revision snapshot room used',sent['briefing']['room']['version']==1)
 check('authenticated target',calls[0]['headers']['Authorization']=='Bearer qa-controlled-auth')
 check('immediate delete HTTP204',c.delete('/api/session',headers=h).status_code==204)
 check('immediate physical files removed',all(not Path(p).exists() for p in paths))

with factory()() as db:
 s=Session(tenant_id='mein-kuechenexperte',token_hash=digest('qa-expired'),expires_at=now()-timedelta(seconds=1));db.add(s);db.flush();expired_id=s.id
 m=store_media(db,'mein-kuechenexperte',s.id,b'QA expired');expired_path=m.path
 alive=Session(tenant_id='mein-kuechenexperte',token_hash=digest('qa-stale'),expires_at=now()+timedelta(days=30));db.add(alive);db.flush();alive_id=alive.id
 st=Studio(tenant_id='mein-kuechenexperte',session_id=alive.id,status='running',prompt='QA stale',source_kind='text');db.add(st);db.flush()
 j=Job(tenant_id='mein-kuechenexperte',session_id=alive.id,studio_id=st.id,operation='brief',idempotency_key='qa-stale',request_hash='qa',payload={},status='running',started_at=now()-timedelta(hours=1));db.add(j);db.flush();jobid=j.id
 r=Reservation(tenant_id='mein-kuechenexperte',job_id=j.id,amount=100,status='reserved');db.add(r)
 account=db.get(Account,'global');tenant=db.get(Tenant,'mein-kuechenexperte');before=account.reserved;account.reserved+=100;tenant.reserved+=100;db.commit()
 maintain(db)
 check('retention removes expired session',db.get(Session,expired_id) is None)
 check('retention removes physical file',not Path(expired_path).exists())
 check('crashed job halted',db.get(Job,jobid).status=='failed')
 check('unknown charge reservation retained',db.get(Account,'global').reserved==before+100 and db.scalar(select(Reservation).where(Reservation.job_id==jobid)).status=='reserved')
 # Restore own fixture accounting only.
 account=db.get(Account,'global');tenant=db.get(Tenant,'mein-kuechenexperte');account.reserved-=100;tenant.reserved-=100;db.delete(db.scalar(select(Reservation).where(Reservation.job_id==jobid)));db.delete(db.get(Session,alive_id));db.commit()

# Isolate retry-admission logic with explicitly controlled readiness/challenge;
# no worker executes these jobs, no provider transport is installed or called.
with TestClient(main.app,base_url='https://localhost') as retry_client:
 info=retry_client.get('/api/session').json();rh={'Origin':'https://localhost','X-CSRF-Token':info['csrf_token']}
 from app.security import challenge
 from fastapi import HTTPException
 import asyncio
 os.environ.pop('TURNSTILE_SECRET',None)
 with factory()() as db:
  t=db.get(Tenant,'mein-kuechenexperte')
  try:asyncio.run(challenge(t,'not-real'));blocked=False
  except HTTPException as e:blocked=e.status_code==503
 check('missing bot secret fails closed',blocked)
 async def controlled_challenge(*a):return None
 with patch.object(main,'ready',lambda t:(True,None)),patch.object(main,'challenge',controlled_challenge):
  attempts=[]
  for idx in range(3):
   response=retry_client.post('/api/studios',headers={**rh,'Idempotency-Key':'qa-retry-'+str(idx)},data={'prompt':'Beispielraum nach abgelehnter Eingabe','source_kind':'text'})
   attempts.append(response.status_code)
   if response.status_code==202:
    with factory()() as db:
     studio=db.get(Studio,response.json()['id']);studio.status='failed'
     for job in db.scalars(select(Job).where(Job.studio_id==studio.id)):job.status='failed'
     db.commit()
  check('failed source permits new example room attempts',attempts==[202,202,202])
  fourth=retry_client.post('/api/studios',headers={**rh,'Idempotency-Key':'qa-retry-4'},data={'prompt':'Noch einmal','source_kind':'text'})
  check('analysis retries bounded',fourth.status_code==429)
 check('retry fixture removed',retry_client.delete('/api/session',headers=rh).status_code==204)

with factory()() as db: baseline=db.scalar(select(func.count()).select_from(Session).where(Session.created_at>now()-timedelta(hours=1)))
os.environ['MAX_SESSIONS_PER_HOUR']=str(baseline+5)
with TestClient(main.app,base_url='https://localhost'):
 def admit(_):
  # Separate cookie jars; real concurrent HTTP admission handlers + DB lock.
  c=TestClient(main.app,base_url='https://localhost');r=c.get('/api/session');c.close();return r.status_code
 with ThreadPoolExecutor(max_workers=20) as pool: statuses=list(pool.map(admit,range(20)))
 check('concurrent admission cap exact five',statuses.count(200)==5 and statuses.count(429)==15)
print(f'PASS {len(checks)} independent lifecycle assertions; zero provider calls; local handoff transport controlled')
for x in checks:print('PASS',x)
