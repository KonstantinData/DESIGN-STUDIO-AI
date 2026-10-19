"""Offline contract verification only; MockTransport never calls OpenAI."""
import asyncio
import base64
import io
import json

import httpx
import pytest
from PIL import Image

from app.provider import Provider, ProviderError, ProviderPreflightError, _validate, BRIEF_SCHEMA


def image_bytes():
    out = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(out, "PNG")
    return out.getvalue()


def brief():
    return {"version": 1, "source_kind": "text", "usable": True,
            "rejection_reason": None,
            "room": {"version": 1, "description": "Beispielraum", "features": [
                {"name": "Fenster", "value": "Nordwand", "provenance": "ASSUMED"}],
                "constraints": ["Fensterposition erhalten"]},
            "user_brief": "Helle Küche", "concepts": {key: {
                "title": key, "layout": "L-Form", "materials": "Holz", "lighting": "Tageslicht"}
                for key in "ABC"}, "assumptions": ["Raum ist angenommen"]}


def structured(value):
    return {"status": "completed", "usage": {"input_tokens": 12},
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": json.dumps(value)}]}]}


def test_source_quality_gate_and_single_request():
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            body = json.loads(request.content)
            assert body["store"] is False
            assert body["service_tier"] == "default"
            assert body["max_output_tokens"] == 6000
            assert body["text"]["format"]["strict"] is True
            assert body["input"][0]["content"][1]["type"] == "input_image"
            result = brief()
            result.update(source_kind="floorplan", usable=False,
                          rejection_reason="Grundriss nicht lesbar")
            return httpx.Response(200, json=structured(result))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = Provider(api_key="test-only", client=client)
            result = await provider.brief("", image_bytes(), "floorplan")
            assert result["usable"] is False
            with pytest.raises(ProviderError):
                await provider.render(result, "A", None, image_bytes())
        assert len(calls) == 1
    asyncio.run(run())


def test_generation_and_edit_contract_and_usage():
    async def run():
        calls = []
        raw = image_bytes()
        def handler(request):
            calls.append(request)
            if request.url.path.endswith("generations"):
                body = json.loads(request.content)
                assert body["model"] == "gpt-image-1.5"
                assert body["n"] == 1
                assert body["output_format"] == "png"
                assert "response_format" not in body
            else:
                assert request.url.path.endswith("edits")
                assert "multipart/form-data" in request.headers["content-type"]
                assert b'name="input_fidelity"\r\n\r\nhigh' in request.content
                assert b'name="image"' in request.content
            return httpx.Response(200, headers={"x-request-id": "offline-123"},
                                  json={"data": [{"b64_json": base64.b64encode(raw).decode()}],
                                        "usage": {"total_tokens": 123}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = Provider(api_key="test-only", client=client)
            generated = await provider.render(brief(), "B", None, None)
            edited = await provider.render(brief(), "C", "Oberflächen aus Eiche", raw)
            assert generated == edited == raw
            assert generated.usage == {"total_tokens": 123}
            assert generated.request_id == "offline-123"
            assert generated.model == "gpt-image-1.5"
            assert generated.model_identity_source == "request"
        assert len(calls) == 2
    asyncio.run(run())


@pytest.mark.parametrize("review", [
    {"lines": ["Raum", "Licht"], "critical_error": False, "critical_reason": None},
    {"lines": ["Raum\nUmbruch", "Licht", "Holz"], "critical_error": False, "critical_reason": None},
    {"lines": ["Raum", "Licht", "Holz"], "critical_error": True, "critical_reason": None},
])
def test_invalid_reviews_are_never_replaced_with_canned_report(review):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=structured(review)))) as client:
            with pytest.raises(ProviderError):
                await Provider(api_key="test-only", client=client).curate(image_bytes(), brief(), "A")
    asyncio.run(run())


def test_critical_shadow_review_retains_evidence():
    async def run():
        review = {"lines": ["Versetztes Fenster", "Helle Fronten", "Holz und Weiß"],
                  "critical_error": True, "critical_reason": "Fensterposition weicht ab"}
        def handler(request):
            assert json.loads(request.content)["max_output_tokens"] == 1200
            return httpx.Response(200, json=structured(review))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await Provider(api_key="test-only", client=client).curate(image_bytes(), brief(), "B")
            assert result["critical_error"] is True
            assert result["critical_reason"] == review["critical_reason"]
            assert len(result["lines"]) == 3
    asyncio.run(run())


def test_unbounded_text_never_reaches_transport():
    async def run():
        def handler(request):
            raise AssertionError("Oversized input must fail before network access")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ProviderPreflightError, match="Länge"):
                await Provider(api_key="test-only", client=client).brief("x" * 65536, None, "text")
    asyncio.run(run())


