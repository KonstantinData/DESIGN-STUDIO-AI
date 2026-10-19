"""Independent negative HTTP checks against real PostgreSQL, no provider calls.
Run after migrations: PYTHONPATH=backend backend/.venv/bin/python tests/independent_http.py
DATABASE_URL and TENANTS_JSON must already be set. No secrets are printed.
"""
import os
from fastapi.testclient import TestClient
from app.main import app

assert os.getenv('PROVIDER_ENABLED', 'false') != 'true', 'Provider must remain disabled'
from app.db import Studio
import app.main as main
checks=[]
def check(name, actual, expected):
    assert actual==expected, (name,actual,expected)
    checks.append(name)

with TestClient(app, base_url='https://localhost') as first, TestClient(app, base_url='https://tenant-two.localhost') as second:
    a=first.get('/api/session'); check('first session',a.status_code,200)
    b=second.get('/api/session'); check('second session',b.status_code,200)
    h={'Origin':'https://localhost','X-CSRF-Token':a.json()['csrf_token']}
    h2={'Origin':'https://tenant-two.localhost','X-CSRF-Token':b.json()['csrf_token']}
    check('two distinct brands',first.get('/api/config').json()['brand']!=second.get('/api/config').json()['brand'],True)
    check('provider closed',first.get('/api/config').json()['generation_ready'],False)
    check('unknown host',first.get('/api/config',headers={'Host':'attacker.invalid'}).status_code,421)
    check('private media missing',first.get('/api/media/not-real').status_code,404)
    check('missing csrf',first.post('/api/session/resume-token',headers={'Origin':'https://localhost'}).status_code,403)
    check('cross origin',first.post('/api/session/resume-token',headers={**h,'Origin':'https://attacker.invalid'}).status_code,403)
    check('cross tenant cookie',first.get('/api/media/not-real',headers={'Host':'tenant-two.localhost'}).status_code,401)
    token=first.post('/api/session/resume-token',headers=h); check('mint resume token',token.status_code,200)
    secret=token.json()['token']; check('token entropy length',len(secret)>=64,True)
    check('cross tenant resume',second.post('/api/session/resume',json={'token':secret},headers=h2).status_code,403)
    replacement=first.post('/api/session/resume-token',headers=h).json()['token']
    check('replaced token revoked',first.post('/api/session/resume',json={'token':secret},headers=h).status_code,403)
    resumed=first.post('/api/session/resume',json={'token':replacement},headers=h); check('resume accepted',resumed.status_code,200)
    h['X-CSRF-Token']=first.get('/api/session').json()['csrf_token']
    check('resume single use',first.post('/api/session/resume',json={'token':replacement},headers=h).status_code,403)
    check('closed provider rejects generation',first.post('/api/studios',data={'prompt':'Helle Familienküche','source_kind':'text'},headers={**h,'Idempotency-Key':'independent-closed'}).status_code,503)
    # A real persisted studio permits room version checks without synthetic image results.
    with main.DB() as db:
        item=Studio(tenant_id='mein-kuechenexperte',session_id=a.json()['id'],status='failed',prompt='QA',source_kind='text',brief={'room':{'version':1,'description':'Testgrundlage','features':[],'constraints':[]},'concepts':{},'assumptions':[]})
        db.add(item); db.commit(); studio_id=item.id
    check('cross tenant studio isolation',second.get('/api/studios/'+studio_id).status_code,404)
    correction={'description':'Fenster links, Tür rechts','features':[{'name':'Fenster','value':'linke Wand','provenance':'USER_GIVEN'}],'constraints':[],'confirm_global':True}
    changed=first.post('/api/studios/'+studio_id+'/room',json=correction,headers=h)
    check('explicit room correction',changed.status_code,200)
    check('room version increment',changed.json()['room']['version'],2)
    with main.DB() as db:
        item=db.get(Studio,studio_id)
        check('historical room persisted',item.brief['room_history'][0]['version'],1)
    check('no fabricated provenance',first.post('/api/studios/'+studio_id+'/room',json={**correction,'features':[{'name':'Fenster','value':'links','provenance':'DETECTED'}]},headers=h).status_code,422)
    check('explicit consent required',first.post('/api/studios/'+studio_id+'/room',json={**correction,'confirm_global':False},headers=h).status_code,422)
    check('no cache',first.get('/api/session').headers['cache-control'],'no-store')
    check('no referrer',first.get('/api/config').headers['referrer-policy'],'no-referrer')
    check('delete first',first.delete('/api/session',headers=h).status_code,204)
    check('delete second',second.delete('/api/session',headers=h2).status_code,204)
print(f'PASS {len(checks)} independent HTTP assertions; real PostgreSQL; zero provider calls')
for name in checks: print('PASS',name)
