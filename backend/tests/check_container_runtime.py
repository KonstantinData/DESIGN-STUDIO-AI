"""Run in built backend image with normal DB env; no writes or provider calls.

python -c 'exec(open("tests/check_container_runtime.py").read())'
Uses a temporary synthetic QA pricing contract, never live rates.
"""
import hashlib,json,os,tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from app.paths import checkout_root
from app.costing import load_contract
from app.smoke import main
assert checkout_root()==Path('/app')
with tempfile.TemporaryDirectory(prefix='qa-container-paths-') as temporary:
    root=Path(temporary);instant=datetime.now(timezone.utc)
    value={'version':1,'currency':'USD','verified_by':'QA container synthetic contract only','verified_at':(instant-timedelta(minutes=1)).isoformat(),'expires_at':(instant+timedelta(hours=1)).isoformat(),'source':'https://openai.com/api/pricing/','models':{'qa-only':{'kind':'responses','input_usd_per_million':'1','output_usd_per_million':'1'}}}
    contract=root/'pricing.json';contract.write_text(json.dumps(value));contract.chmod(0o600)
    os.environ['VERIFIED_PRICING_FILE']=str(contract);os.environ['VERIFIED_PRICING_SHA256']=hashlib.sha256(contract.read_bytes()).hexdigest()
    assert load_contract() is not None
    assert main(['--host','localhost','--state',str(root/'private-state.json'),'--report',str(root/'private-report.json')])==0
    report=json.loads((root/'private-report.json').read_text())
    assert report['actual_images']==0 and report['public_bot_e2e']=='NOT_TESTED'
    assert (root/'private-report.json').stat().st_mode&0o077==0
print('PASS installed /app boundary, external private pricing, read-only operator audit; no provider calls')
