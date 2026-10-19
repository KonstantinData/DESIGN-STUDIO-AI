#!/usr/bin/env python3
"""Exercise real isolated nginx → Caddy → echo with the deployment configs.

Requires Docker, existing Caddy/Python images and nginx:1.28.0-alpine.
Never mounts runtime data, secrets, or the application's existing networks.
"""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PREFIX = f"studio-proxy-test-{os.getpid()}"
NGINX_IMAGE = "nginx:1.28.0-alpine@sha256:30f1c0d78e0ad60901648be663a710bdadf19e4c10ac6782c235200619158284"
containers, networks = [], []


def docker(*args):
    result = subprocess.run(["docker", *args], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"docker {' '.join(args[:3])}: {result.stderr.strip()}")
    return result.stdout.strip()


def run(name, *args):
    name = PREFIX + "-" + name
    containers.append(name)
    # Docker client configuration injects the cloud egress proxy automatically.
    # This fixture talks only to its private local containers, never the internet.
    proxy_environment = []
    for variable in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        proxy_environment.extend(["-e", variable + "="])
    docker("run", "-d", "--name", name, *proxy_environment, *args)
    return name


def request(port, host, auth=True, spoof=False):
    headers = {"Host": host}
    if auth:
        headers["Authorization"] = "Basic " + base64.b64encode(b"fixture:fixture-password").decode()
    if spoof:
        headers.update({"X-Forwarded-For": "198.51.100.66, 203.0.113.77", "Forwarded": "for=198.51.100.66", "X-Real-IP": "198.51.100.66"})
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/proxy-proof", headers=headers)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def main():
    nginx = (ROOT / "deploy/nginx.studio-http.conf").read_text()
    host = re.search(r"server_name\s+([^;\s]+)", nginx).group(1)
    # These two port substitutions are the only changes to the reviewed nginx site.
    nginx, listens = re.subn(r"(?m)^(\s*listen\s+)(?:\[::\]:)?80(?=\s|;)", r"\g<1>127.0.0.1:18888", nginx)
    assert listens == 1, "Expected one HTTP listen directive"
    assert "127.0.0.1:8788" in nginx
    nginx = nginx.replace("127.0.0.1:8788", "127.0.0.1:18788")
    caddy = ROOT / "deploy/Caddyfile.hetzner"
    assert caddy.exists()
    with tempfile.TemporaryDirectory(prefix=PREFIX + "-") as temporary:
        folder = Path(temporary)
        # The runtime UID is 10001; configuration contains no secrets.
        fixture_caddy = folder / "Caddyfile"
        fixture_caddy.write_bytes(caddy.read_bytes())
        fixture_caddy.chmod(0o444)
        (folder / "nginx.conf").write_text("events {}\nhttp {\n" + nginx + "\n}\n")
        (folder / "echo.py").write_text('''import json
from http.server import BaseHTTPRequestHandler, HTTPServer
class Echo(BaseHTTPRequestHandler):
    def do_GET(self):
        body=json.dumps({"peer":self.client_address[0],"headers":dict(self.headers)}).encode()
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(body)
    def log_message(self,*args): pass
HTTPServer(("0.0.0.0",8000),Echo).serve_forever()
''')
        edge, private = PREFIX + "-edge", PREFIX + "-private"
        for name, subnet, gateway, allocation in [(edge,"172.30.75.0/28","172.30.75.1","172.30.75.8/29"),(private,"172.30.76.0/28","172.30.76.1","172.30.76.8/29")]:
            docker("network", "create", "--subnet", subnet, "--gateway", gateway, "--ip-range", allocation, name)
            networks.append(name)
        run("echo", "--network", private, "--ip", "172.30.76.3", "--network-alias", "backend", "-v", f"{folder}/echo.py:/fixture.py:ro", "python:3.12.13-slim-bookworm", "python", "/fixture.py")
        password_hash = docker("run", "--rm", "design-studio-ai-web", "caddy", "hash-password", "--plaintext", "fixture-password")
        web = run("caddy", "--network", edge, "--ip", "172.30.75.2", "--add-host", "backend:172.30.76.3", "-p", "127.0.0.1:18788:8080", "-e", f"SITE_ADDRESSES=http://{host}:8080", "-e", "STUDIO_REVIEW_USERNAME=fixture", "-e", f"STUDIO_REVIEW_PASSWORD_HASH={password_hash}", "-v", f"{fixture_caddy}:/etc/caddy/Caddyfile:ro", "design-studio-ai-web")
        docker("network", "connect", "--ip", "172.30.76.2", private, web)
        direct = docker("exec", web, "wget", "-qO-", "http://172.30.76.3:8000/api/proxy-proof")
        assert json.loads(direct)["peer"] == "172.30.76.2", direct
        nginx_name = run("nginx", "--network", "host", "-v", f"{folder}/nginx.conf:/etc/nginx/nginx.conf:ro", NGINX_IMAGE)
        deadline = time.monotonic() + 25
        while True:
            try:
                status, _ = request(18888, host, auth=False)
                if status == 401:
                    break
            except (OSError, urllib.error.URLError):
                pass
            if time.monotonic() > deadline:
                raise AssertionError("nginx/Caddy did not return Basic Auth 401")
            time.sleep(0.3)
        results = {"unauthenticated_status": status, "host": host}
        for spoof in (False, True):
            status, body = request(18888, host, spoof=spoof)
            assert status == 200, (status, body)
            response = json.loads(body)
            headers = {key.lower(): value for key, value in response["headers"].items()}
            assert headers["x-forwarded-for"] == "127.0.0.1", response
            assert "forwarded" not in headers and "x-real-ip" not in headers, response
            assert response["peer"] == "172.30.76.2", response
            results["forged_headers" if spoof else "normal_headers"] = response
        # Bypassing nginx from an untrusted edge peer must not grant trust to its XFF.
        forged = docker("run", "--rm", "--network", edge, "-e", "http_proxy=", "-e", "HTTP_PROXY=", "--entrypoint", "wget", "design-studio-ai-web", "-qO-", "--header", f"Host: {host}", "--header", "Authorization: Basic Zml4dHVyZTpmaXh0dXJlLXBhc3N3b3Jk", "--header", "X-Forwarded-For: 198.51.100.66", "http://172.30.75.2:8080/api/proxy-proof")
        peer_response = json.loads(forged)
        forwarded = {k.lower(): v for k,v in peer_response["headers"].items()}["x-forwarded-for"]
        assert forwarded != "198.51.100.66" and forwarded.startswith("172.30.75."), peer_response
        results["untrusted_edge_peer_forwarded_as"] = forwarded
        results["result"] = "PASS"
        print(json.dumps(results, indent=2))


try:
    main()
except Exception:
    for container in containers:
        logs = subprocess.run(["docker", "logs", "--tail", "15", container], text=True, capture_output=True)
        print(logs.stdout + logs.stderr)
    raise
finally:
    for container in reversed(containers):
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
    for network in reversed(networks):
        subprocess.run(["docker", "network", "rm", network], capture_output=True)
