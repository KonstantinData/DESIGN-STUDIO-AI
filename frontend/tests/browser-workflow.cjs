// QA ONLY: API fixtures are intercepted inside isolated Chromium contexts.
// No fixture routes, fabricated renders or provider bypasses exist in the application.
// These tests prove browser state transitions, not real AI output or product acceptance.
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const { writeFileSync, existsSync } = require('node:fs');
const assert = require('node:assert/strict');
const path = require('node:path');
const frontend = path.resolve(__dirname, '..');
const origin = process.env.STUDIO_WORKFLOW_URL || 'http://127.0.0.1:4175';
const report = { fixtureOnly: true, providerCalls: 0, checks: [], errors: [] };
const pngFixtures = {};
const config = { brand: 'QA test fixture', expert_name: 'Konstantin', turnstile_site_key: '', generation_ready: true };
function revision(key, number = 1, kind = 'initial', version = 1) {
  return { id: `${key}-${number}`, number, kind, media_id: `media-${key}-${number}`, image_url: `/api/media/media-${key}-${number}`, download_url: `/api/media/media-${key}-${number}?download=1`, curation: [`QA architecture ${key}`, `QA highlight ${key}`, `QA material ${key}`], assumptions: ['Explicit QA-only assumption'], created_at: '2026-10-18T12:00:00Z', room_version: version };
}
function studio() {
  return { id: 'qa-studio', source_kind: 'text', status: 'completed', selected_revision_id: null, changes_remaining: 5, room: { version: 1, description: 'Explicit browser QA room, not an AI result.', features: [{ name: 'Fenster', value: 'Linke Wand', provenance: 'DETECTED' }], constraints: ['Kein Aufmaß'] }, concepts: ['A', 'B', 'C'].map(key => ({ key, title: `QA Konzept ${key}`, status: 'completed', error: null, revisions: [revision(key)] })) };
}
async function json(route, value, status = 200) { return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) }); }
async function check(name, task) { await task(); report.checks.push(name); console.log('PASS ' + name); }
(async () => {
  let server;
  if (!process.env.STUDIO_WORKFLOW_URL) {
    server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4175', '--strictPort'], { cwd: frontend, stdio: ['ignore', 'pipe', 'pipe'] });
    let ready = false;
    for (let attempt = 0; attempt < 100; attempt++) {
      if (server.exitCode !== null) throw new Error('QA preview server exited before startup');
      try { const response = await fetch(origin); if (response.ok) { ready = true; break; } } catch {}
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    if (!ready) { server.kill(); throw new Error('QA preview server did not start'); }
  }
  const executablePath = process.env.CHROMIUM_PATH || (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
  const browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox'] }).catch(error => { if (server) server.kill(); throw error; });
  const imageFactory = await browser.newPage();
  for (const [key, color] of Object.entries({ A: '#9b472b', B: '#2b668e', C: '#506432' })) {
    const base64 = await imageFactory.evaluate(({ key, color }) => { const canvas = document.createElement('canvas'); canvas.width = 640; canvas.height = 480; const ctx = canvas.getContext('2d'); ctx.fillStyle = color; ctx.fillRect(0, 0, 640, 480); ctx.fillStyle = '#fff'; ctx.font = 'bold 64px sans-serif'; ctx.fillText('QA ONLY ' + key, 45, 200); ctx.font = '25px sans-serif'; ctx.fillText('Browserfixture - kein KI-Ergebnis', 45, 260); return canvas.toDataURL('image/png').split(',')[1]; }, { key, color });
    pngFixtures[key] = Buffer.from(base64, 'base64');
  }
  await imageFactory.close();
  let context;
  async function open(options = {}) {
    if (context) await context.close();
    context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
    const page = await context.newPage();
    const state = { studio: studio(), sessions: [{ id: 'qa-studio', status: 'completed' }], posts: [], gets: [], downloads: [], ...options };
    if (options.storedStudio) await page.addInitScript(value => sessionStorage.setItem('design-studio.current-studio', value), options.storedStudio);
    page.on('pageerror', error => report.errors.push(error.message));
    await context.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin !== origin) { report.errors.push('Unexpected external browser request'); return route.abort(); }
      return route.continue();
    });
    await context.route('**/api/**', async route => {
      const request = route.request(); const url = new URL(request.url()); const endpoint = url.pathname;
      if (request.method() === 'GET') state.gets.push(endpoint);
      else {
        assert.equal(request.headers()['x-csrf-token'], 'qa-csrf', 'all fixture mutations require a CSRF token');
        state.posts.push({ endpoint, method: request.method(), body: request.postData(), key: request.headers()['idempotency-key'] });
      }
      if (options.handle && await options.handle({ route, request, endpoint, url, state })) return;
      if (endpoint === '/api/config') return json(route, config);
      if (endpoint === '/api/session') return json(route, { id: 'qa-session', csrf_token: 'qa-csrf', changes_remaining: 5, studios: state.sessions });
      if (endpoint === '/api/studios/qa-studio') return json(route, state.studio);
      if (endpoint === '/api/studios/qa-studio/select') { state.studio.selected_revision_id = request.postDataJSON().revision_id; return json(route, state.studio); }
      if (endpoint === '/api/session/resume-token') return json(route, { token: 'qa-continuation-token-not-production-00000000000000000000000000' });
      if (endpoint.startsWith('/api/media/')) { state.downloads.push(url.search); return route.fulfill({ contentType: 'image/png', headers: url.search ? { 'Content-Disposition': 'attachment; filename="qa-only.png"' } : {}, body: pngFixtures[endpoint.match(/media-([ABC])-/)?.[1] || 'A'] }); }
      throw new Error('Unhandled fixture route ' + endpoint);
    });
    await page.goto(origin, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: 'Was hast Du im Kopf?' }).waitFor();
    await page.getByText('Das Studio wird verbunden …', { exact: true }).waitFor({ state: 'hidden' });
    return { page, state };
  }
  try {
    await check('saved successful studio wins over older failed studio; stale browser id is ignored', async () => {
      const { page, state } = await open({ storedStudio: 'old-failed', sessions: [{ id: 'old-failed', status: 'failed' }, { id: 'qa-studio', status: 'completed' }] });
      await page.getByRole('heading', { name: 'QA Konzept A' }).waitFor();
      assert(!state.gets.includes('/api/studios/old-failed'));
      assert.equal(await page.locator('.curation>div').count(), 9);
    });
    await check('gallery navigation focuses the concept and announces actual available result count', async () => {
      const { page } = await open();
      await page.getByRole('navigation', { name: 'Konzepte direkt öffnen' }).getByRole('link', { name: /Konzept B/ }).click();
      assert.equal(await page.evaluate(() => document.activeElement.id), 'concept-B');
      assert.match(await page.locator('.gallery-announcement').innerText(), /3 von 3/);
    });
    await check('viewing old revisions creates no render; material and layout both retain original A as origin', async () => {
      let accepted = 0;
      const { page, state } = await open({ handle: async ({ route, endpoint, state, request }) => {
        if (endpoint !== '/api/studios/qa-studio/revisions') return false;
        const body = request.postDataJSON(); assert.equal(body.base_revision_id, 'A-1'); assert.equal(body.concept, 'A');
        accepted += 1; state.studio.changes_remaining -= 1;
        state.studio.concepts[0].revisions.push(revision('A', accepted + 1, body.kind));
        await json(route, { job_id: `qa-job-${accepted}` }, 202); return true;
      } });
      const card = page.getByRole('article', { name: 'QA Konzept A' });
      await card.getByRole('button', { name: 'Gezielt verändern' }).click();
      await card.getByLabel('Dein Änderungswunsch').fill('Eiche statt Lack');
      await card.getByRole('button', { name: 'Neue Version erstellen' }).click();
      await card.getByRole('combobox').selectOption('A-1');
      await card.getByRole('button', { name: 'Gezielt verändern' }).click();
      await card.getByRole('radio', { name: 'Aufbau & Anordnung' }).check();
      await card.getByLabel('Dein Änderungswunsch').fill('Mehr Platz im Laufweg');
      await card.getByRole('button', { name: 'Neue Version erstellen' }).click();
      await page.getByText(/Die Änderung für Konzept A/).waitFor();
      assert.deepEqual(state.posts.filter(post => post.endpoint.endsWith('/revisions')).map(post => JSON.parse(post.body).kind), ['material', 'layout']);
      const count = state.posts.length;
      await card.getByRole('combobox').selectOption('A-1');
      await card.getByRole('button', { name: 'Dieses Konzept wählen' }).click();
      assert.equal(state.posts.filter(post => post.endpoint.endsWith('/revisions')).length, 2);
      assert.equal(state.posts.length, count + 1);
      await page.reload();
      assert.equal(await page.getByRole('article', { name: 'QA Konzept A' }).getByRole('combobox').inputValue(), 'A-1');
    });
    await check('accepted render survives refresh failure without offering duplicate render', async () => {
      let failNextRead = false; let changing = false;
      const { page, state } = await open({ handle: async ({ route, endpoint, state }) => {
        if (endpoint.endsWith('/revisions')) { changing = true; failNextRead = true; await json(route, { job_id: 'accepted-qa' }, 202); return true; }
        if (endpoint === '/api/studios/qa-studio' && failNextRead) { failNextRead = false; await route.abort('failed'); return true; }
        if (endpoint === '/api/studios/qa-studio' && changing) { state.studio.status = 'running'; state.studio.concepts[0].status = 'queued'; }
        return false;
      } });
      const card = page.getByRole('article', { name: 'QA Konzept A' });
      await card.getByRole('button', { name: 'Gezielt verändern' }).click();
      await card.getByLabel('Dein Änderungswunsch').fill('Eiche statt Lack');
      await card.getByRole('button', { name: 'Neue Version erstellen' }).click();
      await page.getByText(/Der Änderungsauftrag wurde angenommen/).waitFor();
      await card.getByRole('button', { name: 'Gezielt verändern' }).click();
      assert(await card.getByRole('button', { name: 'Neue Version erstellen' }).isDisabled());
      assert.equal(await card.getByLabel('Dein Änderungswunsch').inputValue(), '');
      assert.equal(state.posts.filter(post => post.endpoint.endsWith('/revisions')).length, 1);
    });
    await check('lost POST response retries with same idempotency key and same origin revision', async () => {
      let calls = 0;
      const { page, state } = await open({ handle: async ({ route, endpoint }) => {
        if (!endpoint.endsWith('/revisions')) return false;
        calls += 1; if (calls === 1) await route.abort('failed'); else await json(route, { job_id: 'qa-recovered' }, 202); return true;
      } });
      const card = page.getByRole('article', { name: 'QA Konzept B' });
      await card.getByRole('button', { name: 'Gezielt verändern' }).click();
      await card.getByLabel('Dein Änderungswunsch').fill('Warme Eiche');
      await card.getByRole('button', { name: 'Neue Version erstellen' }).click();
      await page.getByRole('alert').filter({ hasText: 'Die Verbindung zum Studio' }).waitFor();
      await card.getByRole('button', { name: 'Neue Version erstellen' }).click();
      await page.getByText(/Die Änderung für Konzept B/).waitFor();
      const posts = state.posts.filter(post => post.endpoint.endsWith('/revisions'));
      assert.equal(posts.length, 2); assert.equal(posts[0].key, posts[1].key); assert(posts[0].key);
      assert.equal(JSON.parse(posts[1].body).base_revision_id, 'B-1');
    });
    await check('retry keys remain attached to their intent even after another concept request fails', async () => {
      let aCalls = 0;
      const { page, state } = await open({ handle: async ({ route, endpoint, request }) => {
        if (!endpoint.endsWith('/revisions')) return false;
        const body = request.postDataJSON();
        if (body.concept === 'A') { aCalls += 1; if (aCalls === 1) await route.abort('failed'); else await json(route, { job_id: 'qa-original-intent' }, 202); }
        else await json(route, { detail: 'QA other request rejected' }, 409);
        return true;
      } });
      const a = page.getByRole('article', { name: 'QA Konzept A' });
      const b = page.getByRole('article', { name: 'QA Konzept B' });
      await a.getByRole('button', { name: 'Gezielt verändern' }).click();
      await a.getByLabel('Dein Änderungswunsch').fill('Eiche an den Fronten');
      await a.getByRole('button', { name: 'Neue Version erstellen' }).click();
      await page.getByRole('alert').filter({ hasText: 'Die Verbindung zum Studio' }).waitFor();
      await b.getByRole('button', { name: 'Gezielt verändern' }).click();
      await b.getByLabel('Dein Änderungswunsch').fill('Helle Arbeitsplatte');
      await b.getByRole('button', { name: 'Neue Version erstellen' }).click();
      await page.getByText('QA other request rejected', { exact: true }).waitFor();
      await a.getByRole('button', { name: 'Neue Version erstellen' }).click();
      await page.getByText(/Die Änderung für Konzept A/).waitFor();
      const posts = state.posts.filter(post => post.endpoint.endsWith('/revisions'));
      assert.equal(posts.length, 3); assert.equal(posts[0].key, posts[2].key); assert.notEqual(posts[0].key, posts[1].key);
    });
    await check('room correction failure preserves user input and confirmation; success versions old renders', async () => {
      let attempts = 0;
      const { page, state } = await open({ handle: async ({ route, endpoint, state, request }) => {
        if (!endpoint.endsWith('/room')) return false;
        attempts += 1;
        if (attempts === 1) { await json(route, { detail: 'QA room correction unavailable' }, 503); return true; }
        const body = request.postDataJSON(); assert.equal(body.confirm_global, true); assert.equal(body.features[0].provenance, 'USER_GIVEN');
        state.studio.room.version = 2; state.studio.room.description = body.description;
        state.studio.concepts.forEach(concept => concept.revisions.forEach(rev => rev.previous_room_basis = true));
        await json(route, state.studio); return true;
      } });
      await page.locator('.room-foundation>summary').click();
      await page.getByRole('button', { name: 'Raumgrundlage bewusst korrigieren' }).click();
      await page.getByLabel('Korrigierte vollständige Raumbeschreibung').fill('Das Fenster befindet sich an der rechten Wand.');
      await page.getByLabel('Merkmal ergänzen oder korrigieren').fill('Fenster');
      await page.getByLabel('Deine bestätigte Angabe').fill('Rechte Wand');
      await page.getByRole('checkbox', { name: /Ich bestätige bewusst/ }).check();
      await page.getByRole('button', { name: /Raumgrundlage speichern/ }).click();
      await page.getByText('QA room correction unavailable').waitFor();
      assert.equal(await page.getByLabel('Deine bestätigte Angabe').inputValue(), 'Rechte Wand');
      assert(await page.getByRole('checkbox', { name: /Ich bestätige bewusst/ }).isChecked());
      await page.getByRole('button', { name: /Raumgrundlage speichern/ }).click();
      await page.getByText('Die Raumgrundlage wurde aktualisiert.', { exact: false }).waitFor();
      assert.equal(await page.getByText('Dieser Entwurf basiert auf Raumversion 1, einer früheren Raumgrundlage.').count(), 3);
      assert.equal(state.posts.filter(post => post.endpoint.endsWith('/revisions')).length, 0);
    });
    await check('selective handoff uses persisted selected revision, requires confirmation, and cannot duplicate after toggling', async () => {
      let handoffs = 0;
      const handoffStudio = studio(); handoffStudio.concepts[1].revisions.push(revision('B', 2, 'material'));
      const { page, state } = await open({ studio: handoffStudio, handle: async ({ route, endpoint, state }) => {
        if (!endpoint.endsWith('/handoff')) return false;
        handoffs += 1;
        if (handoffs === 1) await json(route, { status: 'pending' }); else await json(route, { status: 'accepted' });
        return true;
      } });
      await page.getByRole('article', { name: 'QA Konzept B' }).getByRole('combobox').selectOption('B-1');
      await page.getByRole('article', { name: 'QA Konzept B' }).getByRole('button', { name: 'Dieses Konzept wählen' }).click();
      await page.getByRole('article', { name: 'QA Konzept B' }).getByRole('combobox').selectOption('B-2');
      await page.getByText('Dein Favorit ist Version 1.', { exact: false }).waitFor();
      await page.getByRole('button', { name: 'Freiwillige Beratung anfragen' }).click();
      await page.getByLabel('Dein Name', { exact: true }).fill('QA Person');
      await page.getByLabel('Deine E-Mail-Adresse').fill('qa@example.invalid');
      await page.getByRole('checkbox', { name: /Auch das Bild/ }).check();
      await page.getByRole('checkbox', { name: /Ich möchte zu diesem Entwurf/ }).check();
      await page.getByRole('button', { name: 'Beratung anfragen', exact: true }).click();
      await page.getByText(/Die Annahme Deiner Anfrage wurde/).waitFor();
      assert.equal(await page.getByText('Deine Beratungsanfrage wurde angenommen.').count(), 0);
      await page.getByRole('button', { name: 'Beratung anfragen', exact: true }).click();
      await page.getByText('Deine Beratungsanfrage wurde angenommen.').waitFor();
      const posts = state.posts.filter(post => post.endpoint.endsWith('/handoff'));
      assert.equal(posts[0].key, posts[1].key);
      assert.equal(JSON.parse(posts[1].body).revision_id, 'B-1');
      assert.deepEqual(JSON.parse(posts[1].body).media_ids, ['media-B-1']);
      await page.getByRole('button', { name: 'Kontaktformular schließen' }).click();
      await page.getByRole('button', { name: 'Freiwillige Beratung anfragen' }).click();
      await page.getByText('Deine Beratungsanfrage wurde angenommen.').waitFor();
      assert.equal(await page.getByRole('button', { name: 'Beratung anfragen', exact: true }).count(), 0);
      assert.equal(handoffs, 2);
      await page.getByRole('article', { name: 'QA Konzept C' }).getByRole('button', { name: 'Dieses Konzept wählen' }).click();
      await page.getByRole('button', { name: 'Freiwillige Beratung anfragen' }).click();
      assert.equal(await page.getByLabel('Dein Name', { exact: true }).inputValue(), '');
      assert(!(await page.getByRole('checkbox', { name: /Ich möchte zu diesem Entwurf/ }).isChecked()));
      assert(!(await page.getByRole('checkbox', { name: /Auch das Bild/ }).isChecked()));
    });
    await check('quota stop preserves revision browsing and same-origin private download request', async () => {
      const frozen = studio(); frozen.changes_remaining = 0; frozen.concepts[0].revisions.push(revision('A', 2, 'material'));
      const { page, state } = await open({ studio: frozen });
      const card = page.getByRole('article', { name: 'QA Konzept A' });
      await card.getByRole('combobox').selectOption('A-1');
      await card.getByRole('button', { name: 'Gezielt verändern' }).click();
      assert(await card.getByRole('button', { name: 'Neue Version erstellen' }).isDisabled());
      const href = await card.getByRole('link', { name: /herunterladen/ }).getAttribute('href');
      assert.equal(href, '/api/media/media-A-1?download=1');
      // Chromium native downloads bypass route fixtures in this environment. Verify
      // the same private download request via browser fetch; live download is separate acceptance.
      const downloaded = await page.evaluate(async href => { const response = await fetch(href, { credentials: 'same-origin' }); return { type: response.headers.get('Content-Type'), bytes: (await response.arrayBuffer()).byteLength }; }, href);
      assert.equal(downloaded.type, 'image/png'); assert.equal(downloaded.bytes, pngFixtures.A.length);
      assert(state.downloads.includes('?download=1'));
      assert.equal(state.posts.length, 0);
    });
    await check('session expiry stops polling and clears private result and continuation state', async () => {
      const running = studio(); running.status = 'running'; running.concepts[2].status = 'queued';
      let expire = false;
      const { page, state } = await open({ studio: running, handle: async ({ route, endpoint }) => {
        if (endpoint === '/api/studios/qa-studio' && expire) { await json(route, { detail: 'QA expired' }, 401); return true; }
        return false;
      } });
      await page.getByRole('button', { name: 'Fortsetzungscode erstellen' }).click();
      await page.getByLabel('Privater Fortsetzungscode').waitFor();
      expire = true;
      await page.getByRole('button', { name: 'Neue private Sitzung öffnen' }).waitFor({ timeout: 8000 });
      assert.equal(await page.locator('.concept-card').count(), 0);
      assert.equal(await page.getByLabel('Privater Fortsetzungscode').count(), 0);
      assert.equal(await page.evaluate(() => sessionStorage.getItem('design-studio.current-studio')), null);
      assert(await page.getByRole('button', { name: /Meine Konzepte erstellen/ }).isDisabled());
      state.sessions = []; expire = false;
      await page.getByRole('button', { name: 'Neue private Sitzung öffnen' }).click();
      await page.waitForFunction(() => !document.querySelector('#operation-error'));
      assert(await page.getByRole('button', { name: /Meine Konzepte erstellen/ }).isEnabled());
    });
    await check('three visibly distinct QA-only previews progressively appear and one failed concept does not block another', async () => {
      const initial = studio(); initial.status = 'running'; initial.concepts.forEach(concept => { concept.revisions = []; concept.status = 'queued'; });
      let reads = 0;
      const { page, state } = await open({ sessions: [], studio: initial, handle: async ({ route, endpoint, request, state }) => {
        if (endpoint === '/api/studios' && request.method() === 'POST') { state.sessions = [{ id: 'qa-studio', status: 'running' }]; await json(route, state.studio, 202); return true; }
        if (endpoint === '/api/studios/qa-studio') { reads += 1; if (reads >= 1) { state.studio.concepts[0].revisions = [revision('A')]; state.studio.concepts[0].status = 'completed'; } if (reads >= 2) { state.studio.concepts[1].status = 'failed'; state.studio.concepts[1].error = 'QA independent B failure'; } if (reads >= 3) { state.studio.concepts[2].revisions = [revision('C')]; state.studio.concepts[2].status = 'completed'; state.studio.status = 'partial'; } }
        return false;
      } });
      await page.getByLabel('Beschreibe Deinen Küchenwunsch').fill('Expliziter QA Testimpuls');
      await page.getByRole('button', { name: /Meine Konzepte erstellen/ }).click();
      await page.getByText('1 von 3 Konzepten mit Bild verfügbar.', { exact: true }).waitFor({ timeout: 8000 });
      await page.getByRole('article', { name: 'QA Konzept A' }).getByRole('button', { name: 'Dieses Konzept wählen' }).click();
      await page.getByText('QA independent B failure', { exact: true }).waitFor({ timeout: 8000 });
      await page.getByRole('article', { name: 'QA Konzept C' }).locator('img').waitFor({ timeout: 10000 });
      assert.equal(await page.locator('.concept-card img').count(), 2);
      assert.equal(await page.getByRole('article', { name: 'QA Konzept B' }).locator('img').count(), 0);
      assert.equal(state.posts.filter(post => post.endpoint.endsWith('/revisions')).length, 0);
      const images = await page.locator('.concept-card img').evaluateAll(images => images.map(image => ({ loaded: image.complete, width: image.naturalWidth, src: image.getAttribute('src') })));
      assert(images.every(image => image.loaded && image.width === 640)); assert.notEqual(images[0].src, images[1].src);
      const all = await open();
      await all.page.waitForFunction(() => [...document.querySelectorAll('.concept-card img')].length === 3 && [...document.querySelectorAll('.concept-card img')].every(image => image.complete && image.naturalWidth === 640));
      assert.notDeepEqual(pngFixtures.A, pngFixtures.B); assert.notDeepEqual(pngFixtures.B, pngFixtures.C);
      await all.page.screenshot({ path: '/tmp/design-studio-workflow-qa-fixtures.png', fullPage: true });
    });
    await check('all three distinct QA results arrive one at a time rather than as a blocked gallery', async () => {
      const initial = studio(); initial.status = 'running'; initial.concepts.forEach(concept => { concept.revisions = []; concept.status = 'queued'; });
      let reads = 0;
      const { page } = await open({ studio: initial, handle: async ({ endpoint, state }) => {
        if (endpoint === '/api/studios/qa-studio') {
          reads += 1; state.studio.concepts.forEach((concept, index) => { if (index < reads) { concept.revisions = [revision(concept.key)]; concept.status = 'completed'; } });
          if (reads >= 3) state.studio.status = 'completed';
        }
        return false;
      } });
      await page.getByText('1 von 3 Konzepten mit Bild verfügbar.', { exact: true }).waitFor();
      assert.equal(await page.locator('.concept-card img').count(), 1);
      await page.getByText('2 von 3 Konzepten mit Bild verfügbar.', { exact: true }).waitFor({ timeout: 8000 });
      assert.equal(await page.locator('.concept-card img').count(), 2);
      await page.getByText('3 von 3 Konzepten mit Bild verfügbar.', { exact: true }).waitFor({ timeout: 8000 });
      assert.equal(await page.locator('.concept-card img').count(), 3);
    });
    await check('a failed private preview can be retried without generating another image', async () => {
      let calls = 0;
      const { page, state } = await open({ handle: async ({ route, endpoint }) => {
        if (endpoint !== '/api/media/media-A-1') return false;
        calls += 1; if (calls === 1) { await route.fulfill({ status: 503, body: 'QA temporary media failure' }); return true; } return false;
      } });
      const card = page.getByRole('article', { name: 'QA Konzept A' });
      await card.getByRole('button', { name: 'Bild erneut laden' }).click();
      await card.locator('img').waitFor();
      await page.waitForFunction(() => document.querySelector('[aria-labelledby="concept-A"] img')?.naturalWidth === 640);
      assert.equal(state.posts.length, 0); assert.equal(calls, 2);
    });
    await check('secure continuation reopens selected results and deletion clears all local private state', async () => {
      const resumed = studio(); resumed.selected_revision_id = 'C-1';
      const { page, state } = await open({ sessions: [], studio: resumed, storedStudio: 'stale-private-id', handle: async ({ route, endpoint, request, state }) => {
        if (endpoint === '/api/session/resume') { assert.equal(request.postDataJSON().token, 'qa-valid-token-00000000000000000000000000000'); state.sessions = [{ id: 'qa-studio', status: 'completed' }]; await json(route, { resumed: true }); return true; }
        if (endpoint === '/api/session' && request.method() === 'DELETE') { state.sessions = []; await route.fulfill({ status: 204 }); return true; }
        return false;
      } });
      assert.equal(await page.evaluate(() => sessionStorage.getItem('design-studio.current-studio')), null);
      await page.getByRole('button', { name: /Studio fortsetzen/ }).click();
      await page.getByLabel('Fortsetzungscode', { exact: true }).fill('qa-valid-token-00000000000000000000000000000');
      await page.getByRole('button', { name: 'Studio öffnen', exact: true }).click();
      await page.getByText('Dein Studio wurde sicher wieder geöffnet.', { exact: true }).waitFor();
      assert(!page.url().includes('token'));
      assert.equal(await page.getByRole('article', { name: 'QA Konzept C' }).getByRole('button', { name: 'Ausgewählt', exact: true }).count(), 1);
      await page.getByRole('button', { name: 'Fortsetzungscode erstellen' }).click();
      await page.getByLabel('Privater Fortsetzungscode').waitFor();
      await page.getByRole('button', { name: 'Sitzung löschen', exact: true }).click();
      await page.getByRole('button', { name: 'Ja, Sitzung jetzt löschen' }).click();
      await page.getByText('Deine Sitzung wurde gelöscht.', { exact: false }).waitFor();
      assert.equal(await page.locator('.concept-card').count(), 0);
      assert.equal(await page.getByLabel('Privater Fortsetzungscode').count(), 0);
      assert.equal(await page.evaluate(() => sessionStorage.getItem('design-studio.current-studio')), null);
      assert(state.posts.some(post => post.method === 'DELETE'));
    });
    await check('mobile results do not overflow and no unexpected scripts or runtime exceptions occur', async () => {
      const { page } = await open();
      await page.setViewportSize({ width: 390, height: 844 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.equal(await page.locator('script[src*="cloudflare"]').count(), 0);
      assert.deepEqual(report.errors, []);
    });
    report.browser = await browser.version();
  } finally {
    await browser.close();
    if (server) { server.kill('SIGTERM'); if (server.exitCode === null) await Promise.race([once(server, 'exit'), new Promise(resolve => setTimeout(resolve, 1000))]); }
    writeFileSync(process.env.STUDIO_WORKFLOW_REPORT || '/tmp/design-studio-workflow-report.json', JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify(report));
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
