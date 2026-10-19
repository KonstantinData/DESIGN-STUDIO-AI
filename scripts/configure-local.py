#!/usr/bin/env python3
"""Create a private, provider-disabled local environment without replacing existing files."""
import json
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent
path = root / '.env'
tenants = [
    {'host': 'localhost', 'slug': 'mein-kuechenexperte', 'brand': 'Mein Küchenexperte', 'expert_name': 'Konstantin', 'budget_cents': 500, 'enabled': True},
    {'host': 'tenant-two.localhost', 'slug': 'isolation-check', 'brand': 'Isolationsprüfung', 'expert_name': 'Planungsteam', 'budget_cents': 500, 'enabled': True},
]
contents = '\n'.join([
    f'POSTGRES_PASSWORD={secrets.token_hex(32)}',
    f'POSTGRES_ADMIN_PASSWORD={secrets.token_hex(32)}',
    "TENANTS_JSON='" + json.dumps(tenants, ensure_ascii=False) + "'",
    'SITE_ADDRESSES=http://localhost:8080, http://tenant-two.localhost:8080',
    'HEALTH_HOST=localhost',
    'HTTP_BIND=127.0.0.1',
    'HTTPS_BIND=127.0.0.1',
    'PROVIDER_ENABLED=false',
    'BUDGET_APPROVED=false',
    'GLOBAL_KILL_SWITCH=true',
    'GLOBAL_BUDGET_CENTS=500',
    'ALLOW_LOCAL_HTTP=true',
    '',
])
try:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('Existing .env preserved; configuration not changed.')
else:
    with os.fdopen(descriptor, 'w') as output:
        output.write(contents)
    print('Created private .env: local HTTP, two tenant hosts, provider disabled.')
