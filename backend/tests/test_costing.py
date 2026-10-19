"""Synthetic QA prices only. No live price schedule or provider call occurs."""
import hashlib,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from app.costing import load_contract,bound_usage,still_trusted

@pytest.fixture
def pricing(tmp_path,monkeypatch):
    now=datetime.now(timezone.utc)
    contract={'version':1,'currency':'USD','verified_by':'QA synthetic-price-test','verified_at':(now-timedelta(minutes=1)).isoformat(),'expires_at':(now+timedelta(hours=1)).isoformat(),'source':'https://openai.com/api/pricing/','models':{'qa-text':{'kind':'responses','input_usd_per_million':'1.50','output_usd_per_million':'6.00'},'qa-image':{'kind':'image','text_input_usd_per_million':'5','image_input_usd_per_million':'10','text_output_usd_per_million':'10','image_output_usd_per_million':'40'}}}
    path=tmp_path/'synthetic-private-pricing.json';path.write_text(json.dumps(contract));path.chmod(0o600)
    monkeypatch.setenv('VERIFIED_PRICING_FILE',str(path));monkeypatch.setenv('VERIFIED_PRICING_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
    return path,contract

def test_decimal_rounded_up_upper_ignores_cache_discount(pricing):
    contract=load_contract();assert contract and still_trusted(contract)
    result=bound_usage(contract,'text','qa-text',{'input_tokens':1000,'output_tokens':1000,'total_tokens':2000,'input_tokens_details':{'cached_tokens':1000}})
    assert result['upper_bound_cents']==1  # 0.75 cents rounded upward
    assert result['accounting']=='verified_price_upper_bound_not_invoice'
    result=bound_usage(contract,'image','qa-image',{'input_tokens':1000,'input_tokens_details':{'text_tokens':100,'image_tokens':900},'output_tokens':1000,'total_tokens':2000})
    assert result['upper_bound_cents']==5  #4.95 cents, max output rate without breakdown
    assert result['pricing_reference']['sha256']==contract.sha256

@pytest.mark.parametrize('usage',[{}, {'input_tokens':True,'output_tokens':1},{'input_tokens':-1,'output_tokens':1},{'input_tokens':1,'output_tokens':1,'total_tokens':1},{'input_tokens':1,'output_tokens':0},{'input_tokens':'1','output_tokens':1}])
def test_malformed_unknown_usage_never_releases(pricing,usage):
    assert bound_usage(load_contract(),'text','qa-text',usage) is None

def test_image_requires_consistent_input_breakdown(pricing):
    contract=load_contract()
    assert bound_usage(contract,'image','qa-image',{'input_tokens':100,'output_tokens':10}) is None
    assert bound_usage(contract,'image','qa-image',{'input_tokens':100,'output_tokens':10,'input_tokens_details':{'text_tokens':1,'image_tokens':1}}) is None
    assert bound_usage(contract,'text','unlisted-model',{'input_tokens':1,'output_tokens':1}) is None

def test_changed_hash_or_nonprivate_contract_fail_closed(pricing,monkeypatch):
    path,value=pricing;before=load_contract();assert before
    path.write_text(path.read_text()+' ')
    assert load_contract() is None and not still_trusted(before)
    monkeypatch.setenv('VERIFIED_PRICING_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
    path.chmod(0o644)
    assert load_contract() is None

def test_untrusted_source_and_expired_contract_fail_closed(pricing,monkeypatch):
    path,value=pricing
    for field,bad in [('source','https://untrusted.example/pricing'),('expires_at','2000-01-01T00:00:00+00:00')]:
        changed={**value,field:bad};path.write_text(json.dumps(changed));monkeypatch.setenv('VERIFIED_PRICING_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
        assert load_contract() is None

@pytest.mark.parametrize('rate_present',[False,True])
def test_authoritatively_unsupported_text_output_omitted_or_null(pricing,monkeypatch,rate_present):
    path,value=pricing;rates=value['models']['qa-image']
    rates['text_output_supported']=False
    if rate_present:rates['text_output_usd_per_million']=None
    else:rates.pop('text_output_usd_per_million')
    path.write_text(json.dumps(value));monkeypatch.setenv('VERIFIED_PRICING_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
    contract=load_contract();assert contract is not None
    usage={'input_tokens':1000,'input_tokens_details':{'text_tokens':100,'image_tokens':900},'output_tokens':1000,'total_tokens':2000}
    assert bound_usage(contract,'image','qa-image',usage)['upper_bound_cents']==5
    usage['output_tokens_details']={'image_tokens':1000}
    assert bound_usage(contract,'image','qa-image',usage)['upper_bound_cents']==5
    usage['output_tokens_details']={'text_tokens':0,'image_tokens':1000}
    assert bound_usage(contract,'image','qa-image',usage)['upper_bound_cents']==5
    # Contradictory actual text output cannot receive a fictitious tariff/refund.
    usage['output_tokens_details']={'text_tokens':1,'image_tokens':999}
    assert bound_usage(contract,'image','qa-image',usage) is None

@pytest.mark.parametrize('flag,rate',[('false',None),(0,None),(None,None),(False,'0'),(True,None)])
def test_malformed_or_contradictory_text_output_capability_fails_closed(pricing,monkeypatch,flag,rate):
    path,value=pricing
    value['models']['qa-image'].update(text_output_supported=flag,text_output_usd_per_million=rate)
    path.write_text(json.dumps(value));monkeypatch.setenv('VERIFIED_PRICING_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
    assert load_contract() is None
