import asyncio, io
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from app.db import factory,Tenant,Account,Session,Studio,Job,Revision,Media,Reservation,now
from app.security import seed,digest,normalize_image
from app import main
from app.worker import claim,execute,reserve,BudgetBlocked

CONFIG='[{"host":"one.test","slug":"one","brand":"One","turnstile_site_key":"site"},{"host":"two.test","slug":"two","brand":"Two","turnstile_site_key":"site"}]'
@pytest.fixture
def configured(pg,monkeypatch):
    # Explicit offline dependency injection, never a runtime bypass setting.
    async def offline_route():return None
    monkeypatch.setattr('app.worker.route_preflight',offline_route)
    monkeypatch.setenv('TENANTS_JSON',CONFIG)
    monkeypatch.setenv('GLOBAL_BUDGET_CENTS','500')
    monkeypatch.setenv('PROVIDER_ENABLED','true'); monkeypatch.setenv('BUDGET_APPROVED','true')
    monkeypatch.setenv('GLOBAL_KILL_SWITCH','false'); monkeypatch.setenv('STUDIO_OPENAI_API_KEY','controlled-test-key')
    monkeypatch.setenv('TURNSTILE_SECRET','controlled-test-secret'); monkeypatch.setenv('HARD_LIMIT_VERIFIED_AT','controlled-test-evidence')
    with factory()() as db: seed(db)
    return pg

def fixture_job():
    with factory()() as db:
        s=Session(tenant_id='one',token_hash=digest('test'),expires_at=now()+timedelta(days=30)); db.add(s); db.flush()
        st=Studio(tenant_id='one',session_id=s.id,prompt='Eine helle Küche',source_kind='text'); db.add(st); db.flush()
        j=Job(tenant_id='one',session_id=s.id,studio_id=st.id,operation='brief',idempotency_key='test',request_hash='test',payload={});db.add(j);db.commit();return s.id,st.id,j.id

class ControlledProvider:
    """Only injected in tests; never runtime fallback or purported real output."""
    def __init__(self): self.calls=[]
    async def brief(self,*args):
        self.calls.append('brief')
        return {'version':1,'source_kind':'text','usable':True,'room':{'version':1,'description':'Test','features':[],'constraints':[]},'user_brief':'Test','concepts':{k:{'title':k,'layout':'layout','materials':'test','lighting':'test'} for k in 'ABC'},'assumptions':['Test fixture']}
    async def render(self,*args):
        self.calls.append('render'); out=io.BytesIO(); Image.new('RGB',(256,256)).save(out,'PNG'); return out.getvalue()
    async def curate(self,*args): self.calls.append('curate'); return {'lines':['Test architecture','Test design','Test materials'],'critical_error':False,'critical_reason':None}

def test_private_tenant_csrf_and_fail_closed(configured,monkeypatch):
    monkeypatch.setenv('GLOBAL_KILL_SWITCH','true')
    with TestClient(main.app,base_url='https://one.test') as client:
        session=client.get('/api/session').json(); assert session['csrf_token']
        assert client.get('/api/config').json()['generation_ready'] is False
        assert client.post('/api/session/resume-token').status_code==403
        headers={'Origin':'https://one.test','X-CSRF-Token':session['csrf_token']}
        continuation=client.post('/api/session/resume-token',headers=headers);assert continuation.status_code==200
        assert client.get('/api/session',headers={'host':'unknown.test'}).status_code==421
        first=session['id']
        second=client.get('/api/session',headers={'host':'two.test'}).json(); assert second['id']!=first
        assert client.post('/api/session/resume',headers={'host':'two.test','Origin':'https://two.test','X-CSRF-Token':second['csrf_token']},json={'token':continuation.json()['token']}).status_code==403
        assert client.post('/api/studios',headers={'Origin':'https://two.test','X-CSRF-Token':second['csrf_token'],'host':'two.test','Idempotency-Key':'start'},data={'prompt':'Kitchen'}).status_code==503

