import asyncio, hashlib, json, os, secrets
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text, func
from sqlalchemy.exc import IntegrityError
from .db import factory, Tenant, Session, Studio, Job, Revision, Media, Handoff, now
from .security import host_name,digest, token, seed, ready, challenge, normalize_image, store_media
from .admission import RequestGuard,consume,AdmissionDenied
from .privacy import erase,replay

DB=None
@asynccontextmanager
async def lifespan(app):
    global DB
    DB=factory()
    with DB() as db: seed(db); replay(db)
    yield
app=FastAPI(title='Design Studio private API',lifespan=lifespan,docs_url=None,redoc_url=None)
app.add_middleware(RequestGuard)

def database():
    with DB() as db: yield db

def tenant(request:Request,db=Depends(database)):
    host=host_name(request.headers.get('host',''))
    row=db.scalar(select(Tenant).where(Tenant.host==host))
    if not row: raise HTTPException(421,'Unbekanntes Studio.')
    return row

def session(request:Request,db=Depends(database),t=Depends(tenant)):
    raw=request.cookies.get('__Host-studio')
    row=db.scalar(select(Session).where(Session.tenant_id==t.id,Session.token_hash==digest(raw or ''),Session.expires_at>now()))
    if not row: raise HTTPException(401,'Die Sitzung ist abgelaufen. Bitte starte neu.')
    return row

def csrf(request:Request,s=Depends(session)):
    expected='https://'+request.headers.get('host','').lower()
    hostname=urlsplit('//'+request.headers.get('host','')).hostname or ''
    if os.getenv('ALLOW_LOCAL_HTTP','false')=='true' and (hostname in ('localhost','127.0.0.1') or hostname.endswith('.localhost')): expected='http://'+request.headers['host']
    if request.headers.get('origin')!=expected: raise HTTPException(403,'Ungültige Anfrageherkunft.')
    expected_token=digest(s.token_hash+'csrf')
    if not secrets.compare_digest(request.headers.get('x-csrf-token',''),expected_token): raise HTTPException(403,'Ungültiger Sitzungsschutz.')
    return s

@app.middleware('http')
async def headers(request,call_next):
    response=await call_next(request)
    response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Robots-Tag':'noindex, nofollow'})
    return response

@app.get('/healthz')
def health(db=Depends(database)):
    db.execute(text('SELECT 1')); return {'status':'ok'}

@app.get('/api/config')
def config(t=Depends(tenant)):
    ok,reason=ready(t)
    return {'brand':t.config.get('brand','Design Studio'),'expert_name':t.config.get('expert_name','Konstantin'),'turnstile_site_key':t.config.get('turnstile_site_key',''),'generation_ready':ok,'blocked_reason':reason}

@app.get('/api/session')
def get_session(request:Request,response:__import__('fastapi').Response,db=Depends(database),t=Depends(tenant)):
    raw=request.cookies.get('__Host-studio','')
    s=db.scalar(select(Session).where(Session.tenant_id==t.id,Session.token_hash==digest(raw),Session.expires_at>now()))
    if not s:
        try: consume(db,request.scope,'new_session',int(os.getenv('MAX_SESSIONS_PER_IP_HOUR','10')),3600)
        except AdmissionDenied: raise HTTPException(429,'Zu viele neue Sitzungen. Bitte versuche es später erneut.')
        # Database-serialized global anonymous admission cap prevents unbounded cookie rotation.
        db.execute(text("SELECT pg_advisory_xact_lock(681919)"))
        recent=db.scalar(select(func.count()).select_from(Session).where(Session.created_at>now()-timedelta(hours=1)))
        if recent>=int(os.getenv('MAX_SESSIONS_PER_HOUR','500')): raise HTTPException(429,'Das Studio ist momentan ausgelastet.')
        raw=token(); s=Session(tenant_id=t.id,token_hash=digest(raw),expires_at=now()+timedelta(days=30)); db.add(s); db.commit()
        response.set_cookie('__Host-studio',raw,max_age=2592000,secure=True,httponly=True,samesite='strict',path='/')
    studios=db.scalars(select(Studio).where(Studio.session_id==s.id,Studio.tenant_id==t.id)).all()
    return {'id':s.id,'csrf_token':digest(s.token_hash+'csrf'),'changes_remaining':max(0,5-s.changes_used-s.changes_pending),'studios':[{'id':x.id,'status':x.status} for x in studios]}

