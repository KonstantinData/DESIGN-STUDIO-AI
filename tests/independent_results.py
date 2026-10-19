"""Explicitly controlled worker transport, real PostgreSQL and ASGI routes.
Images contain QA labels and never count as product images. No paid API calls.
Run using dedicated QA env; never point a production worker at this database.
"""
import asyncio,io,copy,os
from sqlalchemy.engine import make_url
from unittest.mock import patch
from pathlib import Path
from datetime import timedelta
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app import main,worker
from app.db import factory,Studio,Revision,Job,Media,Session,Reservation,Account,Tenant,now
assert os.getenv('PROVIDER_ENABLED','false')!='true', 'Provider must stay disabled'
assert any(word in make_url(os.environ['DATABASE_URL']).database for word in ('qa','test','acceptance')), 'Dedicated QA database required'
checks=[]
def check(n,b):assert b,n;checks.append(n)
class Controlled:
 def __init__(self):self.calls=[];self.fail_concept='B';self.fail_change=False
 async def brief(self,prompt,source,kind):
  self.calls.append(('brief',kind))
  return {'usable':True,'room':{'version':1,'description':'QA ONLY TEST ROOM','features':[],'constraints':[]},'user_brief':prompt,'concepts':{k:{'title':'QA ONLY '+k,'layout':'test '+k,'materials':'qa','lighting':'qa'} for k in 'ABC'},'assumptions':['QA ORIGINAL ASSUMPTION']}
 async def render(self,brief,key,change,source):
  self.calls.append(('render',key,change,source,copy.deepcopy(brief)))
  if key==self.fail_concept or self.fail_change:raise RuntimeError('controlled failure')
  out=io.BytesIO();im=Image.new('RGB',(512,300),{'A':'blue','B':'red','C':'green'}[key]);ImageDraw.Draw(im).text((30,30),'QA ONLY - NOT A PRODUCT RESULT '+key,fill='white');im.save(out,'PNG');return out.getvalue()
 async def curate(self,*a):self.calls.append(('curate',));return {'lines':['QA architecture','QA highlight','QA material'],'critical_error':False}
