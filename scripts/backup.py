#!/usr/bin/env python3
"""Encrypted, consistent Compose backups and isolated restore with mandatory deletion replay.

No credentials are accepted on the command line. GPG key trust and encrypted/private
scratch storage are operator prerequisites, not inferred from a successful backup.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MEDIA = '/var/lib/studio/private'
LEDGER = '/var/lib/studio/deletions'
WRITERS = ('web', 'backend', 'worker')


def fail(message):
    raise RuntimeError(message)


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def compose(*args, **kwargs):
    env = dict(os.environ)
    env.setdefault('DOCKER_CONFIG', str(ROOT / '.runtime/docker'))
    overlay = ROOT / '.runtime/compose.cloud.json'
    if overlay.exists():
        env.setdefault('COMPOSE_FILE', f'{ROOT / "compose.yaml"}:{overlay}')
    return run(['docker', 'compose', *args], cwd=ROOT, env=env, **kwargs)


def private_directory(value):
    path = Path(value).resolve(strict=True)
    if not path.is_dir() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        fail('Directory must be owned by this operator and deny all group/other access.')
    if path == ROOT or ROOT in path.parents:
        fail('Backup, keys and scratch directories must be outside the repository.')
    return path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as src:
        for block in iter(lambda: src.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


@contextmanager
def paused(resume=True):
    result = compose('ps', '--status', 'running', '--services', capture_output=True, text=True)
    services = [name for name in result.stdout.splitlines() if name in WRITERS]
    if services:
        compose('stop', '--timeout', '45', *services)
    try:
        yield
    finally:
        if services and resume:
            compose('start', '--wait', '--wait-timeout', '120', *services)


def volume_export(directory, output):
    code = "import sys,tarfile; t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|'); t.add(" + repr(directory) + ",arcname='.',recursive=True,filter=lambda m: None if m.name.split('/')[-1] in ('.rate-limit-key','STOP_GENERATION') else m); t.close()"
    with output.open('xb') as out:
        compose('run', '--rm', '--no-deps', '-T', '--entrypoint', 'python', 'backend', '-c', code, stdout=out)


def volume_import(archive, directory, maximum_bytes):
    # Reject links, devices and traversal before extraction; preserve only regular
    # files/directories. Imported ownership is the unprivileged application user.
    code = """import sys,tarfile,pathlib,os
root=pathlib.Path(sys.argv[1]); root.mkdir(parents=True,exist_ok=True)
if any(p.name not in ('.rate-limit-key','STOP_GENERATION') for p in root.iterdir()): raise RuntimeError('Restore target volume must contain no existing data')
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as t:
 count=0;total=0
 for m in t:
  count+=1;total+=m.size
  if count>100000 or total>int(sys.argv[2]) or m.sparse: raise RuntimeError('Media archive exceeds safe limits')
  p=pathlib.PurePosixPath(m.name)
  if p.is_absolute() or '..' in p.parts or not (m.isfile() or m.isdir()): raise RuntimeError('Unsafe archive member')
  if p.name in ('.rate-limit-key','STOP_GENERATION'): raise RuntimeError('Snapshot must not overwrite current control metadata')
  m.uid=os.getuid();m.gid=os.getgid();m.mode=0o700 if m.isdir() else 0o600
  t.extract(m,path=root,filter='data')
