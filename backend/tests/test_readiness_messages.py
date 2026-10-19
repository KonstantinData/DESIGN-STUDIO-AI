"""Manual operator holds must not be presented as budget exhaustion."""
from types import SimpleNamespace
import pytest
from app.security import ready

@pytest.mark.parametrize('file_hold',[False,True])
def test_manual_hold_explains_pending_release_without_claiming_spend(tmp_path,monkeypatch,file_hold):
    monkeypatch.setenv('DATA_DIR',str(tmp_path))
    monkeypatch.setenv('GLOBAL_KILL_SWITCH','false' if file_hold else 'true')
    if file_hold:(tmp_path/'STOP_GENERATION').touch()
    enabled,reason=ready(SimpleNamespace(enabled=True))
    assert enabled is False
    assert reason=='Bildgenerierung ist noch nicht freigegeben.'
    assert 'ausgeschöpft' not in reason and 'Kostenstopp' not in reason
