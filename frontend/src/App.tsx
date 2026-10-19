import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, isPending, privateMediaUrl, request, revisionLabel } from './api';
import type { Concept, Config, Revision, Session, SourceKind, Studio } from './api';
import Turnstile from './Turnstile';
import Icon from './Icon';
import GenerationReadiness from './GenerationReadiness';

const DIRECTIONS = { A: 'Ergonomie & Laufwege', B: 'Licht & Raumwirkung', C: 'Stauraum & Ordnung' };
const CURATION_LABELS = ['Architektonischer Ansatz', 'Design-Highlight', 'Material-Harmonie'];
const STORED_STUDIO = 'design-studio.current-studio';
const numberFormat = new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
function message(error: unknown) { return error instanceof Error ? error.message : 'Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es erneut.'; }
function currentStudio() { try { return sessionStorage.getItem(STORED_STUDIO); } catch { return null; } }
function rememberStudio(id: string | null) {
  try { if (id) sessionStorage.setItem(STORED_STUDIO, id); else sessionStorage.removeItem(STORED_STUDIO); } catch { /* A blocked storage does not block a cookie session. */ }
}
function date(value: string) { const parsed = new Date(value); return Number.isNaN(parsed.valueOf()) ? '' : numberFormat.format(parsed); }

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [studio, setStudio] = useState<Studio | null>(null);
  const [bootError, setBootError] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [prompt, setPrompt] = useState('');
  const [source, setSource] = useState<SourceKind>('text');
  const [file, setFile] = useState<File | null>(null);
  const [challenge, setChallenge] = useState('');
  const [challengeReset, setChallengeReset] = useState(0);
  const [resumeToken, setResumeToken] = useState('');
  const [createdToken, setCreatedToken] = useState('');
  const [resumeVisible, setResumeVisible] = useState(false);
  const [deleteVisible, setDeleteVisible] = useState(false);
  const [handoffVisible, setHandoffVisible] = useState(false);
  const [pollError, setPollError] = useState('');
  const [sessionExpired, setSessionExpired] = useState(false);
  const generation = useRef(0);
  const submitting = useRef(false);
  const formRef = useRef<HTMLTextAreaElement>(null);
  const studioRef = useRef<HTMLElement>(null);
  const idempotency = useRef(new Map<string, string>());
  const selected = studio?.concepts.flatMap(concept => concept.revisions).find(revision => revision.id === studio.selected_revision_id);
  const pending = !!studio && (isPending(studio.status) || studio.concepts.some(concept => isPending(concept.status)));
  const remaining = studio?.changes_remaining ?? session?.changes_remaining ?? 5;
  const readyCount = studio?.concepts.filter(concept => concept.revisions.length > 0).length ?? 0;
  const selectedConcept = studio?.concepts.find(concept => concept.revisions.some(revision => revision.id === selected?.id));
  const resetChallenge = useCallback(() => { setChallenge(''); setChallengeReset(value => value + 1); }, []);
  const onToken = useCallback((token: string) => setChallenge(token), []);

  const boot = useCallback(async () => {
    const run = ++generation.current;
    setLoading(true); setBootError('');
    try {
      const [nextConfig, nextSession] = await Promise.all([request<Config>('/api/config'), request<Session>('/api/session')]);
      if (run !== generation.current) return;
      setConfig(nextConfig); setSession(nextSession); setSessionExpired(false); setError(''); setPollError('');
      const authoritative = nextSession.studios;
      const id = nextSession.studio_id || (authoritative ? authoritative.filter(item => item.status !== 'failed').at(-1)?.id || authoritative.at(-1)?.id : currentStudio());
      if (id) {
        try {
          const nextStudio = await request<Studio>(`/api/studios/${encodeURIComponent(id)}`);
          if (run !== generation.current) return;
          setStudio(nextStudio); rememberStudio(nextStudio.id);
        } catch (reason) {
          if (reason instanceof ApiError && [403, 404, 410].includes(reason.status)) { rememberStudio(null); setStudio(null); }
          else throw reason;
        }
      } else { setStudio(null); rememberStudio(null); }
      return true;
    } catch (reason) { if (run === generation.current) setBootError(message(reason)); return false; }
    finally { if (run === generation.current) setLoading(false); }
  }, []);
  useEffect(() => { void boot(); return () => { generation.current += 1; }; }, [boot]);

  useEffect(() => {
    if (!studio || !pending || busy || sessionExpired) return;
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let failed = 0;
    const poll = async () => {
      try {
        const updated = await request<Studio>(`/api/studios/${encodeURIComponent(studio.id)}`, { signal: abort.signal });
        if (abort.signal.aborted) return;
        setStudio(updated); setPollError(''); failed = 0;
      } catch (reason) {
        if (abort.signal.aborted) return;
        if (reason instanceof ApiError && reason.status === 401) { expireSession(); return; }
        setPollError(message(reason)); failed += 1;
      }
      if (!abort.signal.aborted) timer = setTimeout(() => void poll(), Math.min(15000, 2000 * (failed + 1)));
    };
    timer = setTimeout(() => void poll(), 2000);
    return () => { abort.abort(); clearTimeout(timer); };
  }, [studio?.id, pending, busy, sessionExpired]);

  useEffect(() => {
    if (error) document.getElementById('operation-error')?.focus();
  }, [error]);

  function expireSession() {
    generation.current += 1;
    setSessionExpired(true); setStudio(null); setSession(null); rememberStudio(null);
    setCreatedToken(''); setResumeToken(''); setPrompt(''); setFile(null); setSource('text');
    setHandoffVisible(false); setDeleteVisible(false); setPollError(''); idempotency.current.clear(); resetChallenge();
    setNotice(''); setError('Deine private Sitzung ist abgelaufen oder wurde widerrufen. Die Inhalte wurden aus dieser Ansicht entfernt. Öffne eine neue Sitzung oder verwende einen gültigen Fortsetzungscode.');
  }

  async function action(name: string, task: () => Promise<void>) {
    if (submitting.current) return false;
    submitting.current = true; setBusy(name); setError(''); setNotice('');
    try { await task(); return true; }
    catch (reason) { if (reason instanceof ApiError && reason.status === 401) expireSession(); else setError(message(reason)); return false; }
    finally { submitting.current = false; setBusy(''); }
  }
  function key(signature: string) {
    const existing = idempotency.current.get(signature);
    if (existing) return existing;
    const created = crypto.randomUUID(); idempotency.current.set(signature, created); return created;
  }
  function acceptStudio(next: Studio) { setStudio(next); rememberStudio(next.id); }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (source === 'text' && !prompt.trim()) { setError('Schreibe Deinen Küchenwunsch in einem Satz auf.'); formRef.current?.focus(); return; }
    if (source !== 'text' && !file) { setError('Wähle ein Raumfoto oder einen Grundriss aus.'); return; }
    void action('start', async () => {
      const body = new FormData();
      body.set('prompt', prompt.trim()); body.set('source_kind', source); body.set('challenge_token', challenge);
      if (source !== 'text' && file) body.set('file', file);
      const signature = JSON.stringify(['start', prompt.trim(), source, file?.name, file?.size, file?.lastModified]);
      try {
        const created = await request<Studio>('/api/studios', { method: 'POST', body, headers: { 'Idempotency-Key': key(signature) } });
        acceptStudio(created); idempotency.current.delete(signature); setFile(null); setPrompt('');
        setNotice('Dein Impuls ist angekommen. Die Konzepte erscheinen einzeln, sobald die Bilder fertig sind.');
        setTimeout(() => studioRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
      } finally { resetChallenge(); }
    });
  }
  function pickFile(next: File | undefined) {
    setError('');
    if (!next) { setFile(null); return; }
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(next.type)) { setError('Bitte verwende ein JPG-, PNG- oder WebP-Bild.'); setFile(null); return; }
    if (next.size > 12 * 1024 * 1024) { setError('Das Bild ist größer als 12 MB. Bitte verkleinere es vor dem Hochladen.'); setFile(null); return; }
    setFile(next);
  }
  async function choose(revision: Revision) {
    if (!studio) return;
    await action('select', async () => {
      acceptStudio(await request<Studio>(`/api/studios/${studio.id}/select`, { method: 'POST', body: JSON.stringify({ revision_id: revision.id }) }));
      setHandoffVisible(false); setNotice(`Konzept ${studio.concepts.find(item => item.revisions.some(candidate => candidate.id === revision.id))?.key}, Version ${revision.number} ist ausgewählt. Die Auswahl erzeugt kein neues Bild.`);
    });
  }
  async function change(concept: Concept, revision: Revision, kind: 'material' | 'layout', instruction: string) {
    if (!studio) return false;
    return action('change', async () => {
      const signature = JSON.stringify(['change', studio.id, revision.id, kind, instruction]);
      try {
        await request(`/api/studios/${studio.id}/revisions`, {
          method: 'POST',
          body: JSON.stringify({ concept: concept.key, base_revision_id: revision.id, kind, instruction, challenge_token: challenge }),
          headers: { 'Idempotency-Key': key(signature) },
        });
        idempotency.current.delete(signature);
        setStudio(current => current ? { ...current, status: 'running', concepts: current.concepts.map(item => item.key === concept.key ? { ...item, status: 'queued', error: null } : item) } : current);
        setNotice(`Die Änderung für Konzept ${concept.key} auf Basis von Version ${revision.number} wurde angenommen. Deine bisherigen Versionen bleiben erhalten.`);
        try { acceptStudio(await request<Studio>(`/api/studios/${studio.id}`)); }
        catch (reason) {
          if (reason instanceof ApiError && reason.status === 401) throw reason;
          setPollError('Der Änderungsauftrag wurde angenommen. Sein Status konnte noch nicht geladen werden; er wird automatisch erneut abgefragt. Bitte erteile keinen zweiten Auftrag.');
        }
      } finally { resetChallenge(); }
    });
  }
  async function resume(event: FormEvent) {
    event.preventDefault();
    await action('resume', async () => {
      if (!session) setSession(await request<Session>('/api/session'));
      await request('/api/session/resume', { method: 'POST', body: JSON.stringify({ token: resumeToken.trim() }) });
      setResumeToken(''); setResumeVisible(false); setCreatedToken(''); setStudio(null); rememberStudio(null);
      const restored = await boot(); setNotice(restored ? 'Dein Studio wurde sicher wieder geöffnet.' : 'Dein Fortsetzungscode wurde bestätigt. Deine Inhalte konnten noch nicht geladen werden; prüfe die Verbindung erneut.');
    });
  }
  async function erase() {
    await action('delete', async () => {
      await request('/api/session', { method: 'DELETE' });
      generation.current += 1; setStudio(null); rememberStudio(null); setCreatedToken(''); setResumeToken(''); setFile(null); setPrompt('');
      setDeleteVisible(false); setHandoffVisible(false); setSession(null); setSource('text'); setPollError(''); idempotency.current.clear(); resetChallenge();
      await boot(); setNotice('Deine Sitzung wurde gelöscht. Ihre Fortsetzungscodes sind ungültig.');
    });
  }

  return <>
    <a className="skip-link" href="#main">Zum Inhalt springen</a>
    <header className="site-header">
      <a className="brand" href="/" aria-label="Design Studio AI Startseite"><span className="brand-mark" aria-hidden="true">d<span>·</span>s</span><span>DESIGN STUDIO <b>AI</b><small>{config?.brand || 'Küchen neu denken'}</small></span></a>
      <nav aria-label="Studio"><a href="#so-funktionierts">So funktioniert’s</a><button className="text-button" onClick={() => setResumeVisible(value => !value)} aria-expanded={resumeVisible}>Studio fortsetzen <Icon kind="up-right" /></button></nav>
    </header>
    <main id="main">
      {resumeVisible && <section className="resume-panel section-shell" aria-labelledby="resume-heading"><div><p className="eyebrow">Dein privater Zugang</p><h2 id="resume-heading">Dort weitermachen, wo Du warst.</h2><p>Füge Deinen Fortsetzungscode ein. Er wird sicher übertragen und nicht in der Adresse gespeichert.</p></div><form onSubmit={event => void resume(event)}><label htmlFor="resume-token">Fortsetzungscode</label><input id="resume-token" type="password" autoComplete="off" value={resumeToken} onChange={event => setResumeToken(event.target.value)} required minLength={40} maxLength={256} /><button disabled={!!busy || !resumeToken.trim()} className="button">{busy === 'resume' ? 'Wird geöffnet …' : 'Studio öffnen'}</button></form></section>}
      <section className="hero section-shell" aria-labelledby="hero-title">
        <div className="hero-copy"><p className="eyebrow"><span className="tiny-line" /> Dein persönliches Küchenstudio</p><h1 id="hero-title">Ein Gedanke.<br />Drei neue <em>Perspektiven.</em></h1><p className="hero-description">Deine Küche beginnt mit einer Idee. Aus Deinem Satz, Raumfoto oder Grundriss entstehen drei eigenständige Küchenkonzepte. Du entscheidest, welche Richtung sich nach Dir anfühlt.</p><div className="value-note"><Icon kind="spark" /> Kostenlos. Ohne Registrierung. Ohne Kontaktdaten.</div><a className="inline-link" href="#impuls">Mit Deiner Idee starten <Icon kind="down-right" /></a></div>
        <aside className="studio-note" aria-label="Die drei Entwurfsrichtungen"><div className="note-top"><span>VOM RAUM ZUM ZUHAUSE</span><Icon kind="up-right" /></div><p>Eine gemeinsame<br />Raumgrundlage.<br /><em>Drei eigene Antworten.</em></p><ol className="direction-list">{(Object.entries(DIRECTIONS) as [Concept['key'], string][]).map(([letter, label]) => <li key={letter}><span>{letter}</span><b>{label}</b></li>)}</ol><div className="note-bottom">Von der ersten Idee bis zur bewussten Auswahl.</div></aside>
      </section>
      <section className="input-section section-shell" id="impuls" aria-labelledby="input-title">
        <div className="section-intro"><p className="eyebrow">01 / Dein Impuls</p><h2 id="input-title">Was hast Du im Kopf?</h2><p>Ein Impuls reicht. Was noch offen ist, behandeln wir als Annahme und machen es für Dich sichtbar.</p></div>
        <div className="input-card">
          {sessionExpired && <div className="alert warning"><p>Diese Sitzung ist nicht mehr gültig. Vorhandene Bilder werden nicht weiter angezeigt.</p><button className="button secondary" onClick={() => void boot()}>Neue private Sitzung öffnen</button></div>}
          {loading && <p className="status-line" role="status"><span className="spinner" /> Das Studio wird verbunden …</p>}
          {bootError && <div className="alert error" role="alert"><p>{bootError}</p><button className="button secondary" onClick={() => void boot()}>Verbindung erneut prüfen</button></div>}
          {studio && studio.status !== 'failed' ? <div className="impulse-receipt"><p className="eyebrow">Dein Impuls ist angekommen</p><h3>{studio.source_kind === 'photo' ? 'Dein Raumfoto' : studio.source_kind === 'floorplan' ? 'Dein Grundriss' : 'Deine Küchenidee'}</h3><p>Die drei Konzepte entstehen auf einer gemeinsamen Raumgrundlage. Deine Ergebnisse und alle Versionen findest Du weiter unten.</p><a className="inline-link" href="#results-title">Zu Deinen Konzepten <Icon kind="down" /></a><GenerationReadiness config={config} hasResults={readyCount > 0} />{config?.generation_ready && config.turnstile_site_key && remaining > 0 && <><p className="minor">Bot-Schutz für Deine nächste gezielte Änderung</p><Turnstile siteKey={config.turnstile_site_key} onToken={onToken} resetKey={challengeReset} /></>}</div> : <form onSubmit={submit}>
            <fieldset className="source-options" disabled={!!busy || loading}><legend>Wie möchtest Du starten?</legend>{([{ key: 'text', label: 'Meine Idee' }, { key: 'photo', label: 'Raumfoto' }, { key: 'floorplan', label: 'Grundriss' }] as const).map(option => <label className={source === option.key ? 'source-option active' : 'source-option'} key={option.key}><input type="radio" name="source" value={option.key} checked={source === option.key} onChange={() => { setSource(option.key); setError(''); }} /><span aria-hidden="true" className="source-icon">{option.key === 'text' ? 'Aa' : <Icon kind={option.key} />}</span>{option.label}</label>)}</fieldset>
            {source !== 'text' && <div className="upload-field"><label htmlFor="source-file">{source === 'photo' ? 'Dein Raumfoto' : 'Dein Grundriss'} <span>JPG, PNG oder WebP · bis 12 MB</span></label><input id="source-file" type="file" accept="image/jpeg,image/png,image/webp" onChange={event => pickFile(event.target.files?.[0])} required disabled={!!busy} /><p>{file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB` : source === 'photo' ? 'Wähle ein scharfes, gut belichtetes Foto, das die Wände, Türen und Fenster zeigt.' : 'Wähle einen gut lesbaren Grundriss mit erkennbaren Wänden, Türen und Fenstern.'}</p></div>}
            <label className="prompt-label" htmlFor="prompt">{source === 'text' ? 'Beschreibe Deinen Küchenwunsch' : 'Was ist Dir wichtig? (freiwillig)'}</label>
            <textarea id="prompt" ref={formRef} rows={4} value={prompt} maxLength={2000} required={source === 'text'} onChange={event => setPrompt(event.target.value)} aria-describedby="prompt-hint" disabled={!!busy} />
            <div className="input-hint"><span id="prompt-hint">{source === 'text' ? 'Zum Beispiel: Eine offene Familienküche mit hellem Holz und Platz zum gemeinsamen Kochen.' : 'Ein Wunsch zu Stil oder Nutzung reicht. Du musst keine weiteren Fragen beantworten.'}</span><span aria-label={`${prompt.length} von 2000 Zeichen`}>{prompt.length}/2000</span></div>
            <p className="source-disclosure">{source === 'text' ? 'Aus Deiner Idee entsteht ein gemeinsamer Beispielraum zur Inspiration. Maße und Anschlüsse sind keine bestätigten Planungsdaten.' : 'Dein Bild wird zuerst auf Eignung geprüft. Sichtbare Raummerkmale bilden die gemeinsame Grundlage; ein exaktes Aufmaß ersetzt das nicht.'}</p>
            <GenerationReadiness config={config} hasResults={readyCount > 0} />
            {config?.generation_ready && config.turnstile_site_key && <Turnstile siteKey={config.turnstile_site_key} onToken={onToken} resetKey={challengeReset} />}
            <div className="submit-row"><span>3 Konzepte · 5 erfolgreiche Änderungen<br /><strong>Für Dich 0 €</strong></span><button className="button" aria-describedby={config && !config.generation_ready ? 'generation-readiness' : undefined} disabled={!!busy || loading || !session || sessionExpired || !config?.generation_ready || (!!config?.turnstile_site_key && !challenge)} type="submit">{busy === 'start' ? <><span className="spinner light" /> Impuls wird gesendet …</> : <>Meine Konzepte erstellen <Icon kind="up-right" /></>}</button></div>
            {studio && <p className="minor">Dein vorheriger Impuls konnte nicht verarbeitet werden. Mit einem geeigneten neuen Impuls kannst Du es erneut versuchen.</p>}
          </form>}
        </div>
      </section>
      <div className="section-shell messages" aria-live="polite" aria-atomic="true">{notice && <div className="alert success" role="status">{notice}</div>}</div>
      {error && <div className="section-shell"><div id="operation-error" tabIndex={-1} className="alert error" role="alert"><strong>Das hat noch nicht geklappt.</strong><p>{error}</p></div></div>}
      {studio && <section className="results-section section-shell" ref={studioRef} aria-labelledby="results-title">
        <div className="results-header"><div><p className="eyebrow">02 / Deine Perspektiven</p><h2 id="results-title">Welches Konzept passt zu Dir?</h2><p>Jede Richtung hat ihren eigenen Schwerpunkt. Fertige Bilder erscheinen direkt hier.</p></div><span className="credit-badge">{remaining} von 5 Änderungen verfügbar</span></div>
        <p className="gallery-announcement" role="status" aria-live="polite" aria-atomic="true">{readyCount} von 3 Konzepten mit Bild verfügbar.{!pending && readyCount < 3 ? ' Nicht alle Bilder konnten fertiggestellt werden. Fertige Konzepte bleiben nutzbar.' : ''}</p>
        <nav className="gallery-navigation" aria-label="Konzepte direkt öffnen">{studio.concepts.map(concept => <a key={concept.key} href={`#concept-${concept.key}`}>Konzept {concept.key}<span>{concept.status === 'review_required' ? 'Fachlich prüfen' : concept.revisions.length ? 'Bild verfügbar' : isPending(concept.status) ? 'In Bearbeitung' : 'Kein Bild'}</span></a>)}</nav>
        {pending && <p role="status" className="status-line"><span className="spinner" /> Deine Entwürfe werden bearbeitet. Du kannst fertige Konzepte bereits öffnen.</p>}
        {pollError && <p role="alert" className="alert warning">{pollError} Der Verbindungsaufbau wird automatisch erneut versucht.</p>}
        {studio.error && <p role="alert" className="alert error">{studio.error}</p>}
        {remaining === 0 && <p className="alert warning">Deine fünf erfolgreichen Änderungen sind aufgebraucht. Alle vorhandenen Bilder, Versionen und Downloads bleiben kostenlos verfügbar.</p>}
        {studio.concepts.length === 0 && <p className="empty-status">{pending ? 'Dein Impuls wird analysiert und die gemeinsame Raumgrundlage erstellt.' : 'Für dieses Studio liegen noch keine Bilder vor. Der angezeigte Status ist kein fertiger Entwurf.'}</p>}
        {studio.room && <RoomFoundation studio={studio} busy={!!busy || pending} action={action} onUpdate={acceptStudio} />}
        <div className="concept-grid">{studio.concepts.map(concept => <ConceptCard key={concept.key} concept={concept} studio={studio} selectedId={studio.selected_revision_id} busy={!!busy} canGenerate={!!config?.generation_ready && !sessionExpired && remaining > 0 && !pending} challengeReady={!config?.turnstile_site_key || !!challenge} onSelect={choose} onChange={change} />)}</div>
        <p className="result-disclaimer">{studio.source_kind === 'text' || studio.room?.source_kind === 'text' ? 'Beispielraum zur Inspiration.' : 'Designvisualisierung auf Basis sichtbarer Raummerkmale.'} Keine technische Freigabe, kein exaktes Aufmaß und keine Zusage zu Herstellerverfügbarkeit oder Bildtreue. Eine fachliche Prüfung vor der Umsetzung bleibt erforderlich.</p>
        {selected && <section className="selection-panel" aria-labelledby="selection-title"><div><p className="eyebrow">03 / Deine Auswahl</p><h2 id="selection-title">Dein Favorit steht.</h2><p>Konzept {selectedConcept?.key}, Version {selected.number} ist ausgewählt. Wenn Du möchtest, besprichst Du genau diesen Entwurf mit {config?.expert_name || 'einem unabhängigen Küchenexperten'}.</p><p>Deine Konzepte bleiben auch ohne Kontaktaufnahme vollständig nutzbar.</p></div><button className="button secondary" disabled={!!busy} onClick={() => setHandoffVisible(value => !value)} aria-expanded={handoffVisible}>{handoffVisible ? 'Kontaktformular schließen' : 'Freiwillige Beratung anfragen'} <Icon kind="up-right" /></button></section>}
        {selected && <Handoff visible={handoffVisible} conceptKey={selectedConcept?.key || ''} key={selected.id} studio={studio} revision={selected} expert={config?.expert_name || 'einen unabhängigen Küchenexperten'} busy={!!busy} action={action} />}
        <section className="privacy-tools" aria-labelledby="privacy-tools-title"><div><h3 id="privacy-tools-title">Dein Studio bleibt privat.</h3><p>Bilder und Sitzung werden nach 30 Tagen gelöscht. Du kannst Deine Sitzung auch sofort löschen.</p></div><div className="privacy-actions"><button className="text-button" disabled={!!busy} onClick={() => void action('token', async () => { const result = await request<{ token: string }>('/api/session/resume-token', { method: 'POST' }); setCreatedToken(result.token); setNotice('Dein privater Fortsetzungscode wurde erstellt. Bewahre ihn sicher auf.'); })}>Fortsetzungscode erstellen</button><button className="text-button danger" onClick={() => setDeleteVisible(value => !value)} aria-expanded={deleteVisible}>Sitzung löschen</button></div>
          {createdToken && <div className="token-panel"><label htmlFor="created-token">Privater Fortsetzungscode</label><p>Ein neuer Code macht Deinen vorherigen Code ungültig. Wer diesen Code besitzt, kann Dein Studio öffnen. Teile ihn nur mit Personen, denen Du vertraust. Kopiere und bewahre ihn sicher auf; er steht nicht in der Seitenadresse.</p><input id="created-token" value={createdToken} readOnly autoComplete="off" onFocus={event => event.target.select()} /><button className="text-button" onClick={() => setCreatedToken('')}>Code ausblenden</button></div>}
          {deleteVisible && <div className="delete-panel"><h4>Diese Sitzung mit allen Entwürfen löschen?</h4><p>Dies kann nicht rückgängig gemacht werden. Fortsetzungscodes werden ungültig.</p><div><button className="button danger-button" onClick={() => void erase()} disabled={!!busy}>Ja, Sitzung jetzt löschen</button><button className="button secondary" onClick={() => setDeleteVisible(false)}>Abbrechen</button></div></div>}
        </section>
      </section>}
      <section id="so-funktionierts" className="how-section section-shell" aria-labelledby="how-title"><div className="section-intro"><p className="eyebrow">Weniger Fragen. Mehr Möglichkeiten.</p><h2 id="how-title">Deine Idee gibt die Richtung vor.</h2></div><ol className="how-grid"><li><span>01</span><h3>Ein Impuls genügt.</h3><p>Dein Satz, ein Raumfoto oder ein Grundriss. Offene Punkte werden transparent als Annahmen behandelt.</p></li><li><span>02</span><h3>Drei echte Entwurfsrichtungen.</h3><p>Ergonomie, Licht und Stauraum setzen unterschiedliche Schwerpunkte auf derselben Raumgrundlage.</p></li><li><span>03</span><h3>Du hast die Wahl.</h3><p>Entscheide Dich, ändere gezielt und lade Deine Bilder herunter. Beratung ist immer freiwillig.</p></li></ol></section>
    </main>
    <footer className="site-footer"><a className="footer-brand" href="/">DESIGN STUDIO AI</a><p>Raum für Deine Vorstellungen.</p><span>Privat · Ohne Registrierung · Für Dich kostenlos</span></footer>
  </>;
}

function ConceptCard({ concept, studio, selectedId, busy, canGenerate, challengeReady, onSelect, onChange }: {
  concept: Concept; studio: Studio; selectedId?: string | null; busy: boolean; canGenerate: boolean; challengeReady: boolean;
  onSelect: (revision: Revision) => Promise<void>; onChange: (concept: Concept, revision: Revision, kind: 'material' | 'layout', instruction: string) => Promise<boolean>;
}) {
  const [viewId, setViewId] = useState('');
  const [editing, setEditing] = useState(false);
  const [kind, setKind] = useState<'material' | 'layout'>('material');
  const [instruction, setInstruction] = useState('');
  const [imageFailed, setImageFailed] = useState(false);
  const selectedRevision = concept.revisions.find(item => item.id === selectedId);
  const revision = viewId === 'latest' ? concept.revisions.at(-1) : concept.revisions.find(item => item.id === viewId) || selectedRevision || concept.revisions.at(-1);
  const imageUrl = privateMediaUrl(revision?.image_url);
  const downloadUrl = privateMediaUrl(revision?.download_url);
  const chosen = !!revision && revision.id === selectedId;
  const oldRoom = !!revision && (revision.previous_room_basis || (!!studio.room?.version && revision.room_version < studio.room.version));
  useEffect(() => { setImageFailed(false); }, [revision?.id]);
  async function submitChange(event: FormEvent) {
    event.preventDefault();
    if (!revision || !instruction.trim()) return;
    if (await onChange(concept, revision, kind, instruction.trim())) { setInstruction(''); setEditing(false); setViewId('latest'); }
  }
  return <article className={`concept-card${chosen ? ' chosen' : ''}`} aria-labelledby={`concept-${concept.key}`}>
    <div className="concept-heading"><span className="concept-letter">{concept.key}</span><div><p>{DIRECTIONS[concept.key]}</p><h3 id={`concept-${concept.key}`} tabIndex={-1}>{concept.title || `Konzept ${concept.key}`}</h3></div>{chosen && <span className="selected-mark" aria-label="Ausgewählter Entwurf"><Icon kind="check" /></span>}</div>
    {revision && imageUrl && !imageFailed ? <a href={imageUrl} target="_blank" rel="noopener noreferrer" className="concept-image" aria-label={`Bild von Konzept ${concept.key}, Version ${revision.number}, in Originalgröße öffnen`}><img src={imageUrl} alt={`Küchenvisualisierung: ${concept.title}, Version ${revision.number}. ${revision.curation.join(' ')}`} onError={() => setImageFailed(true)} loading="lazy" /><span>Bild vergrößern <Icon kind="up-right" /></span></a> : <div className="image-status"><span className={isPending(concept.status) ? 'spinner' : 'status-symbol'} aria-hidden="true">{isPending(concept.status) ? '' : '—'}</span><strong>{imageFailed ? 'Das Bild konnte nicht geladen werden.' : isPending(concept.status) ? 'Dein Konzept entsteht.' : 'Noch kein Bild verfügbar.'}</strong><p>{imageFailed ? 'Prüfe Deine Verbindung oder öffne das Studio erneut.' : 'Hier erscheint ausschließlich Dein tatsächlich erzeugtes Bild.'}</p>{imageFailed && imageUrl && <button className="button secondary" onClick={() => setImageFailed(false)}>Bild erneut laden</button>}</div>}
    {revision?.review?.critical_error && <p className="concept-error" role="alert"><strong>Kritischer Raumfehler gemeldet.</strong> {revision.review.critical_reason || 'Dieser Entwurf braucht eine fachliche Prüfung und kann nicht als verlässliche Raumgrundlage verwendet werden.'}</p>}
    {revision?.review?.requires_human_acceptance && <p className="review-note">Fachlich noch nicht abgenommen. Die automatische Bildprüfung dient ausschließlich als Hinweis; eine Auswahl ist keine technische Freigabe.</p>}
    {concept.error && <p className="concept-error" role="alert">{concept.error}</p>}
    {revision && <div className="concept-body">
      <div className="version-row"><label htmlFor={`version-${concept.key}`}>Version ansehen</label><select id={`version-${concept.key}`} value={revision.id} onChange={event => setViewId(event.target.value)}>{concept.revisions.map(item => <option key={item.id} value={item.id}>{revisionLabel(item)}</option>)}</select><small>{date(revision.created_at)}</small></div>
      {selectedRevision && !chosen && <p className="selected-version-note">Dein Favorit ist Version {selectedRevision.number}. Du siehst gerade eine andere Version. <button className="text-button" onClick={() => setViewId(selectedRevision.id)}>Ausgewählte Version ansehen</button></p>}
      {oldRoom && <p className="alert warning">Dieser Entwurf basiert auf Raumversion {revision.room_version}, einer früheren Raumgrundlage.</p>}
      {revision.curation.length === 3 ? <dl className="curation">{CURATION_LABELS.map((label, index) => <div key={label}><dt>{label}</dt><dd>{revision.curation[index]}</dd></div>)}</dl> : <p className="alert error">Der dreizeilige Kuratierungsbericht ist unvollständig. Dieser Entwurf erfüllt die Qualitätsanforderung noch nicht.</p>}
      <details className="assumptions"><summary>Annahmen & Raumgrundlage <span aria-hidden="true">+</span></summary><p>Raumversion {revision.room_version}. Annahmen sind keine bestätigten Maße oder technischen Angaben.</p>{revision.assumptions.length ? <ul>{revision.assumptions.map((assumption, index) => <li key={index}>{assumption}</li>)}</ul> : <p>Für diese Version wurden keine zusätzlichen Annahmen ausgewiesen.</p>}</details>
      <div className="concept-actions"><button className={`button ${chosen ? 'secondary' : ''}`} onClick={() => void onSelect(revision)} disabled={busy || chosen || revision.curation.length !== 3}>{chosen ? <><Icon kind="check" /> Ausgewählt</> : 'Dieses Konzept wählen'}</button>{downloadUrl && <a href={downloadUrl} className="download-link" download aria-label={`Konzept ${concept.key}, Version ${revision.number}, herunterladen`}>Download <Icon kind="down" /></a>}</div>
      <button className="change-toggle text-button" onClick={() => setEditing(value => !value)} aria-expanded={editing}>{editing ? 'Änderung schließen' : 'Gezielt verändern'} <span aria-hidden="true">{editing ? '-' : '+'}</span></button>
      {editing && <form className="change-form" onSubmit={event => void submitChange(event)}><p>Ausgangspunkt: Konzept {concept.key}, Version {revision.number}. Frühere Versionen bleiben erhalten.</p><fieldset disabled={!canGenerate || busy}><legend>Was möchtest Du ändern?</legend><label><input type="radio" name={`kind-${concept.key}`} checked={kind === 'material'} onChange={() => setKind('material')} /> Material & Oberflächen</label><label><input type="radio" name={`kind-${concept.key}`} checked={kind === 'layout'} onChange={() => setKind('layout')} /> Aufbau & Anordnung</label></fieldset><p className="minor">{kind === 'material' ? 'Raum und Möbelanordnung bleiben Zielvorgabe. Du änderst die Oberflächen.' : 'Die Anordnung wird nur in diesem Konzept angepasst. Die gemeinsame Raumgrundlage bleibt erhalten.'}</p><label htmlFor={`instruction-${concept.key}`}>Dein Änderungswunsch</label><textarea id={`instruction-${concept.key}`} rows={3} minLength={3} maxLength={1500} value={instruction} onChange={event => setInstruction(event.target.value)} required disabled={!canGenerate || busy} /><button className="button" disabled={!canGenerate || !challengeReady || busy || instruction.trim().length < 3}>Neue Version erstellen</button>{!canGenerate && <p className="minor">{studio.changes_remaining <= 0 ? 'Das kostenlose Änderungskontingent ist aufgebraucht.' : 'Neue Änderungen sind gerade nicht verfügbar. Warte auf laufende Entwürfe oder prüfe den Hinweis oben.'}</p>}{canGenerate && !challengeReady && <p className="minor">Bestätige zuerst den Bot-Schutz im Bereich „Dein Impuls“.</p>}</form>}
    </div>}
  </article>;
}

function Handoff({ studio, revision, expert, busy, action, visible, conceptKey }: { visible: boolean; conceptKey: string; studio: Studio; revision: Revision; expert: string; busy: boolean; action: (name: string, task: () => Promise<void>) => Promise<boolean> }) {
  const [includeImage, setIncludeImage] = useState(false);
  const [consent, setConsent] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [note, setNote] = useState('');
  const handoffKeys = useRef(new Map<string, string>());
  async function submit(event: FormEvent) {
    event.preventDefault();
    await action('handoff', async () => {
      const body = JSON.stringify({ revision_id: revision.id, media_ids: includeImage && revision.media_id ? [revision.media_id] : [], name: name.trim(), email: email.trim(), message: note.trim(), consent });
      if (!handoffKeys.current.has(body)) handoffKeys.current.set(body, crypto.randomUUID());
      const result = await request<{ status?: string; accepted?: boolean }>(`/api/studios/${studio.id}/handoff`, { method: 'POST', body, headers: { 'Idempotency-Key': handoffKeys.current.get(body)! } });
      if (result.accepted !== true && result.status !== 'accepted') throw new Error('Die Annahme Deiner Anfrage wurde vom Beratungsziel noch nicht bestätigt. Es wird kein erfolgreicher Kontakt angezeigt.');
      setAccepted(true);
    });
  }
  return <section hidden={!visible} className="handoff-panel" aria-labelledby="handoff-title"><p className="eyebrow">Freiwillig / Persönliche Beratung</p><h3 id="handoff-title">Deine Idee. Ein menschlicher Blick.</h3>{accepted ? <div className="alert success" role="status"><strong>Deine Beratungsanfrage wurde angenommen.</strong><p>Das zuständige Beratungsziel hat den Empfang bestätigt. Übertragen wurden nur Deine gewählte Version und die von Dir freigegebenen Inhalte.</p></div> : <form onSubmit={event => void submit(event)}><p>Du kontaktierst {expert} als unabhängigen menschlichen Experten. Übergeben werden Dein gewähltes Konzept {conceptKey}, Version {revision.number} und das dafür erforderliche Briefing. Andere Konzepte und Deine Versionshistorie werden nicht übermittelt.</p><div className="contact-fields"><div><label htmlFor="contact-name">Dein Name</label><input id="contact-name" disabled={busy} autoComplete="name" value={name} onChange={event => setName(event.target.value)} maxLength={120} required /></div><div><label htmlFor="contact-email">Deine E-Mail-Adresse</label><input id="contact-email" disabled={busy} autoComplete="email" type="email" value={email} onChange={event => setEmail(event.target.value)} maxLength={254} required /></div></div><label htmlFor="contact-note">Deine Nachricht (freiwillig)</label><textarea id="contact-note" disabled={busy} rows={3} value={note} onChange={event => setNote(event.target.value)} maxLength={2000} /><label className="checkbox-label"><input type="checkbox" checked={includeImage} disabled={busy || !revision.media_id} onChange={event => setIncludeImage(event.target.checked)} /><span>Auch das Bild dieser ausgewählten Version übermitteln. Andere Bilder bleiben privat.</span></label><label className="checkbox-label"><input type="checkbox" disabled={busy} checked={consent} onChange={event => setConsent(event.target.checked)} required /><span>Ich möchte zu diesem Entwurf kontaktiert werden und stimme der Übermittlung meiner Kontaktdaten, dieser Revision, des erforderlichen Briefings und ausdrücklich ausgewählter Medien an das zuständige Beratungsziel zu.</span></label><button className="button" disabled={busy || !consent}>{busy ? 'Annahme wird geprüft …' : 'Beratung anfragen'} <Icon kind="up-right" /></button><p className="minor">Ein Erfolg wird erst angezeigt, wenn das Beratungsziel Deine Anfrage bestätigt hat.</p></form>}</section>;
}

const PROVENANCE = { USER_GIVEN: 'Von Dir angegeben', DETECTED: 'Im Bild erkannt', ASSUMED: 'Angenommen', UNKNOWN: 'Unbekannt' };
function RoomFoundation({ studio, busy, action, onUpdate }: { studio: Studio; busy: boolean; action: (name: string, task: () => Promise<void>) => Promise<boolean>; onUpdate: (studio: Studio) => void }) {
  const [correcting, setCorrecting] = useState(false);
  const [description, setDescription] = useState(studio.room?.description || '');
  const [featureName, setFeatureName] = useState('');
  const [featureValue, setFeatureValue] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [updated, setUpdated] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!confirmed) return;
    await action('room', async () => {
      const next = await request<Studio>(`/api/studios/${studio.id}/room`, { method: 'POST', body: JSON.stringify({ description: description.trim(), features: featureName.trim() && featureValue.trim() ? [{ name: featureName.trim(), value: featureValue.trim(), provenance: 'USER_GIVEN' }] : [], constraints: studio.room?.constraints || [], confirm_global: confirmed }) });
      onUpdate(next); setCorrecting(false); setConfirmed(false); setFeatureName(''); setFeatureValue(''); setUpdated(true);
    });
  }
  return <details className="room-foundation"><summary>Gemeinsame Raumgrundlage · Version {studio.room?.version} <span aria-hidden="true">+</span></summary><div><p>{studio.room?.description}</p>{!!studio.room?.features?.length && <dl className="room-features">{studio.room.features.map((feature, index) => <div key={index}><dt>{feature.name} <span>{PROVENANCE[feature.provenance] || 'Unbekannt'}</span></dt><dd>{feature.value}</dd></div>)}</dl>}{!!studio.room?.constraints?.length && <><h4>Grenzen der Planung</h4><ul>{studio.room.constraints.map((constraint, index) => <li key={index}>{constraint}</li>)}</ul></>}{updated && <p className="alert success" role="status">Die Raumgrundlage wurde aktualisiert. Vorhandene Bilder behalten ihre ursprüngliche Raumversion. Es wurde kein Bildauftrag ausgelöst.</p>}<button className="text-button" onClick={() => { setCorrecting(value => !value); setDescription(studio.room?.description || ''); setUpdated(false); }} aria-expanded={correcting}>Raumgrundlage bewusst korrigieren</button>{correcting && <form className="room-correction" onSubmit={event => void submit(event)}><p>Dies ändert die gemeinsame Grundlage für spätere Versionen aller Konzepte. Die bereits erzeugten Bilder ändern sich dadurch nicht. Ältere Entwürfe werden als vorherige Raumgrundlage gekennzeichnet.</p><label htmlFor="room-description">Korrigierte vollständige Raumbeschreibung</label><textarea id="room-description" value={description} onChange={event => setDescription(event.target.value)} minLength={3} maxLength={4000} rows={4} required disabled={busy} /><div className="contact-fields"><div><label htmlFor="feature-name">Merkmal ergänzen oder korrigieren (freiwillig)</label><input id="feature-name" value={featureName} onChange={event => setFeatureName(event.target.value)} maxLength={1000} required={!!featureValue.trim()} disabled={busy} /><p className="minor">Benenne das betroffene Merkmal, beispielsweise „Fenster Nordwand“.</p></div><div><label htmlFor="feature-value">Deine bestätigte Angabe</label><input id="feature-value" value={featureValue} onChange={event => setFeatureValue(event.target.value)} maxLength={1000} required={!!featureName.trim()} disabled={busy} /><p className="minor">Nur Dir bekannte Angaben; keine geschätzten Maße als bestätigt übernehmen.</p></div></div><label className="checkbox-label"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} required disabled={busy} /><span>Ich bestätige bewusst diese Korrektur der gemeinsamen Raumgrundlage. Meine Ergänzungen sind als Nutzerangaben erkennbar; vorhandene Bilder bleiben auf ihrer bisherigen Grundlage.</span></label><button className="button secondary" disabled={busy || !confirmed}>Raumgrundlage speichern · ohne Bildauftrag</button>{busy && <p className="minor">Warte bitte, bis laufende Bildaufträge abgeschlossen sind.</p>}</form>}</div></details>;
}
