from datetime import timedelta
from sqlalchemy import select
import pytest
from app.db import factory,Tenant,Account,Session,Job,Studio
from app.security import seed
from app.smoke import submit,report

@pytest.fixture
def smoke_db(pg,monkeypatch):
    monkeypatch.setenv('TENANTS_JSON','[{"host":"one.test","slug":"one","brand":"One","turnstile_site_key":"site","budget_cents":500}]')
    monkeypatch.setenv('GLOBAL_BUDGET_CENTS','500');monkeypatch.setenv('GLOBAL_KILL_SWITCH','false')
    monkeypatch.setenv('PROVIDER_ENABLED','true');monkeypatch.setenv('BUDGET_APPROVED','true')
    monkeypatch.setenv('STUDIO_OPENAI_API_KEY','controlled-test');monkeypatch.setenv('TURNSTILE_SECRET','controlled-test')
    monkeypatch.setenv('HARD_LIMIT_VERIFIED_AT','controlled-evidence')
    with factory()() as db:seed(db)

def test_private_smoke_requires_ready_and_does_not_call_provider(smoke_db,monkeypatch):
    saved=[];state={}
    monkeypatch.setenv('GLOBAL_KILL_SWITCH','true')
    with factory()() as db:
        with pytest.raises(ValueError):submit(db,'one.test','Eine warme Küche',state,saved.append,{'run_budget_cents':500})
        assert not list(db.scalars(select(Job)))
    monkeypatch.setenv('GLOBAL_KILL_SWITCH','false')
    with factory()() as db:
        submit(db,'one.test','Eine warme Küche',state,saved.append,{'run_budget_cents':500})
        jobs=list(db.scalars(select(Job)));assert len(jobs)==1
        assert jobs[0].status=='queued'
        assert db.get(Account,'global').spent==0
        assert db.get(Account,'global').reserved==0
        result=report(db,state)
        assert result['expected_images']==3 and result['actual_images']==0
        assert result['public_bot_e2e']=='NOT_TESTED'
        assert result['status']=='BLOCKED'
        assert 'cookie' not in str(result)
        assert 'Eine warme Küche' not in str(result)
        with pytest.raises(ValueError):submit(db,'one.test','Eine warme Küche',state,saved.append,{'run_budget_cents':500})

def test_operator_changes_both_reference_original_A_and_are_once_only(smoke_db):
    """Only SQL fixtures; no provider call or product output is implied."""
    from app.db import Revision,Media
    from app.smoke import submit_change
    state={};saved=[];gate={'run_budget_cents':500}
    with factory()() as db:
        submit(db,'one.test','Eine helle Küche mit Insel',state,saved.append,gate)
        case=state['cases']['text'];studio=db.get(Studio,case['studio_id'])
        for job in db.scalars(select(Job)):job.status='completed'
        studio.status='completed'
        for key in 'ABC':
            media=Media(tenant_id='one',session_id=case['session_id'],path='/tmp/qa-not-a-product-image-'+key,mime='image/png');db.add(media);db.flush()
            db.add(Revision(studio_id=studio.id,tenant_id='one',concept=key,number=1,kind='initial',media_id=media.id,curation=['QA','QA','QA'],profile={'review':{'critical_error':False}},room_version=1))
        db.commit()
        original=db.scalar(select(Revision).where(Revision.concept=='A'))
        submit_change(db,'one.test','Fronten in hellem Holz',state,saved.append,gate,'material')
        material=db.scalar(select(Job).where(Job.operation=='render'))
        assert material.payload['base_revision_id']==original.id
        assert db.get(Session,case['session_id']).changes_pending==1
        with pytest.raises(ValueError):submit_change(db,'one.test','Insel statt Halbinsel',state,saved.append,gate,'layout')
        db.rollback()
        material.status='completed';db.get(Session,case['session_id']).changes_pending=0;db.commit()
        submit_change(db,'one.test','Insel statt Halbinsel',state,saved.append,gate,'layout')
        layout=db.scalar(select(Job).where(Job.idempotency_key=='trusted-operator-smoke-layout'))
        assert layout.payload['base_revision_id']==original.id
        assert layout.payload['base_revision_id']==material.payload['base_revision_id']
        assert report(db,state)['expected_images']==5
        assert db.get(Account,'global').spent==0
        layout.status='completed';db.get(Session,case['session_id']).changes_pending=0;db.commit()
        with pytest.raises(ValueError):submit_change(db,'one.test','Fronten in hellem Holz',state,saved.append,gate,'material')
        assert len(db.scalars(select(Job).where(Job.operation=='render')).all())==2
