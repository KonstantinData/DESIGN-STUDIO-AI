"""CLI safety tests: isolated HTTP transport; no provider network access."""
import json
from types import SimpleNamespace
import httpx
import pytest
from app import acceptance as cli


def inputs(tmp_path, monkeypatch):
    monkeypatch.setenv('STUDIO_OPENAI_API_KEY', 'private-key')
    cases = {s: {'prompt': 'Kueche mit Insel', 'material_instruction': 'Fronten in Eiche', 'layout_instruction': 'Insel mit Stauraum'} for s in cli.SOURCES}
    (tmp_path / 'input.png').write_bytes(b'private-photo')
    for s in ('photo', 'floorplan'):
        cases[s]['source_file'] = 'input.png'
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'base_url': 'https://studio.example', 'cases': cases}))
    gate = tmp_path / 'gate.json'
    gate.write_text(json.dumps({k: True for k in ('hard_limit_enforced', 'project_key_binding_verified', 'kill_switch_tested', 'pricing_verified')} | {'project_name': 'Design-Studio-AI', 'binding_type': 'operator_attestation', 'run_budget_cents': 500, 'verified_by': 'operator', 'verified_at': '2026-10-18T12:00:00Z'}))
    token = tmp_path / 'token'; token.write_text('real-turnstile-token')
    return manifest, gate, token


class DB:
    def __init__(self, budget=500, spent=0, reserved=0):
        self.account = SimpleNamespace(budget=budget, spent=spent, reserved=reserved)
        self.tenant = SimpleNamespace(id='tenant', enabled=True, budget=budget, spent=spent, reserved=reserved)
    def get(self, cls, key, **kw):
        return self.account if cls is cli.Account else self.tenant if cls is cli.Tenant else None
    def scalar(self, query):
        return self.tenant


@pytest.mark.parametrize('url', ['http://studio.example', 'https://secret@studio.example', 'https://studio.example/path', 'https://studio.example?token=secret'])
def test_rejects_insecure_or_secret_origins(tmp_path, monkeypatch, url):
    path, _, _ = inputs(tmp_path, monkeypatch)
    value = json.loads(path.read_text()); value['base_url'] = url; path.write_text(json.dumps(value))
    with pytest.raises(ValueError): cli.load_manifest(path)


def test_exact_sources_and_private_files(tmp_path, monkeypatch):
    path, _, _ = inputs(tmp_path, monkeypatch)
    assert set(cli.load_manifest(path)['cases']) == set(cli.SOURCES)
    value = json.loads(path.read_text()); del value['cases']['photo']; path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='Exactly'): cli.load_manifest(path)


@pytest.mark.parametrize('budget,spent,reserved', [(501, 0, 0), (500, 400, 100), (500, -1, 0), (0, 0, 0)])
def test_persisted_budget_includes_inflight(budget, spent, reserved):
    with pytest.raises(ValueError): cli.budget_check(DB(budget, spent, reserved), 'studio.example')


def test_key_binding_required(tmp_path, monkeypatch):
    _, path, _ = inputs(tmp_path, monkeypatch)
    assert cli.verify_gate(path)['run_budget_cents'] == 500
    value = json.loads(path.read_text()); value['project_name'] = 'Other'; path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='binding'): cli.verify_gate(path)
    monkeypatch.delenv('STUDIO_OPENAI_API_KEY')
    with pytest.raises(ValueError, match='server-side'): cli.verify_gate(path)


def test_state_private_audit_omits_secrets_and_cost_not_invented(tmp_path):
    path = tmp_path / 'state.json'; cli.private_write(path, {'cookie': 'secret'})
    assert path.stat().st_mode & 0o777 == 0o600
    report = cli.audit(DB(), {'cases': {'text': {'cookie': 'secret'}}})
    assert 'secret' not in json.dumps(report)
    assert report['actual_cost_cents'] is None and report['status'] == 'BLOCKED'


def test_regular_api_contract_and_secure_session(tmp_path, monkeypatch):
    path, gate, token = inputs(tmp_path, monkeypatch)
    manifest = cli.load_manifest(path); seen = []
    def request(req):
        seen.append(req.url.path)
        if req.url.path == '/api/config': return httpx.Response(200, json={'generation_ready': True})
        if req.url.path == '/api/session':
            return httpx.Response(200, json={'id': 'session1', 'csrf_token': 'csrf'}, headers={'set-cookie': '__Host-studio=session-secret; Secure; HttpOnly; Path=/'})
        assert req.url.path == '/api/studios'
        assert req.headers['origin'] == manifest['base_url']
        assert req.headers['x-csrf-token'] == 'csrf'
        assert req.headers['idempotency-key'] == 'acceptance-text-initial'
        assert 'session-secret' in req.headers['cookie']
        assert b'real-turnstile-token' in req.content
        return httpx.Response(202, json={'id': 'studio1'})
    state = {}; snapshots = []
    cli.execute_step(DB(), manifest, state, 'text.initial', token, gate, lambda s: snapshots.append(json.loads(json.dumps(s))), transport=httpx.MockTransport(request))
    assert state['cases']['text']['studio_id'] == 'studio1'
    assert snapshots[0]['cases']['text']['session_id'] == 'session1'
    assert len(seen) == 3 and 'real-turnstile-token' not in json.dumps(state)
    with pytest.raises(ValueError, match='already submitted'):
        cli.execute_step(DB(), manifest, state, 'text.initial', token, gate, lambda s: None)


def test_not_ready_submits_nothing(tmp_path, monkeypatch):
    path, gate, token = inputs(tmp_path, monkeypatch); seen = []
    def request(req):
        seen.append(req.url.path); return httpx.Response(200, json={'generation_ready': False})
    with pytest.raises(ValueError, match='readiness'):
        cli.execute_step(DB(), cli.load_manifest(path), {}, 'text.initial', token, gate, lambda s: None, transport=httpx.MockTransport(request))
    assert seen == ['/api/config']


@pytest.mark.parametrize('action', ['material', 'layout'])
def test_both_changes_independently_start_from_original_a(tmp_path, monkeypatch, action):
    path, gate, token = inputs(tmp_path, monkeypatch)
    class RevisionDB(DB):
        def get(self, cls, key, **kw):
            if cls is cli.Studio:
                return SimpleNamespace(session_id='session1', tenant_id='tenant')
            return super().get(cls, key, **kw)
        def scalars(self, query):
            return SimpleNamespace(all=lambda: [SimpleNamespace(status='completed')])
        def scalar(self, query):
            if 'revisions' in str(query):
                assert 'revisions.kind' in str(query) and 'revisions.concept' in str(query)
                return SimpleNamespace(id='original-A', profile={})
            return self.tenant
    def request(req):
        if req.url.path == '/api/config': return httpx.Response(200, json={'generation_ready': True})
        if req.url.path == '/api/session': return httpx.Response(200, json={'id': 'session1', 'csrf_token': 'csrf'})
        payload = json.loads(req.content)
        assert payload['base_revision_id'] == 'original-A'
        assert payload['kind'] == action and payload['concept'] == 'A'
        return httpx.Response(202, json={'job_id': 'revision-job'})
    state = {'cases': {'text': {'session_id': 'session1', 'cookie': 'session-secret', 'studio_id': 'studio1', 'submitted': ['initial']}}}
    cli.execute_step(RevisionDB(), cli.load_manifest(path), state, 'text.' + action, token, gate, lambda s: None, transport=httpx.MockTransport(request))
    assert action in state['cases']['text']['submitted']
