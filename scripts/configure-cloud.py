#!/usr/bin/env python3
"""Persist a local Compose overlay for the platform's existing proxy and CA, never secrets."""
import json
import os
from pathlib import Path
import socket
from urllib.parse import urlsplit

root = Path(__file__).resolve().parent.parent
if not os.environ.get('HTTPS_PROXY'):
    raise SystemExit(0)
ca = os.environ.get('SSL_CERT_FILE', '/etc/ssl/certs/ca-certificates.crt')
if not Path(ca).is_file():
    raise SystemExit('Configured TLS trust bundle does not exist; no verification bypass allowed.')
hosts = {}
for name in ('HTTPS_PROXY', 'HTTP_PROXY'):
    hostname = urlsplit(os.environ.get(name, '')).hostname
    if hostname:
        hosts[hostname] = socket.gethostbyname(hostname)
build = {'extra_hosts': hosts, 'network': 'host', 'args': ['HTTP_PROXY', 'HTTPS_PROXY'], 'secrets': ['cloud_ca']}
runtime = {
    'HTTP_PROXY': '${HTTP_PROXY:-}', 'HTTPS_PROXY': '${HTTPS_PROXY:-}',
    'NO_PROXY': '${NO_PROXY:-},db,backend,localhost,127.0.0.1',
    'SSL_CERT_FILE': '/run/cloud-ca.pem',
}
services = {}
for name in ('backend', 'worker', 'migrate'):
    services[name] = {'build': build, 'environment': runtime, 'extra_hosts': hosts,
                      'volumes': [{'type': 'bind', 'source': ca, 'target': '/run/cloud-ca.pem', 'read_only': True}]}
services['web'] = {'build': build}
config = {'services': services, 'secrets': {'cloud_ca': {'file': ca}}}
path = root / '.runtime/compose.cloud.json'
path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
path.write_text(json.dumps(config, indent=2) + '\n')
path.chmod(0o600)
print('Configured private cloud Compose overlay: existing proxy and verified TLS trust.')