def own_studio(db,s,ident):
    row=db.scalar(select(Studio).where(Studio.id==ident,Studio.session_id==s.id,Studio.tenant_id==s.tenant_id))
    if not row: raise HTTPException(404,'Entwurf nicht gefunden.')
    return row

def view(db,studio,s):
    jobs=db.scalars(select(Job).where(Job.studio_id==studio.id)).all()
    revs=db.scalars(select(Revision).where(Revision.studio_id==studio.id).order_by(Revision.created_at)).all()
    brief=studio.brief or {}; concepts=[]
    for key,title in [('A','Ergonomie und Laufwege'),('B','Licht und Raumwirkung'),('C','Stauraum und Ordnung')]:
        r=[x for x in revs if x.concept==key]; j=[x for x in jobs if x.payload.get('concept')==key]
        latest_job=max(j,key=lambda x:x.created_at) if j else None
        status='running' if any(x.status=='running' for x in j) else 'queued' if any(x.status=='queued' for x in j) else latest_job.status if latest_job and latest_job.status in ('failed','review_required') else 'completed' if r else studio.status
        concepts.append({'key':key,'title':brief.get('concepts',{}).get(key,{}).get('title',title),'status':status,'error':latest_job.error if latest_job else None,'revisions':[{'id':x.id,'media_id':x.media_id,'number':x.number,'kind':x.kind,'image_url':'/api/media/'+x.media_id,'download_url':'/api/media/'+x.media_id+'?download=1','curation':x.curation,'assumptions':x.profile.get('briefing',{}).get('assumptions',[]),'created_at':x.created_at.isoformat(),'room_version':x.room_version,'previous_room_basis':x.room_version!=brief.get('room',{}).get('version'),'review':x.profile.get('review',{})} for x in r]})
    return {'source_kind':studio.source_kind,'id':studio.id,'status':studio.status,'error':studio.error,'room':brief.get('room'),'assumptions':brief.get('assumptions',[]),'selected_revision_id':studio.selected_revision_id,'changes_remaining':max(0,5-s.changes_used-s.changes_pending),'concepts':concepts}

@app.get('/api/studios/{ident}')
def get_studio(ident:str,db=Depends(database),s=Depends(session)):
    return view(db,own_studio(db,s,ident),s)

def keycheck(key):
    if not key or len(key)>128: raise HTTPException(400,'Ein gültiger Idempotency-Key ist erforderlich.')

def generation_check(db,t,s):
    ok,reason=ready(t)
    if not ok: raise HTTPException(503,reason)
    db.execute(select(Session).where(Session.id==s.id).with_for_update().execution_options(populate_existing=True)).scalar_one()
    active=db.scalar(select(func.count()).select_from(Job).where(Job.session_id==s.id,Job.status.in_(['queued','running'])))
    if active: raise HTTPException(409,'Bitte warte auf die laufende Generierung.')

