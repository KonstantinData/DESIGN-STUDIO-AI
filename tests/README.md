# Independent verification

These checks do not establish that real generated kitchens satisfy product requirements.
All paid provider calls remain disabled. See `docs/acceptance.md` for exact scope.

Run Python checks only against a dedicated, migrated QA PostgreSQL database, with
`DATABASE_URL`, `TENANTS_JSON` (the local `mein-kuechenexperte` / `isolation-check`
tenants), `PROVIDER_ENABLED=false`, `ALLOW_LOCAL_HTTP=false`, and a private
`DATA_DIR`. Do not print environment values or credentials. Backend dependencies
must be installed first. The lifecycle checks create synthetic test data and
adjust their own accounting fixtures; do not run them against production.

```sh
cd /path/to/DESIGN-STUDIO-AI
PYTHONPATH=backend backend/.venv/bin/python tests/independent_http.py
PYTHONPATH=backend backend/.venv/bin/python tests/independent_lifecycle.py
PYTHONPATH=backend backend/.venv/bin/python tests/independent_billing.py
PYTHONPATH=backend backend/.venv/bin/python tests/independent_results.py
node tests/browser-smoke.cjs
```

Browser smoke requires Playwright resolvable by Node and Chromium at
`/usr/bin/chromium` (or `CHROMIUM_PATH`), plus a running local stack at
`http://localhost:8080` (or `STUDIO_TEST_URL`). It sends real HTTP requests;
it does not replace backend responses. It verifies the provider-disabled UI,
not a rendered-image journey. The app must remain provider-disabled.

The lifecycle test replaces only the outgoing Handoff transport with an
explicitly controlled acknowledgement and verifies exact serialized payload.
It also controls readiness/challenge solely to test retry admission; queued
fixtures are never executed by a provider worker. Billing evidence in the
billing test is explicitly synthetic, never proof of actual vendor charges.

`independent_results.py` injects an explicitly QA-labelled local image provider only in its process; real routes and PostgreSQL persist the workflow. It must use its own database without a production worker. Set QA tenant/account budgets to 5000 cents for these controlled quota tests; no actual provider charges occur.
