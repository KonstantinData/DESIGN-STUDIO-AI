#!/usr/bin/env python3
"""Disposable recovery acceptance. Never reads production .env or contacts AI providers.

Creates dedicated Compose volumes/networks, cryptographic test-only keys and three
private generated-media fixtures. Removes only its own projects and temporary files.
"""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import types
import tarfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
IMAGE = 'design-studio-ai-backend'


def run(command, env=None, **kwargs):
    return subprocess.run(command, env=env, check=True, **kwargs)


def verify_cryptography(base, home, encrypted, recipient):
    spec = importlib.util.spec_from_file_location('recovery_backup', ROOT / 'scripts/backup.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    args = types.SimpleNamespace(gpg_home=home, maximum_archive_bytes=128 * 1024 ** 2)
    def reject(path, name):
        stage = base / name; stage.mkdir(mode=0o700)
        try:
            module.unseal(args, path, stage, 'backup')
        except RuntimeError:
            return
        raise AssertionError('Unsafe archive accepted: ' + name)
    valid = base / 'verified-crypto'; valid.mkdir(mode=0o700)
    module.unseal(args, encrypted, valid, 'backup')
    raw = bytearray(encrypted.read_bytes()); raw[-15] ^= 0x10
    tampered = base / 'tampered.gpg'; tampered.write_bytes(raw)
    reject(tampered, 'tamper-rejected')
    wrong = base / 'wrong-key'; wrong.mkdir(mode=0o700)
    run(['gpg', '--homedir', str(wrong), '--batch', '--pinentry-mode', 'loopback', '--passphrase', '', '--quick-gen-key', 'Different disposable decryption key', 'rsa2048', 'encr', '1d'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    args.gpg_home = wrong; reject(encrypted, 'wrong-key-rejected'); args.gpg_home = home
    subprocess.run(['gpgconf', '--homedir', str(wrong), '--kill', 'gpg-agent'], check=True)
    args.maximum_archive_bytes = 64; reject(encrypted, 'size-rejected'); args.maximum_archive_bytes = 128 * 1024 ** 2
    unsafe = base / 'unsafe.tar'
    with tarfile.open(unsafe, 'w') as archive:
        member = tarfile.TarInfo('../escape'); member.size = 0; archive.addfile(member)
    unsafe_encrypted = base / 'unsafe.gpg'
    with unsafe_encrypted.open('xb') as out:
        run(['gpg', '--homedir', str(home), '--batch', '--cipher-algo', 'AES256', '--encrypt', '--recipient', recipient, '--output', '-', str(unsafe)], stdout=out)
    reject(unsafe_encrypted, 'traversal-rejected')
    assert not (base / 'escape').exists()
    print('PASS authenticated GPG roundtrip; tampered ciphertext, wrong key, oversized input and traversal archive rejected.')


def main():
    with tempfile.TemporaryDirectory(prefix='studio-recovery-') as temp:
        base = Path(temp); base.chmod(0o700)
        for name in ('keys', 'scratch', 'archive'):
            (base / name).mkdir(mode=0o700)
        home = base / 'keys'
        run(['gpg', '--homedir', str(home), '--batch', '--pinentry-mode', 'loopback', '--passphrase', '',
             '--quick-gen-key', 'Disposable recovery acceptance', 'rsa2048', 'encr', '1d'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        listing = subprocess.check_output(['gpg', '--homedir', str(home), '--with-colons', '--list-keys'], stderr=subprocess.DEVNULL).decode()
        recipient = next(line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:'))
        override = base / 'isolated.yaml'
        override.write_text('''services:
  backend:
    image: design-studio-ai-backend
    networks: !override [private]
  migrate:
    image: design-studio-ai-migrate
    networks: !override [private]
  worker:
    image: design-studio-ai-worker
    networks: !override [private]
  web:
    ports: !reset []
    networks: !override [edge]
''')
        # An explicit --env-file disables accidental production .env loading;
        # subprocess environments also remove names that could override safe values.
        envfile = base / 'isolated.env'
        envfile.write_text('\n'.join([
            'POSTGRES_PASSWORD=' + secrets.token_hex(32),
            'POSTGRES_ADMIN_PASSWORD=' + secrets.token_hex(32),
            'TENANTS_JSON=\'[{"host":"recovery.invalid","slug":"recovery","brand":"Recovery acceptance","enabled":false,"budget_cents":0}]\'',
            'SITE_ADDRESSES=http://recovery.invalid:8080',
            'PROVIDER_ENABLED=false', 'BUDGET_APPROVED=false', 'GLOBAL_KILL_SWITCH=true',
            'GLOBAL_BUDGET_CENTS=0', 'STUDIO_OPENAI_API_KEY=', 'TURNSTILE_SECRET=',
            'HARD_LIMIT_VERIFIED_AT=', 'RATE_LIMIT_SECRET=',
        ]) + '\n'); envfile.chmod(0o600)
        env = dict(os.environ)
        for name in ('POSTGRES_PASSWORD', 'POSTGRES_ADMIN_PASSWORD', 'TENANTS_JSON', 'PROVIDER_ENABLED', 'BUDGET_APPROVED',
                     'GLOBAL_KILL_SWITCH', 'STUDIO_OPENAI_API_KEY', 'TURNSTILE_SECRET', 'HARD_LIMIT_VERIFIED_AT', 'RATE_LIMIT_SECRET'):
            env.pop(name, None)
        env['COMPOSE_FILE'] = str(ROOT / 'compose.yaml') + ':' + str(override)
        env['COMPOSE_ENV_FILES'] = str(envfile)
        env['DOCKER_CONFIG'] = str(ROOT / '.runtime/docker')
        suffix = uuid.uuid4().hex[:10]
        source = 'studio-recovery-source-' + suffix; target = 'studio-recovery-target-' + suffix
        projects = []

        def compose(project, *args, **kwargs):
            return run(['docker', 'compose', *args], env=dict(env, COMPOSE_PROJECT_NAME=project), cwd=ROOT, **kwargs)

        def python(project, code):
            return compose(project, 'run', '--rm', '--no-deps', '-T', '--entrypoint', 'python', 'backend', '-c', code)

        def operator(project, *args):
            return run(['python3', str(ROOT / 'scripts/backup.py'), '--gpg-home', str(home), '--scratch-dir', str(base / 'scratch'), *args],
                       env=dict(env, COMPOSE_PROJECT_NAME=project), cwd=ROOT)

        try:
            projects.append(source)
            compose(source, 'up', '-d', '--wait', '--wait-timeout', '60', 'db')
            compose(source, 'run', '--rm', '--no-deps', '-T', '--entrypoint', 'alembic', 'backend', 'upgrade', 'head')
            python(source, '''import io,json,os
from datetime import timedelta
from pathlib import Path
from PIL import Image
from app.db import factory,Session,now
from app.security import seed,store_media,digest
assert os.getenv('PROVIDER_ENABLED')=='false'
with factory()() as db:
 seed(db)
 for n in range(3):
  session=Session(id=['00000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000003'][n],tenant_id='recovery',token_hash=digest('recovery-fixture-'+str(n)),expires_at=now()+timedelta(days=-1 if n==2 else 10))
  db.add(session);db.flush(); out=io.BytesIO();Image.new('RGB',(32,32),(n*60,40,60)).save(out,'PNG');store_media(db,'recovery',session.id,out.getvalue())
 db.commit()
 # Control metadata must never be restored from snapshots.
 Path('/var/lib/studio/private/.rate-limit-key').write_text('fixture-only-not-a-production-key')
 print('PASS three private generated-media/session fixtures persisted; no provider called.')
''')
            operator(source, 'backup', '--recipient', recipient, '--output', str(base / 'archive/snapshot.gpg'))
            verify_cryptography(base, home, base / 'archive/snapshot.gpg', recipient)
            python(source, '''from app.db import factory,Session
from app.privacy import erase
with factory()() as db:
 erase(db,db.get(Session,'00000000-0000-4000-8000-000000000002'))
print('PASS post-snapshot deletion durably recorded independently.')
''')
            operator(source, 'export-deletions', '--quiesce-source', '--recipient', recipient,
                     '--output', str(base / 'archive/current-deletions.gpg'))
            projects.append(target)
            compose(target, 'up', '-d', '--wait', '--wait-timeout', '60', 'db')
            # New current target key proves the old snapshot key cannot supersede it.
            python(target, "from pathlib import Path; p=Path('/var/lib/studio/private/.rate-limit-key'); p.write_text('new-target-current-key-at-least-32-bytes'); p.chmod(0o600)")
            operator(target, 'restore', '--confirm-isolated', '--input', str(base / 'archive/snapshot.gpg'),
                     '--current-deletion-ledger', str(base / 'archive/current-deletions.gpg'))
            python(target, '''import os,stat
from pathlib import Path
from sqlalchemy import select
from app.db import factory,Session,Media
root=Path('/var/lib/studio/private')
with factory()() as db:
 sessions=list(db.scalars(select(Session)))
 assert len(sessions)==1 and sessions[0].id=='00000000-0000-4000-8000-000000000001'
 media=list(db.scalars(select(Media))); assert len(media)==1
 p=Path(media[0].path);assert p.is_file() and p.stat().st_uid==10001 and stat.S_IMODE(p.stat().st_mode)==0o600
 assert [q for q in root.iterdir() if q.is_file() and not q.name.startswith('.') and q.name!='STOP_GENERATION']==[p]
 assert (root/'.rate-limit-key').read_text()=='new-target-current-key-at-least-32-bytes'
 assert (root/'STOP_GENERATION').is_file()
print('PASS restored active session/private media, UID10001 mode0600; post-snapshot deleted and expired sessions/media absent; current HMAC key preserved; STOP enforced.')
''')
            # A second restore must refuse this occupied target rather than overwrite.
            bad = subprocess.run(['python3', str(ROOT / 'scripts/backup.py'), '--gpg-home', str(home), '--scratch-dir', str(base / 'scratch'),
                       'restore', '--confirm-isolated', '--input', str(base / 'archive/snapshot.gpg'), '--current-deletion-ledger', str(base / 'archive/current-deletions.gpg')],
                      env=dict(env, COMPOSE_PROJECT_NAME=target), cwd=ROOT, check=False)
            assert bad.returncode != 0, 'Occupied target overwrite was accepted'
            print('PASS occupied restore target rejected.')
            print('PASS isolated full database + private-media encrypted recovery acceptance. No live application database or volume changed.')
        finally:
            for project in reversed(projects):
                compose(project, 'down', '--volumes', '--remove-orphans')
            subprocess.run(['gpgconf', '--homedir', str(home), '--kill', 'gpg-agent'])


if __name__ == '__main__':
    main()