def test_atomic_budget_and_kill_switch(configured,monkeypatch):
    _,_,job=fixture_job()
    def attempt():
        with factory()() as db:
            try:return reserve(db,job,100)
            except BudgetBlocked:return None
    with ThreadPoolExecutor(max_workers=10) as pool: results=list(pool.map(lambda _:attempt(),range(10)))
    assert sum(x is not None for x in results)==5
    with factory()() as db:
        assert db.get(Account,'global').reserved==500
        assert db.get(Tenant,'one').reserved==500
        with pytest.raises(BudgetBlocked,match='Der verfügbare Kostenrahmen ist ausgeschöpft'):
            reserve(db,job,1)
    monkeypatch.setenv('GLOBAL_KILL_SWITCH','true')
    assert attempt() is None
    monkeypatch.setenv('GLOBAL_KILL_SWITCH','false')
    from app.security import data_dir,ready
    (data_dir()/'STOP_GENERATION').touch()
    with factory()() as db: assert ready(db.get(Tenant,'one'))[0] is False

@pytest.mark.asyncio
async def test_three_concepts_immutable_history_and_delete(configured):
    sid,stid,jid=fixture_job(); provider=ControlledProvider()
    with factory()() as db: assert claim(db)==jid
    await execute(jid,provider)
    with factory()() as db: ids=list(db.scalars(select(Job.id).where(Job.operation=='render')))
    await asyncio.gather(*(execute(i,provider) for i in ids))
    with factory()() as db:
        revisions=db.scalars(select(Revision)).all(); assert len(revisions)==3
        assert all(r.profile['briefing']['room']['version']==1 for r in revisions)
        assert db.get(Studio,stid).status=='completed'
        assert len(db.scalars(select(Reservation)).all())==7
        assert all(r.usage['actual_cost_cents'] is None for r in db.scalars(select(Reservation)))
    assert provider.calls.count('render')==3
    with TestClient(main.app,base_url='https://one.test') as client:
        client.cookies.set('__Host-studio','test',domain='one.test',path='/')
        session=client.get('/api/session').json(); rev=revisions[0]
        assert client.get('/api/media/'+rev.media_id).status_code==200
        assert client.get('/api/media/'+rev.media_id,headers={'host':'two.test'}).status_code==401
        result=client.delete('/api/session',headers={'Origin':'https://one.test','X-CSRF-Token':session['csrf_token']}); assert result.status_code==204
    with factory()() as db:
        assert db.get(Session,sid) is None
        assert not list(db.scalars(select(Media)))
        assert not list(db.scalars(select(Revision)))

@pytest.mark.asyncio
async def test_deleted_session_cannot_publish(configured):
    sid,stid,jid=fixture_job()
    class DeleteDuringProvider(ControlledProvider):
        async def brief(self,*args):
            result=await super().brief(*args)
            with factory()() as db: db.delete(db.get(Session,sid));db.commit()
            return result
    await execute(jid,DeleteDuringProvider())
    with factory()() as db:
        assert not list(db.scalars(select(Revision)))
        assert not list(db.scalars(select(Job)))
        assert db.get(Account,'global').spent==10

def test_exif_rotation():
    image=Image.new('RGB',(300,500)); exif=Image.Exif(); exif[274]=6
    buf=io.BytesIO();image.save(buf,'JPEG',exif=exif)
    with Image.open(io.BytesIO(normalize_image(buf.getvalue()))) as result:
        assert result.size==(500,300)
        assert not result.getexif()

