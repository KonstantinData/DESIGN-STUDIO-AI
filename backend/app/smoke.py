"""Privileged local operator text-provider smoke, never public bot E2E acceptance.

Without --execute, this only inspects existing private state and durable results.
With --execute, one text studio enters the ordinary durable worker queue after
operator/pricing/project/budget/readiness gates. No provider is called by this
CLI; workers may execute the authorized job after commit. Production HTTP bot
protection remains untouched. Keep all inputs/state outside Git, mode0600.
"""
import argparse,secrets,json
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from .acceptance import verify_gate,budget_check,private_write,read_json,audit
from .paths import checkout_root

from .db import Session,Studio,Job,Revision,factory,now,uid
from .security import digest,host_name,ready


def submit(db,host,prompt,state,save,gate):
    if not 3<=len(prompt.strip())<=4000:raise ValueError('A real text impulse of 3–4000 characters is required')
    tenant_id=budget_check(db,host)
    from .db import Tenant,Account
    tenant=db.get(Tenant,tenant_id);account=db.get(Account,'global')
    if any(row.budget>gate['run_budget_cents'] for row in (account,tenant)):raise ValueError('Persisted cap exceeds approved run budget')
    permitted,reason=ready(tenant)
    if not permitted:raise ValueError(reason)
    if state.get('kind') not in (None,'private_operator_provider_smoke'):raise ValueError('State belongs to another workflow')
    if state.get('host',host)!=host:raise ValueError('Private state belongs to a different tenant host')
    case=state.setdefault('cases',{}).setdefault('text',{})
    if case.get('studio_id'):
        existing=db.get(Studio,case['studio_id'])
        if existing:
            if existing.session_id!=case.get('session_id') or existing.tenant_id!=tenant_id:raise ValueError('Persisted smoke ownership mismatch')
            raise ValueError('This smoke was already submitted; inspect instead of repeating')
        # Precommitted private intent can be safely recovered only with the exact same prompt.
        if case.get('request_hash')!=digest(prompt):raise ValueError('Uncommitted smoke intent does not match the original prompt')
    else:
        case.update(session_id=uid(),studio_id=uid(),job_id=uid(),cookie=secrets.token_urlsafe(48),request_hash=digest(prompt))
    state.update(kind='private_operator_provider_smoke',host=host,base_url='https://'+host)
    save(state)  # durable private intent precedes any possible worker admission
    db.add(Session(id=case['session_id'],tenant_id=tenant_id,token_hash=digest(case['cookie']),expires_at=now()+timedelta(days=30)))
    db.flush()
    db.add(Studio(id=case['studio_id'],tenant_id=tenant_id,session_id=case['session_id'],prompt=prompt,source_kind='text'))
    db.flush()
    db.add(Job(id=case['job_id'],tenant_id=tenant_id,session_id=case['session_id'],studio_id=case['studio_id'],operation='brief',idempotency_key='trusted-operator-smoke',request_hash=digest(prompt),payload={}))
    db.commit()
    case['submitted']=['initial'];save(state)


