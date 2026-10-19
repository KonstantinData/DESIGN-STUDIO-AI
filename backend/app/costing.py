"""Verified price-based exposure bounds. Never claims actual provider billing.

No rates are shipped. An operator must verify an authoritative OpenAI price source,
save a private immutable JSON contract outside Git and pin its SHA-256 separately.
Invalid/missing/changing contracts or unfamiliar usage retain the full reservation.
"""
from dataclasses import dataclass
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation,ROUND_CEILING
import hashlib,json,os,stat
from pathlib import Path
from urllib.parse import urlsplit

from .paths import checkout_root

@dataclass(frozen=True)
class PricingContract:
    path:Path
    sha256:str
    value:dict


def _decimal(value):
    if not isinstance(value,str):raise ValueError('Rates must be explicit decimal strings')
    parsed=Decimal(value)
    if not parsed.is_finite() or parsed<0 or parsed>Decimal('1000000'):raise ValueError('Invalid rate')
    return parsed


def _timestamp(value):
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.tzinfo is None:raise ValueError('Timestamp must include timezone')
    return stamp


def _image_fields(rates):
    supported=rates.get('text_output_supported',True)
    if type(supported) is not bool:raise ValueError('text_output_supported must be an explicit boolean')
    fields=('text_input_usd_per_million','image_input_usd_per_million','image_output_usd_per_million')
    if supported:return fields+('text_output_usd_per_million',)
    # Unsupported is a capability assertion, never an invented zero-price tariff.
    if rates.get('text_output_usd_per_million') is not None:raise ValueError('Unsupported text output cannot carry a text-output tariff')
    return fields


def load_contract():
    try:
        configured=os.getenv('VERIFIED_PRICING_FILE','')
        expected=os.getenv('VERIFIED_PRICING_SHA256','').lower()
        if not configured or len(expected)!=64:return None
        path=Path(configured).resolve(strict=True)
        checkout=checkout_root()
        metadata=path.stat()
        if path.is_relative_to(checkout) or not stat.S_ISREG(metadata.st_mode) or metadata.st_mode&0o077 or metadata.st_uid not in (os.getuid(),0) or metadata.st_size>65536:return None
        raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if digest!=expected:return None
        value=json.loads(raw)
        if value.get('version')!=1 or value.get('currency')!='USD' or not isinstance(value.get('verified_by'),str) or not value['verified_by'].strip():return None
        now=datetime.now(timezone.utc)
        verified=_timestamp(value['verified_at']);expires=_timestamp(value['expires_at'])
        if verified>now or expires<=now or expires<=verified:return None
        source=urlsplit(value['source'])
        if source.scheme!='https' or source.hostname not in ('openai.com','www.openai.com','platform.openai.com','developers.openai.com') or source.username or source.password or source.fragment or source.query:return None
        if not isinstance(value.get('models'),dict) or not value['models'] or len(value['models'])>30:return None
        for name,rates in value['models'].items():
            if not isinstance(name,str) or not name or not isinstance(rates,dict):return None
            kind=rates.get('kind')
            fields=('input_usd_per_million','output_usd_per_million') if kind=='responses' else _image_fields(rates) if kind=='image' else ()
            if not fields:return None
            for field in fields:_decimal(rates[field])
        return PricingContract(path,digest,value)
    except (OSError,ValueError,KeyError,TypeError,AttributeError,InvalidOperation):return None


def still_trusted(contract):
    if not contract:return False
    current=load_contract()
    return current is not None and current.path==contract.path and current.sha256==contract.sha256


def _tokens(value):
    if type(value) is not int or value<0 or value>100_000_000:raise ValueError('Invalid token count')
    return value


def bound_usage(contract,kind,model,usage):
    """Returns conservative rounded-up cents or None. Cache discounts ignored."""
    try:
        if not contract or not isinstance(usage,dict) or not isinstance(model,str):return None
        rates=contract.value['models'].get(model)
        expected='image' if kind=='image' else 'responses'
        if not rates or rates['kind']!=expected:return None
        inputs=_tokens(usage['input_tokens']);outputs=_tokens(usage['output_tokens'])
        if outputs==0:return None
        if 'total_tokens' in usage and _tokens(usage['total_tokens'])!=inputs+outputs:return None
        if expected=='responses':
            cost=Decimal(inputs)*_decimal(rates['input_usd_per_million'])+Decimal(outputs)*_decimal(rates['output_usd_per_million'])
        else:
            details=usage['input_tokens_details']
            text_input=_tokens(details['text_tokens']);image_input=_tokens(details['image_tokens'])
            if text_input+image_input!=inputs:return None
            cost=Decimal(text_input)*_decimal(rates['text_input_usd_per_million'])+Decimal(image_input)*_decimal(rates['image_input_usd_per_million'])
            _image_fields(rates)
            text_supported=rates.get('text_output_supported',True)
            if 'output_tokens_details' in usage:
                details=usage['output_tokens_details']
                text_output=_tokens(details.get('text_tokens',0)) if not text_supported else _tokens(details['text_tokens'])
                image_output=_tokens(details['image_tokens'])
                if text_output+image_output!=outputs or (not text_supported and text_output!=0):return None
                cost+=Decimal(image_output)*_decimal(rates['image_output_usd_per_million'])
                if text_supported:cost+=Decimal(text_output)*_decimal(rates['text_output_usd_per_million'])
            elif not text_supported:
                # Authoritatively unsupported text output: all output is billed as image.
                cost+=Decimal(outputs)*_decimal(rates['image_output_usd_per_million'])
            else:
                # Missing output breakdown: all output assigned the more expensive rate.
                cost+=Decimal(outputs)*max(_decimal(rates['text_output_usd_per_million']),_decimal(rates['image_output_usd_per_million']))
        cents=int((cost/Decimal('10000')).to_integral_value(rounding=ROUND_CEILING))
        return {'upper_bound_cents':cents,'pricing_reference':{'sha256':contract.sha256,'source':contract.value['source'],'verified_by':contract.value['verified_by'],'verified_at':contract.value['verified_at'],'expires_at':contract.value['expires_at'],'model':model,'currency':'USD','rates_snapshot':dict(rates)},'accounting':'verified_price_upper_bound_not_invoice'}
    except (KeyError,ValueError,TypeError,InvalidOperation):return None
