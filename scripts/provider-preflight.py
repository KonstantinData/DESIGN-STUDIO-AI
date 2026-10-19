#!/usr/bin/env python3
"""Free operator network preflight; never submits generation or changes configuration."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CODE = '''import asyncio,json,os,socket,time
from urllib.parse import urlsplit
import httpx
result={'key_present':bool(os.getenv('STUDIO_OPENAI_API_KEY'))}
proxy=urlsplit(os.getenv('HTTPS_PROXY','')).hostname
result['proxy_hostname']=proxy
try:result['proxy_addresses']=list({row[4][0] for row in socket.getaddrinfo(proxy,None)}) if proxy else []
except Exception as exc:result['dns_error']=type(exc).__name__;result['proxy_addresses']=[]
async def probe():
 if not result['key_present']:return
 start=time.monotonic()
 try:
  async with httpx.AsyncClient(timeout=httpx.Timeout(20,connect=15),follow_redirects=False) as client:
   response=await client.get('https://api.openai.com/v1/models',headers={'Authorization':'Bearer '+os.environ['STUDIO_OPENAI_API_KEY']})
   result['models_status']=response.status_code
 except Exception as exc:result['error_type']=type(exc).__name__
 result['seconds']=round(time.monotonic()-start,2)
asyncio.run(probe());print(json.dumps(result))
'''


def main():
    proxy = urlsplit(os.getenv('HTTPS_PROXY', '')).hostname
    try:
        addresses = {row[4][0] for row in socket.getaddrinfo(proxy, None)} if proxy else set()
    except OSError:
        print(json.dumps({'provider_network_ready': False, 'reason': 'host_proxy_dns_failed'})); return 1

    def probe(service):
        try:
            completed = subprocess.run(['docker', 'compose', 'exec', '-T', service, 'python', '-c', CODE], cwd=ROOT,
                                       capture_output=True, text=True, timeout=30, check=True)
            result = json.loads(completed.stdout)
            actual_proxy = result.pop('proxy_hostname')
            actual_addresses = set(result.pop('proxy_addresses'))
            matches = actual_proxy == proxy and (not proxy or bool(actual_addresses & addresses))
            result['proxy_matches_current_host_dns'] = matches
            result['ready'] = matches and result.get('models_status') == 200
            return service, result
        except (subprocess.SubprocessError, ValueError, OSError):
            return service, {'ready': False, 'error_type': 'preflight_execution_failed'}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = dict(pool.map(probe, ['backend', 'worker']))
    ready = all(result['ready'] for result in results.values())
    print(json.dumps({'provider_network_ready': ready, 'generation_authentication': 'NOT_VERIFIED_BY_MODEL_LIST', 'services': results}, sort_keys=True))
    return 0 if ready else 1


if __name__ == '__main__':
    sys.exit(main())