@pytest.mark.asyncio
async def test_five_changes_room_correction_and_rollback_no_provider(configured,monkeypatch):
    sid,stid,jid=fixture_job(); provider=ControlledProvider()
    await execute(jid,provider)
    with factory()() as db: ids=list(db.scalars(select(Job.id).where(Job.operation=='render')))
    for ident in ids: await execute(ident,provider)
    async def accepted(*args): return None
    monkeypatch.setattr(main,'challenge',accepted)
    with TestClient(main.app,base_url='https://one.test') as client:
        client.cookies.set('__Host-studio','test',domain='one.test',path='/')
        initial=client.get('/api/session').json()
        headers={'Origin':'https://one.test','X-CSRF-Token':initial['csrf_token']}
        studio=client.get('/api/studios/'+stid).json(); base=studio['concepts'][0]['revisions'][0]['id']
        before=len(provider.calls)
        corrected=client.post('/api/studios/'+stid+'/room',headers=headers,json={'description':'Nutzer korrigiert Fenster','features':[{'name':'Fenster','value':'an Nordwand laut Nutzer','provenance':'USER_GIVEN'}],'constraints':['Tür freihalten'],'confirm_global':True})
        assert corrected.status_code==200
        assert corrected.json()['room']['version']==2
        assert corrected.json()['concepts'][0]['revisions'][0]['previous_room_basis'] is True
        assert len(provider.calls)==before
        # More budget for controlled quota test; separate from $5 cap concurrency test.
        with factory()() as db: db.get(Account,'global').budget=5000;db.commit()
        for index in range(5):
            h={**headers,'Idempotency-Key':f'change-{index}'}
            body={'concept':'A','kind':'material' if index%2==0 else 'layout','instruction':'Test instruction','base_revision_id':base,'challenge_token':'controlled'}
            result=client.post('/api/studios/'+stid+'/revisions',headers=h,json=body);assert result.status_code==202,result.text
            repeated=client.post('/api/studios/'+stid+'/revisions',headers=h,json=body);assert repeated.json()==result.json()
            await execute(result.json()['job_id'],provider)
        latest=client.get('/api/studios/'+stid).json()
        assert latest['changes_remaining']==0
        assert latest['concepts'][0]['revisions'][-1]['room_version']==2
        assert client.post('/api/studios/'+stid+'/revisions',headers={**headers,'Idempotency-Key':'sixth'},json=body).status_code==429
        count=len(provider.calls)
        assert client.post('/api/studios/'+stid+'/select',headers=headers,json={'revision_id':base}).status_code==200
        assert len(provider.calls)==count

@pytest.mark.asyncio
async def test_failed_provider_records_unknown_cost_and_no_retry(configured):
    sid,stid,jid=fixture_job()
    class Fail(ControlledProvider):
        async def brief(self,*args): self.calls.append('brief');raise RuntimeError('controlled transport failure')
    provider=Fail();await execute(jid,provider)
    assert provider.calls==['brief']
    with factory()() as db:
        assert db.get(Job,jid).status=='failed'
        assert db.get(Account,'global').spent==10
        reservation=db.scalar(select(Reservation))
        assert reservation.usage['actual_cost_cents'] is None
        assert reservation.status=='ceiling_charged'