"""
    with archive.open('rb') as source:
        compose('run', '--rm', '--no-deps', '-T', '--entrypoint', 'python', 'backend', '-c', code, directory, str(maximum_bytes), stdin=source)


def seal(args, staging, kind, captured_at):
    recipient = args.recipient.replace(' ', '')
    if not re.fullmatch(r'[0-9A-Fa-f]{40}|[0-9A-Fa-f]{64}', recipient):
        fail('Use the independently verified full GPG recipient fingerprint.')
    output = Path(args.output).resolve()
    private_directory(output.parent)
    manifest = {'format': 1, 'kind': kind, 'created_at': captured_at, 'source_quiesced': kind == 'deletions',
                'media_directory': MEDIA, 'sha256': {p.name: digest(p) for p in staging.iterdir() if p.is_file()}}
    (staging / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True))
    bundle = staging / 'bundle.tar'
    with tarfile.open(bundle, 'w') as archive:
        for path in sorted(staging.iterdir()):
            if path != bundle:
                archive.add(path, arcname=path.name, recursive=False)
    if os.path.lexists(output):
        fail('Encrypted output already exists and will never be overwritten.')
    descriptor, temporary = tempfile.mkstemp(prefix='.studio-encrypted-', suffix='.pending', dir=output.parent)
    created = False
    try:
        with os.fdopen(descriptor, 'wb') as target:
            run(['gpg', '--homedir', str(args.gpg_home), '--batch', '--cipher-algo', 'AES256',
                 '--encrypt', '--recipient', recipient, '--output', '-', str(bundle)], stdout=target)
            target.flush(); os.fsync(target.fileno())
            if target.tell() == 0: fail('Encryption produced no output.')
        # Atomic exclusive publication: an interrupted writer leaves no seemingly
        # complete final backup, and concurrent writers cannot replace each other.
        os.link(temporary, output); created = True
        directory = os.open(output.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
    finally:
        Path(temporary).unlink(missing_ok=True)


def unseal(args, encrypted, staging, kind):
    bundle = staging / 'encrypted-payload.tar'
    encrypted = Path(encrypted)
    if encrypted.stat().st_size > args.maximum_archive_bytes:
        fail('Encrypted archive exceeds configured maximum size.')
    # Limit decrypted output before disk writes; never accept missing MDC/AEAD.
    with tempfile.TemporaryFile() as status, bundle.open('xb') as target:
        process = subprocess.Popen(['gpg', '--homedir', str(args.gpg_home), '--batch', '--status-fd', '2',
                                    '--decrypt', str(encrypted)], stdout=subprocess.PIPE, stderr=status)
        total = 0
        try:
            while block := process.stdout.read(1024 * 1024):
                total += len(block)
                if total > args.maximum_archive_bytes:
                    fail('Decrypted archive exceeds configured maximum size.')
                target.write(block)
            result = process.wait()
            status.seek(0); messages = status.read().decode(errors='replace')
            if result != 0 or '[GNUPG:] GOODMDC' not in messages or '[GNUPG:] DECRYPTION_OKAY' not in messages:
                fail('Authenticated decryption failed; key or archive integrity is invalid.')
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            process.stdout.close()
    allowed = {'manifest.json', 'database.dump', 'media.tar'} if kind == 'backup' else {'manifest.json', 'deletions.tar'}
    with tarfile.open(bundle, 'r:') as archive:
        members = []
        for member in archive:
            members.append(member)
            if len(members) > len(allowed) or member.size > args.maximum_archive_bytes:
                fail('Archive has excessive members or member size.')
        if sum(m.size for m in members) > args.maximum_archive_bytes:
            fail('Archive contents exceed total extraction limit.')
        if {m.name for m in members} != allowed or any(not m.isfile() or m.sparse for m in members) or len(members) != len(allowed):
            fail('Unexpected or unsafe backup contents.')
        archive.extractall(staging, members=members, filter='data')
    if (staging / 'manifest.json').stat().st_size > 65536:
        fail('Manifest exceeds maximum size.')
    manifest = json.loads((staging / 'manifest.json').read_text())
    if manifest.get('format') != 1 or manifest.get('kind') != kind or manifest.get('media_directory') != MEDIA:
        fail('Unsupported archive format or media path.')
    if set(manifest.get('sha256', {})) != allowed - {'manifest.json'}:
        fail('Manifest is incomplete.')
    for name, expected in manifest['sha256'].items():
        if digest(staging / name) != expected:
            fail('Archive checksum mismatch.')
    return manifest


def backup(args, staging):
    with paused():
        with (staging / 'database.dump').open('xb') as target:
            compose('exec', '-T', 'db', 'pg_dump', '-U', 'studio_app', '-Fc', 'studio', stdout=target)
        volume_export(MEDIA, staging / 'media.tar')
        captured_at = datetime.now(timezone.utc).isoformat()
    seal(args, staging, 'backup', captured_at)
    print('PASS: consistent database and media encrypted; previous running services restored.')


def export_deletions(args, staging):
    if not args.quiesce_source:
        fail('Deletion export requires --quiesce-source; writers remain stopped for safe disaster cutover.')
    with paused(resume=False):
        volume_export(LEDGER, staging / 'deletions.tar')
        captured_at = datetime.now(timezone.utc).isoformat()
    seal(args, staging, 'deletions', captured_at)
    print('PASS: current deletion ledger encrypted. SOURCE WRITERS REMAIN STOPPED for cutover.')


def restore(args, staging):
    if not 0 < args.maximum_ledger_age_seconds <= 1800 or not 0 < args.maximum_archive_bytes <= 1024 ** 4:
        fail('Restore limits must be positive; ledger max 1800 seconds, archive max 1 TiB.')
    if not args.confirm_isolated:
        fail('Restore requires explicit --confirm-isolated and a separate empty Compose project.')
    if not os.environ.get('COMPOSE_PROJECT_NAME') or os.environ['COMPOSE_PROJECT_NAME'] == 'design-studio-ai':
        fail('Set a distinct COMPOSE_PROJECT_NAME and separate credential file for isolated restore.')
    # Unlike normal Compose interpolation, --env-file is explicit to avoid loading
    # source production bindings. Caller provides COMPOSE_ENV_FILES securely.
    if not os.environ.get('COMPOSE_ENV_FILES'):
        fail('Restore requires COMPOSE_ENV_FILES pointing to the isolated private configuration.')
    services = compose('ps', '--status', 'running', '--services', capture_output=True, text=True).stdout.splitlines()
    if any(name in WRITERS for name in services):
        fail('Restore target must have no API, web or worker running.')
    backup_dir = staging / 'backup'; backup_dir.mkdir()
    ledger_dir = staging / 'ledger'; ledger_dir.mkdir()
    snapshot = unseal(args, args.input, backup_dir, 'backup')
    latest = unseal(args, args.current_deletion_ledger, ledger_dir, 'deletions')
    snapshot_time = datetime.fromisoformat(snapshot['created_at'])
    ledger_time = datetime.fromisoformat(latest['created_at'])
    age = (datetime.now(timezone.utc) - ledger_time).total_seconds()
    if latest.get('source_quiesced') is not True or ledger_time < snapshot_time or not 0 <= age <= args.maximum_ledger_age_seconds:
        fail('Ledger must be newer than snapshot and freshly exported from the authoritative current ledger.')
    # No process receives inherited enabled-provider or live-handoff settings.
    result = compose('exec', '-T', 'db', 'psql', '-U', 'studio_app', '-d', 'studio', '-Atc',
                     "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'", capture_output=True, text=True)
    if result.stdout.strip() != '0':
        fail('Restore target database must be empty; existing data will never be overwritten.')
    volume_import(backup_dir / 'media.tar', MEDIA, args.maximum_archive_bytes)
    volume_import(ledger_dir / 'deletions.tar', LEDGER, args.maximum_archive_bytes)
    with (backup_dir / 'database.dump').open('rb') as source:
        compose('exec', '-T', 'db', 'pg_restore', '--exit-on-error', '--no-owner', '-U', 'studio_app', '-d', 'studio', stdin=source)
    compose('run', '--rm', '--no-deps', '-T', '--entrypoint', 'python', 'backend', '-c',
            "from pathlib import Path; Path('/var/lib/studio/private/STOP_GENERATION').touch(mode=0o600)")
    for command in (['alembic', 'upgrade', 'head'], ['python', '-m', 'app.privacy', 'replay'], ['python', '-c', 'from app.db import factory; from app.worker import maintain; db=factory()(); maintain(db); db.close()']):
        compose('run', '--rm', '--no-deps', '-T', '-e', 'PROVIDER_ENABLED=false', '-e', 'BUDGET_APPROVED=false',
                '-e', 'GLOBAL_KILL_SWITCH=true', '--entrypoint', command[0], 'backend', *command[1:])
    print('PASS: isolated database/media restored; current deletions and expiry replayed. Services remain stopped.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpg-home', required=True, type=private_directory)
    parser.add_argument('--scratch-dir', required=True, type=private_directory)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('backup', 'export-deletions'):
        p = sub.add_parser(action); p.add_argument('--recipient', required=True); p.add_argument('--output', required=True)
        if action == 'export-deletions': p.add_argument('--quiesce-source', action='store_true')
    p = sub.add_parser('restore')
    p.add_argument('--input', required=True, type=Path)
    p.add_argument('--current-deletion-ledger', required=True, type=Path)
    p.add_argument('--maximum-ledger-age-seconds', type=int, default=1800)
    p.add_argument('--maximum-archive-bytes', type=int, default=16 * 1024 ** 3)
    p.add_argument('--confirm-isolated', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if not shutil.which('gpg'):
        fail('GPG is required; never use an unencrypted fallback.')
    with tempfile.TemporaryDirectory(prefix='studio-backup-', dir=args.scratch_dir) as tmp:
        globals()[args.action.replace('-', '_')](args, Path(tmp))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError) as exc:
        # subprocess arguments contain service names/public paths only, no secrets;
        # avoid dumping arbitrary archive metadata or environment configuration.
        reason = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print('BLOCKED: '+reason+'. Inspect safe command diagnostics; no recovery services were published.', file=__import__('sys').stderr)
        raise SystemExit(1)
