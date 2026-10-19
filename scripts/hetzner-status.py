#!/usr/bin/env python3
"""Private operator diagnostics: aggregate state only; never enables generation."""
import argparse,json,os,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--target',type=Path,default=Path('/srv/design-studio-review'))
p.add_argument('--check-provider-auth',action='store_true',help='One deliberately invalid POST {} without model/input; no generation request')
a=p.parse_args();root=a.target.resolve()
env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','DOCKER_CONFIG','DOCKER_HOST','DOCKER_CONTEXT')};env['COMPOSE_DISABLE_ENV_FILE']='true'
code='''import os,json
from sqlalchemy import select,func
from app.db import factory,Account,Tenant,Job
from app.security import data_dir,ready
from app.costing import load_contract
pricing=load_contract()
conf=json.loads(os.getenv('TENANTS_JSON','[]'))
result={'provider_key_present':bool(os.getenv('STUDIO_OPENAI_API_KEY')),'provider_enabled':os.getenv('PROVIDER_ENABLED','false').lower()=='true','budget_approved':os.getenv('BUDGET_APPROVED','false').lower()=='true','manual_hold':os.getenv('GLOBAL_KILL_SWITCH','true').lower()!='false','runtime_hold':(data_dir()/'STOP_GENERATION').exists(),'turnstile_secret_present':bool(os.getenv('TURNSTILE_SECRET')) or any(bool(t.get('turnstile_secret')) for t in conf),'hard_limit_attested':bool(os.getenv('HARD_LIMIT_VERIFIED_AT')),'pricing_current_and_pinned':pricing is not None,'pricing_expires_at':pricing.value.get('expires_at') if pricing else None,'text_model':os.getenv('OPENAI_TEXT_MODEL','gpt-4.1-mini'),'image_model':os.getenv('OPENAI_IMAGE_MODEL','gpt-image-1.5'),'reference_image_model':os.getenv('OPENAI_REFERENCE_IMAGE_MODEL') or os.getenv('OPENAI_IMAGE_MODEL','gpt-image-1.5')}
with factory()() as db:
 account=db.get(Account,'global')
 active=list(db.scalars(select(Tenant).where(Tenant.enabled==True)))
 result['generation_ready_for_enabled_tenants']=bool(active) and all(ready(t)[0] for t in active)
 result.update({'account_cap_cents':account.budget if account else None,'conservative_charged_cents':account.spent if account else None,'reserved_cents':account.reserved if account else None,'remaining_ceiling_cents':account.budget-account.spent-account.reserved if account else None,'enabled_tenant_count':db.scalar(select(func.count()).select_from(Tenant).where(Tenant.enabled==True)),'queued_jobs':db.scalar(select(func.count()).select_from(Job).where(Job.status=='queued'))})
'''
if a.check_provider_auth:
 code+='''
import httpx
key=os.getenv('STUDIO_OPENAI_API_KEY')
if not key:result['auth_probe']={'performed':False,'reason':'key_absent'}
else:
 try:
  with httpx.Client(timeout=httpx.Timeout(20,connect=10),follow_redirects=False) as client:
   response=client.post('https://api.openai.com/v1/responses',headers={'Authorization':'Bearer '+key},json={})
  try:error=response.json().get('error',{})
  except ValueError:error={}
  raw_code=error.get('code')
  result['auth_probe']={'performed':True,'http_status':response.status_code,'authentication_rejected':response.status_code==401,'error_code':raw_code if raw_code in ('invalid_api_key','invalid_request_error','missing_required_parameter','insufficient_quota') else None,'generation_requested':False}
 except httpx.HTTPError:result['auth_probe']={'performed':True,'network_failed':True,'generation_requested':False}
'''
code+="\nprint(json.dumps(result,sort_keys=True))\n"
command=['docker','compose','--project-name','design-studio-review','--env-file',str(root/'.deploy.env'),'-f',str(root/'compose.yaml'),'-f',str(root/'deploy/compose.hetzner-review.yaml'),'exec','-T','backend','python','-c',code]
r=subprocess.run(command,env=env,capture_output=True,text=True)
try:
 if r.returncode:raise ValueError()
 output=json.loads(r.stdout)
 print(json.dumps(output,sort_keys=True,ensure_ascii=False))
except (ValueError,TypeError):raise SystemExit('Status unavailable; no raw container output printed.')