@pytest.mark.asyncio
async def test_handoff_selective_authenticated_idempotent(configured,monkeypatch):
    sid,stid,jid=fixture_job(); provider=ControlledProvider()
    await execute(jid,provider)
    with factory()() as db: ids=list(db.scalars(select(Job.id).where(Job.operation=='render')))
    for ident in ids: await execute(ident,provider)
    with factory()() as db:
        tenant=db.get(Tenant,'one');tenant.config={**tenant.config,'handoff_url':'https://expert.example/accept'};db.commit()
        revision=db.scalar(select(Revision).where(Revision.concept=='B'))
    monkeypatch.setenv('HANDOFF_AUTH_ONE','controlled-target-secret')
    # Startup seed must retain endpoint configured above.
    monkeypatch.setenv('TENANTS_JSON',CONFIG.replace('"brand":"One"','"brand":"One","handoff_url":"https://expert.example/accept"'))
    calls=[]
    import httpx
    class TargetClient:
        def __init__(self,*args,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):
            calls.append(kwargs)
            return httpx.Response(200,json={'accepted':True},request=httpx.Request('POST',url))
    monkeypatch.setattr(main.httpx,'AsyncClient',TargetClient)
    with TestClient(main.app,base_url='https://one.test') as client:
        client.cookies.set('__Host-studio','test',domain='one.test',path='/')
        initial=client.get('/api/session').json();headers={'Origin':'https://one.test','X-CSRF-Token':initial['csrf_token'],'Idempotency-Key':'handoff-one'}
        body={'revision_id':revision.id,'media_ids':[revision.media_id],'name':'Test User','email':'test@example.org','message':'Test','consent':True}
        first=client.post('/api/studios/'+stid+'/handoff',headers=headers,json=body)
        assert first.status_code==200,first.text
        second=client.post('/api/studios/'+stid+'/handoff',headers=headers,json=body)
        assert second.json()==first.json();assert len(calls)==1
    sent=calls[0]
    assert sent['headers']['Authorization']=='Bearer controlled-target-secret'
    assert sent['json']['revision']['concept']=='B'
    assert 'concepts' not in sent['json']['briefing']
    assert 'briefing' not in sent['json']['revision']['profile']
    assert len(sent['json']['media'])==1

def test_invoice_reconciliation_releases_only_verified_actual(configured,tmp_path):
    import json
    from app.worker import settle
    from app.reconcile import reconcile
    _,_,jid=fixture_job()
    with factory()() as db:
        ident=reserve(db,jid,100)
        settle(db,ident,{'provider_request_id':'req_controlled','actual_cost_cents':None})
        evidence=tmp_path/'billing.json'
        evidence.write_text(json.dumps({'provider_request_id':'wrong','actual_usd_cents':24,'billing_record_id':'invoice1','verified_by':'test-operator'}))
        with pytest.raises(ValueError):reconcile(db,ident,24,evidence)
        db.rollback()
        assert db.get(Account,'global').spent==100
        evidence.write_text(json.dumps({'provider_request_id':'req_controlled','actual_usd_cents':24,'billing_record_id':'invoice1','verified_by':'test-operator'}))
        reconcile(db,ident,24,evidence)
        assert db.get(Account,'global').spent==24
        assert db.get(Reservation,ident).usage['actual_cost_cents']==24
        with pytest.raises(ValueError):reconcile(db,ident,24,evidence)

def test_restart_does_not_clear_runtime_cost_stop(configured,monkeypatch):
    with factory()() as db:
        tenant=db.get(Tenant,'one');tenant.enabled=False
        account=db.get(Account,'global');account.budget=123;db.commit()
        monkeypatch.setenv('GLOBAL_BUDGET_CENTS','500')
        seed(db)
        assert db.get(Tenant,'one').enabled is False
        assert db.get(Account,'global').budget==123

def test_concurrent_duplicate_settlement_exactly_once(configured):
    from app.worker import settle
    from threading import Barrier
    _,_,jid=fixture_job()
    with factory()() as db: ident=reserve(db,jid,100)
    barrier=Barrier(10)
    def callback(_):
        with factory()() as db:
            # Deliberately cache stale ORM entities before all callbacks race.
            cached=(db.get(Account,'global'),db.get(Tenant,'one'),db.get(Reservation,ident))
            assert cached[2].status=='reserved'
            barrier.wait(timeout=10)
            settle(db,ident,{'provider_request_id':'req_duplicate','actual_cost_cents':None})
    with ThreadPoolExecutor(max_workers=10) as pool:list(pool.map(callback,range(10)))
    with factory()() as db:
        for row in (db.get(Account,'global'),db.get(Tenant,'one')):
            assert row.spent==100
            assert row.reserved==0
        assert db.get(Reservation,ident).status=='ceiling_charged'

