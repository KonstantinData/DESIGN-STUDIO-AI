#!/usr/bin/env python3
"""First-install protected review only; never changes nginx, firewall or existing projects."""
import getpass,json,os,re,secrets,shutil,socket,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
PROJECT='design-studio-review'
ENV=ROOT/'.deploy.env'
def run(args,**kw):
    return subprocess.run(args,check=True,**kw)
def fail(message):
    raise SystemExit(message)
if len(sys.argv)!=2 or sys.argv[1] not in ('prepare','start'):
    fail('Usage: python3 scripts/hetzner-install.py prepare|start')
if os.geteuid()!=0: fail('Run on the server as root; no automatic escalation.')
if not shutil.which('docker'): fail('Docker is required; installation is not automated.')
run([sys.executable,'scripts/hetzner-preflight.py'])
base=['docker','compose','--project-name',PROJECT,'--env-file',str(ENV),'-f','compose.yaml','-f','deploy/compose.hetzner-review.yaml']
# Prevent inherited application/config overrides. Keep Docker client connectivity only.
child={k:v for k,v in os.environ.items() if k in ('PATH','HOME','DOCKER_CONFIG','DOCKER_HOST','DOCKER_CONTEXT','TERM','SSH_AUTH_SOCK')}
child['COMPOSE_DISABLE_ENV_FILE']='true'
if sys.argv[1]=='prepare':
    if ENV.exists() or (ROOT/'.env').exists(): fail('Existing private configuration: refusing to overwrite.')
    for kind in ('container','volume','network'):
        command=['docker',kind,'ls','-q','--filter',f'label=com.docker.compose.project={PROJECT}']
        if run(command,capture_output=True,text=True).stdout.strip(): fail('Existing review project: first-install refused.')
    username=input('Private review username: ').strip()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}',username): fail('Invalid username.')
    password_hash=getpass.getpass('Paste the bcrypt hash from interactive caddy hash-password (hidden): ').strip()
    if not re.fullmatch(r'\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}',password_hash): fail('Expected a bcrypt hash; no plaintext password accepted.')
    tenants=json.dumps(json.loads((ROOT/'deploy/tenants.hetzner-review.json').read_text()),separators=(',',':'),ensure_ascii=True)
    values={'POSTGRES_PASSWORD':secrets.token_hex(32),'POSTGRES_ADMIN_PASSWORD':secrets.token_hex(32),
      'TENANTS_JSON':tenants,'SITE_ADDRESSES':'http://studio.mein-kuechenexperte.de:8080',
      'STUDIO_REVIEW_USERNAME':username,'STUDIO_REVIEW_PASSWORD_HASH':password_hash,
      'PROVIDER_ENABLED':'false','BUDGET_APPROVED':'false','GLOBAL_KILL_SWITCH':'true','GLOBAL_BUDGET_CENTS':'500'}
    fd=os.open(ENV,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        stream.write(''.join(f"{k}='{v}'\n" for k,v in values.items()));stream.flush();os.fsync(stream.fileno())
    print('Private .deploy.env created mode0600; no credentials printed. No service was started.')
else:
    if not ENV.is_file() or ENV.stat().st_mode&0o077: fail('Missing/private configuration permissions invalid.')
    run(base+['config','--quiet'],env=child)
    # Serialized builds keep pressure off the shared server; no image pruning.
    run(base+['build','backend'],env=child)
    run(base+['build','web'],env=child)
    run(base+['up','-d','--wait','--wait-timeout','240'],env=child)
    print('Review project started. nginx remains untouched. Check loopback authentication and real TLS before external access.')
