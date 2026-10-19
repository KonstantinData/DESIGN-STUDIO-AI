import hashlib, io, json, os, secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from fastapi import HTTPException
from .db import Tenant, Account, Media, now, uid

def host_name(value):
    if not value or len(value)>300 or any(character in value for character in '/\\@#?') or any(character.isspace() for character in value):raise HTTPException(421,'Ungültiger Studio-Host.')
    try:
        parsed=urlsplit('//'+value)
        parsed.port  # validate port syntax, never derive tenant from a forwarding field
        hostname=parsed.hostname
    except ValueError:raise HTTPException(421,'Ungültiger Studio-Host.')
    if not hostname:raise HTTPException(421,'Ungültiger Studio-Host.')
    return hostname.lower()

def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def token(): return secrets.token_urlsafe(48)
def data_dir():
    p=Path(os.getenv('DATA_DIR','/workspace/studio-private')); p.mkdir(parents=True,exist_ok=True,mode=0o700); return p

def seed(db):
    configs=json.loads(os.getenv('TENANTS_JSON','[]'))
    for conf in configs:
        host=conf['host'].lower()
        if '/' in host or ':' in host: raise RuntimeError('Tenant host must be a hostname without port')
        row=db.scalar(select(Tenant).where(Tenant.host==host))
        public={k:v for k,v in conf.items() if k not in ('turnstile_secret',)}
        if row: row.config=public; row.enabled=row.enabled and conf.get('enabled',True); row.budget=int(conf.get('budget_cents',2500))
        else: db.add(Tenant(id=conf['slug'],host=host,config=public,budget=int(conf.get('budget_cents',2500)),enabled=conf.get('enabled',True)))
    if not db.get(Account,'global'): db.add(Account(id='global',budget=int(os.getenv('GLOBAL_BUDGET_CENTS','2500'))))
    else:
        account=db.get(Account,'global')
        account.budget=min(account.budget,int(os.getenv('GLOBAL_BUDGET_CENTS','2500')))
    db.commit()

def ready(tenant):
    if (data_dir()/'STOP_GENERATION').exists(): return False,'Bildgenerierung ist noch nicht freigegeben.'
    if os.getenv('GLOBAL_KILL_SWITCH','true').lower()!='false': return False,'Bildgenerierung ist noch nicht freigegeben.'
    if not tenant.enabled: return False,'Generierung für dieses Studio ist deaktiviert.'
    if os.getenv('PROVIDER_ENABLED','false').lower()!='true' or os.getenv('BUDGET_APPROVED','false').lower()!='true': return False,'Anbieter und geprüftes Laufbudget sind noch nicht freigegeben.'
    if not os.getenv('STUDIO_OPENAI_API_KEY'): return False,'Der serverseitige Anbieterschlüssel fehlt.'
    tenant_conf=next((item for item in json.loads(os.getenv('TENANTS_JSON','[]')) if item.get('slug')==tenant.id),{})
    if not tenant.config.get('turnstile_site_key') or not (tenant_conf.get('turnstile_secret') or os.getenv('TURNSTILE_SECRET')): return False,'Der Bot-Schutz benötigt Site-Key und serverseitiges Geheimnis.'
    if not os.getenv('HARD_LIMIT_VERIFIED_AT'): return False,'Der überprüfte Anbieter-Hard-Limit-Nachweis fehlt.'
    from .costing import load_contract
    pricing=load_contract()
    if not pricing:return False,'Ein aktueller, geprüfter und mit festem Hash geprüfter Preisvertrag fehlt.'
    expected=[(os.getenv('OPENAI_TEXT_MODEL','gpt-4.1-mini'),'responses'),(os.getenv('OPENAI_IMAGE_MODEL','gpt-image-1.5'),'image')]
    if os.getenv('OPENAI_REFERENCE_IMAGE_MODEL'):expected.append((os.environ['OPENAI_REFERENCE_IMAGE_MODEL'],'image'))
    if any(pricing.value['models'].get(model,{}).get('kind')!=kind for model,kind in expected):return False,'Der geprüfte Preisvertrag deckt die konfigurierten Modelle nicht ab.'
    return True,None

async def challenge(tenant,value):
    configs=json.loads(os.getenv('TENANTS_JSON','[]'))
    conf=next((x for x in configs if x['slug']==tenant.id),{})
    secret=conf.get('turnstile_secret') or os.getenv('TURNSTILE_SECRET')
    if not secret: raise HTTPException(503,'Bot-Schutz ist noch nicht eingerichtet.')
    if not value: raise HTTPException(400,'Bitte bestätige den Bot-Schutz.')
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response=await client.post('https://challenges.cloudflare.com/turnstile/v0/siteverify',data={'secret':secret,'response':value})
            response.raise_for_status(); result=response.json()
    except (httpx.HTTPError,ValueError): raise HTTPException(503,'Bot-Schutz ist vorübergehend nicht erreichbar.')
    if not result.get('success') or result.get('hostname')!=tenant.host.split(':')[0]: raise HTTPException(403,'Bot-Prüfung fehlgeschlagen.')

def normalize_image(raw):
    if len(raw)>12*1024*1024: raise HTTPException(413,'Das Bild darf höchstens 12 MB groß sein.')
    try:
        with Image.open(io.BytesIO(raw), formats=['JPEG','PNG','WEBP']) as image:
            if image.format not in ('JPEG','PNG','WEBP') or image.width<256 or image.height<256 or image.width*image.height>25_000_000 or max(image.size)>4096: raise ValueError()
            image.load()
            image=ImageOps.exif_transpose(image)
            result=io.BytesIO(); image.convert('RGB').save(result,'JPEG',quality=95); return result.getvalue()
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError): raise HTTPException(422,'Bitte lade ein lesbares Foto oder einen Grundriss als PNG, JPEG oder WebP hoch (256 bis 4096 Pixel je Kante).')

def store_media(db,tenant_id,session_id,raw,mime='image/png'):
    ident=uid(); path=data_dir()/ident
    with path.open('xb') as file: file.write(raw)
    path.chmod(0o600)
    media=Media(id=ident,tenant_id=tenant_id,session_id=session_id,path=str(path),mime=mime); db.add(media); db.flush(); return media