def test_long_lived_session_refreshes_budget_under_lock(configured):
    _,_,jid=fixture_job()
    with factory()() as stale:
        cached=(stale.get(Account,'global'),stale.get(Tenant,'one'))
        with factory()() as other:reserve(other,jid,450)
        assert cached[0].reserved==0  # identity map deliberately retains outdated balance
        with pytest.raises(BudgetBlocked):reserve(stale,jid,100)

@pytest.mark.asyncio
async def test_provider_deadline_charges_unknown_once(configured,monkeypatch):
    from app.worker import paid
    _,_,jid=fixture_job()
    monkeypatch.setenv('PROVIDER_TEXT_DEADLINE_SECONDS','0.01')
    called=[]
    async def hang():called.append(True);await asyncio.sleep(10)
    with factory()() as db:
        with pytest.raises(TimeoutError):await paid(db,db.get(Job,jid),'text',hang)
        reservations=db.scalars(select(Reservation)).all()
        assert len(reservations)==1
        assert reservations[0].usage['outcome']=='timeout_unknown'
        assert reservations[0].usage['actual_cost_cents'] is None
        assert reservations[0].usage['duration_seconds']>=0.01
        assert db.get(Account,'global').spent==10
        assert db.get(Account,'global').reserved==0
    assert called==[True]

@pytest.mark.asyncio
async def test_critical_shadow_result_is_review_required_not_success(configured,monkeypatch):
    sid,stid,jid=fixture_job()
    class Critical(ControlledProvider):
        async def curate(self,*args):return {'lines':['Test architecture','Test design','Test materials'],'critical_error':True,'critical_reason':'Test visible doorway blocked'}
    provider=Critical();await execute(jid,provider)
    with factory()() as db:ids=list(db.scalars(select(Job.id).where(Job.operation=='render')))
    for ident in ids:await execute(ident,provider)
    with factory()() as db:
        assert db.get(Studio,stid).status=='review_required'
        assert all(db.get(Job,ident).status=='review_required' for ident in ids)
        assert len(db.scalars(select(Revision)).all())==3
        assert db.get(Session,sid).changes_used==0

def test_privacy_restore_replay_and_gc_preserve_metadata(configured,tmp_path,monkeypatch):
    import os,time,json
    from app.security import data_dir,store_media
    from app.privacy import tombstone,replay,ledger_dir
    from app.worker import maintain
    from uuid import uuid4
    monkeypatch.setenv('DELETION_LEDGER_DIR',str(tmp_path/'separate-ledger'))
    sid,stid,jid=fixture_job()
    with factory()() as db:
        session=db.get(Session,sid);media=store_media(db,'one',sid,b'test');db.commit();media_path=media.path
        # A tombstone that exists outside snapshot is replayed against restored DB state.
        tombstone(session)
        outcome=replay(db)
        assert outcome['sessions_removed']==1
        assert db.get(Session,sid) is None
        assert not __import__('pathlib').Path(media_path).exists()
        root=data_dir();key=root/'.rate-limit-key';key.write_bytes(b'private-key-test'*4)
        config=root/'operator-config.json';config.write_text('{}')
        orphan=root/str(uuid4());orphan.write_bytes(b'orphan')
        for path in (key,config,orphan):os.utime(path,(time.time()-7200,time.time()-7200))
        maintain(db)
        assert key.exists() and config.exists()
        assert list(ledger_dir().glob('*.json'))
        assert not orphan.exists()

@pytest.mark.asyncio
async def test_verified_provider_preflight_releases_without_charge(configured):
    from app.worker import paid
    from app.provider import Provider,ProviderPreflightError
    import httpx
    calls=[]
    async def transport(request):calls.append(request);return httpx.Response(500)
    provider=Provider(api_key='controlled-key',client=httpx.AsyncClient(transport=httpx.MockTransport(transport)))
    _,_,jid=fixture_job()
    try:
        with factory()() as db:
            with pytest.raises(ProviderPreflightError):
                await paid(db,db.get(Job,jid),'text',lambda:provider.brief('Test',b'invalid-image','photo'))
            reservation=db.scalar(select(Reservation))
            assert reservation.status=='released_no_call'
            assert reservation.usage['actual_cost_cents']==0
            assert db.get(Account,'global').spent==0
            assert db.get(Account,'global').reserved==0
    finally:await provider._client.aclose()
    assert not calls