@app.post('/api/studios',status_code=202)
async def create_studio(prompt:str=Form(''),source_kind:str=Form('text'),challenge_token:str=Form(''),file:UploadFile|None=File(None),idempotency_key:str|None=Header(None),db=Depends(database),t=Depends(tenant),s=Depends(csrf)):
    keycheck(idempotency_key)
    if source_kind not in ('text','photo','floorplan') or len(prompt)>4000 or (source_kind=='text' and not prompt.strip()) or (source_kind!='text' and not file): raise HTTPException(422,'Bitte gib einen Impuls oder ein geeignetes Bild ein.')
    raw=normalize_image(await file.read(12*1024*1024+1)) if file else None
    fingerprint=digest(json.dumps([prompt,source_kind,hashlib.sha256(raw or b'').hexdigest()]))
    existing=db.scalar(select(Job).where(Job.session_id==s.id,Job.idempotency_key==idempotency_key,Job.operation=='brief'))
    if existing:
        if existing.request_hash!=fingerprint: raise HTTPException(409,'Der Schlüssel wurde für einen anderen Auftrag verwendet.')
        return view(db,own_studio(db,s,existing.studio_id),s)
    generation_check(db,t,s)
    existing=db.scalar(select(Job).where(Job.session_id==s.id,Job.idempotency_key==idempotency_key,Job.operation=='brief'))
    if existing:
        if existing.request_hash!=fingerprint: raise HTTPException(409,'Der Schlüssel wurde für einen anderen Auftrag verwendet.')
        return view(db,own_studio(db,s,existing.studio_id),s)
    studios=db.scalars(select(Studio).where(Studio.session_id==s.id)).all()
    if any(x.status!='failed' for x in studios): raise HTTPException(429,'Pro Sitzung ist ein kostenloser Start mit drei Konzepten verfügbar.')
    if len(studios)>=3: raise HTTPException(429,'Die sichere Grenze für erneute Eingabeanalysen wurde erreicht.')
    await challenge(t,challenge_token)
    studio=Studio(tenant_id=t.id,session_id=s.id,prompt=prompt,source_kind=source_kind); db.add(studio); db.flush()
    if raw: studio.source_media_id=store_media(db,t.id,s.id,raw,'image/jpeg').id
    db.add(Job(tenant_id=t.id,session_id=s.id,studio_id=studio.id,operation='brief',idempotency_key=idempotency_key,request_hash=fingerprint,payload={}))
    db.commit(); return view(db,studio,s)

class Change(BaseModel):
    concept:str=Field(pattern='^[ABC]$')
    kind:str=Field(pattern='^(material|layout)$')
    instruction:str=Field(min_length=3,max_length=2000)
    base_revision_id:str
    challenge_token:str=''
@app.post('/api/studios/{ident}/revisions',status_code=202)
async def change(ident:str,body:Change,idempotency_key:str|None=Header(None),db=Depends(database),t=Depends(tenant),s=Depends(csrf)):
    keycheck(idempotency_key); studio=own_studio(db,s,ident)
    fp=digest(body.model_dump_json(exclude={'challenge_token'}))
    old=db.scalar(select(Job).where(Job.session_id==s.id,Job.idempotency_key==idempotency_key,Job.operation=='render'))
    if old:
        if old.request_hash!=fp: raise HTTPException(409,'Der Schlüssel wurde für einen anderen Auftrag verwendet.')
        return {'job_id':old.id}
    generation_check(db,t,s)
    if s.changes_used+s.changes_pending>=5: raise HTTPException(429,'Deine fünf kostenlosen Änderungen sind verbraucht. Alle bisherigen Entwürfe bleiben verfügbar.')
    base=db.scalar(select(Revision).where(Revision.id==body.base_revision_id,Revision.studio_id==ident,Revision.tenant_id==t.id,Revision.concept==body.concept))
    if not base: raise HTTPException(404,'Ausgangsversion nicht gefunden.')
    await challenge(t,body.challenge_token)
    job=Job(tenant_id=t.id,session_id=s.id,studio_id=ident,operation='render',idempotency_key=idempotency_key,request_hash=fp,payload=body.model_dump(exclude={'challenge_token'})); db.add(job); s.changes_pending+=1; studio.status='running'; db.commit(); return {'job_id':job.id}
class Select(BaseModel): revision_id:str
@app.post('/api/studios/{ident}/select')
def select_revision(ident:str,body:Select,db=Depends(database),s=Depends(csrf)):
    studio=own_studio(db,s,ident)
    if not db.scalar(select(Revision).where(Revision.id==body.revision_id,Revision.studio_id==ident,Revision.tenant_id==s.tenant_id)): raise HTTPException(404,'Version nicht gefunden.')
    studio.selected_revision_id=body.revision_id; db.commit(); return view(db,studio,s)