def test_image_dimension_bound_precedes_provider_request():
    async def run():
        out = io.BytesIO()
        Image.new("RGB", (4097, 16), "white").save(out, "PNG")
        def handler(request):
            raise AssertionError("Oversized image must fail before network access")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = Provider(api_key="test-only", client=client)
            with pytest.raises(ProviderPreflightError, match="4096"):
                await provider.brief("", out.getvalue(), "photo")
            with pytest.raises(ProviderPreflightError, match="4096"):
                await provider.render(brief(), "A", None, out.getvalue())
    asyncio.run(run())


def test_errors_never_expose_upstream_bodies_and_do_not_retry():
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429, json={"error": "secret and private content"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ProviderError) as caught:
                await Provider(api_key="test-only", client=client).brief("private prompt", None, "text")
            assert caught.value.retryable
            assert caught.value.status_code == 429
            assert not isinstance(caught.value, ProviderPreflightError)
            assert "private" not in str(caught.value)
            assert "secret" not in str(caught.value)
        assert len(calls) == 1
    asyncio.run(run())


@pytest.mark.parametrize("operation", ["bad_source", "bad_kind", "bad_render", "long_render"])
def test_local_failures_have_proven_no_request_classification(operation):
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            raise AssertionError("Local failure must not reach transport")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = Provider(api_key="test-only", client=client)
            with pytest.raises(ProviderPreflightError):
                if operation == "bad_source":
                    await provider.brief("", b"invalid image", "photo")
                elif operation == "bad_kind":
                    await provider.brief("", None, "other")
                elif operation == "bad_render":
                    await provider.render(brief(), "Z", None, None)
                else:
                    await provider.render(brief(), "A", "x" * 32000, None)
        assert calls == []
    asyncio.run(run())


def test_transport_failure_retains_uncertain_cost_classification():
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.ReadTimeout("private request detail", request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ProviderError) as caught:
                await Provider(api_key="test-only", client=client).brief("Küche", None, "text")
            assert not isinstance(caught.value, ProviderPreflightError)
            assert caught.value.retryable
        assert len(calls) == 1
    asyncio.run(run())


def test_invalid_returned_image_is_not_a_local_preflight_failure():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(b"invalid").decode()}]}))) as client:
            with pytest.raises(ProviderError) as caught:
                await Provider(api_key="test-only", client=client).render(brief(), "A", None, None)
            assert not isinstance(caught.value, ProviderPreflightError)
    asyncio.run(run())


def test_strict_schema_refuses_extra_fields_and_fabricated_provenance():
    value = brief()
    assert _validate(value, BRIEF_SCHEMA)
    value["room"]["features"][0]["provenance"] = "VERIFIED"
    assert not _validate(value, BRIEF_SCHEMA)
    value = brief()
    value["unexpected"] = "value"
    assert not _validate(value, BRIEF_SCHEMA)


def test_no_key_never_issues_a_request():
    async def run():
        def handler(request):
            raise AssertionError("Network call must never be attempted")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ProviderError, match="fehlt"):
                await Provider(api_key="", client=client).brief("Küche", None, "text")
    asyncio.run(run())


@pytest.mark.parametrize("returned_model", [None, "gpt-4.1-mini-2025-04-14"])
def test_responses_model_identity_comes_only_from_upstream(returned_model):
    async def run():
        payload = structured(brief())
        if returned_model is not None:
            payload["model"] = returned_model
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload))) as client:
            result = await Provider(api_key="test-only", text_model="gpt-4.1-mini", client=client).brief("Küche", None, "text")
            assert result["_provider_model"] == returned_model
            assert result["_provider_model_identity_source"] == ("response" if returned_model else None)
    asyncio.run(run())


@pytest.mark.parametrize("payload,expected", [
    ({"error": {"type": "invalid_request_error", "code": None,
                "message": "Your organization must be verified to use this model. private upload secret"}},
     "organization_verification_required"),
    ({"error": {"type": "permission_error", "code": "organization_verification_required",
                "message": "private prompt secret"}}, "organization_verification_required"),
    ({"error": {"type": "private prompt secret", "code": "sk-private-secret",
                "message": "private upload secret"}}, "provider_http_error"),
    ({"error": "private prompt secret"}, "provider_http_error"),
    ({}, "provider_http_error"),
])
def test_http_error_diagnostics_keep_only_allowlisted_metadata(payload, expected):
    async def run():
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(403, headers={"x-request-id": "req_offline_123"}, json=payload)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ProviderError) as caught:
                await Provider(api_key="test-only", client=client).brief("private prompt", None, "text")
        error = caught.value
        diagnostics = error.safe_diagnostics()
        assert diagnostics["provider_error_classification"] == expected
        assert diagnostics["provider_request_id"] == "req_offline_123"
        assert diagnostics["provider_status_code"] == 403
        assert diagnostics["provider_retryable"] is False
        exposed = str(error) + json.dumps(diagnostics)
        assert "private" not in exposed
        assert "secret" not in exposed
        assert "upload" not in exposed
        assert len(calls) == 1
    asyncio.run(run())


