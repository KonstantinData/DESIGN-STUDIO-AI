#!/usr/bin/env python3
"""Operator-only aggregate readiness. No tokens, prompts, media paths or IPs."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('studio_backup', Path(__file__).with_name('backup.py'))
backup = importlib.util.module_from_spec(spec); spec.loader.exec_module(backup)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--require-generation', action='store_true')
args = parser.parse_args()
try:
    result = backup.compose('ps', '--format', 'json', capture_output=True, text=True)
    containers = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    expected = {'db', 'backend', 'worker', 'web'}
    health = {}
    for item in containers:
        service = item['Service']
        if service in expected:
            health[service] = health.get(service, True) and item.get('Health') == 'healthy' and item.get('State') == 'running'
    code = '''import json,os
from sqlalchemy import select,func
from app.db import factory,Session,Job,now
from app.security import data_dir,ready
from app.db import Tenant,Account,Reservation
from datetime import timedelta
with factory()() as db:
 overdue=db.scalar(select(func.count()).select_from(Session).where(Session.expires_at<now()-timedelta(seconds=120)))
 stale=db.scalar(select(func.count()).select_from(Job).where(Job.status=='running',Job.started_at<now()-timedelta(minutes=30)))
 queued=db.scalar(select(func.count()).select_from(Job).where(Job.status=='queued'))
 tenants=list(db.scalars(select(Tenant)))
 active=[t for t in tenants if t.enabled]
 enabled=bool(active) and all(ready(t)[0] for t in active)
 account=db.get(Account,'global')
 reserved=account.reserved if account else None
 ceiling=account.spent if account else None
 print(json.dumps({'overdue_sessions':overdue,'stale_running_jobs':stale,'queued_jobs':queued,'generation_ready_for_enabled_tenants':enabled,'private_storage_writable':os.access(data_dir(),os.W_OK|os.X_OK),'reserved_cents':reserved,'conservative_charged_cents':ceiling}))
'''
    stats = json.loads(backup.compose('exec', '-T', 'backend', 'python', '-c', code,
                                     capture_output=True, text=True).stdout)
    healthy = set(health) == expected and all(health.values())
    healthy = healthy and not stats['overdue_sessions'] and not stats['stale_running_jobs'] and stats['private_storage_writable']
    output = {'infrastructure_ready': healthy, 'services': health, **stats}
    print(json.dumps(output, sort_keys=True))
    raise SystemExit(0 if healthy and (not args.require_generation or stats['generation_ready_for_enabled_tenants']) else 1)
except Exception:
    print(json.dumps({'infrastructure_ready': False, 'error': 'readiness_check_failed'}))
    sys.exit(1)