def test_privacy_replay_purges_expired_preserves_live(configured,tmp_path,monkeypatch):
    from app.privacy import replay
    monkeypatch.setenv('DELETION_LEDGER_DIR',str(tmp_path/'ledger'))
    sid,_,_=fixture_job()
    with factory()() as db:
        expired=Session(tenant_id='one',token_hash=digest('expired'),expires_at=now()-timedelta(seconds=1));db.add(expired);db.commit();expired_id=expired.id
        result=replay(db)
        assert result['expired_sessions_removed']==1
        assert db.get(Session,expired_id) is None
        assert db.get(Session,sid) is not None

def test_explicit_resume_revocation(configured):
    with TestClient(main.app,base_url='https://one.test') as client:
        session=client.get('/api/session').json();headers={'Origin':'https://one.test','X-CSRF-Token':session['csrf_token']}
        value=client.post('/api/session/resume-token',headers=headers).json()['token']
        assert client.delete('/api/session/resume-token',headers=headers).status_code==204
        assert client.post('/api/session/resume',headers=headers,json={'token':value}).status_code==403

def test_cookie_rotation_and_spoofed_forwarding_cannot_reset_admission(configured,monkeypatch):
    monkeypatch.setenv('MAX_SESSIONS_PER_IP_HOUR','2')
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS','172.30.74.2/32')
    for index in range(3):
        with TestClient(main.app,base_url='https://one.test',client=('203.0.113.15',10000)) as client:
            result=client.get('/api/session',headers={'X-Forwarded-For':'198.51.100.'+str(index)})
            assert result.status_code==(200 if index<2 else 429)
    from app.db import AdmissionBucket
    with factory()() as db:
        assert len(db.scalars(select(Session)).all())==2
        assert len(db.scalars(select(AdmissionBucket)).all())==1

def test_price_upper_bound_distinct_from_invoice_and_excess_halts(configured):
    from app.worker import settle
    _,_,jid=fixture_job()
    with factory()() as db:
        first=reserve(db,jid,100)
        settle(db,first,{'actual_cost_cents':None,'accounting':'verified_price_upper_bound_not_invoice'},upper_bound_cents=7)
        assert db.get(Account,'global').spent==7
        assert db.get(Reservation,first).status=='priced_upper_bound'
        assert db.get(Reservation,first).usage['actual_cost_cents'] is None
        second=reserve(db,jid,100)
        settle(db,second,{'actual_cost_cents':None},upper_bound_cents=101)
        assert db.get(Account,'global').spent==108
        assert db.get(Tenant,'one').enabled is False
        assert db.get(Reservation,second).status=='ceiling_exceeded'
        with pytest.raises(BudgetBlocked):reserve(db,jid,1)

