"""Operator reconciliation logic against real QA Postgres; synthetic invoice evidence.
This is not actual billing evidence and never establishes actual product costs.
"""
import json,tempfile
from pathlib import Path
from app.db import factory,Account,Tenant,Reservation
from app.reconcile import reconcile
checks=[]
def check(n,b):assert b,n;checks.append(n)
with factory()() as db:
 a=db.get(Account,'global');t=db.get(Tenant,'mein-kuechenexperte');state=(a.spent,a.budget,t.spent,t.enabled)
 r=Reservation(tenant_id=t.id,amount=100,status='ceiling_charged',usage={'provider_request_id':'qa-only-synthetic-request'});db.add(r);a.spent+=100;t.spent+=100;db.commit();ident=r.id
 evidence=Path(tempfile.mkstemp(prefix='qa-not-real-invoice-')[1]);record={'provider_request_id':'mismatch','actual_usd_cents':24,'billing_record_id':'qa-synthetic','verified_by':'test-only-not-actual-cost'};evidence.write_text(json.dumps(record))
 try:
  try:reconcile(db,ident,24,evidence);rejected=False
  except ValueError:db.rollback();rejected=True
  check('wrong request ID rejected',rejected and db.get(Reservation,ident).status=='ceiling_charged')
  record['provider_request_id']='qa-only-synthetic-request';evidence.write_text(json.dumps(record));reconcile(db,ident,24,evidence)
  check('single correct delta applied',db.get(Account,'global').spent==state[0]+24)
  try:reconcile(db,ident,24,evidence);rejected=False
  except ValueError:db.rollback();rejected=True
  check('duplicate invoice cannot double release',rejected and db.get(Account,'global').spent==state[0]+24)
  extra=Reservation(tenant_id=t.id,amount=100,status='ceiling_charged',usage={'provider_request_id':'qa-over-ceiling'});db.add(extra);a=db.get(Account,'global');t=db.get(Tenant,t.id);a.spent+=100;t.spent+=100;db.commit();extraid=extra.id
  record.update(provider_request_id='qa-over-ceiling',actual_usd_cents=125);evidence.write_text(json.dumps(record));reconcile(db,extraid,125,evidence)
  check('over ceiling disables tenant',db.get(Tenant,t.id).enabled is False)
  a=db.get(Account,'global');check('over ceiling caps new global exposure',a.budget<=a.spent+a.reserved)
 finally:
  db.rollback();a=db.get(Account,'global');t=db.get(Tenant,'mein-kuechenexperte');a.spent,a.budget,t.spent,t.enabled=state
  db.delete(db.get(Reservation,ident))
  if 'extraid' in locals():db.delete(db.get(Reservation,extraid))
  db.commit();evidence.unlink(missing_ok=True)
# One affected regression: invoice delta uses the already charged price bound,
# never the original conservative 100-cent reservation.
from app.worker import settle
with factory()() as db:
 a=db.get(Account,'global');t=db.get(Tenant,'mein-kuechenexperte');state=(a.spent,a.reserved,t.spent,t.reserved,t.enabled,a.budget)
 r=Reservation(tenant_id=t.id,amount=100,status='reserved');db.add(r);a.reserved+=100;t.reserved+=100;db.commit();ident=r.id
 evidence=Path(tempfile.mkstemp(prefix='qa-synthetic-priced-invoice-')[1])
 try:
  settle(db,ident,{'provider_request_id':'qa-priced-request','actual_cost_cents':None,'accounting':'verified_price_upper_bound_not_invoice'},upper_bound_cents=24)
  row=db.get(Reservation,ident)
  check('price bound is accounted separately from actual invoice',row.status=='priced_upper_bound' and row.usage['actual_cost_cents'] is None and db.get(Account,'global').spent==state[0]+24)
  evidence.write_text(json.dumps({'provider_request_id':'qa-priced-request','actual_usd_cents':20,'billing_record_id':'qa-only-synthetic-record','verified_by':'QA only not actual billing'}))
  reconcile(db,ident,20,evidence)
  check('invoice delta uses charged24 bound rather than original100',db.get(Account,'global').spent==state[0]+20 and db.get(Tenant,t.id).spent==state[2]+20 and db.get(Reservation,ident).usage['actual_cost_cents']==20)
  try:reconcile(db,ident,20,evidence);rejected=False
  except ValueError:db.rollback();rejected=True
  check('priced invoice cannot release delta twice',rejected and db.get(Account,'global').spent==state[0]+20)
 finally:
  db.rollback();a=db.get(Account,'global');t=db.get(Tenant,'mein-kuechenexperte');a.spent,a.reserved,t.spent,t.reserved,t.enabled,a.budget=state;db.delete(db.get(Reservation,ident));db.commit();evidence.unlink(missing_ok=True)
print('PASS',len(checks),'independent billing-logic checks; synthetic evidence; zero real costs established')
for x in checks:print('PASS',x)