def test_unknown_http_error_code_type_and_request_id_are_discarded():
    async def run():
        response = httpx.Response(403, headers={"x-request-id": "sk-private-secret"},
                                 json={"error": {"code": ["private"], "type": {"secret": 1}}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as client:
            with pytest.raises(ProviderError) as caught:
                await Provider(api_key="test-only", client=client).brief("Küche", None, "text")
            diagnostics = caught.value.safe_diagnostics()
            assert diagnostics["provider_error_code"] is None
            assert diagnostics["provider_error_type"] is None
            assert diagnostics["provider_request_id"] is None
    asyncio.run(run())


def test_worker_records_safe_failure_metadata_and_retains_unknown_cost(monkeypatch):
    from types import SimpleNamespace
    from app import worker

    reservations = []
    settlements = []
    monkeypatch.setattr(worker, "load_contract", lambda: SimpleNamespace(
        value={"models": {"gpt-image-1.5": {"kind": "image"}}}))
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-1.5")
    # This isolated transport diagnostic injects its already-verified local guards.
    monkeypatch.setattr(worker, "ready", lambda tenant: (True, None))
    async def offline_route(): return None
    monkeypatch.setattr(worker, "route_preflight", offline_route)
    offline_db=SimpleNamespace(get=lambda *args:SimpleNamespace(tenant_id="offline-tenant"))
    monkeypatch.setattr(worker, "reserve", lambda db, job, amount:
                        reservations.append(amount) or "offline-reservation")
    monkeypatch.setattr(worker, "settle", lambda db, ident, details, **kwargs:
                        settlements.append((details, kwargs)))

    async def run():
        response = httpx.Response(403, headers={"x-request-id": "req_offline_403"}, json={
            "error": {"type": "invalid_request_error", "code": None,
                      "message": "Your organization must be verified. private prompt secret"}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as client:
            provider = Provider(api_key="test-only", client=client)
            with pytest.raises(ProviderError):
                await worker.paid(offline_db, SimpleNamespace(id="offline-job"), "image",
                                  lambda: provider.render(brief(), "A", None, None))
    asyncio.run(run())
    assert reservations == [100]
    assert len(settlements) == 1
    details, kwargs = settlements[0]
    assert details["provider_error_classification"] == "organization_verification_required"
    assert details["provider_request_id"] == "req_offline_403"
    assert details["actual_cost_cents"] is None
    assert kwargs == {}  # Never releases unknown post-request exposure.
    assert "private" not in json.dumps(details)
    assert "secret" not in json.dumps(details)


def test_optional_reference_model_routes_all_reference_sources_and_identity(monkeypatch):
    """Offline payload/identity evidence only, no actual image generation."""
    monkeypatch.setenv('OPENAI_REFERENCE_IMAGE_MODEL','gpt-image-1')
    async def run():
        calls=[];raw=image_bytes()
        def handler(request):
            calls.append(request)
            if request.url.path.endswith('generations'):
                assert json.loads(request.content)['model']=='gpt-image-1.5'
            else:
                assert request.url.path.endswith('edits')
                assert b'name="model"\r\n\r\ngpt-image-1\r\n' in request.content
                assert b'name="input_fidelity"\r\n\r\nhigh' in request.content
            return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(raw).decode()}],'usage':{}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider=Provider(api_key='test-only',image_model='gpt-image-1.5',client=client)
            generated=await provider.render(brief(),'A',None,None)
            assert generated.model=='gpt-image-1.5'
            for kind,change in [('photo',None),('floorplan',None),('text','Oberflächen aus Eiche')]:
                source_brief=brief();source_brief['source_kind']=kind
                result=await provider.render(source_brief,'A',change,raw)
                assert result.model=='gpt-image-1' and result.model_identity_source=='request'
        assert len(calls)==4
    asyncio.run(run())


def test_reference_model_default_tracks_explicit_generation_model(monkeypatch):
    monkeypatch.delenv('OPENAI_REFERENCE_IMAGE_MODEL',raising=False)
    provider=Provider(api_key='test-only',image_model='gpt-image-1.5')
    assert provider.reference_image_model==provider.image_model=='gpt-image-1.5'


def test_reference_aspect_bound_is_verified_before_any_provider_call():
    async def run():
        raw=io.BytesIO();Image.new('RGB',(4096,128)).save(raw,'PNG')
        async def handler(request):raise AssertionError('Aspect over16:1 must never incur a provider call')
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider=Provider(api_key='test-only',reference_image_model='gpt-image-1',client=client)
            with pytest.raises(ProviderPreflightError,match='16:1'):
                await provider.render(brief(),'A',None,raw.getvalue())
    asyncio.run(run())
