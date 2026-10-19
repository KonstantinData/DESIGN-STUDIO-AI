#!/usr/bin/env python3
"""Secure direct-server credentials only. Never changes provider/budget/tenant gates."""
import argparse,getpass,json,os,re,ssl,subprocess,tempfile,urllib.error,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--target',type=Path,default=Path('/srv/design-studio-review'));a=p.parse_args();root=a.target.resolve();private=root/'.deploy.env'
def fail(message):raise SystemExit(message)
if os.geteuid()!=0:fail('Run locally as root on the Hetzner server, not in the cloud workspace.')
if not (root/'scripts/hetzner-status.py').is_file():fail('Apply the targeted readiness update first.')
ignore=root/'.dockerignore'
if not ignore.is_file() or '.deploy.env.*' not in ignore.read_text().splitlines():fail('Future credential package Docker exclusions are required first; nothing saved.')
if not private.is_file() or private.is_symlink() or private.stat().st_mode&0o077:fail('Private server configuration missing or permissions invalid.')
env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','DOCKER_CONFIG','DOCKER_HOST','DOCKER_CONTEXT')};env['COMPOSE_DISABLE_ENV_FILE']='true'
compose=['docker','compose','--project-name','design-studio-review','--env-file',str(private),'-f',str(root/'compose.yaml'),'-f',str(root/'deploy/compose.hetzner-review.yaml')]
def run(*args,**kw):return subprocess.run(compose+list(args),env=env,cwd=root,check=True,**kw)
configuration=json.loads(run('config','--format','json',capture_output=True,text=True).stdout)
for name in ('backend','worker'):
 e=configuration['services'][name]['environment']
 if str(e.get('PROVIDER_ENABLED')).lower()!='false' or str(e.get('GLOBAL_KILL_SWITCH')).lower()!='true':fail('Credentials setup requires closed generation. No flags will be changed.')
original=private.read_bytes()
key=getpass.getpass('Existing real Design-Studio-AI OpenAI project key (hidden): ').strip()
turnstile=getpass.getpass('Turnstile server secret for studio.mein-kuechenexperte.de (hidden): ').strip()
for name,value in [('OpenAI',key),('Turnstile',turnstile)]:
 if len(value)<20 or any(ch.isspace() or ord(ch)<32 for ch in value) or "'" in value:fail(name+' secret has invalid characters; nothing saved.')
if not key.startswith('sk-'):fail('Expected a real OpenAI key; cloud placeholder bindings must not be copied.')
request=urllib.request.Request('https://api.openai.com/v1/responses',data=b'{}',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
try:
 with urllib.request.urlopen(request,timeout=20,context=ssl.create_default_context()) as response:
  status=response.status;body=response.read(65537)
except urllib.error.HTTPError as error:
 status=error.code;body=error.read(65537)
except (urllib.error.URLError,TimeoutError,OSError):fail('TLS/network authentication probe failed; nothing saved. No generation requested.')
if status==401:fail('Provider authentication rejected (401); nothing saved. Verify the existing project key securely.')
if status!=400:fail('Unexpected nonbillable validation status '+str(status)+'; nothing saved. No generation requested.')
# A generic proxy400/HTML is not authentication evidence. Accept only a narrow
# structured OpenAI missing-required-field validation error for the fixed {} body.
try:
 if len(body)>65536:raise ValueError()
 error=json.loads(body).get('error',{})
 expected=(isinstance(error,dict) and error.get('type')=='invalid_request_error'
   and error.get('code')=='missing_required_parameter' and error.get('param') in ('model','input'))
except (ValueError,AttributeError,TypeError):expected=False
if not expected:fail('Unexpected or unstructured validation response; nothing saved. No generation requested.')
text=original.decode()
for name,value in [('STUDIO_OPENAI_API_KEY',key),('TURNSTILE_SECRET',turnstile)]:
 pattern=r'(?m)^'+re.escape(name)+r'=.*$'
 if len(re.findall(pattern,text))>1:fail('Duplicate configuration entry; nothing saved.')
 line=name+"='"+value+"'"
 text=re.sub(pattern,lambda _:line,text) if re.search(pattern,text) else text.rstrip('\n')+'\n'+line+'\n'
if private.read_bytes()!=original:fail('Configuration changed concurrently; nothing saved.')
fd,temporary=tempfile.mkstemp(prefix='.deploy.env.new-',dir=root)
try:
 with os.fdopen(fd,'wb') as stream:stream.write(text.encode());stream.flush();os.fsync(stream.fileno())
 os.chmod(temporary,0o600);os.replace(temporary,private)
 descriptor=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(descriptor)
 finally:os.close(descriptor)
finally:
 if os.path.exists(temporary):os.unlink(temporary)
print('Credentials saved privately after structured missing-field validation. No model/input/generation requested. Image-model entitlement remains unverified.',flush=True)
configuration=json.loads(run('config','--format','json',capture_output=True,text=True).stdout)
for name in ('backend','worker'):
 e=configuration['services'][name]['environment']
 if str(e.get('PROVIDER_ENABLED')).lower()!='false' or str(e.get('GLOBAL_KILL_SWITCH')).lower()!='true':fail('Flags changed concurrently; refusing restart. Credentials saved privately, generation not enabled by this helper.')
if private.read_bytes()!=text.encode():fail('Configuration changed concurrently; refusing restart.')
run('up','-d','--no-deps','--no-build','--wait','--wait-timeout','180','backend','worker')
subprocess.run(['python3',str(root/'scripts/hetzner-status.py'),'--target',str(root)],env=env,check=True)
print('Closed backend/worker refreshed. Web, DB, nginx and TLS unchanged. No gate, budget, tenant or pricing contract changed.')