@pytest.mark.asyncio
async def test_real_provider_transport_to_verified_price_settlement(configured,tmp_path,monkeypatch):
    """Real Provider implementation, offline HTTP transport, synthetic QA rates."""
    import base64,hashlib,json
    from app.provider import Provider
    from app.worker import paid
    import httpx
    instant=now()
    contract={'version':1,'currency':'USD','verified_by':'QA synthetic rates, not live prices','verified_at':(instant-timedelta(minutes=1)).isoformat(),'expires_at':(instant+timedelta(hours=1)).isoformat(),'source':'https://openai.com/api/pricing/','models':{'qa-text':{'kind':'responses','input_usd_per_million':'1.50','output_usd_per_million':'6'},'qa-image':{'kind':'image','text_input_usd_per_million':'5','image_input_usd_per_million':'10','text_output_usd_per_million':'10','image_output_usd_per_million':'40'}}}
    path=tmp_path/'pricing.json';path.write_text(json.dumps(contract));path.chmod(0o600)
    monkeypatch.setenv('VERIFIED_PRICING_FILE',str(path));monkeypatch.setenv('VERIFIED_PRICING_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
    monkeypatch.setenv('OPENAI_TEXT_MODEL','qa-text');monkeypatch.setenv('OPENAI_IMAGE_MODEL','qa-image')
    _,_,jid=fixture_job();calls=[];change_during_call=[]
    raw=io.BytesIO();Image.new('RGB',(256,256)).save(raw,'PNG')
    review={'lines':['QA architecture','QA design','QA material'],'critical_error':False,'critical_reason':None}
    def handler(request):
        calls.append(request)
        if change_during_call:path.write_text(path.read_text()+' ')
        if request.url.path.endswith('responses'):
            return httpx.Response(200,headers={'x-request-id':'req_qa_text'},json={'model':'qa-text','status':'completed','usage':{'input_tokens':1000,'output_tokens':1000,'total_tokens':2000},'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(review)}]}]})
        return httpx.Response(200,headers={'x-request-id':'req_qa_image'},json={'data':[{'b64_json':base64.b64encode(raw.getvalue()).decode()}],'usage':{'input_tokens':1000,'input_tokens_details':{'text_tokens':100,'image_tokens':900},'output_tokens':1000,'total_tokens':2000}})
    brief=await ControlledProvider().brief()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider=Provider(api_key='controlled',text_model='qa-text',image_model='qa-image',client=client)
        with factory()() as db:
            await paid(db,db.get(Job,jid),'curation',lambda:provider.curate(raw.getvalue(),brief,'A'))
            await paid(db,db.get(Job,jid),'image',lambda:provider.render(brief,'A',None,None))
            rows=list(db.scalars(select(Reservation).order_by(Reservation.created_at)))
            assert [row.status for row in rows]==['priced_upper_bound','priced_upper_bound']
            assert [row.usage['accounted_upper_bound_cents'] for row in rows]==[1,5]
            assert all(row.usage['actual_cost_cents'] is None for row in rows)
            assert db.get(Account,'global').spent==6
            assert db.get(Account,'global').reserved==0
            # Contract was valid at reservation, then changed during the request.
            change_during_call.append(True)
            await paid(db,db.get(Job,jid),'curation',lambda:provider.curate(raw.getvalue(),brief,'A'))
            latest=db.scalar(select(Reservation).order_by(Reservation.created_at.desc()).limit(1))
            assert latest.status=='ceiling_charged'
            assert latest.usage['actual_cost_cents'] is None
            assert db.get(Account,'global').spent==16
    assert len(calls)==3

@pytest.mark.asyncio
async def test_missing_or_expired_pricing_prevents_any_new_call_or_reservation(configured,monkeypatch):
    import os,json,hashlib
    from pathlib import Path
    from app.worker import paid
    _,_,jid=fixture_job();calls=[]
    async def provider_call():calls.append(True);return {}
    path=Path(os.environ['VERIFIED_PRICING_FILE']);valid=path.read_text()
    with factory()() as db:
        monkeypatch.delenv('VERIFIED_PRICING_FILE')
        with pytest.raises(BudgetBlocked):await paid(db,db.get(Job,jid),'text',provider_call)
        monkeypatch.setenv('VERIFIED_PRICING_FILE',str(path))
        expired=json.loads(valid);expired['expires_at']='2000-01-01T00:00:00+00:00';path.write_text(json.dumps(expired));monkeypatch.setenv('VERIFIED_PRICING_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
        with pytest.raises(BudgetBlocked):await paid(db,db.get(Job,jid),'text',provider_call)
        assert not list(db.scalars(select(Reservation)))
        assert db.get(Account,'global').spent==0
        assert db.get(Account,'global').reserved==0
    assert calls==[]

@pytest.mark.asyncio
@pytest.mark.parametrize('route_reachable',[False,True])
async def test_transport_probe_before_paid_reservation(configured,monkeypatch,route_reachable):
    import httpx
    from app.transport import RouteProbe
    from app.provider import ProviderError
    from app.worker import paid
    _,_,jid=fixture_job();probe_calls=[];model_calls=[]
    async def route(request):
        probe_calls.append(request)
        assert 'authorization' not in request.headers
        if not route_reachable:raise httpx.ConnectTimeout('controlled dead proxy')
        return httpx.Response(401)
    probe=RouteProbe(transport=httpx.MockTransport(route))
    monkeypatch.setattr('app.worker.route_preflight',probe.check)
    async def model():model_calls.append(True);raise ProviderError('controlled transport failure',retryable=True)
    with factory()() as db:
        expected=ProviderError if route_reachable else BudgetBlocked
        with pytest.raises(expected):await paid(db,db.get(Job,jid),'text',model)
        reservations=list(db.scalars(select(Reservation)))
        assert len(reservations)==(1 if route_reachable else 0)
        assert db.get(Account,'global').reserved==0
        assert db.get(Account,'global').spent==(10 if route_reachable else 0)
        if reservations:
            assert reservations[0].status=='ceiling_charged'
            assert reservations[0].usage['actual_cost_cents'] is None
    assert len(model_calls)==(1 if route_reachable else 0)
    assert len(probe_calls)==1

@pytest.mark.asyncio
async def test_reference_model_requires_own_contract_and_records_actual_request_identity(configured,monkeypatch):
    import os,json,hashlib,base64,httpx
    from pathlib import Path
    from app.security import ready
    from app.provider import Provider
    from app.worker import paid
    monkeypatch.setenv('OPENAI_REFERENCE_IMAGE_MODEL','gpt-image-1')
    _,_,jid=fixture_job();calls=[]
    raw=io.BytesIO();Image.new('RGB',(256,256)).save(raw,'PNG')
    async def handler(request):
        calls.append(request)
        assert b'name="model"\r\n\r\ngpt-image-1\r\n' in request.content
        return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(raw.getvalue()).decode()}],'usage':{'input_tokens':1,'input_tokens_details':{'text_tokens':1,'image_tokens':0},'output_tokens':1,'total_tokens':2}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider=Provider(api_key='controlled-qa',client=client)
        brief=await ControlledProvider().brief()
        with factory()() as db:
            assert ready(db.get(Tenant,'one'))[0] is False
            with pytest.raises(BudgetBlocked):
                await paid(db,db.get(Job,jid),'image',lambda:provider.render(brief,'A','Holzfronten',raw.getvalue()),requested_model=provider.reference_image_model)
            assert calls==[] and not list(db.scalars(select(Reservation)))
            path=Path(os.environ['VERIFIED_PRICING_FILE']);value=json.loads(path.read_text())
            # Explicit QA contract only; no runtime tariff is installed by this test.
            value['models']['gpt-image-1']={'kind':'image','text_input_usd_per_million':'5','image_input_usd_per_million':'10','image_output_usd_per_million':'40','text_output_supported':False}
            path.write_text(json.dumps(value));monkeypatch.setenv('VERIFIED_PRICING_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
            assert ready(db.get(Tenant,'one'))[0] is True
            await paid(db,db.get(Job,jid),'image',lambda:provider.render(brief,'A','Holzfronten',raw.getvalue()),requested_model=provider.reference_image_model)
            reservation=db.scalar(select(Reservation))
            assert reservation.usage['provider_model']=='gpt-image-1'
            assert reservation.usage['model_identity_source']=='request'
            assert reservation.status=='priced_upper_bound'
            assert reservation.usage['actual_cost_cents'] is None
    assert len(calls)==1