@app.get('/api/media/{ident}')
def media(ident:str,download:int=0,db=Depends(database),s=Depends(session)):
    row=db.scalar(select(Media).where(Media.id==ident,Media.session_id==s.id,Media.tenant_id==s.tenant_id))
    if not row or not Path(row.path).is_file(): raise HTTPException(404,'Bild nicht gefunden.')
    return FileResponse(row.path,media_type=row.mime,filename='kuechenentwurf.png' if download else None)
@app.post('/api/session/resume-token')
def resume_token(db=Depends(database),s=Depends(csrf)):
    value=token(); s.resume_hash=digest(value); db.commit(); return {'token':value}
@app.delete('/api/session/resume-token',status_code=204)
def revoke_resume_token(db=Depends(database),s=Depends(csrf)):
    db.execute(select(Session).where(Session.id==s.id).with_for_update().execution_options(populate_existing=True)).scalar_one()
    s.resume_hash=None;db.commit()
    return __import__('fastapi').Response(status_code=204)

class Resume(BaseModel): token:str=Field(min_length=40,max_length=256)
@app.post('/api/session/resume')
def resume(body:Resume,response:__import__('fastapi').Response,db=Depends(database),t=Depends(tenant),current=Depends(csrf)):
    s=db.scalar(select(Session).where(Session.tenant_id==t.id,Session.resume_hash==digest(body.token),Session.expires_at>now()).with_for_update().execution_options(populate_existing=True))
    if not s: raise HTTPException(403,'Der Fortsetzungscode ist ungültig oder widerrufen.')
    value=token(); s.token_hash=digest(value); s.resume_hash=None; db.commit()
    response.set_cookie('__Host-studio',value,max_age=2592000,secure=True,httponly=True,samesite='strict',path='/'); return {'resumed':True}
@app.delete('/api/session',status_code=204)
def delete_session(response:__import__('fastapi').Response,db=Depends(database),s=Depends(csrf)):
    # Same session lock as generation completion: deletion cannot race a publication.
    db.execute(select(Session).where(Session.id==s.id).with_for_update().execution_options(populate_existing=True)).scalar_one()
    erase(db,s)
    response.delete_cookie('__Host-studio',secure=True,httponly=True,samesite='strict'); response.status_code=204; return response
class HandoffBody(BaseModel):
    revision_id:str
    media_ids:list[str]=Field(max_length=5)
    name:str=Field(min_length=1,max_length=120)
    email:str=Field(min_length=3,max_length=254)
    message:str=Field(max_length=3000,default='')
    consent:bool
