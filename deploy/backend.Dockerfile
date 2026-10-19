FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=secret,id=cloud_ca,required=false \
    if [ -f /run/secrets/cloud_ca ]; then export SSL_CERT_FILE=/run/secrets/cloud_ca REQUESTS_CA_BUNDLE=/run/secrets/cloud_ca UV_SYSTEM_CERTS=true; fi; \
    pip install --no-cache-dir uv==0.12.23 && uv sync --frozen --no-dev --no-install-project && groupadd --gid 10001 studio && useradd --uid 10001 --gid studio --no-create-home studio && mkdir -p /var/lib/studio/private /var/lib/studio/deletions /etc/studio/pricing && chown studio:studio /var/lib/studio/private /var/lib/studio/deletions /etc/studio/pricing
COPY --chown=studio:studio backend/ ./
USER studio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers", "--limit-concurrency", "32", "--backlog", "128"]
