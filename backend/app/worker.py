"""Durable PostgreSQL jobs. Unknown provider outcomes consume full reserved ceiling.
Never retries unknown outcomes automatically. No provider call without a committed reservation.
"""
import asyncio, copy, json, os, time
from datetime import timedelta
from pathlib import Path
from uuid import UUID
from sqlalchemy import select, func
from .db import factory,Tenant,Account,Session,Studio,Job,Revision,Media,Reservation,AdmissionBucket,now
from .privacy import erase,replay
from .security import ready,seed,store_media,data_dir
from .provider import Provider,ProviderError,ProviderPreflightError
from .costing import load_contract,still_trusted,bound_usage
from .transport import route_preflight,RouteUnavailable

class BudgetBlocked(RuntimeError): pass

def reserve(db,job_id,amount):
    job=db.get(Job,job_id)
    if not job: raise BudgetBlocked('Sitzung wurde gelöscht.')
    # Constant lock order across every worker; global account serializes total exposure.
    account=db.scalar(select(Account).where(Account.id=='global').with_for_update().execution_options(populate_existing=True))
    tenant=db.scalar(select(Tenant).where(Tenant.id==job.tenant_id).with_for_update().execution_options(populate_existing=True))
    ok,reason=ready(tenant)
    if not ok: raise BudgetBlocked(reason)
    if amount<=0 or any(x.spent+x.reserved+amount>x.budget for x in (account,tenant)): raise BudgetBlocked('Der verfügbare Kostenrahmen ist ausgeschöpft.')
    for item in (account,tenant): item.reserved+=amount
    row=Reservation(tenant_id=tenant.id,job_id=job.id,amount=amount); db.add(row); db.commit(); return row.id

def settle(db,reservation_id,usage,*,known_no_call=False,upper_bound_cents=None):
    # Read immutable tenant ID, then one lock order shared by all money mutations.
    tenant_id=db.scalar(select(Reservation.tenant_id).where(Reservation.id==reservation_id))
    if tenant_id is None: return
    account=db.scalar(select(Account).where(Account.id=='global').with_for_update().execution_options(populate_existing=True))
    tenant=db.scalar(select(Tenant).where(Tenant.id==tenant_id).with_for_update().execution_options(populate_existing=True))
    r=db.scalar(select(Reservation).where(Reservation.id==reservation_id).with_for_update().execution_options(populate_existing=True))
    # Re-read status under the row lock: duplicated callbacks charge exactly once.
    if not r or r.status!='reserved':
        db.commit(); return
    charge=0 if known_no_call else upper_bound_cents if type(upper_bound_cents) is int and upper_bound_cents>=0 else r.amount
    for item in (account,tenant):
        item.reserved-=r.amount
        item.spent+=charge
    exceeded=charge>r.amount
    if exceeded:
        tenant.enabled=False
        account.budget=min(account.budget,account.spent+account.reserved)
    r.status='released_no_call' if known_no_call else 'ceiling_exceeded' if exceeded else 'priced_upper_bound' if upper_bound_cents is not None else 'ceiling_charged'
    r.usage={**usage,'accounted_upper_bound_cents':charge,'ceiling_exceeded':exceeded}; db.commit()

async def paid(db,job,kind,call,*,requested_model=None):
    amount=int(os.getenv('RESERVATION_'+kind.upper()+'_CENTS',{'text':'10','image':'100','curation':'10'}[kind]))
    pricing_contract=load_contract()
    requested_model=requested_model or (os.getenv('OPENAI_IMAGE_MODEL','gpt-image-1.5') if kind=='image' else os.getenv('OPENAI_TEXT_MODEL','gpt-4.1-mini'))
    expected_kind='image' if kind=='image' else 'responses'
    if not pricing_contract or pricing_contract.value['models'].get(requested_model,{}).get('kind')!=expected_kind:raise BudgetBlocked('Ein aktueller, unverändert geprüfter Preisvertrag für diesen Anbieteraufruf fehlt.')
    pending_job=db.get(Job,job.id)
    pending_tenant=db.get(Tenant,pending_job.tenant_id) if pending_job else None
    permitted,reason=ready(pending_tenant) if pending_tenant else (False,'Die Sitzung wurde gelöscht.')
    if not permitted:raise BudgetBlocked(reason)
    try:await route_preflight()
    except RouteUnavailable as exc:raise BudgetBlocked(str(exc)) from None
    reservation=reserve(db,job.id,amount)
    started=time.monotonic()
    try:
        deadline=float(os.getenv('PROVIDER_'+kind.upper()+'_DEADLINE_SECONDS',{'text':'90','image':'240','curation':'90'}[kind]))
        if not 0<deadline<=600: raise ValueError('Provider deadline must be positive and at most 600 seconds')
        async with asyncio.timeout(deadline):
            result=await call()
        usage=result.get('_provider_usage',{}) if isinstance(result,dict) else getattr(result,'usage',{})
        request_id=result.get('_provider_request_id') if isinstance(result,dict) else getattr(result,'request_id',None)
        model=result.get('_provider_model') if isinstance(result,dict) else getattr(result,'model',None)
        model_basis=result.get('_provider_model_identity_source') if isinstance(result,dict) else getattr(result,'model_identity_source',None)
        priced=bound_usage(pricing_contract,kind,model,usage) if still_trusted(pricing_contract) and model_basis==('request' if kind=='image' else 'response') else None
        details={'duration_seconds':round(time.monotonic()-started,3),'provider_request_id':request_id,'provider_model':model,'model_identity_source':model_basis,'measured_usage':usage,'actual_cost_cents':None,'accounting':'conservative_ceiling_pending_invoice_reconciliation'}
        if priced:details.update(priced)
        settle(db,reservation,details,upper_bound_cents=priced['upper_bound_cents'] if priced else None)
        return result
    except ProviderPreflightError:
        settle(db,reservation,{'duration_seconds':round(time.monotonic()-started,3),'outcome':'verified_local_no_call','actual_cost_cents':0},known_no_call=True)
        raise
    except BaseException as exc:
        details={'duration_seconds':round(time.monotonic()-started,3),'outcome':'timeout_unknown' if isinstance(exc,TimeoutError) else 'cancelled_unknown' if isinstance(exc,asyncio.CancelledError) else 'unknown_or_failed','actual_cost_cents':None}
        if isinstance(exc,ProviderError): details.update(exc.safe_diagnostics())
        settle(db,reservation,details)
        raise

