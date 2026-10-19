"""Durable abuse limits. IP addresses are HMAC-pseudonymized with daily rotation.
Only explicitly trusted immediate reverse proxies may supply forwarding data.
"""
import asyncio
import hashlib
import hmac
import ipaddress
import os
import secrets
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from .db import AdmissionBucket, Tenant, factory, now
from .security import data_dir,host_name

class AdmissionDenied(Exception): pass

def client_address(scope):
    peer=(scope.get('client') or ('unknown',0))[0]
    try: address=ipaddress.ip_address(peer)
    except ValueError: return 'unknown'
    networks=[ipaddress.ip_network(item.strip()) for item in os.getenv('TRUSTED_PROXY_CIDRS','').split(',') if item.strip()]
    def trusted(value): return any(value in network for network in networks)
    if not trusted(address): return str(address)
    headers={key.lower():value for key,value in scope.get('headers',[])}
    forwarded=headers.get(b'x-forwarded-for',b'')
    if len(forwarded)>2048: return str(address)
    try:
        chain=[ipaddress.ip_address(item.strip()) for item in forwarded.decode('ascii').split(',') if item.strip()]
    except (ValueError,UnicodeDecodeError): return str(address)
    if not chain or len(chain)>10: return str(address)
    # Walk from immediate peer backwards; client-supplied left entries are ignored.
    for candidate in reversed(chain):
        if not trusted(address): break
        address=candidate
    return str(address)

def hmac_key():
    configured=os.getenv('RATE_LIMIT_SECRET')
    if configured:
        if len(configured)<32: raise RuntimeError('RATE_LIMIT_SECRET needs at least 32 characters')
        return configured.encode()
    path=data_dir()/'.rate-limit-key'
    if not path.exists():
        temporary=path.with_name(path.name+'.'+str(uuid4())+'.tmp')
        descriptor=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        try:
            with os.fdopen(descriptor,'wb') as file:
                file.write(secrets.token_bytes(48));file.flush();os.fsync(file.fileno())
            try:os.link(temporary,path)  # atomic publish: readers never see a partial key
            except FileExistsError:pass
        finally:temporary.unlink(missing_ok=True)
    key=path.read_bytes()
    if len(key)<32: raise RuntimeError('Rate limit key unavailable')
    return key

def consume(db,scope,action,limit,window_seconds):
    instant=now(); epoch=int(instant.timestamp())
    window=epoch//window_seconds
    host=host_name(dict(scope.get('headers',[])).get(b'host',b'').decode('ascii','ignore'))
    identity=f'{instant.date().isoformat()}|{host}|{action}|{client_address(scope)}'
    pseudonym=hmac.new(hmac_key(),identity.encode(),hashlib.sha256).hexdigest()
    key=hashlib.sha256(f'{pseudonym}|{window}'.encode()).hexdigest()
    expiry=instant+timedelta(seconds=window_seconds*2)
    statement=insert(AdmissionBucket).values(id=key,count=1,expires_at=expiry)
    statement=statement.on_conflict_do_update(index_elements=[AdmissionBucket.id],set_={'count':AdmissionBucket.count+1},where=AdmissionBucket.count<limit).returning(AdmissionBucket.count)
    admitted=db.scalar(statement)
    db.commit()
    if admitted is None: raise AdmissionDenied()

class RequestGuard:
    """Bound bodies before multipart parsing, with an overall receive deadline."""
    def __init__(self,app): self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or not scope.get('path','').startswith('/api/'):
            return await self.app(scope,receive,send)
        method=scope.get('method','GET')
        headers={k.lower():v for k,v in scope.get('headers',[])}
        async def reject(code,message):
            response=JSONResponse({'detail':message},status_code=code,headers={'Cache-Control':'no-store','Retry-After':'60'} if code==429 else {'Cache-Control':'no-store'})
            await response(scope,receive,send)
        if method in ('POST','PUT','PATCH','DELETE'):
            if headers.get(b'content-encoding',b'identity').lower()!=b'identity':
                return await reject(415,'Komprimierte Anfragekörper werden nicht unterstützt.')
            maximum=int(os.getenv('MAX_UPLOAD_REQUEST_BYTES',str(13*1024*1024))) if scope['path']=='/api/studios' else int(os.getenv('MAX_JSON_REQUEST_BYTES','32768'))
            try: length=int(headers.get(b'content-length',b'0'))
            except ValueError:return await reject(400,'Ungültige Anfragelänge.')
            if length<0:return await reject(400,'Ungültige Anfragelänge.')
            if length>maximum:return await reject(413,'Die Anfrage ist zu groß.')
            def throttle():
                with factory()() as db:
                    hostname=host_name(headers.get(b'host',b'').decode('ascii','ignore'))
                    if not db.scalar(select(Tenant.id).where(Tenant.host==hostname)):return False
                    consume(db,scope,'mutation',int(os.getenv('MAX_MUTATIONS_PER_IP_MINUTE','30')),60)
                    return True
            try:
                known=await asyncio.to_thread(throttle)
                if not known:return await reject(421,'Unbekanntes Studio.')
            except HTTPException:return await reject(421,'Ungültiger Studio-Host.')
            except AdmissionDenied:return await reject(429,'Zu viele Anfragen. Bitte versuche es später erneut.')
            chunks=[];total=0
            try:
                async with asyncio.timeout(float(os.getenv('REQUEST_BODY_TIMEOUT_SECONDS','20'))):
                    while True:
                        message=await receive()
                        if message['type']=='http.disconnect':return
                        chunk=message.get('body',b'');total+=len(chunk)
                        if total>maximum:return await reject(413,'Die Anfrage ist zu groß.')
                        chunks.append(chunk)
                        if not message.get('more_body',False):break
            except TimeoutError:return await reject(408,'Die Übertragung hat zu lange gedauert.')
            delivered=False
            async def replay():
                nonlocal delivered
                if delivered:return await receive()
                delivered=True;return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await self.app(scope,replay,send)
        return await self.app(scope,receive,send)