@app.post('/api/studios/{ident}/handoff')
async def handoff(ident:str,body:HandoffBody,idempotency_key:str|None=Header(None),db=Depends(database),t=Depends(tenant),s=Depends(csrf)):
    studio=own_studio(db,s,ident)
    keycheck(idempotency_key)
    db.execute(select(Session).where(Session.id==s.id).with_for_update().execution_options(populate_existing=True)).scalar_one()
    fingerprint=digest(body.model_dump_json())
    existing=db.scalar(select(Handoff).where(Handoff.session_id==s.id,Handoff.idempotency_key==idempotency_key))
    if existing:
        if existing.request_hash!=fingerprint: raise HTTPException(409,'Der Schlüssel wurde für eine andere Übergabe verwendet.')
        if existing.status=='accepted': return {'id':existing.id,'status':'accepted'}
        raise HTTPException(409,'Die Übergabe wurde bereits angefordert; ihre Annahme ist noch nicht bestätigt.')
    if not body.consent or '@' not in body.email: raise HTTPException(422,'Bitte bestätige die freiwillige Übermittlung und prüfe Deine E-Mail-Adresse.')
    rev=db.scalar(select(Revision).where(Revision.id==body.revision_id,Revision.studio_id==ident,Revision.tenant_id==t.id))
    if not rev: raise HTTPException(404,'Version nicht gefunden.')
    allowed={rev.media_id,studio.source_media_id}
    if not set(body.media_ids)<=allowed: raise HTTPException(422,'Nur gewählte Revision und eigenes Ausgangsbild sind übertragbar.')
    target=t.config.get('handoff_url','')
    if not target.startswith('https://') or not os.getenv('HANDOFF_AUTH_'+t.id.upper().replace('-','_')): raise HTTPException(503,'Die authentifizierte persönliche Übergabe ist noch nicht eingerichtet.')
    record=Handoff(tenant_id=t.id,session_id=s.id,revision_id=rev.id,idempotency_key=idempotency_key,request_hash=fingerprint); db.add(record); db.commit()
    import base64
    selected=db.scalars(select(Media).where(Media.id.in_(body.media_ids),Media.session_id==s.id,Media.tenant_id==t.id)).all()
    payload={'handoff_id':record.id,'contact':{'name':body.name,'email':body.email,'message':body.message},'consent':True,'revision':{'id':rev.id,'concept':rev.concept,'curation':rev.curation,'profile':rev.profile['briefing']['concepts'][rev.concept],'instruction':rev.profile.get('instruction')},'briefing':{'room':rev.profile['briefing']['room'],'user_brief':rev.profile['briefing']['user_brief'],'assumptions':rev.profile['briefing'].get('assumptions',[])},'media':[{'id':m.id,'mime':m.mime,'base64':base64.b64encode(Path(m.path).read_bytes()).decode()} for m in selected]}
    try:
        async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
            result=await client.post(target,json=payload,headers={'Idempotency-Key':record.id,'Authorization':'Bearer '+os.environ['HANDOFF_AUTH_'+t.id.upper().replace('-','_')]})
            result.raise_for_status()
            if result.json().get('accepted') is not True: raise ValueError()
    except (httpx.HTTPError,ValueError): record.status='unconfirmed'; db.commit(); raise HTTPException(502,'Die Annahme konnte nicht bestätigt werden. Es wurde kein Erfolg gemeldet.')
    record.status='accepted'; db.commit(); return {'id':record.id,'status':'accepted'}

class RoomCorrection(BaseModel):
    description:str=Field(min_length=3,max_length=4000)
    features:list[dict]=Field(max_length=60)
    constraints:list[str]=Field(max_length=30)
    confirm_global:bool
@app.post('/api/studios/{ident}/room')
def correct_room(ident:str,body:RoomCorrection,db=Depends(database),s=Depends(csrf)):
    """Explicit global fact correction, no automatic image call or invented provenance."""
    studio=own_studio(db,s,ident)
    db.execute(select(Session).where(Session.id==s.id).with_for_update().execution_options(populate_existing=True)).scalar_one()
    if not studio.brief: raise HTTPException(409,'Das gemeinsame Raumbriefing ist noch nicht verfügbar.')
    if not body.confirm_global: raise HTTPException(422,'Bitte bestätige die bewusste Änderung der gemeinsamen Raumgrundlage.')
    if db.scalar(select(func.count()).select_from(Job).where(Job.studio_id==ident,Job.status.in_(['queued','running']))): raise HTTPException(409,'Bitte warte auf laufende Bilder, bevor Du den gemeinsamen Raum korrigierst.')
    features=[]
    for feature in body.features:
        if set(feature)!={'name','value','provenance'} or feature.get('provenance')!='USER_GIVEN' or not all(isinstance(feature[k],str) and 0<len(feature[k])<=1000 for k in ('name','value')): raise HTTPException(422,'Raumkorrekturen müssen explizite Nutzerangaben mit Provenienz USER_GIVEN sein.')
        features.append(feature)
    import copy
    brief=copy.deepcopy(studio.brief)
    old=copy.deepcopy(brief['room']); history=brief.get('room_history',[])
    history.append(old)
    brief['room_history']=history
    by_name={item['name'].casefold():item for item in old.get('features',[])}
    by_name.update({item['name'].casefold():item for item in features})
    brief['room']={'version':old['version']+1,'description':body.description,'features':list(by_name.values()),'constraints':list(dict.fromkeys(old.get('constraints',[])+body.constraints))}
    studio.brief=brief; db.commit(); return view(db,studio,s)