async def challenge(*a):pass
provider=Controlled()
with patch.object(main,'ready',lambda t:(True,None)),patch.object(main,'challenge',challenge),patch.object(worker,'ready',lambda t:(True,None)):
 with TestClient(main.app,base_url='https://localhost') as c:
  sess=c.get('/api/session').json();headers={'Origin':'https://localhost','X-CSRF-Token':sess['csrf_token']}
  created=c.post('/api/studios',data={'prompt':'QA isolated integration, not real kitchen'},headers={**headers,'Idempotency-Key':'qa-result-start'})
  check('real API accepts controlled test start',created.status_code==202);stid=created.json()['id']
  with factory()() as db:briefjob=db.scalar(select(Job).where(Job.studio_id==stid,Job.operation=='brief')).id
  asyncio.run(worker.execute(briefjob,provider))
  with factory()() as db:jobs={j.payload['concept']:j.id for j in db.scalars(select(Job).where(Job.studio_id==stid,Job.operation=='render'))}
  asyncio.run(worker.execute(jobs['A'],provider));view=c.get('/api/studios/'+stid).json()
  check('A appears before B and C finished',len(view['concepts'][0]['revisions'])==1 and not view['concepts'][1]['revisions'] and not view['concepts'][2]['revisions'])
  base=view['concepts'][0]['revisions'][0];original= c.get(base['image_url']).content
  asyncio.run(worker.execute(jobs['B'],provider));asyncio.run(worker.execute(jobs['C'],provider));view=c.get('/api/studios/'+stid).json()
  check('B failure does not block C',view['concepts'][1]['status']=='failed' and len(view['concepts'][2]['revisions'])==1 and view['status']=='partial')
  check('three curation lines for available results',all(len(x['revisions'][0]['curation'])==3 for x in [view['concepts'][0],view['concepts'][2]]))
  # A failed change must release its pending user credit.
  body={'concept':'A','kind':'material','instruction':'QA controlled material','base_revision_id':base['id']}
  failed=c.post('/api/studios/'+stid+'/revisions',json=body,headers={**headers,'Idempotency-Key':'qa-failed-change'});provider.fail_change=True
  asyncio.run(worker.execute(failed.json()['job_id'],provider));provider.fail_change=False
  check('failed change consumes no user credit',c.get('/api/studios/'+stid).json()['changes_remaining']==5)
  for index in range(5):
   body['kind']='material' if index%2==0 else 'layout';body['instruction']='QA change '+str(index)
   r=c.post('/api/studios/'+stid+'/revisions',json=body,headers={**headers,'Idempotency-Key':'qa-change-'+str(index)})
   check('change '+str(index)+' accepted',r.status_code==202)
   asyncio.run(worker.execute(r.json()['job_id'],provider))
  renders=[x for x in provider.calls if x[0]=='render' and x[2] is not None]
  check('material and layout independently use original A image',all(x[3]==original for x in renders))
  check('other concept profiles remain unchanged',all(x[4]['concepts']['B']['layout']=='test B' and x[4]['concepts']['C']['layout']=='test C' for x in renders))
  view=c.get('/api/studios/'+stid).json();check('five successful changes exhaust quota',view['changes_remaining']==0)
  check('latest success clears earlier concept error',not view['concepts'][0]['error'])
  check('sixth change blocked',c.post('/api/studios/'+stid+'/revisions',json=body,headers={**headers,'Idempotency-Key':'qa-sixth'}).status_code==429)
  before=len(provider.calls);chosen=c.post('/api/studios/'+stid+'/select',json={'revision_id':base['id']},headers=headers)
  check('rollback selects original without provider call',chosen.status_code==200 and chosen.json()['selected_revision_id']==base['id'] and len(provider.calls)==before)
  downloads=[c.get(base['download_url']) for _ in range(3)]
  check('downloads remain available repeatedly after quota',all(x.status_code==200 and x.content==original for x in downloads))
  check('private downloads disable caching and sniffing',all(x.headers.get('cache-control')=='no-store' and x.headers.get('x-content-type-options')=='nosniff' and x.headers.get('referrer-policy')=='no-referrer' for x in downloads))
  check('versions remain accessible after quota',len(c.get('/api/studios/'+stid).json()['concepts'][0]['revisions'])==6)
  with factory()() as db:
   row=db.get(Session,sess['id']);expiry=row.expires_at;row.expires_at=now()-timedelta(seconds=1);db.commit()
  check('expired session cannot download private media',c.get(base['download_url']).status_code==401)
  check('expired session cannot mutate existing revision',c.post('/api/studios/'+stid+'/select',json={'revision_id':base['id']},headers=headers).status_code==401)
  with factory()() as db:db.get(Session,sess['id']).expires_at=expiry;db.commit()
  with factory()() as db:paths=list(db.scalars(select(Media.path).where(Media.session_id==sess['id'])))
  # Undo only costs recorded by this explicitly synthetic fixture before deleting jobs.
  with factory()() as db:
   own_jobs=list(db.scalars(select(Job.id).where(Job.studio_id==stid)))
   own_reservations=list(db.scalars(select(Reservation).where(Reservation.job_id.in_(own_jobs))))
   charged=sum(r.amount for r in own_reservations if r.status=='ceiling_charged')
   db.get(Account,'global').spent-=charged;db.get(Tenant,'mein-kuechenexperte').spent-=charged
   for row in own_reservations:db.delete(row)
   db.commit()
  check('cleanup own QA session',c.delete('/api/session',headers=headers).status_code==204)
  check('cleanup own QA files',all(not Path(p).exists() for p in paths))
print('PASS',len(checks),'independent controlled results-flow assertions; no paid calls; QA images are not product results')
for n in checks:print('PASS',n)
