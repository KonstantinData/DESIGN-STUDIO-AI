"""Operator-only invoice reconciliation. Never infers actual billed cost from tokens.

python -m app.reconcile RESERVATION_ID ACTUAL_CENTS /private/evidence.json
Evidence must be a provider billing/export record, independently verified by operator.
Private evidence content is never stored/logged; only its SHA-256 audit reference.
"""
import argparse,hashlib,json
from pathlib import Path
from sqlalchemy import select
from .db import factory,Reservation,Account,Tenant,now

def reconcile(db,ident,actual,evidence):
    if actual<0: raise ValueError('Actual cents must be nonnegative, rounded upward')
    raw=Path(evidence).read_bytes()
    record=json.loads(raw)
    required={'provider_request_id','actual_usd_cents','billing_record_id','verified_by'}
    if not required<=record.keys() or not all(record[k] for k in ('provider_request_id','billing_record_id','verified_by')) or record['actual_usd_cents']!=actual: raise ValueError('Verified billing evidence with matching amount required')
    tenant_id=db.scalar(select(Reservation.tenant_id).where(Reservation.id==ident))
    if tenant_id is None: raise ValueError('Reservation not found')
    account=db.scalar(select(Account).where(Account.id=='global').with_for_update().execution_options(populate_existing=True))
    tenant=db.scalar(select(Tenant).where(Tenant.id==tenant_id).with_for_update().execution_options(populate_existing=True))
    row=db.scalar(select(Reservation).where(Reservation.id==ident).with_for_update().execution_options(populate_existing=True))
    if not row or row.status not in ('ceiling_charged','priced_upper_bound','ceiling_exceeded'): raise ValueError('Reservation is not awaiting reconciliation')
    usage=row.usage or {}
    if not usage.get('provider_request_id') or usage['provider_request_id']!=record['provider_request_id']: raise ValueError('Provider request ID must match recorded invocation; unknown outcomes need separate provider investigation')
    prior_bound=usage.get('accounted_upper_bound_cents',row.amount)
    delta=actual-prior_bound
    for item in (account,tenant): item.spent+=delta
    if delta>0:
        tenant.enabled=False
        # Halt globally by setting remaining exposure cap to current incurred+reserved.
        account.budget=min(account.budget,account.spent+account.reserved)
    row.status='invoice_reconciled'
    row.usage={**usage,'prior_accounted_upper_bound_cents':prior_bound,'accounted_upper_bound_cents':actual,'actual_cost_cents':actual,'reconciled_at':now().isoformat(),'billing_record_id':record['billing_record_id'],'verified_by':record['verified_by'],'evidence_sha256':hashlib.sha256(raw).hexdigest(),'ceiling_exceeded':delta>0}
    db.commit()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reservation_id');parser.add_argument('actual_cents',type=int);parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    with factory()() as db: reconcile(db,args.reservation_id,args.actual_cents,args.evidence)
    print('Reconciled verified billing record; no provider call made.')
if __name__=='__main__': main()
