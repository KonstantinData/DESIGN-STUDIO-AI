from pathlib import Path
from app.paths import checkout_root

def test_checkout_boundary_and_installed_image_layout(tmp_path):
    repository=tmp_path/'repo';(repository/'.git').mkdir(parents=True);(repository/'.git'/'HEAD').write_text('ref: refs/heads/main\n')
    module=repository/'backend'/'app'/'costing.py';module.parent.mkdir(parents=True);module.touch()
    assert checkout_root(module)==repository
    deployed=tmp_path/'installed'/'app'/'costing.py';deployed.parent.mkdir(parents=True);deployed.touch()
    assert checkout_root(deployed)==tmp_path/'installed'
    assert checkout_root('/app/app/costing.py')==Path('/app')
    assert not Path('/run/pricing/private.json').is_relative_to(checkout_root('/app/app/costing.py'))