def submit_change(db,host,instruction,state,save,gate,kind):
    """Trusted local operator continuation; never adds a public bot exemption."""
    if kind not in ('material','layout') or not 3<=len(instruction.strip())<=2000:raise ValueError('A bounded material/layout instruction is required')
    tenant_id=budget_check(db,host)
    from .db import Tenant,Account
    tenant=db.get(Tenant,tenant_id);account=db.get(Account,'global')
    if any(row.budget>gate['run_budget_cents'] for row in (account,tenant)):raise ValueError('Persisted cap exceeds approved run budget')
    permitted,reason=ready(tenant)
    if not permitted:raise ValueError(reason)
    if state.get('kind')!='private_operator_provider_smoke' or state.get('host')!=host:raise ValueError('Matching private operator session state required')
    case=state.get('cases',{}).get('text',{})
    session=db.scalar(select(Session).where(Session.id==case.get('session_id'),Session.tenant_id==tenant_id,Session.token_hash==digest(case.get('cookie','')),Session.expires_at>now()).with_for_update().execution_options(populate_existing=True))
    if not session:raise ValueError('Saved session authorization expired or revoked')
    studio=db.scalar(select(Studio).where(Studio.id==case.get('studio_id'),Studio.session_id==session.id,Studio.tenant_id==tenant_id))
    if not studio:raise ValueError('Smoke studio ownership mismatch')
    if db.scalar(select(Job.id).where(Job.studio_id==studio.id,Job.status.in_(['queued','running'])).limit(1)):raise ValueError('Wait for terminal initial/revision jobs')
    initials=list(db.scalars(select(Revision).where(Revision.studio_id==studio.id,Revision.tenant_id==tenant_id,Revision.kind=='initial').order_by(Revision.created_at)))
    if set(revision.concept for revision in initials)!=set('ABC') or len({revision.room_version for revision in initials})!=1 or any(revision.profile.get('review',{}).get('critical_error') for revision in initials):raise ValueError('Three noncritical initial concepts on one shared room version are required')
    original=next((revision for revision in initials if revision.concept=='A'),None)
    if not original or original.profile.get('review',{}).get('critical_error'):raise ValueError('A noncritical original initial A is required for this smoke')
    payload={'concept':'A','kind':kind,'instruction':instruction,'base_revision_id':original.id}
    fingerprint=digest(json.dumps(payload,sort_keys=True))
    key='trusted-operator-smoke-'+kind
    existing=db.scalar(select(Job).where(Job.session_id==session.id,Job.operation=='render',Job.idempotency_key==key))
    if existing:
        if existing.request_hash!=fingerprint:raise ValueError('Action already submitted with another instruction')
        raise ValueError('Action already submitted; inspect durable result rather than repeat')
    if session.changes_used+session.changes_pending>=5:raise ValueError('Successful-change quota is exhausted')
    intent=case.setdefault('intents',{}).get(kind)
    if intent and intent['request_hash']!=fingerprint:raise ValueError('Saved action intent differs; investigate before spending')
    if not intent:
        intent={'job_id':uid(),'request_hash':fingerprint}
        case['intents'][kind]=intent
    save(state)
    job=Job(id=intent['job_id'],tenant_id=tenant_id,session_id=session.id,studio_id=studio.id,operation='render',idempotency_key=key,request_hash=fingerprint,payload=payload)
    db.add(job);session.changes_pending+=1;studio.status='running';db.commit()
    case.setdefault('submitted',[]).append(kind);save(state)


def report(db,state):
    result=audit(db,state)
    result.update(workflow='private_operator_provider_smoke',expected_images=3+sum(kind in state.get('cases',{}).get('text',{}).get('submitted',[]) for kind in ('material','layout')),public_bot_e2e='NOT_TESTED',status='BLOCKED',human_acceptance='required')
    # Photo and floorplan paths are deliberately not implied by a text smoke.
    result['cases']=[case for case in result['cases'] if case['source']=='text']
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--action',choices=['initial','material','layout'],default='initial')
    parser.add_argument('--instruction-file',type=Path)
    parser.add_argument('--prompt-file',type=Path)
    parser.add_argument('--gate-file',type=Path)
    args=parser.parse_args(argv)
    try:
        checkout=checkout_root()
        paths=[args.state.resolve(),args.report.resolve()]
        inputs=[p.resolve() for p in (args.prompt_file,args.instruction_file,args.gate_file) if p]
        if len(set(paths+inputs))!=len(paths+inputs) or any(path.is_relative_to(checkout) for path in paths):raise ValueError('Use distinct private state/report paths outside checkout')
        host=host_name(args.host)
        if host!=args.host:raise ValueError('Use the configured lowercase hostname without port')
        state=read_json(args.state) if args.state.exists() else {}
        with factory()() as db:
            if args.execute:
                if not args.gate_file:raise ValueError('--execute requires a verified private gate file')
                gate=verify_gate(args.gate_file)
                source=args.prompt_file if args.action=='initial' else args.instruction_file
                if not source or source.stat().st_size>16000:raise ValueError('A bounded private prompt/instruction file is required')
                save=lambda value:private_write(args.state,value)
                if args.action=='initial':submit(db,host,source.read_text(),state,save,gate)
                else:submit_change(db,host,source.read_text(),state,save,gate,args.action)
            private_write(args.report,report(db,state))
        print('Private smoke audit saved. Public bot E2E and human image acceptance remain BLOCKED.')
        return 0
    except (ValueError,OSError,SQLAlchemyError):
        print('BLOCKED: verify private inputs, operator gates, persisted caps and deployment readiness.')
        return 2
if __name__=='__main__':raise SystemExit(main())
