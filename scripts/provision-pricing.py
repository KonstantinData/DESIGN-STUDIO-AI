#!/usr/bin/env python3
"""Install an explicitly operator-approved private pricing contract, without activation.

The input must be independently verified against an authoritative price source.
A separately supplied SHA-256 pins its bytes. This script does not verify the
external tariff, enable generation, alter credentials, or restart any service.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('pricing_ops', ROOT / 'scripts/backup.py')
ops = importlib.util.module_from_spec(spec); spec.loader.exec_module(ops)


def install(source, expected, approved):
    if not approved:
        raise ValueError('Explicit --operator-verified is required after pricing approval.')
    path = Path(source).resolve(strict=True)
    metadata = path.stat()
    if path.is_relative_to(ROOT) or not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077 or metadata.st_uid not in (os.getuid(), 0):
        raise ValueError('Use a private owner-only regular file outside checkout.')
    if metadata.st_size > 65536 or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('Contract size or separately verified SHA-256 is invalid.')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Pricing source does not match the independently supplied SHA-256.')
    value = json.loads(raw)
    required = {'version', 'currency', 'verified_by', 'verified_at', 'expires_at', 'source', 'models'}
    if not required <= value.keys():
        raise ValueError('Pricing metadata fields are incomplete.')
    # Select only the actual pricing mount name, never inspect or print credentials.
    identifier = ops.compose('ps', '-q', 'backend', capture_output=True, text=True).stdout.strip()
    if not identifier or '\n' in identifier:
        raise ValueError('Exactly one running API container is required for mount discovery.')
    result = subprocess.run(['docker', 'inspect', '--format', '{{json .Mounts}}', identifier], check=True,
                            capture_output=True, text=True)
    mounts = [mount for mount in json.loads(result.stdout) if mount.get('Destination') == '/etc/studio/pricing']
    if len(mounts) != 1 or mounts[0].get('Type') != 'volume' or mounts[0].get('RW') is not False:
        raise ValueError('API pricing must be an existing read-only named volume.')
    volume = mounts[0]['Name']
    image = subprocess.run(['docker', 'inspect', '--format', '{{.Image}}', identifier], check=True, capture_output=True, text=True).stdout.strip()
    models = json.loads(ops.compose('exec', '-T', 'backend', 'python', '-c', "import json,os;print(json.dumps({name:os.getenv(name,default) for name,default in [('OPENAI_TEXT_MODEL','gpt-4.1-mini'),('OPENAI_IMAGE_MODEL','gpt-image-1.5'),('OPENAI_REFERENCE_IMAGE_MODEL','')]}))", capture_output=True, text=True).stdout)
    filename = '/etc/studio/pricing/verified-' + expected + '.json'
    code = '''import hashlib,os,sys,tempfile
from pathlib import Path
from app.costing import load_contract
raw=sys.stdin.buffer.read(65537)
expected=sys.argv[1];target=Path(sys.argv[2])
assert len(raw)<=65536 and hashlib.sha256(raw).hexdigest()==expected
root=target.parent
fd,temp=tempfile.mkstemp(prefix='.pricing-',dir=root)
try:
 with os.fdopen(fd,'wb') as out:
  out.write(raw);out.flush();os.fsync(out.fileno())
 os.chmod(temp,0o600)
 os.environ['VERIFIED_PRICING_FILE']=temp;os.environ['VERIFIED_PRICING_SHA256']=expected
 contract=load_contract()
 if contract is None:raise ValueError('Invalid, expired or unsupported verified contract')
 models=[(os.getenv('OPENAI_TEXT_MODEL','gpt-4.1-mini'),'responses'),(os.getenv('OPENAI_IMAGE_MODEL','gpt-image-1.5'),'image')]
 if os.getenv('OPENAI_REFERENCE_IMAGE_MODEL'):models.append((os.environ['OPENAI_REFERENCE_IMAGE_MODEL'],'image'))
 if any(contract.value['models'].get(model,{}).get('kind')!=kind for model,kind in models):raise ValueError('Configured models missing')
 try:os.link(temp,target)
 except FileExistsError:
  if target.read_bytes()!=raw:raise ValueError('Immutable target differs')
 parent=os.open(root,os.O_RDONLY)
 try:os.fsync(parent)
 finally:os.close(parent)
 assert target.stat().st_uid==10001 and (target.stat().st_mode&0o777)==0o600
 print('PASS private verified contract installed immutably; provider flags unchanged.')
finally:Path(temp).unlink(missing_ok=True)
'''
    # Compose run -v does not reliably replace an inherited :ro mount. Use the
    # exact deployed image in a networkless disposable container with only this
    # one volume writable; ordinary API/worker mounts remain read-only.
    subprocess.run(['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only', '--user', '10001:10001',
                    '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                    '--volume', volume + ':/etc/studio/pricing:rw',
                    *[item for name, value in models.items() for item in ('-e', name+'='+value)],
                    '--entrypoint', 'python', image, '-c', code, expected, filename], input=raw, check=True)
    print(json.dumps({'VERIFIED_PRICING_FILE': filename, 'VERIFIED_PRICING_SHA256': expected,
                      'activation': 'NOT_ENABLED', 'service_restart': False}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--operator-verified', action='store_true')
    args = parser.parse_args()
    try:
        install(args.source, args.sha256.lower(), args.operator_verified)
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError):
        print('BLOCKED: private contract, approval, pinned digest or read-only deployment precondition failed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
