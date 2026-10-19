"""Integration DB must be a disposable PostgreSQL database, never production."""
import os,json,hashlib
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import create_engine,text
from app.db import Base

@pytest.fixture
def pg(monkeypatch,tmp_path):
    url=os.getenv('TEST_DATABASE_URL')
    if not url: pytest.skip('TEST_DATABASE_URL disposable PostgreSQL required')
    monkeypatch.setenv('DATABASE_URL',url)
    monkeypatch.setenv('DATA_DIR',str(tmp_path))
    # Explicit synthetic QA contract; never a production pricing fallback.
    instant=datetime.now(timezone.utc)
    contract={'version':1,'currency':'USD','verified_by':'QA synthetic fixture, not actual live rates','verified_at':(instant-timedelta(minutes=1)).isoformat(),'expires_at':(instant+timedelta(hours=1)).isoformat(),'source':'https://openai.com/api/pricing/','models':{'gpt-4.1-mini':{'kind':'responses','input_usd_per_million':'1','output_usd_per_million':'1'},'gpt-image-1.5':{'kind':'image','text_input_usd_per_million':'1','image_input_usd_per_million':'1','text_output_usd_per_million':'1','image_output_usd_per_million':'1'}}}
    price=tmp_path/'synthetic-fixture-pricing.json';price.write_text(json.dumps(contract));price.chmod(0o600)
    monkeypatch.setenv('VERIFIED_PRICING_FILE',str(price));monkeypatch.setenv('VERIFIED_PRICING_SHA256',hashlib.sha256(price.read_bytes()).hexdigest())
    engine=create_engine(url)
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine); engine.dispose()
