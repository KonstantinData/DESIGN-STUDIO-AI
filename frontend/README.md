# Studio frontend

React / TypeScript application with a same-origin FastAPI backend. No browser API keys, generated example gallery, artificial curation or fallback images are included. Tenant branding and generation readiness are read at runtime from `/api/config`.

## Development

Use Node 24 and the committed npm lockfile:

```sh
npm ci
npm run dev
```

Vite listens on port 5173 and proxies `/api` to `http://127.0.0.1:8000`. The backend's strict Host, Origin, secure-cookie and CSRF configuration still applies. For an integrated private-browser test use the HTTPS Compose/Caddy setup in [operations](../docs/operations.md); a standalone dev server does not prove authenticated integration.

```sh
npm test
npm run build
npm audit
```

`dist/` is the production artifact. It contains no secrets and needs no build-time environment variables. Production requests must use the same origin; see [API contract](../docs/api.md). Serve the SPA and `/api` through the configured HTTPS proxy, not Vite's development server.

## Private state and external calls

- The server controls tenant identity, media authorization, hard budget stops, quotas and the customer change allowance.
- Session authorization uses an HttpOnly server cookie. CSRF tokens stay in memory; continuation codes are submitted by POST and never included in URLs. Session storage contains at most a non-secret studio identifier.
- Images and downloads use only same-origin `/api/media/` routes. No external placeholder media, fonts or analytics are loaded.
- Cloudflare Turnstile loads only when generation is ready and the runtime configuration supplies a site key. A missing key never creates a client bypass; backend readiness and challenge verification remain authoritative.
- Room corrections, revision viewing/selection and downloads do not issue rendering requests. Material and layout changes explicitly include the revision serving as their starting point.
- Handoff success requires the backend's confirmed `accepted` result. Contact and image sharing require explicit consent. Each handoff sends one selected revision, its necessary briefing, and only its optionally selected result image.

## Verification limits

The frontend build and security boundary tests are independent from product acceptance. A real provider-backed text/photo/floorplan run, manually reviewed image geometry and curation, live bot validation, actual private-image downloads, assistive browser testing and a confirmed downstream handoff remain release requirements. A configured HTTP server or an empty studio is not a completed product result. The application shows missing provider/budget configuration and does not replace it with demonstration content.

## Controlled browser workflow regression tests

After `npm ci` and `npm run build`, run:

```sh
npm run test:browser
```

The runner starts a private production-preview server on `127.0.0.1:4175`, opens real Chromium, and intercepts API requests **inside the test browser only**. Chromium must be installed. The runner uses `CHROMIUM_PATH` when provided, otherwise `/usr/bin/chromium` if available, otherwise the browser installed by the locked Playwright package. CI installs the browser and system prerequisites with `npx playwright install --with-deps chromium` before this command. The locked Playwright dependency is used. No test routes, fixture images or generation bypasses are compiled into the production application.

Fifteen browser workflows verify progressive A/B/C arrivals, independent failure, keyboard navigation, original-revision material/layout changes, lost-response idempotency, accepted-job refresh failures, room corrections, private-state expiry/deletion, selected-revision handoff, quota retention and image retry. Test images are three different 640×480 PNGs visibly labeled **QA ONLY**; they are not kitchen renders or evidence of image-generation acceptance. Browser reports are written to `/tmp/design-studio-workflow-report.json`, with a clearly labeled fixture screenshot at `/tmp/design-studio-workflow-qa-fixtures.png`. All external requests are blocked in these contexts.

The controlled download check verifies the same-origin media URL and fetched binary; native authenticated downloads require the separate live-backend acceptance tests. These isolated browser checks never call a paid provider or claim to prove real image quality, bot verification or downstream delivery.
