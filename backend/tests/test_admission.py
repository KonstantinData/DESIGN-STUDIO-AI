import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from sqlalchemy import select
from app.admission import client_address,consume,AdmissionDenied,RequestGuard
from app.db import AdmissionBucket,factory,now

def scope(peer='203.0.113.1',forwarded=None,host='one.test'):
    headers=[(b'host',host.encode())]
    if forwarded:headers.append((b'x-forwarded-for',forwarded.encode()))
    return {'type':'http','method':'POST','path':'/api/studios','client':(peer,123),'headers':headers}

def test_proxy_trust_boundary(monkeypatch):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS','172.30.74.2/32')
    assert client_address(scope('203.0.113.1','192.0.2.1'))=='203.0.113.1'
    assert client_address(scope('172.30.74.2','203.0.113.4'))=='203.0.113.4'
    assert client_address(scope('172.30.74.2','1.1.1.1, 203.0.113.4'))=='203.0.113.4'
    assert client_address(scope('172.30.74.2','not-an-ip'))=='172.30.74.2'

def test_atomic_rate_limit_private_and_port_independent(pg,monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_SECRET','controlled-test-secret'*3)
    def attempt(index):
        with factory()() as db:
            try:consume(db,scope(host='one.test:'+str(8000+index)),'new_session',5,3600);return True
            except AdmissionDenied:return False
    with ThreadPoolExecutor(max_workers=10) as pool:assert sum(pool.map(attempt,range(10)))==5
    with factory()() as db:
        records=db.scalars(select(AdmissionBucket)).all();assert len(records)==1
        assert records[0].count==5
        assert '203.0.113' not in records[0].id
        assert len(records[0].id)==64

@pytest.mark.asyncio
async def test_request_body_size_and_timeout_before_app(monkeypatch):
    invoked=[];sent=[]
    async def app(*args):invoked.append(True)
    guard=RequestGuard(app)
    async def receive():return {'type':'http.request','body':b'a'*30,'more_body':False}
    async def send(message):sent.append(message)
    sc=scope();sc['headers'].append((b'content-length',b'999999999'))
    await guard(sc,receive,send)
    assert sent[0]['status']==413
    assert not invoked

@pytest.mark.asyncio
async def test_streamed_body_limit_and_deadline(pg,monkeypatch):
    from app.security import seed
    monkeypatch.setenv('TENANTS_JSON','[{"host":"one.test","slug":"one"}]')
    with factory()() as db:seed(db)
    monkeypatch.setenv('RATE_LIMIT_SECRET','controlled-test-secret'*3)
    monkeypatch.setenv('MAX_UPLOAD_REQUEST_BYTES','10')
    invoked=[];sent=[]
    async def app(*args):invoked.append(True)
    guard=RequestGuard(app)
    async def send(message):sent.append(message)
    async def large():return {'type':'http.request','body':b'x'*11,'more_body':False}
    await guard(scope(),large,send)
    assert sent[0]['status']==413 and not invoked
    sent.clear();monkeypatch.setenv('REQUEST_BODY_TIMEOUT_SECONDS','0.01')
    async def slow():await asyncio.sleep(.2);return {'type':'http.request','body':b'','more_body':False}
    await guard(scope(),slow,send)
    assert sent[0]['status']==408 and not invoked

def test_invalid_host_is_rejected_without_parser_crash():
    from app.security import host_name
    from fastapi import HTTPException
    for value in ('[broken','one.test:not-a-port','evil@one.test','one.test/path','one.test\\evil'):
        with pytest.raises(HTTPException) as error:host_name(value)
        assert error.value.status_code==421
    assert host_name('ONE.TEST:8080')=='one.test'
