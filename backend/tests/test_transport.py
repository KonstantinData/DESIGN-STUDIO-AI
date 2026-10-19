"""Offline route availability evidence; never uses an API credential or real network."""
import asyncio
import httpx
import pytest
from app.transport import RouteProbe,RouteUnavailable

@pytest.mark.asyncio
async def test_anonymous_reachable_401_cached_briefly(monkeypatch):
    monkeypatch.setenv('STUDIO_OPENAI_API_KEY','this-must-never-be-read-or-sent')
    calls=[];clock=[100.0]
    async def handler(request):
        calls.append(request)
        assert request.method=='GET' and str(request.url)=='https://api.openai.com/v1/models'
        assert 'authorization' not in request.headers
        return httpx.Response(401)
    probe=RouteProbe(transport=httpx.MockTransport(handler),clock=lambda:clock[0])
    await asyncio.gather(*(probe.check() for _ in range(5)))
    assert len(calls)==1
    clock[0]+=21
    await probe.check();assert len(calls)==2

@pytest.mark.asyncio
async def test_dead_proxy_fails_sanitized_without_auth_or_raw_details():
    async def handler(request):raise httpx.ConnectTimeout('private-proxy-and-request-details-must-not-leak')
    probe=RouteProbe(transport=httpx.MockTransport(handler))
    with pytest.raises(RouteUnavailable) as error:await probe.check()
    assert 'private-proxy' not in str(error.value)

@pytest.mark.asyncio
@pytest.mark.parametrize('status',[302,403,407,429,500])
async def test_only_reachable_accepted_upstream_statuses(status):
    probe=RouteProbe(transport=httpx.MockTransport(lambda request:httpx.Response(status)))
    with pytest.raises(RouteUnavailable):await probe.check()