def claim(db):
    # Advisory lock serializes global worker admission, SKIP LOCKED distributes jobs.
    db.execute(__import__('sqlalchemy').text('SELECT pg_advisory_xact_lock(681920)'))
    active=db.scalar(select(func.count()).select_from(Job).where(Job.status=='running'))
    if active>=int(os.getenv('MAX_PROVIDER_CONCURRENCY','3')): db.rollback(); return None
    job=db.scalar(select(Job).where(Job.status=='queued').order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
    if not job: db.rollback(); return None
    job.status='running'; job.started_at=now(); db.commit(); return job.id

def source_bytes(db,ident):
    media=db.get(Media,ident) if ident else None
    return Path(media.path).read_bytes() if media else None

async def execute(job_id,provider=None):
    db=factory()(); provider=provider or Provider()
    generated=None
    try:
        job=db.get(Job,job_id)
        if not job: return
        studio=db.get(Studio,job.studio_id)
        if not studio: return
        if job.operation=='brief':
            brief=await paid(db,job,'text',lambda:provider.brief(studio.prompt,source_bytes(db,studio.source_media_id),studio.source_kind))
            if not brief.get('usable'): raise BudgetBlocked(brief.get('rejection_reason') or 'Die Vorlage ist nicht ausreichend lesbar. Bitte lade ein anderes Bild hoch oder starte mit einem Beispielraum.')
            # Serialize deletion and publication; no stale result survives session removal.
            s=db.scalar(select(Session).where(Session.id==job.session_id).with_for_update().execution_options(populate_existing=True))
            if not s: return
            db.refresh(studio); studio.brief=brief; studio.status='running'
            for key in 'ABC':
                db.add(Job(tenant_id=job.tenant_id,session_id=job.session_id,studio_id=studio.id,operation='render',idempotency_key='initial-'+key,request_hash='initial',payload={'concept':key,'kind':'initial'}))
            job.status='completed'; db.commit(); return
        brief=copy.deepcopy(studio.brief); key=job.payload['concept']; kind=job.payload['kind']
        source=source_bytes(db,studio.source_media_id)
        change=job.payload.get('instruction')
        if job.payload.get('base_revision_id'):
            base=db.get(Revision,job.payload['base_revision_id'])
            if not base or base.studio_id!=studio.id: raise BudgetBlocked('Die gewählte Ausgangsversion ist nicht mehr verfügbar.')
            source=source_bytes(db,base.media_id)
            base_brief=copy.deepcopy(base.profile['briefing'])
            # Keep selected concept revision as origin while applying explicitly corrected global room.
            base_brief['room']=copy.deepcopy(studio.brief['room'])
            base_brief['room_history']=copy.deepcopy(studio.brief.get('room_history',[]))
            brief=base_brief
            brief['revision_instruction']={'kind':kind,'instruction':change,'preserve_geometry':True,'preserve_furniture_layout':kind=='material'}
            chosen=copy.deepcopy(brief['concepts'][key])
            chosen['revision_instruction']=change
            chosen['revision_kind']=kind
            brief['concepts'][key]=chosen
        generation_model=getattr(provider,'image_model',os.getenv('OPENAI_IMAGE_MODEL','gpt-image-1.5'))
        selected_image_model=getattr(provider,'reference_image_model',os.getenv('OPENAI_REFERENCE_IMAGE_MODEL') or generation_model) if source is not None else generation_model
        image=await paid(db,job,'image',lambda:provider.render(brief,key,change,source),requested_model=selected_image_model)
        curation=await paid(db,job,'curation',lambda:provider.curate(image,brief,key))
        # Shadow-only observation: no automated acceptance or concealment of failures.
        review={'mode':'shadow','requires_human_acceptance':True,'critical_error':curation.get('critical_error',False),'critical_reason':curation.get('critical_reason')}
        s=db.scalar(select(Session).where(Session.id==job.session_id).with_for_update().execution_options(populate_existing=True))
        if not s: return
        # Session may have been deleted while external generation ran; check fresh Job.
        db.expire_all(); job=db.get(Job,job_id)
        if not job: return
        studio=db.get(Studio,job.studio_id)
        m=store_media(db,job.tenant_id,job.session_id,image)
        generated=m.path
        number=(db.scalar(select(func.max(Revision.number)).where(Revision.studio_id==studio.id,Revision.concept==key)) or 0)+1
        db.add(Revision(studio_id=studio.id,tenant_id=job.tenant_id,concept=key,number=number,kind=kind,media_id=m.id,curation=curation['lines'],profile={'briefing':brief,'instruction':change,'base_revision_id':job.payload.get('base_revision_id'),'automated_review':'shadow_only_not_human_acceptance','review':review},room_version=brief['room']['version']))
        if kind!='initial':
            if not review['critical_error']: s.changes_used+=1
            s.changes_pending=max(0,s.changes_pending-1)
        job.status='review_required' if review['critical_error'] else 'completed'; job.error=review['critical_reason'] if review['critical_error'] else None
        db.flush(); update_studio(db,studio); db.commit(); generated=None
    except Exception as exc:
        db.rollback()
        # Do not log request data, prompts, keys or provider bodies.
        job=db.get(Job,job_id)
        if job:
            s=db.scalar(select(Session).where(Session.id==job.session_id).with_for_update().execution_options(populate_existing=True))
            if s:
                job.status='failed'; job.error=str(exc) if isinstance(exc,BudgetBlocked) else 'Die Generierung ist technisch fehlgeschlagen. Dein Änderungsguthaben wurde nicht verbraucht.'
                if job.operation=='render' and job.payload.get('kind')!='initial': s.changes_pending=max(0,s.changes_pending-1)
                studio=db.get(Studio,job.studio_id)
                if studio:
                    if job.operation=='brief': studio.status='failed'; studio.error=job.error
                    else: db.flush(); update_studio(db,studio)
                db.commit()
    finally:
        if generated: Path(generated).unlink(missing_ok=True)
        db.close()

def update_studio(db,studio):
    jobs=db.scalars(select(Job).where(Job.studio_id==studio.id,Job.operation=='render')).all()
    if any(j.status in ('running','queued') for j in jobs): studio.status='running'
    else:
        keys=set(db.scalars(select(Revision.concept).where(Revision.studio_id==studio.id)))
        critical=any(j.status=='review_required' for j in jobs)
        studio.status='review_required' if critical else 'completed' if len(keys)==3 else 'partial' if keys else 'failed'

def maintain(db):
    # Expired jobs never get silently replayed: provider outcome may be unknown.
    stale=db.scalars(select(Job).where(Job.status=='running',Job.started_at<now()-timedelta(minutes=30)).with_for_update(skip_locked=True)).all()
    for job in stale:
        job.status='failed'; job.error='Der Auftrag wurde nach einem unterbrochenen Worker sicher angehalten.'
        s=db.get(Session,job.session_id)
        if s and job.operation=='render' and job.payload.get('kind')!='initial': s.changes_pending=max(0,s.changes_pending-1)
        studio=db.get(Studio,job.studio_id)
        if studio: db.flush(); update_studio(db,studio)
    expired=db.scalars(select(Session).where(Session.expires_at<=now()).with_for_update(skip_locked=True)).all()
    for s in expired: erase(db,s)
    db.execute(__import__('sqlalchemy').delete(AdmissionBucket).where(AdmissionBucket.expires_at<=now()))
    db.commit()
    # Crash-orphan reconciliation; grace period avoids racing in-flight fs writes.
    live=set(db.scalars(select(Media.path)))
    import time
    for path in data_dir().iterdir():
        # Only files named exactly like generated media IDs belong to media GC.
        try:
            if str(UUID(path.name))!=path.name:continue
        except ValueError:continue
        if path.name not in ('STOP_GENERATION','.rate-limit-key') and path.is_file() and str(path) not in live and path.stat().st_mtime<time.time()-3600: path.unlink(missing_ok=True)

async def run():
    make=factory()
    with make() as db: seed(db); replay(db); maintain(db)
    pending=set(); ticks=0
    while True:
        pending={t for t in pending if not t.done()}
        with make() as db:
            if ticks%60==0: maintain(db)
            ident=claim(db) if len(pending)<3 else None
        Path('/tmp/worker-heartbeat').touch()
        if ident: pending.add(asyncio.create_task(execute(ident)))
        else: await asyncio.sleep(1)
        ticks+=1
if __name__=='__main__': asyncio.run(run())
