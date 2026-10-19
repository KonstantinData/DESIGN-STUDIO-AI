"""Source repository boundary, with a safe installed-package boundary fallback."""
from pathlib import Path

def checkout_root(source=None):
    source=Path(source or __file__).resolve()
    for candidate in source.parents:
        if candidate==candidate.parent:break  # '/' is never a repository exclusion root.
        marker=candidate/'.git'
        repository=(marker/'HEAD').is_file()
        if marker.is_file():
            try:repository=marker.read_text()[:7]=='gitdir:'
            except OSError:pass
        if repository or (candidate/'compose.yaml').is_file():return candidate
    # Deployed image layout: /app/app/module.py -> package deployment root /app.
    fallback=source.parent.parent
    return fallback if fallback!=fallback.parent else Path('/app')
