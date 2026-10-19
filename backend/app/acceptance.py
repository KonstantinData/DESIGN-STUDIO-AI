"""Operator CLI for the real 15-image acceptance run; never a bot bypass.

Default: validate private manifest and emit a redacted durable audit. A paid step
requires --execute --step SOURCE.ACTION --token-file FILE --gate-file FILE.
Each invocation submits at most one generation request through the ordinary API. Re-run without execute
until durable jobs finish; supply a new genuine hostname-bound Turnstile token
for every new action. Keep manifest, state, tokens and evidence outside Git.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from .paths import checkout_root

from .db import Account, Job, Reservation, Revision, Studio, Tenant, factory

SOURCES = ('text', 'photo', 'floorplan')
ACTIONS = ('initial', 'material', 'layout')
MAX_FILE = 12 * 1024 * 1024


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('JSON input exceeds bounded size')
    return json.loads(path.read_text())


def private_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_manifest(path):
    path = Path(path)
    manifest = read_json(path)
    if set(manifest) != {'base_url', 'cases'}:
        raise ValueError('Manifest requires base_url and cases only')
    url = urlsplit(manifest['base_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise ValueError('Use a direct HTTPS tenant origin without credentials/path/query')
    cases = manifest['cases']
    if not isinstance(cases, dict) or set(cases) != set(SOURCES):
        raise ValueError('Exactly text/photo/floorplan cases required (15 images)')
    for source, case in cases.items():
        allowed = {'prompt', 'material_instruction', 'layout_instruction'} | ({'source_file'} if source != 'text' else set())
        if set(case) != allowed:
            raise ValueError('Case fields do not match source contract')
        for field, limit in [('prompt', 4000), ('material_instruction', 2000), ('layout_instruction', 2000)]:
            value = case[field]
            minimum = 0 if field == 'prompt' and source != 'text' else 3
            if not isinstance(value, str) or not minimum <= len(value.strip()) <= limit:
                raise ValueError('Invalid prompt/instruction length')
        if source != 'text':
            media = (path.parent / case['source_file']).resolve()
            if not media.is_file() or not 0 < media.stat().st_size <= MAX_FILE:
                raise ValueError('Private source file absent or over 12 MiB')
            case['source_file'] = str(media)
    manifest['base_url'] = manifest['base_url'].rstrip('/')
    return manifest


def budget_check(db, host):
    account = db.get(Account, 'global', populate_existing=True)
    tenant = db.scalar(select(Tenant).where(Tenant.host == host).execution_options(populate_existing=True))
    if not account or not tenant or not tenant.enabled:
        raise ValueError('Matching enabled tenant and global account required')
    for row in (account, tenant):
        if not 0 < row.budget <= 500 or min(row.spent, row.reserved) < 0 or row.spent + row.reserved >= row.budget:
            raise ValueError('Persisted global/tenant cap must be <=500 cents with remaining headroom')
    return tenant.id


def verify_gate(path):
    gate = read_json(path)
    required = ('hard_limit_enforced', 'project_key_binding_verified', 'kill_switch_tested', 'pricing_verified')
    key = os.getenv('STUDIO_OPENAI_API_KEY', '')
    if not key or any(gate.get(k) is not True for k in required):
        raise ValueError('Verified operator gates and server-side STUDIO key required')
    if gate.get('project_name') != 'Design-Studio-AI' or gate.get('binding_type') != 'operator_attestation':
        raise ValueError('Explicit operator attestation for Design-Studio-AI project binding required')
    if type(gate.get('run_budget_cents')) is not int or not 0 < gate['run_budget_cents'] <= 500:
        raise ValueError('Explicit run budget must be at most 500 cents')
    if not gate.get('verified_by') or not gate.get('verified_at'):
        raise ValueError('Identifiable dated operator verification required')
    return gate


def audit(db, state):
    result = {'status': 'BLOCKED', 'expected_images': 15, 'actual_images': 0,
              'human_acceptance': 'required', 'cases': [], 'truncated': False}
    for source in SOURCES:
        entry = state.get('cases', {}).get(source, {})
        studio = db.get(Studio, entry.get('studio_id', ''))
        item = {'source': source, 'status': studio.status if studio else 'not_started', 'revisions': [], 'attempts': []}
        if studio:
            if studio.session_id != entry.get('session_id'):
                raise ValueError('State does not match durable session ownership')
            revisions = db.scalars(select(Revision).where(Revision.studio_id == studio.id).order_by(Revision.created_at).limit(257)).all()
            jobs = db.scalars(select(Job).where(Job.studio_id == studio.id).order_by(Job.created_at).limit(257)).all()
            if len(revisions) > 256 or len(jobs) > 256:
                result['truncated'] = True
            revisions, jobs = revisions[:256], jobs[:256]
            for rev in revisions:
                item['revisions'].append({'id': rev.id, 'concept': rev.concept, 'kind': rev.kind,
                    'base_revision_id': rev.profile.get('base_revision_id'), 'room_version': rev.room_version,
                    'critical_error': bool(rev.profile.get('review', {}).get('critical_error')),
                    'human_acceptance': 'required'})
            result['actual_images'] += len(revisions)
            for job in jobs:
                reservations = db.scalars(select(Reservation).where(Reservation.job_id == job.id).order_by(Reservation.created_at).limit(257)).all()
                if len(reservations) > 256:
                    result['truncated'] = True
                for reservation in reservations[:256]:
                    usage = reservation.usage or {}
                    item['attempts'].append({'job_id': job.id, 'job_status': job.status,
                        'operation': job.operation, 'reservation_id': reservation.id,
                        'reserved_ceiling_cents': reservation.amount, 'accounted_upper_bound_cents':usage.get('accounted_upper_bound_cents',reservation.amount),'pricing_reference':usage.get('pricing_reference'),'accounting_status': reservation.status,
                        'actual_cost_cents': usage.get('actual_cost_cents') if reservation.status in ('invoice_reconciled','released_no_call') else None,
                        'started_at': reservation.created_at.isoformat(),
                        'duration_seconds': usage.get('duration_seconds'),
                        'outcome': usage.get('outcome', 'recorded')})
            item['jobs'] = [{'id': job.id, 'status': job.status, 'operation': job.operation} for job in jobs]
        result['cases'].append(item)
    amounts = [x['actual_cost_cents'] for c in result['cases'] for x in c['attempts']]
    result['accounted_upper_bound_cents'] = sum(x['accounted_upper_bound_cents'] for c in result['cases'] for x in c['attempts']) if not result['truncated'] else None
    result['actual_cost_cents'] = sum(amounts) if amounts and not result['truncated'] and all(type(x) is int for x in amounts) else None
    return result


def execute_step(db, manifest, state, step, token_file, gate_file, save_state, transport=None):
    source, action = step.split('.')
    gate = verify_gate(gate_file)
    host = urlsplit(manifest['base_url']).hostname
    tenant_id = budget_check(db, host)
    account = db.get(Account, 'global')
    tenant = db.get(Tenant, tenant_id)
    if any(row.budget > gate['run_budget_cents'] for row in (account, tenant)):
        raise ValueError('Persisted cap exceeds explicitly approved run budget')
    if state.get('base_url', manifest['base_url']) != manifest['base_url']:
        raise ValueError('State origin does not match manifest')
    state['base_url'] = manifest['base_url']
    case_state = state.setdefault('cases', {}).setdefault(source, {})
    case = manifest['cases'][source]
    if action != 'initial' and not case_state.get('studio_id'):
        raise ValueError('Initial studio required before revisions')
    if action in case_state.get('submitted', []):
        raise ValueError('Step already submitted; inspect durable audit instead of repeating')
    token_path = Path(token_file)
    if token_path.stat().st_size > 4096:
        raise ValueError('Challenge token exceeds limit')
    token = token_path.read_text().strip()
    if not token:
        raise ValueError('Supply a fresh genuine Turnstile token for this request')
    with httpx.Client(base_url=manifest['base_url'], timeout=60, follow_redirects=False, transport=transport) as client:
        config = client.get('/api/config')
        config.raise_for_status()
        if config.json().get('generation_ready') is not True:
            raise ValueError('Deployment readiness blocks generation')
        if case_state.get('cookie'):
            client.cookies.set('__Host-studio', case_state['cookie'], domain=host, path='/')
        session = client.get('/api/session')
        session.raise_for_status()
        session = session.json()
        if case_state.get('session_id', session['id']) != session['id']:
            raise ValueError('Saved session expired; refusing a new paid start')
        cookie = client.cookies.get('__Host-studio')
        if not cookie:
            raise ValueError('Secure session cookie was not established')
        case_state.update(session_id=session['id'], cookie=cookie)
        save_state(state)  # persist before request, so uncertain HTTP outcomes can be investigated
        headers = {'Origin': manifest['base_url'], 'X-CSRF-Token': session['csrf_token'],
                   'Idempotency-Key': 'acceptance-' + source + '-' + action}
        if action == 'initial':
            if case_state.get('studio_id'):
                raise ValueError('Initial studio already exists')
            data = {'prompt': case['prompt'], 'source_kind': source, 'challenge_token': token}
            if source == 'text':
                response = client.post('/api/studios', data=data, headers=headers)
            else:
                with Path(case['source_file']).open('rb') as stream:
                    response = client.post('/api/studios', data=data, files={'file': ('source', stream, 'application/octet-stream')}, headers=headers)
        else:
            studio_id = case_state['studio_id']
            studio = db.get(Studio, studio_id, populate_existing=True)
            if not studio or studio.session_id != session['id'] or studio.tenant_id != tenant_id:
                raise ValueError('Studio/session/tenant mismatch')
            jobs = db.scalars(select(Job).where(Job.studio_id == studio_id)).all()
            if any(job.status in ('queued', 'running') for job in jobs):
                raise ValueError('Wait until durable jobs are terminal')
            original = db.scalar(select(Revision).where(Revision.studio_id == studio_id, Revision.concept == 'A', Revision.kind == 'initial').order_by(Revision.created_at))
            if not original or original.profile.get('review', {}).get('critical_error'):
                raise ValueError('Noncritical original A required')
            response = client.post('/api/studios/' + studio_id + '/revisions', headers=headers,
                json={'concept': 'A', 'kind': action, 'instruction': case[action + '_instruction'],
                      'base_revision_id': original.id, 'challenge_token': token})
        response.raise_for_status()
        if action == 'initial':
            case_state['studio_id'] = response.json()['id']
        case_state.setdefault('submitted', []).append(action)
        save_state(state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--state', type=Path, required=True, help='Private resumable session state outside Git')
    parser.add_argument('--report', type=Path, required=True, help='Redacted audit output outside Git')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--step', choices=[s + '.' + a for s in SOURCES for a in ACTIONS])
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--gate-file', type=Path)
    args = parser.parse_args(argv)
    try:
        checkout = checkout_root()
        outputs = [args.state.resolve(), args.report.resolve()]
        inputs = [p.resolve() for p in (args.manifest, args.token_file, args.gate_file) if p]
        if len(set(outputs + inputs)) != len(outputs + inputs):
            raise ValueError('State, report and input paths must be distinct')
        if any(path.is_relative_to(checkout) for path in outputs):
            raise ValueError('Private acceptance state and reports must be outside the checkout')
        manifest = load_manifest(args.manifest)
        state = read_json(args.state) if args.state.exists() else {}
        with factory()() as db:
            if args.execute:
                if not all((args.step, args.token_file, args.gate_file)):
                    raise ValueError('--execute requires --step, --token-file and --gate-file')
                execute_step(db, manifest, state, args.step, args.token_file, args.gate_file,
                             lambda value: private_write(args.state, value))
            private_write(args.report, audit(db, state))
    except (ValueError, OSError, httpx.HTTPError, KeyError, SQLAlchemyError) as exc:
        # HTTP exceptions can contain private URLs/body; expose only class, never raw text.
        parser.exit(2, 'Acceptance blocked (' + type(exc).__name__ + '); inspect private configuration and durable audit.\n')
    print('Audit written; human image acceptance and verified billing remain required.')


if __name__ == '__main__':
    main()
